# fix-verify-acked-transfer-overwritten-2 · 0e1949506e0ec5407eb17348c627c8a3-63-12 · current@e874e3a9 + fixes/acked-transfer-overwritten.patch · completed · 30 m
Report: https://honey-whale.antithesis.com/report/1m1Ur9qEIU4qMIV6bVIJALEA/TZXCICByv8d1_9cYxLwOit-JGi3xkzPHbasNfHMMLcE.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE2OjUzOjMzLjg0MzAwNTQ2MloiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiVFpYQ0lDQnl2OGQxXzljWXhMd09pdC1KR2kzeGt6UEhiYXNOZkhNTUxjRS5odG1sIiwicmVwb3J0X2lkIjoiMW0xVXI5cUVJVTRxTUlWNmJWSUpBTEVBIn19fYRMwrkd2H--hy32gsQF2UrB5cW93Y848VKOv1g5hnJSqlsgMIE2PmVkcLF8QqXEllbUn3BJk5KjacXN5k-TeQg

Run: completed 2026-10-08T17:53:34Z, antithesis v63-12. FULL fault set (network, node pause, CPU throttle, node kill/stop + restart, clock jumps). Same workload as iterate-3. The image adds acked-transfer-overwritten.patch.
Summary: 11 properties fail. Node exit code 3 (6 + 4) and Guarantee 5 ×3 (4 each) have the same harness/environment causes as iterate-3: a single seed that doesn't resolve while node1 is down, and container IP churn on restart that deadlocks the CMS. All 27 command-exit failures are `cassandra.UnresolvableContactPoints` in `helper_accord.connect` (same as iterate-3). One audit (1 counterexample each for Guarantee 1 sum and Guarantee 1 even-counters) failed right after node restarts. It is classified suspect. ALLOW_UNSAFE_STARTUP was not exercised in that history: node2's stop was graceful and completed, and the killed node1 had not restarted yet. The coordinator was a node that had just restarted with a new IP and logged "Could not catchup with peers; continuing to startup". Guarantee 2 conditional write and every other Guarantee 1–Guarantee 4 safety Always pass. acked-transfer-overwritten's conservation symptom had 0 failures in the network-only acked-transfer-overwritten run, and here it fails once, only in a restart history.

