# acked-txn-durable (G3)

## Claim
D1: "**Durable Writes**: Committed transactions survive node failures."

## What "acknowledged" means in code
- The client gets success after `ExecuteTxn.onDone` (`A/coordinate/ExecuteTxn.java:442`). At that
  point the txn is Stable at a quorum and its reads have completed. The callback fires **before**
  `PersistTxn`/Apply is sent (`A/coordinate/CoordinationAdapter.java:289–297`). An acked write is
  therefore guaranteed by the commit decision held by a quorum's journals, not by applied data.
- Replica protocol replies (PreAccept/Accept/Commit acks) are released only after the journal
  record is "durable": `AccordTask.java:639–654,714–716` → `AccordJournal.saveCommand`
  (`C/service/accord/journal/AccordJournal.java:162–178`) → `Journal.onDurable`
  (`C/journal/Journal.java:207`).
  - In the default `PERIODIC` flush mode, "durable" means an fsync finished for time
    `writtenAt - periodicFlushLagBlock` (1500 ms) (`C/journal/Flusher.java:477–505`;
    `AccordConfig.java:400–402`). A reply can precede the fsync by up to that lag.
  - In `BATCH` mode the reply waits for the fsync. The project's simulator uses `BATCH` for the
    journal and `batch` for the commitlog (`test/simulator/.../ClusterSimulation.java:888–889`).
    `tuning.md` adopts the same.
- After a restart, the journal is replayed (`C/service/accord/journal/Replay.java:53`), the node
  catches up (`accord.catchup_on_start`, `AccordConfig.java:314–320`), and the progress log
  re-drives Apply for committed-but-unapplied txns.
- Data path: `TxnWrite.apply` (`C/service/accord/txn/TxnWrite.java:479`) writes to the normal
  memtable/commitlog. Accord also re-applies from its own journal state, so a lost memtable is
  recovered by Accord rather than by the commitlog alone.

## Client semantics the checker must respect
- **Ledger on the shared volume** (`/ledger/<writer>.jsonl`, append-only, one file per writer).
  Write `attempted` before sending and `acked` after success. The record survives client
  container restarts (workload-guidance §6).
- Only `acked` rows are required to be present. Ambiguous rows (timeouts, failures,
  `OperationTimedOut`, `NoHostAvailable`) may be present or absent. Do **not** retry the same
  `(k,seq)` and assert exactly-once. If a retry is used, give it a new `seq`.
- **Read-back:**
  - Use txn reads or plain SELECTs by explicit partition key, at CL `QUORUM` (in full mode CL is
    ignored, but `LOCAL_*` is rejected).
  - Use no paging: keep each `ledger` partition small (≤ a few hundred rows) and set `fetch_size`
    above the partition size, or read a clustering slice per `seq`.
  - Use no full-table scans (D2: range reads are not strict serializable and may time out).
- Run the final check after faults stop, and after all nodes are `UN` or after reads succeed.
  While a node is down, reads still succeed with quorum. The periodic in-run check must treat a
  read *timeout* as "unknown", not as "missing".
- The guarantee covers a **minority** crash. With BATCH flush the property should also hold when
  2 or 3 nodes are killed together, as long as data directories persist. If it fails only with
  PERIODIC flush and a majority killed, that is outside the claim.

## Failure scenario
The coordinator acks, then dies before sending Apply. One replica that had Stable restarts and
replays a journal segment that misses the record. Recovery then invalidates the txn, and the
acked row is gone.

## Known closed issues
- CASSANDRA-20641, "journal replay rejected startup". A restart-path journal bug; it relates to
  G5 rather than to data loss.
- CASSANDRA-21440 (expunged records resurrected as NotDefined) can also surface here as a missing
  acked write. See txn-strict-serializable.
