---
sut_path: /home/exedev/cassandra/cassandra-accord/src/cassandra
commit: e874e3a90b1942b945477e6d9ba03880b4f4a19d
updated: 2026-10-08
external_references:
  - path: https://github.com/apache/cassandra/blob/trunk/doc/modules/cassandra/pages/developing/cql/transactions.adoc
    why: D1, the stated transaction guarantees
  - path: https://github.com/apache/cassandra/blob/cassandra-6.0-alpha2/doc/modules/cassandra/pages/managing/operating/onboarding-to-accord.adoc
    why: D2, full-mode linearizability, CL handling, paging/range caveats
  - path: https://cwiki.apache.org/confluence/display/CASSANDRA/CEP-15%3A+General+Purpose+Transactions
    why: D3, failure tolerance
---

# Property catalog: Cassandra 6.0-alpha2 + Accord

There is one property per guarantee in `guarantees.md`, and the slugs match it 1:1. The ranking
follows the guarantee rank. Evidence for each property is in `properties/<slug>.md`.

Common client rules for all properties (details are in the evidence files):
- Every statement runs at CL `QUORUM`. The driver default `LOCAL_ONE` is rejected by Accord.
- Use `FallthroughRetryPolicy`.
- Any `WriteTimeout`/`ReadTimeout`/`WriteFailure`/`ReadFailure`/`OperationTimedOut`/`NoHostAvailable`
  on a write is an **ambiguous** outcome.
- Checks read only explicit partition keys (single key or `IN` list, no paging, no range scans).

## Safety

### txn-strict-serializable — Multi-partition transactions are strictly serializable

| | |
|---|---|
| **Type** | Safety |
| **Property** | `BEGIN TRANSACTION` transfers between accounts on different partitions, together with read-only snapshot transactions, behave as one real-time-respecting total order. |
| **Invariant** | Transfer txn: `LET a = (SELECT … WHERE id=?) ; LET b = (SELECT … WHERE id=?) ; IF a.balance >= amt THEN UPDATE a … balance-amt, xfers+1 ; UPDATE b … balance+amt, xfers+1 END IF`. Audit txn: read-only `SELECT … WHERE id IN (all N ids)` inside BEGIN/COMMIT (one Accord `Read` over all keys, ≥2 keys so not ephemeral). **`Always`**: the audited sum equals the fixed initial total, and no balance is negative. **`Always`**: per client, each account's `xfers` counter seen by an audit started after an acknowledged transfer that touched that account is ≥ the counter that transfer returned or implied. Use the RETURNING/LET values, or read `xfers` back in the transfer txn. **`Sometimes`**: an audit observed a transfer that was in flight (ambiguous) when it started, and an audit ran while a node was down. |
| **Antithesis Angle** | Partitions and delays between coordinator and replicas during PreAccept/Accept/Commit; killing a coordinator mid-transfer, so recovery races the original; restarts that force journal replay; conflicting transfers on hot accounts; durability/GC cycles shortened (`tuning.md`) so expunged records meet late messages. Clock skips stress HLC-based TxnIds. |
| **Priority** | P1 (G1, rank 1) |
| **Status** | implemented (workload, template `antithesis/test/v1/accord/`: `parallel_driver_bank_transfers.py`, `parallel_driver_bank_autoretry.py`, `parallel_driver_rt_marker.py`, `anytime_bank_audit.py`, `eventually_bank_audit.py`, shared `helper_accord.py`; seed + tables `accounts`, `accounts_b` (ids 100–105), `rt_accounts` in `test/setup/client_setup.py`) |
| **Guarantee** | G1 |

**Open Questions:**
- Real-time check granularity: ambiguous transfers make exact counter prediction impossible. Checks must use "≥ last acknowledged" bounds, not equality. *(design choice for workload)*

### txn-all-or-nothing — A transaction's writes appear together or not at all

| | |
|---|---|
| **Type** | Safety |
| **Property** | All writes of one transaction become visible together across partitions and tables, even when its coordinator fails mid-commit. |
| **Invariant** | Each write txn generates a unique token `t` and writes `pair_a[k1].token = t` and `pair_b[k2].token = t` (different tables, different partitions). Reader txn: one `BEGIN TRANSACTION` with `LET x = (SELECT token FROM pair_a WHERE k=k1); LET y = (SELECT token FROM pair_b WHERE k=k2); SELECT x.token, y.token`, or a two-table returning select. **`Always`**: `x == y` (both from the same last writer). The checker needs the pair (k1, k2) to be fixed per slot, so each slot is always written as a unit. **`Sometimes`**: the read observed a token whose writer got an ambiguous outcome. |
| **Antithesis Angle** | Killing or partitioning the coordinator after Commit but before Apply reaches all replicas (the ack precedes Apply); recovery choosing commit vs invalidate; restart of one replica during Apply. |
| **Priority** | P2 (G2, rank 2) |
| **Status** | implemented: `parallel_driver_pair_writes.py` (unconditional/conditional txn + logged batch writes of one unique token to 2-4 partitions over pair_a/pair_b, read-back after unknown outcomes), `parallel_driver_pair_reads.py` (one-txn group reads), `eventually_pair_check.py` (all groups incl. logged-batch groups after quiescence); helpers in `helper_accord.py` |
| **Guarantee** | G2 |

**Open Questions:**
- None.

### acked-txn-durable — Acknowledged transactions survive minority crash/restart