| Property | Guarantee (type) | Status | Examples | Counterexamples |
|---|---|---|---|---|
| container: cassandra-accord-node2, exit code: 3 | Antithesis default/setup (-) | Failing | 0 | 6 |
| container: cassandra-accord-node3, exit code: 3 | Antithesis default/setup (-) | Failing | 0 | 4 |
| All commands were run to completion at least once | Antithesis default/setup (-) | Passing | 1 | 0 |
| All commands were started at least once | Antithesis default/setup (-) | Passing | 1 | 0 |
| Always: Peak memory usage | Antithesis default/setup (-) | Passing | 4519 | 0 |
| Always: Unreachable | Antithesis default/setup (-) | Passing | 0 | 0 |
| Cassandra node startup complete | Antithesis default/setup (-) | Passing | 57 | 0 |
| Containers joined the Antithesis network | Antithesis default/setup (-) | Passing | 4 | 0 |
| Customer output volume | Antithesis default/setup (-) | Passing | 1 | 0 |
| Invalid paths found during Antithesis instrumention | Antithesis default/setup (-) | Passing | 1 | 0 |
| Language name: Java, sdk version: 1.7.0 | Antithesis default/setup (-) | Passing | 57 | 0 |
| Language name: Python, sdk version: 0.4.0 | Antithesis default/setup (-) | Passing | 2613 | 0 |
| Never: Invalid commands found | Antithesis default/setup (-) | Passing | 0 | 0 |
| No Antithesis build errors | Antithesis default/setup (-) | Passing | 1 | 0 |
| No Antithesis build warnings | Antithesis default/setup (-) | Passing | 1 | 0 |
| No Antithesis errors | Antithesis default/setup (-) | Passing | 0 | 0 |
| No Antithesis session errors | Antithesis default/setup (-) | Passing | 0 | 0 |
| No unexpected crashes | Antithesis default/setup (-) | Passing | 0 | 0 |
| Paths found for Antithesis instrumentation | Antithesis default/setup (-) | Passing | 1 | 0 |
| Recent software version provided | Antithesis default/setup (-) | Passing | 1 | 0 |
| Software images match expected platform | Antithesis default/setup (-) | Passing | 3 | 0 |
| Software was instrumented | Antithesis default/setup (-) | Passing | 1 | 0 |
| Symbols were extracted from every binary provided for symbolization | Antithesis default/setup (-) | Passing | 1 | 0 |
| Symbols were uploaded | Antithesis default/setup (-) | Passing | 1 | 0 |
| Test ran with full parallelism | Antithesis default/setup (-) | Passing | 1 | 0 |
| The Antithesis Fault Injector was started | Antithesis default/setup (-) | Passing | 1 | 0 |
| Thread pausing was enabled | Antithesis default/setup (-) | Passing | 3 | 0 |
| Unique commands found | Antithesis default/setup (-) | Passing | 1 | 0 |
| Virtual time per wall time | Antithesis default/setup (-) | Passing | 1 | 0 |
| a durability sample during the run could not read some rows within its time budget | Antithesis default/setup (-) | Passing | 3 | 0 |
| a final durability check could not connect to the cluster | Antithesis default/setup (-) | Passing | 3 | 0 |
| a final durability check could not read some acknowledged rows within its time budget | Antithesis default/setup (-) | Passing | 2 | 0 |
| a read-back of an acknowledged durable write did not complete in its time budget | Antithesis default/setup (-) | Passing | 6 | 0 |
| audited bank balances sum to the initial total | Guarantee 1 (always) | Failing | 345 | 1 |
| audited transfer counters sum to an even number | Guarantee 1 (always) | Failing | 345 | 1 |
| a final audit after faults stopped saw committed transfers | Guarantee 1 (sometimes) | Passing | 12 | 43 |
| a private-slot transfer reads the markers acknowledged before it and none from later transfers | Guarantee 1 (always) | Passing | 97 | 0 |
| a private-slot transfer was declined for insufficient balance | Guarantee 1 (sometimes) | Passing | 86 | 98 |
| a read started after a transfer was acknowledged sees that transfer | Guarantee 1 (always) | Passing | 93 | 0 |
| a read-back of a private slot sees one consistent transfer state | Guarantee 1 (always) | Passing | 93 | 0 |
| a transfer ended with an unknown outcome | Guarantee 1 (reachable) | Passing | 42 | 0 |
| a transfer moved a source account's entire balance | Guarantee 1 (sometimes) | Passing | 5 | 76 |
| a transfer reads balances within the bank total | Guarantee 1 (always) | Passing | 76 | 0 |
| a transfer reads every transfer acknowledged or observed before it started | Guarantee 1 (always) | Passing | 76 | 0 |
| a transfer saw transfers committed by other clients since this client last looked | Guarantee 1 (sometimes) | Passing | 50 | 71 |
| a transfer transaction reads both of its accounts | Guarantee 1 (always) | Passing | 76 | 0 |
| a transfer was acknowledged after resubmitting an attempt whose outcome was unknown | Guarantee 1 (sometimes) | Passing | 9 | 65 |
| a transfer was declined because the source balance was too low | Guarantee 1 (sometimes) | Passing | 61 | 76 |
| a transfer whose outcome was unknown was later seen applied | Guarantee 1 (reachable) | Passing | 8 | 0 |
| a transfer's effect was read back through a different coordinator | Guarantee 1 (sometimes) | Passing | 93 | 24 |
| an application-retried transfer reads both accounts with balances within the bank total | Guarantee 1 (always) | Passing | 65 | 0 |
| an application-retried transfer reads every transfer this client saw complete before it | Guarantee 1 (always) | Passing | 65 | 0 |
| an audit completed while an earlier transfer's outcome was still unknown | Guarantee 1 (sometimes) | Passing | 15 | 74 |
| an audit reflects every transfer acknowledged or observed before it started | Guarantee 1 (always) | Passing | 345 | 0 |
| an audit saw a bank account drained to exactly zero | Guarantee 1 (sometimes) | Passing | 17 | 343 |
| consecutive audits by one client observed newly committed transfers | Guarantee 1 (sometimes) | Passing | 46 | 139 |
| every seeded bank account is visible to an audit transaction | Guarantee 1 (always) | Passing | 345 | 0 |
| no bank account balance is negative in an audit | Guarantee 1 (always) | Passing | 345 | 0 |
| a conditional cross-table write read the same token in every slot of its group | Guarantee 2 (always) | Passing | 99 | 0 |
| a conditional cross-table write was declined because another writer changed the group | Guarantee 2 (sometimes) | Passing | 23 | 54 |
| a cross-table read saw a group rewritten since this reader's previous read | Guarantee 2 (sometimes) | Passing | 8 | 119 |
| a cross-table read transaction saw the same token in every slot of a group | Guarantee 2 (always) | Passing | 119 | 0 |
| a cross-table write of one token to four partitions was acknowledged | Guarantee 2 (sometimes) | Passing | 67 | 99 |
| a cross-table write transaction ended with an unknown outcome | Guarantee 2 (reachable) | Passing | 42 | 0 |
| a final check after faults stopped saw logged-batch groups written | Guarantee 2 (sometimes) | Passing | 3 | 60 |
| a final check after faults stopped saw transactional groups written | Guarantee 2 (sometimes) | Passing | 8 | 55 |
| a read-back after a cross-table write saw the same token in every slot | Guarantee 2 (always) | Passing | 26 | 0 |
| a read-back found a write of unknown outcome applied to every slot of its group | Guarantee 2 (sometimes) | Passing | 7 | 22 |
| after faults stopped every logged-batch group holds the same token in every slot | Guarantee 2 (always) | Passing | 62 | 0 |
| after faults stopped every transactional group holds the same token in every slot | Guarantee 2 (always) | Passing | 62 | 0 |
| a check during the run verified sampled acknowledged durable writes | Guarantee 3 (sometimes) | Passing | 38 | 3 |
| a conditional insert of a fresh id found no existing row for it | Guarantee 3 (always_or_unreachable) | Passing | 50 | 0 |
| a durable write ended with an unknown outcome | Guarantee 3 (reachable) | Passing | 7 | 0 |
| a durable write transaction spanning three partitions was acknowledged | Guarantee 3 (sometimes) | Passing | 46 | 59 |
| a final check found a write of unknown outcome applied | Guarantee 3 (sometimes) | Passing | 5 | 12 |
| a final check verified acknowledged durable writes from the ledgers | Guarantee 3 (sometimes) | Passing | 13 | 4 |
| a final check verified acknowledged multi-partition durable writes in every partition | Guarantee 3 (sometimes) | Passing | 11 | 6 |
| after faults stopped every acknowledged durable write is present with its value | Guarantee 3 (always) | Passing | 13 | 0 |
| an acknowledged durable write is visible with its value to the next read | Guarantee 3 (always) | Passing | 83 | 0 |
| an acknowledged durable write sampled during the run is present with its value | Guarantee 3 (always) | Passing | 40 | 0 |
| an acknowledged durable write was read back through a different coordinator | Guarantee 3 (sometimes) | Passing | 82 | 16 |
| a conditional single-statement write on a full-mode table was applied | Guarantee 4 (sometimes) | Passing | 97 | 4 |
| a consistency-level ONE read right after an acknowledged plain write returned that write | Guarantee 4 (sometimes) | Passing | 139 | 150 |
| a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one | Guarantee 4 (always) | Passing | 4 | 0 |
| a multi-key IN read of published registers completed | Guarantee 4 (reachable) | Passing | 7 | 0 |
| a plain read of a published register returned a version newer than its published floor | Guarantee 4 (sometimes) | Passing | 9 | 18 |
| a plain read of a published register sees at least the version acknowledged before the read started | Guarantee 4 (always) | Passing | 18 | 0 |
| a plain read on a full-mode table returns only versions that were written | Guarantee 4 (always) | Passing | 151 | 0 |
| a plain read on a full-mode table returns the latest acknowledged write or a newer one | Guarantee 4 (always) | Passing | 151 | 0 |
| a plain write was read back through a different coordinator than the one that acknowledged it | Guarantee 4 (sometimes) | Passing | 149 | 118 |
| a plain write with an unknown outcome was later read back | Guarantee 4 (reachable) | Passing | 6 | 0 |
| a reader saw a published register advance between two of its plain reads | Guarantee 4 (sometimes) | Passing | 3 | 18 |
| one client's successive plain reads of a single-writer register never go backwards | Guarantee 4 (always) | Passing | 18 | 0 |
| a plain write and read on a transactional table succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 51 | 4 |
| a transaction succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 51 | 4 |
| every node coordinated a transaction within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 51 | 4 |
| a node coordinated a transaction after earlier attempts through it failed | Guarantee 5 (sometimes) | Passing | 22 | 48 |
| a transaction succeeded after the first attempt once faults stopped had failed | Guarantee 5 (sometimes) | Passing | 16 | 39 |
| the first transaction attempt once faults stopped succeeded | Guarantee 5 (sometimes) | Passing | 35 | 20 |
| accord/anytime_bank_audit.py | command exit (-) | Failing | 212 | 3 |
| accord/parallel_driver_bank_autoretry.py | command exit (-) | Failing | 64 | 10 |
| accord/parallel_driver_pair_reads.py | command exit (-) | Failing | 125 | 3 |
| accord/parallel_driver_rt_marker.py | command exit (-) | Failing | 122 | 11 |
| accord/anytime_durable_sample.py | command exit (-) | Passing | 291 | 0 |
| accord/eventually_bank_audit.py | command exit (-) | Passing | 59 | 0 |
| accord/eventually_durable_check.py | command exit (-) | Passing | 79 | 0 |
| accord/eventually_pair_check.py | command exit (-) | Passing | 64 | 0 |
| accord/eventually_recovery_probe.py | command exit (-) | Passing | 55 | 0 |
| accord/parallel_driver_bank_transfers.py | command exit (-) | Passing | 80 | 0 |
| accord/parallel_driver_durable_readback.py | command exit (-) | Passing | 129 | 0 |
| accord/parallel_driver_durable_writes.py | command exit (-) | Passing | 61 | 0 |
| accord/parallel_driver_fm_readers.py | command exit (-) | Passing | 122 | 0 |
| accord/parallel_driver_fm_register.py | command exit (-) | Passing | 138 | 0 |
| accord/parallel_driver_pair_writes.py | command exit (-) | Passing | 131 | 0 |

