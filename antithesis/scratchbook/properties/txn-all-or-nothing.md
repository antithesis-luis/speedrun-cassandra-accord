# txn-all-or-nothing (G2)

## Claim
D1: "**Atomic Commitment**: All changes commit together or none at all"; "Multi-Table Atomicity:
Ensure related changes across tables succeed or fail together".

## Code path
- Write fragments for all tables and partitions go into one `TxnUpdate` and one Accord txn
  (`C/cql3/statements/TransactionStatement.java:520–536`). There is one `TxnId`, one `executeAt`
  and one `Writes`, computed once at the coordinator (`A/coordinate/ExecuteTxn.java:442–458`).
- The ack precedes Apply: `A/coordinate/CoordinationAdapter.java:289–297` calls the client
  callback, then starts `PersistTxn` (`A/coordinate/PersistTxn.java:36`, `Persist.java:56`), which
  sends `Apply` (`A/messages/Apply.java:64`) to each shard.
- Each replica applies its slice: `A/local/Commands.java:535/540` `apply` →
  `C/service/accord/txn/TxnWrite.java:479` `apply`, which writes into memtables/commitlog.
- If the coordinator dies after Commit, the progress log (`A/impl/progresslog/DefaultProgressLog.java:88`)
  fetches the outcome and recovers it (`A/coordinate/Recover.java:106`). A txn that never reached
  a decision is invalidated as a whole (`Recover.java:594–621`), never per shard.
- Readers wait on deps, so a read txn that conflicts with the writer executes after it on every
  shard. Seeing exactly one table's write would mean the two shards ordered the txns differently,
  or one shard applied a txn that the other invalidated.

## Client semantics the checker must respect
- Use a fresh unique token per write txn, e.g. `<writer>-<seq>`. A retry after an ambiguous
  failure writes a *new* token, so a retry never collides with the old one.
- Ambiguous outcomes (`WriteTimeout`/`WriteFailure`/`OperationTimedOut`/`NoHostAvailable`) mean
  the token may appear in both places or in neither. **It must never appear in exactly one.**
  Both reads must be in **one** txn. Two separate SELECTs are not atomic and would cause false
  alarms.
- Read with explicit keys (`LET` single rows, or a returning `SELECT` per table). No range scans,
  no paging (D2).
- CL `QUORUM` (the driver default `LOCAL_ONE` is rejected; `IAccordService.java:84`).
- Initial state: both rows absent or null in a slot counts as "neither", which is consistent.

## Failure scenario
The coordinator is killed after one shard got Apply. Recovery on another node decides
`Invalidate` (or a different `executeAt`), so one table keeps the token and the other doesn't.

## Known closed issues
- **CASSANDRA-20325**, "Accord: Fix recovery when one shard is committed/stable and another is
  preaccepted" (https://issues.apache.org/jira/browse/CASSANDRA-20325). Recovery of a multi-shard
  txn failed to create a correct edge with recovery of earlier txns. Fixed by accord
  `1542da5d8acf08b8226227c91d4f81c64ed9762c` / cassandra
  `64c4aa88f56da790d6a96e23828a8b162a905e2b`.
- CASSANDRA-20089 (Accord double apply), fixed before alpha1.
