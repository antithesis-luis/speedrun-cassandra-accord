---
sut_path: /home/exedev/cassandra/cassandra-accord/src/cassandra
commit: e874e3a90b1942b945477e6d9ba03880b4f4a19d
updated: 2026-10-08
---

# Tuning (apply identically to current and pre-fix builds)

All rows target a *class* of behaviour (workload-guidance §4), and none targets a specific bug.
YAML keys under `accord.journal` are the snake_case forms of the `JournalConfig` fields
(`config/DefaultLoader.java:49` uses `camelToSnake`).

Sources:
- `TB` = `test/distributed/.../accord/AccordTestBase.java:388–400`
- `GC` = `test/distributed/org/apache/cassandra/fuzz/topology/JournalGCTest.java:58–65`
- `EX` = `test/distributed/.../accord/journal/AccordJournalConsistentExpungeTest.java:70`
- `SIM` = `test/simulator/main/org/apache/cassandra/simulator/ClusterSimulation.java:875–891`
- `UT` = `test/unit/.../service/accord/AccordExpungeTest.java:164`

## Required to enable Accord (not tuning)

| Setting | Value | Note |
|---|---|---|
| `accord.enabled` | `true` | D2 "YAML": required for Accord to initialise |
| `accord.journal_directory` | `/var/lib/cassandra/accord_journal` | must persist across restarts |
| `accord.default_transactional_mode` | `full` | safety net; tables also set `transactional_mode='full'` |
| table option | `WITH transactional_mode='full'` | every test table |
| `accord.journal.stop_marker_failure_policy` | `ALLOW_UNSAFE_STARTUP` | Added at setup. Default `EXIT` makes a node killed without a clean stop refuse to start again (`AccordService.localStartup`), so every node-termination fault would be a permanent node loss. Journal segments are mmap'd and Antithesis kills the process, not the kernel, so the vote log is complete, which is the condition this policy asks for. `REBOOTSTRAP` was tried first: locally the restarted node was still not started after 12+ min (`logs/local-rebootstrap-stuck.txt`; possible lead, rebootstrap is recently changed code). Available at both refs. |

## Tuning rows

| Setting | Value | Production default | Behaviour class | Source |
|---|---|---|---|---|
| `accord.shard_durability_cycle` | `20s` | `5m` (AccordConfig.java:244) | Shard durability (ExclusiveSyncPoints), which advances RedundantBefore and so GC/cleanup on a test timescale | project test value (`EX`, AccordBootstrapTest, AccordMoveTest …; 9 uses of `20s`) |
| `accord.global_durability_cycle` | `20s` | `5m` (:245) | Global DurableBefore propagation, which gates ERASE/EXPUNGE | our choice, between `GC` (`1s`) and the default; matches the shard cycle |
| `accord.shard_durability_target_splits` | `4` | `8` (:241) | Smaller number of sync-point slices per cycle, so cycles finish quickly on a small dataset | `TB` |
| `accord.retry_syncpoint` | `1s*attempts` | `10s*attempt <= 600s` (:231) | Sync-point retry after failure on the fault timescale | `TB`, `GC` |
| `accord.retry_durability` | `1s*attempts` | `10s*attempt <= 600s` (:232) | Durability retry after failure on the fault timescale | `TB` |
| `accord.expire_syncpoint` | `1s*attempts<=300s` | `60s*attempts<=300s` (:224) | Stuck sync points expire on the fault timescale | `GC` |
| `accord.recover_txn` | `1s*attempts <= 10s` | `5s*attempts <= 60s` (:219) | Recovery of stalled txns (coordinator failure) on the fault timescale, including recovery racing live coordinators | our choice, informed by test values `1s` and `100ms` |
| `accord.command_store_shard_count` | `2` | #cores (:205) | Fewer command stores, so more txns share a store (CFK contention) and less CPU in simulation | `TB` |
| `accord.queue_shard_count` | `2` | #cores (:164) | Executor shards to match | `TB` |
| `accord.journal.segment_size` | `1048576` (1 MiB, int bytes) | 32 MiB (:392) | Journal segment rollover and compaction happen frequently with test-sized data | `UT` (`1 << 20`) |
| `accord.journal.compaction_period` | `10000ms` | `60000ms` (:403) | Journal compaction (merge, cleanup of expunged records) every few seconds | our choice. The project calls `600s` "deliberately high" (`IdenticalTopologyTest.java:50`) |
| `accord.journal.flush_mode` | `PERIODIC` (unchanged) | `PERIODIC` (:400) | Kept at the production default: Antithesis node termination kills the process, not the kernel, so page cache survives; BATCH would only hide durability behaviour users actually run with | boost decision (proposal was BATCH, from SIM) |
| `commitlog_sync` | `periodic` (unchanged) | `periodic` / 10000ms | Kept at production default, same reasoning | boost decision (proposal was batch, from SIM) |
| `memtable_heap_space` | `16MiB` | 1/4 heap | Frequent memtable flush to SSTables, so reads merge memtable and SSTable state and flush/compaction run during the test | our choice (`SIM` uses `1MiB`) |
| `commitlog_segment_size` | `5MiB` | 32MiB | Commitlog segment rollover and recycling | `test/conf/cassandra.yaml:10` |
| `num_tokens` | `1` | 16 | Simple ring like the project's Accord dtests (`withoutVNodes()`). Fewer ranges, so faster sync points | `TB` |
| `write_request_timeout` | `10s` | 2000 ms in Config (10 s in shipped yaml) | Accord write-txn deadline. The project raises it because "tests get flaky" | `TB` |
| `read_request_timeout` | `10s` | 5000 ms | Accord read-txn deadline, matched to writes | our choice |
| `native_transport_timeout` | `30s` | 12 s | Server queue timeout above txn deadlines | `TB` |
| `phi_convict_threshold` | `8` (unchanged) | 8 | Failure detection already works on a seconds timescale. No change | default |
| `accord.ephemeral_reads` | `true` (unchanged) | true | Keep the production single-key read path under test (G4) | default (`TB` disables it; we deliberately don't) |
| `accord.catchup_on_start` | `NORMAL` (unchanged) | NORMAL | Keep production restart behaviour (G5) | default (some tests use DISABLED) |
| JVM `MAX_HEAP_SIZE` | `1536M` | ½ RAM, capped | Capped memory, so resource bugs surface. Accord cache = 10% heap, working set = 5% heap, so evictions and loads from the journal get exercised | our choice |

## Notes
- None of these removes a means of availability: RF=3, quorum 2, CMS RF 3, and any node can
  coordinate.
- Durability and GC run in about 20 s cycles with journal compaction every 10 s. Expunge
  therefore happens many times in a 30–60 min run, instead of almost never (default 5 min cycles,
  1 min compaction).
- Revisit with `Sometimes` coverage for "journal compaction ran", "sync point completed" and
  "recovery invoked". If any is rarely hit, adjust the governing row above, never a single bug's
  window.