Note: all other Antithesis default/setup properties pass. For Sometimes/Reachable rows, "Counterexamples" counts the evaluations where the condition was false.

## Failing: container: cassandra-accord-node2, exit code: 3 (6) / cassandra-accord-node3, exit code: 3 (4)
- moment: node2 -2229495156264603638 @ 169.58804939873517; node3 3051685627654177193 @ 227.5636098345276
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMTY5LjU4ODA0OTM5ODczNTE3In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii0yMjI5NDk1MTU2MjY0NjAzNjM4In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6Ijk0NGUxYmMxNjliZTM4ZDk0ZDQ1NjVmN2JiMmY3ODE5LTYzLTEyIn0 · https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjI3LjU2MzYwOTgzNDUyNzYifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzA1MTY4NTYyNzY1NDE3NzE5MyJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiI5NDRlMWJjMTY5YmUzOGQ5NGQ0NTY1ZjdiYjJmNzgxOS02My0xMiJ9
- log: not downloaded separately. The same event appears in antithesis/scratchbook/logs/fv2-7848957582273250159.log (206.37 node2 exit=3, right after node1 died at 206.37).
- timeline/details: A run-wide `snouty runs events -m "Exception encountered during startup"` finds only `The seed provider lists no seeds.`, 6× node2 and 4× node3, which matches the counts exactly. The cause is the same as iterate-3: the only seed is `cassandra-accord-node1`, and its DNS name disappears while node1's container is down. Class: **false-positive** (checklist 3).

