# full-mode-linearizable (G4)

## Claim
- D1: "Normal CQL reads and writes become linearizable when `transactional_mode='full'`".
- D2 (`onboarding-to-accord.adoc`, "non-SERIAL consistency"): "non-SERIAL operations are
  linearizable by default when migrated to Accord". `full` means "all reads and writes will
  execute on Accord".

## Code path
- Reads: `C/service/StorageProxy.java:2174` `read` → `dispatchReadWithRetryOnDifferentSystem` →
  `readWithAccordAsync` (:2286–2302) → `AccordService.coordinateAsync` (:1155).
  - Kind: `shouldReadEphemerally` (`ConsensusRequestRouter.java:506–521`). A single-partition
    SELECT on a `full` table with `accord.ephemeral_reads=true` (the default,
    `AccordConfig.java:300`) is an **EphemeralRead**, which "only provides per key
    linearizability" (`cql-on-accord.adoc:46–49`). This is enough for this per-key property.
  - A multi-partition `IN` SELECT is a full `Read`.
  - Note: the project's dtests run with `accord.ephemeral_reads=false`
    (`AccordTestBase.java:395`). We keep the production default so that the ephemeral path is
    under test.
- Writes: `StorageProxy.dispatchMutationsWithRetryOnDifferentSystem` (:1267) →
  `ConsensusMigrationMutationHelper.mutateWithAccordAsync` (:269), a write-only Accord txn.
- Coordinator and replica: as in txn-strict-serializable (`CoordinateTransaction.java:123`,
  `ExecuteTxn.java:442`; ephemeral path `A/coordinate/CoordinateEphemeralRead.java`,
  `ExecuteEphemeralRead.java`).
- Timestamps: on `full` tables, writes use the Accord timestamp unless `USING TIMESTAMP` is given
  (D2). With a client timestamp, application is ordered, but "the merged result may not appear
  linearizable".

## Client semantics the checker must respect
- **CL:** use `QUORUM` (or `ONE`/`ALL`). The CL is ignored in `full` mode (`TransactionalMode.java:169–192`)
  but `LOCAL_ONE` (the driver default), `LOCAL_QUORUM`, `TWO` and `THREE` are rejected with
  `InvalidRequest` (`StorageProxy.java:2288–2289`; `ConsensusMigrationMutationHelper.java:275–276`).
  Do not use SERIAL reads here, because the point is to test the non-SERIAL path.
- **Never use `USING TIMESTAMP`.** Do not mix it into batches either, because mixed batches are
  rejected by default (`accord.mixed_time_source_handling=reject`).
- **Ambiguous writes:** a `WriteTimeout` (write_type `CAS`), `WriteFailure`, `OperationTimedOut`
  or `NoHostAvailable` means the version may or may not be applied. A later read may legally
  return it. The checker treats ambiguous versions as "possibly written".
- **Read timeouts:** the driver's default `RetryPolicy` retries a `ReadTimeout` once (Accord sends
  received=0, required=0, data_present=false). Use `FallthroughRetryPolicy` so that the read's
  start time is the attempt that returned. Otherwise the "started after ack" window is wrong. With
  this policy it is still correct, just less precise.
- **No paging, no range scans:** D2 says paging and partition-range reads are not linearizable or
  strict serializable. Use single-key SELECTs or `IN` lists with `fetch_size` above the row count.
- Monotonic per-key versions come from one writer per key. Do not blind-write the same key from
  two clients with client-chosen versions, because "newer" would then be ambiguous.

## Failure scenario
An ephemeral read on a replica that has not yet applied (or has lost) an acknowledged write
returns the older version. Or GC makes a replica treat a decided write as unknown, and the read is
served without waiting for it.

## Known closed issues
- CASSANDRA-21440 (expunged records read as NotDefined instead of Erased, "linearizability
  violations") is likely to surface here as a stale read too. Fixed by accord `66cab49` /
  cassandra `3d40c88`.
