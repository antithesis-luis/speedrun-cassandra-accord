# committed-rows-read-absent adversarial review: Guarantee 1 txn-strict-serializable (committed seeded row read as absent)

Reviewer brief: defend Cassandra 6.0-alpha2 + Accord. Explain the missing-row reads as caused by the
harness, configuration, tuning, faults, driver or checker. Checklist: false-positive-review.md, items 1–5.
**Verdict: stands.**

Runs examined:
- `0b77f2b9…-63-12` (fv1): SUT plus `fixes/acked-transfer-overwritten.patch`. Log `logs/fv1-6718656826655334244.log`.
- `83ddaf62…-63-12` (unpatched): log fetched with `snouty runs logs … -3359217870427620869 155.436`, 21.9k lines. Not stored in the scratchbook.
- `e4947374…-63-12` (unpatched, iterate-1): `runs/iterate-1.md`, `logs/iter1-*`.

## 1. Harness intervention: none between the faults and the symptom
- **fv1:** `containers_meta` shows exactly one `init`/`start` per container: node1 @10.88, node2 @57.87, node3 @89.16, client @107.12. After that there are only health checks, and no stop, kill or restart.
- **83dd:** also one `init`/`start` per container: node1 @5.90, node2 @52.65, node3 @69.12, client @85.12.
- **Faults:** in both runs every `fault_injector` FAULT is `network/partition`, `network/clog` or `network/restore`. There are no kills, pauses or clock faults.
- **Restart path never ran.** Without restarts, `stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP`, journal replay, the entrypoint restart path and `helper-cms-bootstrap.sh` do not run during the workload. The CMS helper finishes before `setup_complete`: fv1 139.53, 83dd 123.98.
- **`fixes/acked-transfer-overwritten.patch` (fv1 only).** It switches fast read/write execution from `MAY_BYPASS_SAFESTORE` to `MAY_BYPASS_COMMANDSFORKEY`, which is Accord's own default and is stricter: it keeps the per-command state checks. It also changes the failed-read branch of `ExecuteTxn.onDone`, which reports an error and never returns data. Neither change can make a successful read return an absent row. The same symptom also appears on the unpatched build in two independent runs (83dd and e4947374), so the patch is neither necessary nor a plausible cause.
- **Setup.** `client_setup.py` creates the tables, waits for driver schema agreement, runs the probe transactions and then seeds the accounts. The seed is one Accord transaction, `IF s IS NULL THEN` with 12 INSERTs, so it is all-or-nothing. It is acknowledged before `setup_complete`: fv1 139.5223 → 139.5259, 83dd 123.9772 → 123.9809. Later audits saw all 12 rows (`every seeded bank account is visible` HIT): fv1 at 153.90 and 166.18, 83dd at 127.09, 130.85, 140.74, 143.05, 143.61 and 155.37. So the seed was committed and visible, and the later reads went back on that.

## 2. Configuration and tuning: no tuned value is a plausible safety cause
- **Tables.** Every bank table is created `WITH transactional_mode='full'`. `TransactionalMigrationFromMode.fromMode` only produces a non-`none` value on an ALTER that flips `accordIsEnabled`. CREATE gives `none` (TableParams default), so no migration or interop read path applies. In full mode `readCLForMode` is null, which means a plain Accord read.
- **Tuning.** All tuned values change timing or size only: durability cycles of 20 s, journal compaction every 10 s with 1 MiB segments, `recover_txn 1s*attempts<=10s`, `command_store_shard_count=2`, `num_tokens=1`, memtable 16 MiB. Most come from the project's own dtests.
- **Correlation with durability (a lead, not a defence).** Both failures follow durability or GC activity closely, and that activity runs far more often under the tuned cycles:
  - fv1: node3 completes its first shard-durability cycle for `accounts` (tid:1a) and `accounts_b` (tid:1b) at 251.21 and 251.44 ("in 120s", so stuck since the seed). The read of `accounts_b:102` with node3 as coordinator returns absent at 253.57.
  - 83dd: journal compaction runs on node1 and node3 at 150.95. Node3 completes cycles at 154.86 and node2 starts compacting at 155.32. The audit fails at 155.44 (coordinator 10.89.0.3 = node2).

  Shorter cycles make the GC, durability and truncation paths run more often. They do not relax any safety condition: production runs the same paths every 5 min. So tuning can raise the frequency but cannot explain the violation away.
- **Durability flush settings** (`commitlog_sync`, `journal.flush_mode`) stay at their production defaults, and they are irrelevant without crashes.

## 3. Faults within the promise
Only network partitions, clogs and latency, with RF=3 and no node loss or restart. The documented model of epochs and recovery (accord-architecture.adoc "epochs", cql-on-accord.adoc) is meant to tolerate exactly this. The docs never ask the user to wait for Accord epoch readiness after `CREATE TABLE` before writing. Epoch readiness is internal to the protocol: messages for future epochs are parked. Lag can be seen: node3 retires the table-creation epochs late (fv1 epochs 27 and 28 at 162.36; 83dd epoch 24 at 141.05), but that is something the SUT must handle, not a harness misuse.

## 4. Checker: sound
- **Transfer check (fv1).** It is one prepared BEGIN TRANSACTION. Two LETs do point SELECTs by full primary key. There are 7 bind markers in order (s, d, a, a, s, a, d), matching `transfer_bind`. The same prepared statement for (accounts_b → accounts) succeeds on every other execution. The assertion fires only when the server returned a row whose src columns are null while dst = 1000/0. An empty result would make all four values None. So this is server-side absence, not an empty or paged result and not a mis-decode.
- **Audit check (83dd, e4947374).** One unprepared 12-LET transaction with `fetch_size` 1000, so a single row and no paging. The missing set is `accounts:3` plus all six `accounts_b` rows, the same set in two independent runs. That is a table or token-range pattern, which points to one replica or command store lacking those partitions. A driver decode bug would not be that selective.
- **No deleting writes.** No command writes DELETE, TTL or null, and transfers only do `+=`/`-=`. The only ambiguous transfer that touched `accounts_b:102` in fv1 is an UPDATE.
- **The docs give no escape.** Even an `EphemeralRead` promises per-key linearizability (cql-on-accord.adoc:46-48), and the transfer is a Write transaction anyway. No documented case lets a point read in a full-mode transaction return a committed, previously visible row as absent.

## 5. Reproduction
- **Counts:**
  - fv1 (patched): 3 failing events, one operation on sibling branches.
  - 83dd (unpatched): 3 audit failures, one operation on sibling branches.
  - e4947374 (unpatched): a transfer read `accounts_b:105` as absent at 276.46 via 10.89.0.2, and an audit was missing the same 7 rows at 285.33.
- **Same mechanism.** Different coordinators (node1, node2, node3), different commands (transfers prepared, audits literal), both builds. The class is the same every time: an Accord transaction executes its read against state that lacks a committed and previously visible write, sometimes a whole table's rows.

## What would sharpen the root cause (not needed for the verdict)
- Log the txnId and executeAt of failing reads, and which replica served the data: Accord tracing, or debug logging of `ReadData` on the replica.
- Check whether the replica that served the read had the table-creation epoch retired or bootstrapped, and whether a durability cycle or `RedundantBefore` advance on that range happened between the seed and the read. The timing lead is node3's first `ShardDurability` completion for tid:1a/1b just before the fv1 failure.