## Failing: a transaction succeeded within 120 seconds after faults stopped (also "every node coordinated …", "a plain write and read …", 4 each)
- moment: input_hash=-7563627453930811647 vtime=274.10750866355374
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjc0LjEwNzUwODY2MzU1Mzc0In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii03NTYzNjI3NDUzOTMwODExNjQ3In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6Ijk0NGUxYmMxNjliZTM4ZDk0ZDQ1NjVmN2JiMmY3ODE5LTYzLTEyIn0
- log: antithesis/scratchbook/logs/fv2-m7563627453930811647.log
- timeline:
  - 139.17 FAULT node/stop node1 (exit 137 at 139.62), restarted 141.62. 144.46 node1 `Listening on address: (cassandra-accord-node1/10.89.0.6:7000)` (it was 10.89.0.2).
  - 151.89 FAULT node/stop node2 (exit 137), restarted 154.12. 156.91 node2 listens on **10.89.0.7** (it was .3).
  - 153.06–158.83 node1 finishes journal replay. `Fetching topologies … from [/10.89.0.3, /10.89.0.2, /10.89.0.4]` (stale addresses). Catch-up: "2 is considered faulty", "timeout 3". 158.83 `ERROR AccordService.java:764 - Could not catchup with peers; continuing to startup`, then `Committing STARTUP`.
  - 158.83, 170.63, 264.03 [node3] `Caught an exception while trying to CAS: UnavailableException: Cannot achieve consistency level SERIAL 2 > 1`. node3 is the only CMS member at its registered address, so the address changes can't commit.
  - 164.16 onward: the recovery probe gets `10.89.0.6 / 10.89.0.7 not in driver metadata`, and node3's txns time out. FAIL at 274.11.
