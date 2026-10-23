---
sut_path: /home/exedev/cassandra/cassandra-accord/src/cassandra
commit: e874e3a90b1942b945477e6d9ba03880b4f4a19d
updated: 2026-10-08
external_references:
  - path: /home/exedev/cassandra/cassandra-accord/src/cassandra-accord
    why: Accord library at the submodule commit fff32de2e915772fbc70d16b1c32346313877838 (coordination, recovery, CFK, durability, cleanup)
  - path: https://github.com/apache/cassandra/blob/trunk/doc/modules/cassandra/pages/developing/cql/transactions.adoc
    why: D1, the user-facing transaction guarantees (strict serializability, atomic commit, durability, full-mode linearizability)
  - path: https://github.com/apache/cassandra/blob/cassandra-6.0-alpha2/doc/modules/cassandra/pages/managing/operating/onboarding-to-accord.adoc
    why: D2, accord yaml, transactional_mode, supported consistency levels, paging/range-read caveats
  - path: https://cwiki.apache.org/confluence/display/CASSANDRA/CEP-15%3A+General+Purpose+Transactions
    why: D3, failure-tolerance claim behind G5
---

# SUT analysis: Cassandra 6.0-alpha2 + Accord (scoped to G1–G5)

Scope: only the components and data paths that the five guarantees in `guarantees.md` depend on.
`C/` means `src/cassandra/src/java/org/apache/cassandra/` at `e874e3a9`. `A/` means
`src/cassandra-accord/accord-core/src/main/java/accord/` at `fff32de`. Line numbers refer to those
trees.

## 1. Request entry points

### 1.1 `BEGIN TRANSACTION … COMMIT TRANSACTION` (G1, G2, G3, G5)

- `C/cql3/statements/TransactionStatement.java:586` `execute()` checks
  `accord.enabled`/transactions enabled. It rejects multi-row `LET` selects and `IN` with `LIMIT`
  (lines 591–599), builds a `Txn` (`createTxn`, :504), and calls
  `AccordService.instance().coordinate(...)` (:606). A `retry_new_protocol` result becomes
  `InvalidRequestException(UNSUPPORTED_MIGRATION)` (:607–608).
- `createTxn` (:504–537):
  - **Read-only transaction** (no updates): reads go through `createTxnRead` with the *serial*
    consistency from the query options. The kind comes from
    `ConsensusRequestRouter.shouldReadEphemerally` (:517). On a `full` table with
    `accord.ephemeral_reads=true` (the default), a read-only txn over **exactly one key** becomes an
    `EphemeralRead`; more than one key stays a full `Read`
    (`C/service/consensus/migration/ConsensusRequestRouter.java:506–521`). The docs say
    EphemeralRead "only provides per key linearizability" (`doc/.../architecture/cql-on-accord.adoc:46–49`).
  - **Read-write transaction:** `TxnUpdate(tables, writeFragments, condition, commitCL, …)` (:534).
    The `IF` condition is evaluated at execution time inside Accord
    (`C/service/accord/txn/TxnUpdate.java:700` `apply`, `:729` `checkCondition`).
- Consistency levels: in `full` mode the supplied read and commit CLs are **ignored**. Both
  `readCLForMode` and `commitCLForMode` return `null` once the table is not migrating
  (`C/service/consensus/TransactionalMode.java:139–160, 169–192`). Unsupported CLs are still
  **rejected** before that point: `LOCAL_*`, `TWO`, `THREE` and `EACH_QUORUM` throw
  `UnsupportedTransactionConsistencyLevel` (an `InvalidRequestException`; `TransactionalMode.java:147,177`;
  supported sets at `C/service/accord/IAccordService.java:83–84`). **The Python driver's default
  CL is `LOCAL_ONE`, so the workload must set `QUORUM` (or `ONE`/`ALL`) explicitly.**

### 1.2 Plain CQL on a `transactional_mode='full'` table (G4)

- Reads: `C/service/StorageProxy.java:2174` `read()` → non-SERIAL →
  `dispatchReadWithRetryOnDifferentSystem`. The Accord path is `readWithAccordAsync` (:2286–2302):
  it rejects unsupported CLs (:2288–2289), builds `TxnRead.createSerialRead`, and picks the kind
  through `shouldReadEphemerally`. A single-partition SELECT is an `EphemeralRead` (per-key
  linearizable). A multi-partition `IN` SELECT is a full `Read`.