| | |
|---|---|
| **Type** | Safety |
| **Property** | Every transaction acknowledged to the client is still visible after crash and restart of a minority of replicas. |
| **Invariant** | Writer: a txn appends row `(k, seq)` to `ledger` for a random `k`, with a unique `seq` per writer. Before sending, the client records `attempted(k,seq)` in `/ledger/<writer>.jsonl` on the shared volume; after success it records `acked(k,seq)`. Checker (an `eventually_`/`finally_` command after faults stop, and periodically during the run): read each partition `k` with a txn, by key, with no paging (keep partitions small; one key per SELECT, or an `IN` list of ≤ ~20 keys). **`Always`**: every `acked` row is present. Rows that are only `attempted` may be present or absent. **`Sometimes`**: an acked row was verified after a node restart. |
| **Antithesis Angle** | Node termination plus restart (journal replay, catch-up on start), kills during the window between quorum commit and Apply, partitions that isolate the restarted node, all with GC/durability cycles running. |
| **Priority** | P3 (G3, rank 3) |
| **Status** | implemented (P6): table `durable` (k int, id bigint, v text), ledger `/ledger/durable-<writer>.jsonl`; `parallel_driver_durable_writes`, `parallel_driver_durable_readback`, `anytime_durable_sample`, `eventually_durable_check` (shared `helper_durable.py`). The planned `ledger` table is unused (unique bigint ids instead of per-writer int seq). No "verified after a node restart" marker: a restart is not directly observable from the client. |
| **Guarantee** | G3 |

**Open Questions:**
- Whether Antithesis node termination can drop data that was written but not fsynced. `tuning.md` sets `accord.journal.flush_mode: BATCH` and `commitlog_sync: batch`, as the project simulator does, so the property holds even if ≥2 nodes are killed together. *(resolved by tuning)*

### full-mode-linearizable — Plain CQL is linearizable on transactional_mode='full'

| | |
|---|---|
| **Type** | Safety |
| **Property** | On a `transactional_mode='full'` table, single-statement INSERT/UPDATE/SELECT without `BEGIN TRANSACTION` is linearizable per key, whichever node coordinates. |
| **Invariant** | Per key `k` in table `kv`, writers issue plain `UPDATE kv SET ver=? WHERE k=?` with strictly increasing versions per key. Each key has one writer process, so versions come from a client counter, and writes never use `USING TIMESTAMP`. Readers issue plain `SELECT ver FROM kv WHERE k=?` (single partition → EphemeralRead) or `WHERE k IN (…)` (→ full Read) at CL QUORUM against random coordinators. **`Always`**: a read that starts after write `v` was acknowledged returns ≥ `v`. **`Always`**: a read never returns a version that was never attempted. **`Always`**: reads by one client of one key never go backwards. A version from an ambiguous write counts as attempted; once observed, it becomes a lower bound for later reads. **`Sometimes`**: a read was served by a different coordinator than the preceding write. |
| **Antithesis Angle** | Partitions between the coordinator and one replica, coordinator kill mid-write, restarts, clock skips; ephemeral reads concurrent with writes and recoveries. |
| **Priority** | P4 (G4, rank 4) |
| **Status** | implemented: `parallel_driver_fm_register.py` (write-then-read on private single-writer keys of table `fm_reg`, plain UPDATE/INSERT plus conditional INSERT IF NOT EXISTS / UPDATE IF, reads at ONE/QUORUM/ALL/SERIAL through a different coordinator, single-key or IN) and `parallel_driver_fm_readers.py` (concurrent readers of published single-writer keys: read-after-published-ack and per-client monotonic reads). Sessions disable client-side timestamps (`helper_accord.connect(client_timestamps=False)` → `session.use_client_timestamp = False`). Table is `fm_reg (k bigint, ver bigint, pad text)` rather than `kv`. |
| **Guarantee** | G4 |

**Open Questions:**
- None.

## Liveness

### recovers-after-faults — Transactions succeed again within 120 s after faults stop

| | |
|---|---|
| **Type** | Liveness |
| **Property** | Once fault injection stops, a small read-write transaction against the cluster succeeds within 120 s. |
| **Invariant** | `eventually_` command (runs after faults stop and nodes are restarted): loop for up to **120 s** of wall time. Each iteration issues `BEGIN TRANSACTION LET r = (SELECT …WHERE k=0); UPDATE probe SET n = n + 1 WHERE k=0 (or a fresh unique key); COMMIT TRANSACTION` at CL QUORUM through a session with all 3 contact points, with a 15 s client timeout and a 2 s sleep between attempts. **`Always(success within 120 s)`**. **`Sometimes`**: the first attempt failed and a later one succeeded. **`Sometimes`**: the first attempt succeeded. |
| **Antithesis Angle** | Everything the run threw at the cluster: stuck txns that need recovery, unrecovered dependencies blocking execution, nodes restarting and replaying journals, CMS member loss, fast-path electorate changes. |
| **Priority** | P5 (G5, rank 5) |
| **Status** | implemented (P6): `eventually_recovery_probe.py`. Window starts when the command starts; 3 s between rounds; 15 s client timeout, driver reconnects to a down node every 2 s (`helper_accord.connect(request_timeout=, reconnect_delay_s=)`). Probes: a multi-partition read-write BEGIN TRANSACTION through each of the 3 nodes (host-targeted; keys `kv` -1000-10i / -1001-10i, unique probe id per attempt) and a plain INSERT+SELECT on a fresh `kv` key. Always: a txn succeeded within 120 s (any node); every node coordinated a txn within 120 s; the plain write+read succeeded within 120 s. Sometimes: first attempt failed then later succeeded; first attempt succeeded; a node coordinated after earlier attempts through it failed. Every error/timeout counts as "not yet". |
| **Guarantee** | G5 |

**Open Questions:**
- The window starts at the first probe. If Antithesis restarts terminated nodes only when faults stop, JVM boot plus journal replay (tens of seconds) counts against 120 s. That only matters when ≥2 nodes were down, because one up node plus one more restored node is enough for quorum. *(watch in first runs)*
