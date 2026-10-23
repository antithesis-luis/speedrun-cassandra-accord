# txn-strict-serializable (G1)

## Claim
D1 (trunk `developing/cql/transactions.adoc`): "**Strict Serializability**: Transactions execute
as if in a single, total order that respects real-time ordering." CEP-15 makes the same claim.

## Code path (C = cassandra `e874e3a9` `src/java/org/apache/cassandra/`, A = accord `fff32de` `accord-core/src/main/java/accord/`)
- CQL entry: `C/cql3/statements/TransactionStatement.java:586` `execute`, `:504` `createTxn`, `:606` coordinate.
- Transaction kind selection: a read-only txn over 1 key becomes `EphemeralRead`, which is only
  per-key linearizable (`C/service/consensus/migration/ConsensusRequestRouter.java:506–521`;
  `doc/.../architecture/cql-on-accord.adoc:46–49`). **The audit txn must therefore read ≥2 keys**
  so that it is a full `Read` and joins the strict-serializable order.
- Coordinator: `C/service/accord/AccordService.java:1155` → `A/coordinate/CoordinateTransaction.java:123`
  (fast :149, medium :166, slow :177) → `A/coordinate/ExecuteTxn.java:442` → ack-then-persist
  `A/coordinate/CoordinationAdapter.java:289–297`.
- Replica side: `A/local/Commands.java` preaccept :150, accept :291, commit :342, apply :535.
  Deps come from `A/local/cfk/CommandsForKey.java:231`.
- Conditional update evaluation: `C/service/accord/txn/TxnUpdate.java:700,729`.
- Recovery: `A/coordinate/Recover.java:106` (invalidate :594/:617).
- GC/expunge: `A/impl/CommandChange.java:358–372` `shouldCleanup`, `A/local/Cleanup.java:75,111`,
  `C/service/accord/journal/CommandChanges.java:89`. Durability scheduling:
  `A/local/durability/ShardDurability.java:75,369`, cycles at `C/config/AccordConfig.java:244–245`.
- SUT self-checks to grep in logs: `C/service/accord/api/AccordViolationHandler.java:45,50`
  (timestamp/dependency violation, ERROR).

## Client semantics the checker must respect
- **CL:** set `QUORUM` on every statement. In `full` mode the CL is ignored
  (`TransactionalMode.java:139–160,169–192`) but still validated. `LOCAL_ONE` (the driver
  default), `LOCAL_QUORUM`, `TWO`, `THREE` and `EACH_QUORUM` are rejected with `InvalidRequest`
  (`IAccordService.java:83–84`). The serial CL in options feeds read-only txns (TransactionStatement :516). Leave it as the default `SERIAL`.
- **Ambiguous outcomes:** `WriteTimeout` (write_type `CAS`, CL `SERIAL`, message `"<txnId>: <keys>"`),
  the preempted/exhausted subclasses, `WriteFailure`, `OperationTimedOut`, `NoHostAvailable`:
  the transfer may or may not have applied (`AccordResult.java:130–205`,
  `RequestBookkeeping.java:85–113`).
  - Never assume it did not apply.
  - The total-sum invariant is unaffected, because each transfer conserves money.
  - Real-time checks may use only *acknowledged* transfers as lower bounds.
- **Non-idempotent retries:** a transfer that is retried after an ambiguous failure may apply
  twice. That is legal (two transfers), and it keeps the sum. The workload must not retry
  automatically under the same "logical op id" and then assert exactly-once.
  - Use `FallthroughRetryPolicy`.
  - The default driver `RetryPolicy` silently retries a `ReadTimeout` once, because Accord
    reports received=0 ≥ required=0. That is harmless for audits, but it hides attempts.
- **No paging, no range scans:** D2 says "Paging runs a separate transaction per page … not
  linearizable" and "Partition range reads are split into multiple transactions … will not produce
  a strict serializable result".
  - Audits use `WHERE id IN (…)` with an explicit key list. `IN` with `LIMIT` is rejected
    (TransactionStatement :594–599). `LET` must select a single row (:593).
  - Keep the account count small (e.g. 8–16) so the result fits in one page. Set
    `fetch_size` ≥ the row count.
- **Txn deadline:** `write_request_timeout` (tuned to 10 s) for transfers, `read_request_timeout`
  for audits (`AccordService.java:1158`). The client timeout must exceed `native_transport_timeout`.
- Do not use `USING TIMESTAMP` anywhere on these tables.

## Failure scenario
A replica omits a conflicting transfer from its deps (a CFK bug), or forgets a decided txn after
GC. Recovery or a late message then decides it differently, and an audit sees money created or
destroyed, or misses a transfer that was acknowledged before the audit started.

## Known closed issues
- **CASSANDRA-21440**, "Accord: CommandChanges.shouldCleanup must maintain EXPUNGE result after
  data expunged" (https://issues.apache.org/jira/browse/CASSANDRA-21440). Expunged journal records
  could be resurrected and read back as `NotDefined` instead of `Erased`. A replica then treats an
  already-decided txn as unknown, which can feed a wrong decision into recovery. JIRA: "This can
  lead to linearizability violations."
  - Fixed by accord `66cab49f1c9af471795339a5fdf9522e6e73b691` ("Expunged records may be
    resurrected"), picked up by cassandra `3d40c8825c8b06bcbd8378d698f6d2f3bf5dc25e`. Pre-fix
    cassandra is `c9ffe116457384200851939e3687f81c00015e02` (accord `0a10cd0`).
  - Fix hunk: `accord-core/.../impl/CommandChange.java` `shouldCleanup`, today at :358–372.
  - Trigger class: journal GC/expunge after durability bounds advance, plus delayed or retried
    messages or a restart reload.
- **CASSANDRA-20292**, "Accord: Various fixes": "Even if we can decide autonomously that we took
  the fast path, we must still wait for earlier transactions to decide themselves". Fixed by
  accord `344c20b6` / cassandra `d7ed1ad3`.
- **CASSANDRA-20427**: "Fast path stable commits must not override recovery propose/commit
  decisions" (omnibus fix).