- Partition-range reads go through `readWithAccord(PartitionRangeReadCommand…)` (:2269). Per D2
  (`onboarding-to-accord.adoc`, "non-SERIAL consistency") they "are split into multiple
  transactions during execution and will not produce a strict serializable result", and "Paging
  runs a separate transaction per page and does not produce a linearizable result". **Checkers
  must not use range scans or multi-page results.**
- Writes: `StorageProxy.dispatchMutationsWithRetryOnDifferentSystem` (:1267) splits mutations into
  Accord and normal ones. The Accord ones go to
  `C/service/consensus/migration/ConsensusMigrationMutationHelper.java:269`
  `mutateWithAccordAsync`, which wraps each `PartitionUpdate` in a `TxnWrite.Fragment` and
  coordinates a write-only Accord txn. With `USING TIMESTAMP`, application order is linearizable
  but "from the perspective of a reader the merged result may not appear linearizable" (D2), so the
  workload must not use `USING TIMESTAMP`. Logged batches that touch only Accord tables skip the
  batchlog (D2).

## 2. Accord coordinator (library) — G1, G2, G4

- `C/service/accord/AccordService.java:1155` `coordinateAsync` allocates a `TxnId`. It sets the
  deadline from `write_request_timeout` for write txns and `read_request_timeout` for read txns
  (:1158), then calls `node.coordinate(txnId, txn, minEpoch, deadline)`.
- `A/coordinate/CoordinateTransaction.java:123` `onPreAccepted`:
  - REJECTED and too-many SOFT_REJECT votes fail the txn (:126–147).
  - **Fast path:** with a fast-path quorum, it executes with `executeAt = txnId` and merged deps
    (:149–165).
  - **Medium path:** propose MEDIUM (:166–175).
  - **Slow path:** otherwise `Propose`/Accept at `max(witnessedAt)` (:177–180).
- Execution is in `A/coordinate/ExecuteTxn.java`. `onDone` (:442) computes `Writes` and `Result`
  and calls `adapter().persist(...)`. **The client is acknowledged before Apply is sent:** the
  default adapter calls `callback.accept(result, null)` first, then starts `PersistTxn` (Apply to
  all replicas) (`A/coordinate/CoordinationAdapter.java:289–297`). So an acknowledged txn is
  committed/stable at a quorum but may not be applied anywhere yet. Applying it later is the job of
  `PersistTxn`, and if the coordinator dies, of the progress log and recovery.
- Replica state machine (`A/local/Commands.java`): `preaccept` :150, `recover` :162, `accept`
  :291, `commit` :342, `apply` :535/:540. Message classes: `A/messages/PreAccept.java:56`,
  `Accept.java:64`, `Commit.java:66`, `Apply.java:64`, `BeginRecovery.java:71`,
  `ReadData.java:82`, `StableThenRead.java:50`. Inbound messages are handled by
  `C/service/accord/AccordVerbHandler.java:56`.
- Ephemeral reads use `A/coordinate/CoordinateEphemeralRead.java` and `ExecuteEphemeralRead.java`.
  They have no durable txn record (`Txn.Kind.EphemeralRead`, `A/primitives/Txn.java:58–61`).
- Integration of reads and writes with Cassandra storage: `C/service/accord/txn/TxnRead.java:385`
  `read`. `C/service/accord/txn/TxnWrite.java:479` `apply` writes the mutations into normal
  memtables/commitlog at `executeAt`.

## 3. Recovery after coordinator failure — G1, G2, G5

- Recovery: `A/coordinate/Recover.java:106`, entry points at :163–184. It decides from the
  `RecoverOk` replies: it re-proposes or commits a known decision, or invalidates
  (`finishAndInvalidate` :594, `commitInvalidate` :617) when it can prove the fast path was not
  taken. Ballots (`Promised`) keep competing recoverers from deciding differently.
- Trigger: the progress log (`A/impl/progresslog/DefaultProgressLog.java:88`) on the home shard
  invokes `MaybeRecover` when coordination stalls (architecture doc
  `doc/.../architecture/accord-architecture.adoc:157–172`). Its timing comes from
  `C/service/accord/api/AccordAgent.java:309` `slowCoordinatorDelay`, which uses the
  `accord.recover_txn` retry strategy (default `"5s*attempts <= 60s"`,
  `C/config/AccordConfig.java:219`). Expiry of in-flight coordination uses `accord.expire_txn`
  (`"5s*attempts <= 60s"`, :223).