- details: Same mechanism as iterate-3 (2 of 3 CMS members re-addressed before either `Startup` committed). Class: **false-positive** (checklist 3, environment IP churn). Same fix.

## Failing: audited bank balances sum to the initial total / audited transfer counters sum to an even number (1 counterexample each, same audit)
- moment: input_hash=1866202673575119510 vtime=200.67971567227505 (counters: 200.67972798924893)
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjAwLjY3OTcxNTY3MjI3NTA1In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjE4NjYyMDI2NzM1NzUxMTk1MTAifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiOTQ0ZTFiYzE2OWJlMzhkOTRkNDU2NWY3YmIyZjc4MTktNjMtMTIifQ
- log: antithesis/scratchbook/logs/fv2-1866202673575119510.log (+ fv2-1866202673575119510.ndjson from 133 s)
- timeline:
  - 133.96–181.73 every audit in this history passes (total 12000), including one at 181.73 by the same client pid 132 via node3 (10.89.0.4).
  - 153.5, 158.4, 167.1, 195.4 clock/skip +0.8–1.3 s on all nodes.
  - 155.60 node2 `Announcing shutdown`. 157.61 `RejectedExecutionException: 12 is terminated. Cannot execute Clear Progress …` (AccordExecutor, during shutdown). 159.93 `Cassandra shutdown complete` (graceful: SIGTERM, exit 143 at 160.62, so the safe-stop marker was written and no "Stop marker is older than start marker" warning appears at restart).
  - 162.62 node2 restarted. 168.22 it listens on **10.89.0.6** (it was .3). 177.95 journal replay finishes (0.01 s). 188.88 `ERROR AccordService.java:764 - Could not catchup with peers; continuing to startup`. 188.88 `Committing STARTUP` (this one succeeds: node1 and node3 are still at their registered addresses). 194.41 `Startup complete`.
  - 199.35 FAULT node/kill node1 (exit 137 at 199.62). It does not restart before the failure.
  - 200.68 [client pid 132, bank_transfers audit] coordinator **10.89.0.6 (node2, just restarted)**. Total 11939 (expected 12000), xfer sum 155 (odd). Balances a0..a5 = 781, 209, 1021, 2064, 1153, 671; b100..b105 = 618, 567, 945, 1958, 945, 1007.
