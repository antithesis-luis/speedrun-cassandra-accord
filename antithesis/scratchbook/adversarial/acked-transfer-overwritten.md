# acked-transfer-overwritten adversarial review: Guarantee 1 txn-strict-serializable (bank conservation, lost update, stale read)

Run: e4947374c51cfdaaffd0d6ff6ae5dc10-63-12 (6.0-alpha2, network faults only).
Reviewer brief: defend the SUT and explain the failure as caused by the harness, config, driver or checker.
**Verdict: stands.**

## 1. Harness intervention: none between fault and symptom
- `containers_meta` in both failing logs shows exactly one `init/start` per container: node1 @10.88, node2 @57.87, node3 @89.19, client @119.12. There is no stop, kill or restart. `Startup complete` appears once per node, before 120 s.
- Every `fault_injector` FAULT line is `network/partition` (Slowed/Stopped/Jammed, symmetric and asymmetric) or `network/clog`. There are no node kills, pauses or clock faults. So `stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP`, the entrypoint (`exec cassandra -f -R`) and the restart path never ran.
- `helper-cms-bootstrap.sh` only waits for CMS membership at startup, which finished well before the workload (setup_complete about 205 s).
- `patches/common`: 0001 adds the SDK dependency. 0002 adds one `reachable` after "Startup complete" in CassandraDaemon. Neither touches the txn path. There are no shims and no LD_PRELOAD.

## 2. Configuration and tuning: no safety knob relaxed
- Every tuned value is a timing or sizing knob that cassandra.yaml/AccordConfig supports: `recover_txn 1s*attempts<=10s`, durability cycles of 20 s, journal compaction every 10 s with 1 MiB segments, `command_store_shard_count=2`, `num_tokens=1`, `memtable_heap_space=16MiB`, request timeouts of 10 s and 30 s. Most values come from the project's own dtests (AccordTestBase, JournalGCTest). `commitlog_sync` and `journal.flush_mode` stay at their production defaults. The run had no crashes, so durability flush settings cannot matter anyway.
- The most plausible enabler is `recover_txn` at 1 s instead of 5 s. It makes recovery race live coordinators more often under partitions. Accord must be safe for any timing of recovery against a live coordinator, because that race is the core case the protocol is built for. A shorter delay can make the bug more frequent, but it cannot turn a correct execution into a lost update. Nothing in the docs says a short retry delay weakens isolation. With the defaults the window is probably rarer, not closed.

## 3. Client driver (top suspect): ruled out
What differs between bank_autoretry and bank_transfers:
- unprepared literal CQL vs prepared statements
- the driver's default `RetryPolicy` vs `FallthroughRetryPolicy`
- application resubmits (up to 3) vs none

Consistency settings are the same (QUORUM/SERIAL) and so is `RoundRobinPolicy`. Neither uses speculative execution: the driver default is NoSpeculativeExecutionPolicy, and the statements are not idempotent.

**Client timestamps do not matter.** cassandra-driver 3.30.1 (`test/requirements.txt`) sends a default timestamp on protocol v3+ for both simple and bound statements (`use_client_timestamp=True`), so both commands send one. Cassandra ignores it for transactions:
- `TransactionStatement.createTxn` builds `new TxnUpdate(..., PreserveTimestamp.no)` (TransactionStatement.java:534).
- `USING TIMESTAMP` inside a transaction is rejected (`NO_TIMESTAMPS_IN_UPDATES_MESSAGE`, :818).
- `ModificationStatement.getTxnWriteFragment` reads a timestamp only when `attrs.isTimestampSet()` is true, which means only an explicit USING TIMESTAMP. Otherwise it uses `NO_TIMESTAMP` (ModificationStatement.java:1004).
- At apply time, `TxnWrite.applyDirect` sets `timestamp = executeAt.uniqueHlc()` (TxnWrite.java:493). `Update.write` then calls `updateAllTimestamp(timestamp)` whenever `!preserveTimestamps` (TxnWrite.java:147-148).
- `processCondition` builds `AccordUpdateParameters` with `executeAt.uniqueHlc()` (TxnUpdate.java:~890).

So every cell timestamp is Accord's executeAt, and no client clock or LWW skew is possible. The docs line about `USING TIMESTAMP` "not appearing linearizable" covers the non-transactional mutation path (`PreserveTimestamp.yes`, ModificationStatement.java:687). It does not cover BEGIN TRANSACTION.

**The arithmetic runs inside Accord.** `balance -= a, xfers += 1` are `TxnReferenceOperations`, completed in `Fragment.complete` from the `TxnData` read by the same transaction, at executeAt. They are not a client read-modify-write.

**Retries and resubmits:** each driver retry or application resubmit is a separate, whole Accord transaction that conserves money and adds +1 to the counters of both accounts. "Applied once or more" keeps `sum == 12000` and keeps the counter sum even. A stale in-flight first attempt that executes late is still a whole transfer.

**Decisive evidence that this is not about the client path.** Failing audits also come from commands that use the default `FallthroughRetryPolicy` profile, run by separate processes:
- `bank_audit_final` @275.96 (input -1621130149510642966): total 11938, xfer_sum 15 (odd)
- `bank_audit` @296.66 (-2471289866021418454): total 11992
- `bank_audit_final` @300.59 (3661212306508931859): total 12144, xfer_sum 29 (odd)

No single-attempt read can show an odd counter sum in a consistent snapshot unless the stored state is already non-atomic or has lost an update. No retry or timestamp behaviour can produce one. The zero failures in bank_transfers are statistical: it ran only about 29 audits, against about 302 for autoretry, which had 8 failures.

## 4. Faults within the promise
The run used only network partitions, latency and clogs, with RF=3 and no node loss. These are within Guarantee 1's promise.

## 5. Checker: sound
- `total == 12000` and an even `sum(xfers)` hold for any set of whole transfers applied any number of times.
- The seed is one conditional transaction (`IF s IS NULL`), so resubmitting it is a no-op, and it finished before setup_complete. No other command writes `accounts` or `accounts_b`.
- The account ids in the two tables do not overlap, and `src != dst`.
- The audit is one 12-LET transaction (full Accord read, one page).
- Floors are raised only from acknowledged reads, using exactly the transaction's `IF`.

The docs promise strict serializability for `transactional_mode='full'`. Nothing in the docs allows a non-atomic or lost-update state.

## 6. Reproduction
- 17+ failing events for the conservation and even-sum assertions on 15+ distinct input hashes, with totals 11992, 11938, 12144 and 11939 and odd sums 5, 9, 11, 15, 21, 23, 29 and 33.
- The stale-read regression (b105 floor 1, seen 0) fails on 3 branches, as does the lost update (`src_xfers < floor_src`).
- The bad state is stored: different processes see it through 10.89.0.2, .3 and .4 as coordinators.

There are at least two independent mechanism lineages: total 11992 in 3115707109627864019, and 11938 → 12144 in 2977298595378160927.

## Residual notes
- The node1 NPE in `ExecuteTxn.onDone → TxnAdapter.persist(result=null)` @235.33 is in the read-txn failure path. It may or may not be related. That question belongs to the root-cause analysis.
- No workload change is needed to clear harness doubt. Optional ways to strengthen the evidence:
  - log every autoretry attempt with its outcome and coordinator, so the transfer history can be rebuilt;
  - optionally a control run with `recover_txn` at the production default, to measure how much the tuning affects frequency. The verdict does not depend on that run.