- Client-visible: a recovery that races the original coordinator produces `Preempted` at that
  coordinator. That surfaces as `AccordWritePreemptedException`/`AccordReadPreemptedException`,
  which are subclasses of `WriteTimeoutException`/`ReadTimeoutException`
  (`C/service/accord/RequestBookkeeping.java:92–96`). **The txn may still commit through the
  recoverer.**

## 4. Accord journal, durability scheduling and cleanup — G1, G3

- Journal: `C/service/accord/journal/AccordJournal.java:91`. `saveCommand` (:162–178) appends a
  command diff and registers `onFlush` through `segments.onDurable(pointer, onFlush)`.
  `AccordTask` finishes a task, and so releases its reply, only in that `onFlush` callback
  (`C/service/accord/AccordTask.java:639–654, 714–716`).
  - Flush modes are `BATCH`, `GROUP` and `PERIODIC` (`C/journal/Params.java:24`); the default is
    `PERIODIC` (`AccordConfig.java:400`).
  - In PERIODIC mode a record counts as durable once an fsync has finished for time
    `writtenAt - periodicFlushLagBlock` (default 1500 ms) (`C/journal/Flusher.java:477–505`). A
    reply can therefore precede the fsync by up to the lag.
  - The project's simulator runs `accord.journal.flush_mode: BATCH` and `commitlog_sync: batch`
    (`test/simulator/main/org/apache/cassandra/simulator/ClusterSimulation.java:888–889`).
- Replay on restart: `C/service/accord/journal/Replay.java:53`, invoked through
  `AccordJournal.replay` (:601, :609). `catchup_on_start` (default `NORMAL`, success latency 60 s,
  fail latency 900 s, `AccordConfig.java:314–320`) governs post-restart catch-up.
- Journal compaction: segments roll at `accord.journal.segment_size` (default 32 MiB) and are
  compacted every `compaction_period` (default 60 s) (`AccordConfig.java:392–406`). The compactor
  is `C/service/accord/journal/SegmentCompactor.java:30`.
- Durability scheduling: `A/local/durability/DurabilityService.java:52` (start :93) and
  `ShardDurability.java:75` run periodic `ExclusiveSyncPoint`s (:369) per shard. The cycles are
  `accord.shard_durability_cycle` and `global_durability_cycle`, default **5 min each**
  (`AccordConfig.java:244–245`, applied at `AccordService.java:694–695`). Their success advances
  `RedundantBefore`/`DurableBefore`, which gate GC.
- Cleanup and GC: `A/local/Cleanup.java` (`EXPUNGE` :75, `shouldCleanup` :111–122).
  `A/impl/CommandChange.java:358–372` `shouldCleanup` decides ERASE vs EXPUNGE for journal
  records. Cassandra applies it on load at `C/service/accord/journal/CommandChanges.java:89`. A
  wrong cleanup decision makes a replica forget or misreport a decided txn. The docs define
  ERASE/EXPUNGE/INVALIDATE/VESTIGIAL/TRUNCATE in `accord-architecture.adoc:300–316`.
- **Implication for testing:** with production defaults, GC and expunge only start after several
  5-minute durability cycles, so they barely run within a test. See `tuning.md`.

## 5. CommandsForKey (CFK) — G1, G4

- `A/local/cfk/CommandsForKey.java:231`: the per-key index of txns. It computes deps at PreAccept
  and gates execution order. Pruning is controlled by `commands_for_key_prune_delta`/`_interval`
  (`AccordConfig.java:310–311`). A dep missing from CFK means two conflicting txns execute in
  different orders on different replicas, which shows up as a G1/G4 anomaly.
- In-SUT safety net: `C/service/accord/api/AccordViolationHandler.java:45,50` logs
  timestamp/dependency violations at ERROR. `accord.utils.Invariants` throws on internal invariant
  failures. Both are useful log signals during triage.

## 6. Topology, TCM and CMS bootstrap — G5 (and setup)

- Startup modes are in `C/tcm/Startup.java:573–627`:
  - `FIRST_CMS` applies only when the node is the sole seed *and* that seed is a loopback address.
  - Otherwise a fresh node uses `VOTE`, which runs `initializeForDiscovery` (:232–281). Nodes
    discover each other through the seeds, the smallest address nominates itself, and a
    **single-member CMS is created automatically**.
  - `nodetool cms initialize` (`C/tools/nodetool/CMSAdmin.java:95`) is **only for upgrading a
    gossip-mode cluster** and is not needed on a fresh cluster.