- details / checklist:
  1. Client API: clean, same analysis as iterate-1. The audit is one read-only BEGIN TRANSACTION with 12 LETs, and transfers are self-contained, money-conserving transactions.
  2. Wrong assumption: none. Accord transactions on `full` tables promise strict serializability whatever node restarts or catch-up failures happen.
  3. Configuration/topology: two harness or environment factors sit right before the failure. (a) node2 restarted with a **new IP**. Its catch-up failed ("Could not catchup with peers"), and it coordinated the failing audit 6 s after `Startup complete` while node1 was dead. (b) `stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP` is **not** involved: node2's stop was graceful (shutdown complete, safe-stop marker written), and node1 was killed but not restarted before the audit.
     Note on the ALLOW_UNSAFE_STARTUP assumption (for future restart failures): Antithesis docs say a restarted node "may keep durably synced filesystem changes, or may lose all of their modified data", so the "page cache survives a kill" premise in cassandra-overrides.yaml is not guaranteed. On the other hand, AccordTask replies only after `journal.saveCommand(…, onFlush)` → `segments.onDurable` (AccordTask.java:714–716, AccordJournal.java:162–177), and in PERIODIC mode that fires after the fsync that covers the record (Flusher.PeriodicMode.isDurable). So acknowledged votes are fsynced before the reply. The stop marker (`writeSafeStopMarker` = `segments.fsync()` + marker) also covers non-vote state: periodic C* commitlog (10 s) data applied by Accord, and store state. A failure after an ALLOW_UNSAFE_STARTUP restart would therefore have to be classified at best `undetermined`.
  4. Orchestration: none. Kills and stops come from the Antithesis fault injector.
  5. Checker: the same assertions passed 345 times in this run. The check is a sum over one snapshot.
- Class: **suspect**. The audit broke conservation, but only through a coordinator that had just re-joined under a new IP after a failed catch-up, and the IP change is an environment artifact (production nodes keep their address). It is not reported as a violation. After the static-IP fix, a recurrence on a restarted node with a stable address should go to the adversarial reviewer as a candidate new bug: "a node that logs *Could not catchup with peers; continuing to startup* serves a non-serializable read". To tighten it, the bank audit should log `coordinator` and also emit `Reachable("an audit was coordinated by a node within 30 s of its restart")`. The details already carry coordinator, balances and xfers.

## Failing: accord/parallel_driver_bank_autoretry.py (10), accord/parallel_driver_rt_marker.py (11), accord/anytime_bank_audit.py (3), accord/parallel_driver_pair_reads.py (3)
- moment: input_hash=7848957582273250159 vtime=225.79899993818253 (autoretry; pair_reads @ 225.84740288998 and rt_marker @ 225.8542898669839 in the same moment). anytime_bank_audit: 7139701874135329358 @ 237.96382902306505
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjI1Ljc5ODk5OTkzODE4MjUzIn1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ijc4NDg5NTc1ODIyNzMyNTAxNTkifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiOTQ0ZTFiYzE2OWJlMzhkOTRkNDU2NWY3YmIyZjc4MTktNjMtMTIifQ · https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjM3Ljk2MzgyOTAyMzA2NTA1In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjcxMzk3MDE4NzQxMzUzMjkzNTgifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiOTQ0ZTFiYzE2OWJlMzhkOTRkNDU2NWY3YmIyZjc4MTktNjMtMTIifQ
- log: antithesis/scratchbook/logs/fv2-7848957582273250159.log
- timeline: 203.37 node2 killed. 206.37 node1 dies, and node2's restart exits 3 (no seeds). 224.87 node3 killed. 225.77 FAULT node/kill node1. At 225.79–225.85, three commands each raise `helper_accord.py line 98, in connect → cluster = Cluster(` → `cassandra.UnresolvableContactPoints: {}`, then `task finished … exit=1`.
- details: A run-wide events search finds 27 `UnresolvableContactPoints`, which equals 10+11+3+3. Class: **false-positive** (harness: the `Cluster()` constructor is outside the try/retry in `connect`). Same fix as iterate-3.
