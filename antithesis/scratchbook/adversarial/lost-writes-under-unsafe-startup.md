# lost-writes-under-unsafe-startup adversarial review — Guarantee 3 acknowledged writes lost after kill/restart

**Verdict: harness-caused** (configuration). The violation needs the non-default, documented-unsafe
`accord.journal.stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP`. It persists with batch fsync of both
commitlog and journal (hunt-5) and disappears under the documented safe policy REBOOTSTRAP with the same
workload and faults (hunt-6: Guarantee 3 146/0 and 632/0, exercised).

Remaining doubt (why this is not `undetermined` but is still worth a note): the policy's javadoc warns about
"isolation guarantees" and an incomplete "log of our votes", not explicitly about losing applied data. With
journal BATCH the vote log should be complete, so you could argue the unsafe path should still keep acked
data. But the code shows that durability of Accord-applied data rests on more than the vote log (below).
The doc says the operator must have "determined [the log] complete externally". Our harness never does that.
So a loss under this policy is outside what Cassandra promises.

## Evidence

Runs: hunt-5 `823089f61fb59e015811e6e85ed39aa6-63-12` (cfg-durable), hunt-6 `0458bd361e685fcd215c0f52bee40ab2-63-12`
(cfg-rebootstrap). Digests: runs/hunt-5.md, runs/hunt-6.md. Properties: logs/props-*.json.

### Q1: hunt-5 first Guarantee 3 moment (log `logs/hunt5--14343964086619208.{log,ndjson}`, 393.97)
- Two kills came before the read, and each was followed by an unsafe restart:
  - node/kill node3 at 304.50, then at 310.49 `Stop marker is older than start marker (-1<…) … Continuing to startup as configured`. The value -1 means node3 had never written a clean stop marker.
  - node/kill node2 at 322.84, then at 328.19 the same WARN.
  - Earlier clean node/stop events (node2 at 227/271/292, node1 at 254/272) did not trigger the WARN.
- The failing read was a plain QUORUM SELECT (`txn_read=false`) on the full-mode table `accord_ks.durable`. The chunks were coordinated by all three nodes.
- 5 of 14 rows were missing. None had a wrong value. Every missing row is an Accord write: `txn`, `txn_cas`, or `plain` INSERT on a `transactional_mode='full'` table.
- Two multi-partition ops lost only one partition each: 725240628426616792 lost k=2 of [26,2], and 6692637172817547563 lost 1559479 of 3. That points to state lost on one replica, not to a transaction that was never applied.
- I could not tell which replica served the read. The ack times of these 5 ops are not in this log (the ack assertions log only first hits).
- The "visible to the next read" property passes (904/0), so these writes were readable after the ack and disappeared later.

### Q2: what ALLOW_UNSAFE_STARTUP skips that batch fsync does not cover
- Accord applies transaction writes **without the commitlog**: `TxnWrite.java:150` calls `mutation.apply(false, false)` (durableWrites=false). So `commitlog_sync: batch` does nothing for Accord-applied rows. On a crash they exist only in memtables, and recovery depends entirely on Accord journal replay.
- Replay (`AccordService.localStartup` 530-655, `AbstractReplayer.shouldReplay`) uses the default `replay=PART_NON_DURABLE` and `replay_save_point=LATEST`:
  - It restores command-store state (RedundantBefore and min segments) from save points. Those are written only on a clean shutdown (`commandStores.saveState(lastSegment)` at AccordService ~1270, together with the stop marker).
  - It then replays only commands whose ranges are not `LOCALLY_DURABLE_TO_DATA_STORE` or `LOCALLY_DURABLE_TO_COMMAND_STORE`, skipping anything bounded by `LOG_UNAVAILABLE`.
- After a kill, the stop marker is older than the start marker. The code then knows it cannot trust that this state is consistent with what is on disk. Examples:
  - the save point is stale, since it comes from an earlier clean stop or does not exist (-1);
  - durability bounds were advanced by flushes or compaction of `system_accord` after the save point.
- Under EXIT the node refuses to start. Under REBOOTSTRAP it discards its local state and re-fetches data from peers (`commandStores().rebootstrap`). ALLOW_UNSAFE_STARTUP skips both protections and trusts its local state anyway.
- Documentation, AccordConfig.java:383-387: "assuming the consensus log has been determined complete externally. Note this is VERY UNSAFE if you care about isolation guarantees." The default is EXIT.

### Q3: checker soundness
- The ack line is appended and fsync'd only after `session.execute` returns success (`helper_durable.do_write`). Any exception records the op as `ambiguous`, which is excluded from the check.
- With the auto-retry profile, the driver's RetryPolicy can resend the statement. A final success still means one execution committed. Every style is idempotent at the row level (same id and same value; `txn_cas` inserts only if absent). So a hidden retry cannot produce a false ack.
- The ledger is per-writer, append-only and fsync'd. Torn lines are skipped.
- Reads give up after their time budget as "unknown" rather than "missing". The `missing` list holds only rows that were absent from a completed read.
- Checker: sound. I found no false-ack path.

### Q4: separating run hunt-6 (REBOOTSTRAP, periodic commitlog and journal = weaker fsync than hunt-5)
- Guarantee 3 passed:

  | Property | Examples | Counterexamples |
  |---|---|---|
  | after faults stopped every acknowledged durable write is present | 146 | 0 |
  | sampled during the run | 632 | 0 |
  | visible to the next read | 1014 | 0 |

- Guarantee 3 was exercised: the final check verified ledgers 149 times, and the in-run check verified samples 635 times.
- Rebootstrap was exercised: at least 500 `Rebootstrapping` events on all 3 nodes, the first at 206.74.
- Guarantee 2 (all 5 cross-table properties) also passes in hunt-6, which suggests that hunt-5's Guarantee 2 failures are also unsafe-startup artifacts.
- **Guarantee 1 still fails** in hunt-6 (bank sum 95, counters even 208, audit reflects 12, reads both accounts 10, app-retried 7, seeded visible 5). So acked-transfer-overwritten is not explained by this confound.
- Guarantee 5 availability fails (every-node 126, any-node 24). That is expected while nodes rebootstrap.

## Adversarial checklist
1. Harness intervention: yes. The SUT override `stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP` decides how a killed node rejoins. This is the enabling condition.
2. Config: with the documented default (EXIT) a killed node does not restart at all. With the documented safe REBOOTSTRAP, the violation is absent.
3. Faults: at most one node is down at a time. The kills are within the minority-crash promise, but only under the safe restart policy.
4. Checker: sound (Q3).
5. Reproduction: seen in hunts 1, 2, 3, 5 and fix-verify-journal-unreadable-after-kill, always with ALLOW_UNSAFE_STARTUP. Never seen with REBOOTSTRAP (one 300 m run).

Caveat: hunt-6 is a single run. A strict "never under REBOOTSTRAP" claim needs more runs. The mechanism (Accord data bypasses the commitlog, and replay trusts state that is valid only after a clean stop) fully explains why batch fsync did not help.