- Initial metadata keyspace replication is `simpleMeta(1, …)`
  (`C/schema/DistributedMetadataLogKeyspace.java:253`). After each join,
  `ensureCMSPlacement` (`C/tcm/ClusterMetadataService.java:514`; called from
  `BootstrapAndJoin.java:302`) re-applies the *current* meta RF, which is still 1. **The CMS
  therefore stays at 1 member until an operator runs `nodetool cms reconfigure 3`**
  (`CMSAdmin.java:108`; `C/tcm/CMSOperations.java:165`).
- Accord topology follows TCM epochs (`C/service/accord/topology/AccordTopologyService.java`). The
  project's own tests wait until `ClusterMetadata.epoch == accord.topology().current().epoch()`
  before issuing txns (`test/distributed/.../accord/AccordTestBase.java:184`). Setup should do the
  same, or simply retry a probe txn until it succeeds.
- The fast-path electorate adapts to down nodes after `fast_path_update_delay` (5 s per the yaml
  comment, `conf/cassandra.yaml:2827`). With 1 of 3 down, txns still commit through the slow
  path with a simple quorum of 2.

## 7. Client-visible outcomes (what the checker sees)

`C/service/accord/AccordResult.java:130–205` maps coordination failures:

| Accord outcome | Server exception | Python driver exception | Outcome known? |
|---|---|---|---|
| `Timeout` (deadline) | `WriteTimeoutException(WriteType.CAS, SERIAL, 0, 0, "<txnId>: <keys>")` / `ReadTimeoutException(SERIAL, 0, 0, false, …)` (`RequestBookkeeping.java:85–90, 111–113`) | `cassandra.WriteTimeout` (`write_type=CAS`) / `cassandra.ReadTimeout` | **No**: the txn may or may not apply |
| `Preempted` (recovery raced) | `AccordWritePreemptedException` ⊂ WriteTimeout / `AccordReadPreemptedException` ⊂ ReadTimeout | same as above | **No** |
| `Exhausted` | `AccordWriteExhaustedException` / `AccordReadExhaustedException` (timeouts) | same as above | **No** |
| other `CoordinationFailed` | `WriteFailureException` / `ReadFailureException` (:197–202) | `cassandra.WriteFailure` / `ReadFailure` | **No** (treat as ambiguous) |
| `TopologyMismatch` | retried as `RetryWithNewProtocol`; for `BEGIN TRANSACTION`, `InvalidRequest` (TransactionStatement :607) | `InvalidRequest` | definite no-op (rejected before execution), but treat it as ambiguous to be safe |
| unsupported CL | `InvalidRequestException` | `InvalidRequest` | definitely not executed |
| client-side timeout / connection loss | none | `cassandra.OperationTimedOut`, `NoHostAvailable`, `ConnectionShutdown` | **No** |

Python driver retries:
- The default `RetryPolicy` rethrows a `WriteTimeout` with `write_type=CAS`.
- It retries a `ReadTimeout` **once** when `received >= required and not data_retrieved`. Accord
  reports 0/0, so a timed-out read-only txn or full-mode SELECT is retried once transparently.
- Statements are `is_idempotent=False` by default, so there is no speculative execution.
- Recommendation: use `FallthroughRetryPolicy` and do every retry explicitly in the workload, so
  each attempt is recorded.

Timeouts:
- Server: `write_request_timeout` (Config default 2000 ms; `conf/cassandra.yaml` sets 10000 ms)
  for write txns and `read_request_timeout` (5000 ms) for read txns (`AccordService.java:1158`).
- `native_transport_timeout` is 12 s (`C/config/Config.java:1616`).
- The client's request timeout must be larger than all of these, or the client turns
  server-side answers into `OperationTimedOut`.

## 8. Attack surfaces relevant to G1–G5

1. **Recovery racing the live coordinator** under partition or message delay. This is the
   fast-path vs recovery decision, and an invalidate vs commit decision. The fixed bugs
   CASSANDRA-20292 and -20325 lived here.
2. **Journal GC/expunge plus delayed messages or restart.** A replica that has expunged a txn
   must still answer as "Erased", not "unknown". This needs durability cycles to run inside the
   test.
3. **Crash between commit-at-quorum and Apply.** The ack precedes Apply (§2), so durability of an
   acked write depends on recovery or progress-log re-applying it after restart.
4. **Restart and journal replay** under PERIODIC flush. Replay of partially flushed segments, and
   catch-up on start.
5. **Ephemeral (single-key) reads vs concurrent writes**, which matters for G4 per-key
   linearizability.
6. **CMS/TCM availability.** With CMS RF=1, losing that node blocks epoch changes. Hence the
   reconfigure to 3 in setup.
