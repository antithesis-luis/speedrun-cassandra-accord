# hunt-1 · 42229a5d3c2580dbfcf6cf6dd13c5cc5-63-12 · current@e874e3a9 · completed · 300 m
Report: https://honey-whale.antithesis.com/report/NktZzXJr0UO579BjgdL5Mfs8/WahXSL5t4V92DlKQs1q_ypABQrL0eoB0t4m9lTR2aRQ.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA5VDAwOjQ1OjUwLjE3MzY4NTQyNloiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiV2FoWFNMNXQ0VjkyRGxLUXMxcV95cEFCUXJMMGVvQjB0NG05bFRSMmFSUS5odG1sIiwicmVwb3J0X2lkIjoiTmt0WnpYSnIwVU81NzlCamdkTDVNZnM4In19fWrNFp5DNmFdjXAMDyLShAIiDFVbFBq3o-ivCj39i3X6r5xWrcK63PhPBBMfCW9XFdEfA-U-ykSWQds9ci3dMAE

Run: workload 63f7cc96e480, static IPs, multi-seed on restart, turbo tier. Full fault set: network, node pause, CPU throttle, node kill/stop + restart, clock jumps. Created 2026-10-08T19:29:00Z, completed 2026-10-09T01:45:50Z, antithesis v63-12. Overrides: `accord.journal.stop_marker_failure_policy: ALLOW_UNSAFE_STARTUP`, commitlog periodic 10 s, Accord journal flush PERIODIC.

Summary: every history examined for the new Guarantee 2–Guarantee 5 failures has at least one **unclean node restart** before the failure (SIGKILL `exit=137` → `Stop marker is older than start marker … Continuing to startup as configured`). In each case the stale or absent data was served by, or coordinated through, a node that restarted that way. So every new hunt-1 failure is `suspect (unsafe-startup confound)`. The data symptoms are committed-rows-read-absent-shaped (whole rows or tables read as absent), not values from the wrong version. Guarantee 1 failures are the known acked-transfer-overwritten/committed-rows-read-absent signatures and are not re-investigated here.

| Property | Guarantee (type) | Status | Examples | Counterexamples |
|---|---|---|---|---|
| a private-slot transfer reads the markers acknowledged before it and none from later transfers | Guarantee 1 (always) | Passing | 2083 | 0 |
| a read started after a transfer was acknowledged sees that transfer | Guarantee 1 (always) | Passing | 2079 | 0 |
| a read-back of a private slot sees one consistent transfer state | Guarantee 1 (always) | Passing | 2079 | 0 |
| a transfer reads balances within the bank total | Guarantee 1 (always) | Passing | 2593 | 0 |
| a transfer reads every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 2594 | 13 |
| a transfer transaction reads both of its accounts | Guarantee 1 (always) | Failing | 2593 | 16 |
| an application-retried transfer reads both accounts with balances within the bank total | Guarantee 1 (always) | Failing | 1701 | 11 |
| an application-retried transfer reads every transfer this client saw complete before it | Guarantee 1 (always) | Failing | 1701 | 15 |
| an audit reflects every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 7115 | 57 |
| audited bank balances sum to the initial total | Guarantee 1 (always) | Failing | 6453 | 762 |
| audited transfer counters sum to an even number | Guarantee 1 (always) | Failing | 6723 | 518 |
| every seeded bank account is visible to an audit transaction | Guarantee 1 (always) | Failing | 7116 | 6 |
| no bank account balance is negative in an audit | Guarantee 1 (always) | Passing | 7116 | 0 |
| a transfer ended with an unknown outcome | Guarantee 1 (reachable) | Passing | 1622 | 0 |
| a transfer whose outcome was unknown was later seen applied | Guarantee 1 (reachable) | Passing | 77 | 0 |
| a final audit after faults stopped saw committed transfers | Guarantee 1 (sometimes) | Passing | 241 | 625 |
| a private-slot transfer was declined for insufficient balance | Guarantee 1 (sometimes) | Passing | 2011 | 1992 |
| a transfer moved a source account's entire balance | Guarantee 1 (sometimes) | Passing | 97 | 2593 |
| a transfer saw transfers committed by other clients since this client last looked | Guarantee 1 (sometimes) | Passing | 2153 | 2311 |
| a transfer was acknowledged after resubmitting an attempt whose outcome was unknown | Guarantee 1 (sometimes) | Passing | 482 | 1686 |
| a transfer was declined because the source balance was too low | Guarantee 1 (sometimes) | Passing | 2218 | 2584 |
| a transfer's effect was read back through a different coordinator | Guarantee 1 (sometimes) | Passing | 1830 | 681 |
| an audit completed while an earlier transfer's outcome was still unknown | Guarantee 1 (sometimes) | Passing | 740 | 2333 |
| an audit saw a bank account drained to exactly zero | Guarantee 1 (sometimes) | Passing | 347 | 7042 |
| consecutive audits by one client observed newly committed transfers | Guarantee 1 (sometimes) | Passing | 689 | 1958 |
| a conditional cross-table write read the same token in every slot of its group | Guarantee 2 (always) | Failing | 1540 | 16 |
| a cross-table read transaction saw the same token in every slot of a group | Guarantee 2 (always) | Failing | 2101 | 13 |
| a read-back after a cross-table write saw the same token in every slot | Guarantee 2 (always) | Passing | 331 | 0 |
| after faults stopped every logged-batch group holds the same token in every slot | Guarantee 2 (always) | Passing | 918 | 0 |
| after faults stopped every transactional group holds the same token in every slot | Guarantee 2 (always) | Failing | 914 | 20 |
| a cross-table write transaction ended with an unknown outcome | Guarantee 2 (reachable) | Passing | 633 | 0 |
| a conditional cross-table write was declined because another writer changed the group | Guarantee 2 (sometimes) | Passing | 314 | 915 |
| a cross-table read saw a group rewritten since this reader's previous read | Guarantee 2 (sometimes) | Passing | 173 | 2101 |
| a cross-table write of one token to four partitions was acknowledged | Guarantee 2 (sometimes) | Passing | 1053 | 1605 |
| a final check after faults stopped saw logged-batch groups written | Guarantee 2 (sometimes) | Passing | 106 | 813 |
| a final check after faults stopped saw transactional groups written | Guarantee 2 (sometimes) | Passing | 135 | 784 |
| a read-back found a write of unknown outcome applied to every slot of its group | Guarantee 2 (sometimes) | Passing | 79 | 285 |
| after faults stopped every acknowledged durable write is present with its value | Guarantee 3 (always) | Failing | 239 | 44 |
| an acknowledged durable write is visible with its value to the next read | Guarantee 3 (always) | Passing | 3639 | 0 |
| an acknowledged durable write sampled during the run is present with its value | Guarantee 3 (always) | Failing | 1276 | 110 |
| a conditional insert of a fresh id found no existing row for it | Guarantee 3 (always_or_unreachable) | Passing | 1529 | 0 |
| a durable write ended with an unknown outcome | Guarantee 3 (reachable) | Passing | 592 | 0 |
| a check during the run verified sampled acknowledged durable writes | Guarantee 3 (sometimes) | Passing | 1333 | 233 |
| a durable write transaction spanning three partitions was acknowledged | Guarantee 3 (sometimes) | Passing | 1353 | 1600 |
| a final check found a write of unknown outcome applied | Guarantee 3 (sometimes) | Passing | 154 | 164 |
| a final check verified acknowledged durable writes from the ledgers | Guarantee 3 (sometimes) | Passing | 275 | 35 |
| a final check verified acknowledged multi-partition durable writes in every partition | Guarantee 3 (sometimes) | Passing | 261 | 49 |
| an acknowledged durable write was read back through a different coordinator | Guarantee 3 (sometimes) | Passing | 3324 | 869 |
| a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one | Guarantee 4 (always) | Passing | 58 | 0 |
| a plain read of a published register sees at least the version acknowledged before the read started | Guarantee 4 (always) | Failing | 445 | 38 |
| a plain read on a full-mode table returns only versions that were written | Guarantee 4 (always) | Passing | 1935 | 0 |
| a plain read on a full-mode table returns the latest acknowledged write or a newer one | Guarantee 4 (always) | Failing | 1935 | 19 |
| one client's successive plain reads of a single-writer register never go backwards | Guarantee 4 (always) | Failing | 445 | 30 |
| a multi-key IN read of published registers completed | Guarantee 4 (reachable) | Passing | 157 | 0 |
| a plain write with an unknown outcome was later read back | Guarantee 4 (reachable) | Passing | 84 | 0 |
| a conditional single-statement write on a full-mode table was applied | Guarantee 4 (sometimes) | Passing | 1062 | 58 |
| a consistency-level ONE read right after an acknowledged plain write returned that write | Guarantee 4 (sometimes) | Passing | 1730 | 1902 |
| a plain read of a published register returned a version newer than its published floor | Guarantee 4 (sometimes) | Passing | 85 | 437 |
| a plain write was read back through a different coordinator than the one that acknowledged it | Guarantee 4 (sometimes) | Passing | 1777 | 1456 |
| a reader saw a published register advance between two of its plain reads | Guarantee 4 (sometimes) | Passing | 52 | 445 |
| a plain write and read on a transactional table succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Passing | 892 | 0 |
| a transaction succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Passing | 892 | 0 |
| every node coordinated a transaction within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 851 | 41 |
| a node coordinated a transaction after earlier attempts through it failed | Guarantee 5 (sometimes) | Passing | 542 | 816 |
| a transaction succeeded after the first attempt once faults stopped had failed | Guarantee 5 (sometimes) | Passing | 322 | 570 |
| the first transaction attempt once faults stopped succeeded | Guarantee 5 (sometimes) | Passing | 570 | 322 |
| container: cassandra-accord-node1, exit code: 3 | Antithesis default/setup (-) | Failing | 0 | 1 |
| container: cassandra-accord-node2, exit code: 134 | Antithesis default/setup (-) | Failing | 0 | 1 |
| container: cassandra-accord-node3, exit code: 3 | Antithesis default/setup (-) | Failing | 0 | 37 |
| java | Antithesis default/setup (-) | Failing | 0 | 1 |

111 properties reported; 21 not passing. Antithesis default properties not listed above are Passing.

## Failing: an acknowledged durable write sampled during the run is present with its value (Guarantee 3, 110 counterexamples)
- Moment: input_hash -6514846605191129539, vtime 278.8677. Log: scratchbook/logs/hunt1--6514846605191129539.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjc4Ljg2NzcwNjc3ODkyNDkifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiLTY1MTQ4NDY2MDUxOTExMjk1MzkifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiMWRlZDk4ODg2YmM5ZDRmZDU4NzYxN2JlNmQ0MjlkMTgtNjMtMTIifQ
- Timeline:
  - 127.93 setup_complete. 143.88 node2 graceful stop (clean shutdown, exit 143), restarted.
  - 138.8–212.7: every durable_writes writer in this history finishes. The last one is done at 212.69, and samples at 175.35, 175.55, 177.06 and 210.97 verify all of their rows (149/147/14/13 of 13).
  - 214.64 **node/kill node2** (exit 137). It restarts at 216.96. 221.60 node2 WARN `Stop marker is older than start marker (1791488031484<1791488110156) … Continuing to startup`. 249.45 node2 `ERROR Could not catchup with peers; continuing to startup`. 259.48 Startup complete.
  - 262.98 **node/kill node1** (exit 137). It restarts at 265.46. 268.49 node1 stop-marker WARN (`-1<…`, no safe marker ever written).
  - 278.14 two new writers start and their writes are acknowledged.
  - 278.8677 FAIL: plain (non-txn) reads via coordinators .12 (node2) and .13 (node3) find 18 acknowledged rows of partition 0 absent, then 7 of partition 1 and 11 of partition 0 again (three chunks, same moment). Some of the ops are single-partition `plain`/`txn`/`txn_cas` and some are multi-partition. `wrong={}` (absent, not stale).
- Kill before failure: yes. Every missing write was acknowledged ≤212.7, before node2's kill at 214.64. Both node2 (coordinator) and node1 restarted unsafely. node1 was mid-startup at the failure, so the read was served by node2 and/or node3.
- Several missing rows were acknowledged 60–75 s before the kill, far outside the 10 s periodic commitlog window. If node2 lost them, it lost more than the documented unsynced tail. This could also be the committed-rows-read-absent "rows read absent" mechanism on a node that restarted after a failed catch-up. Either way, a node that started with ALLOW_UNSAFE_STARTUP served the read.
- Class: suspect (unsafe-startup confound).

## Failing: after faults stopped every acknowledged durable write is present with its value (Guarantee 3, 44 counterexamples)
- Moment: input_hash -684858565517636670, vtime 307.3659. Log: scratchbook/logs/hunt1--684858565517636670.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzA3LjM2NTk0MDc5OTQ3MSJ9XSwibyI6Im9yIn0seyJoIjpbeyJjIjoibW9tZW50LmlucHV0X2hhc2giLCJmIjoiZ2VuZXJhbC5jdXN0b20iLCJvIjoibWF0Y2hlcyIsInYiOiItNjg0ODU4NTY1NTE3NjM2NjcwIn1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjFkZWQ5ODg4NmJjOWQ0ZmQ1ODc2MTdiZTZkNDI5ZDE4LTYzLTEyIn0
- Timeline:
  - 149.80 node1 graceful stop. 158.23 node3 graceful stop. 171.68 node1 `node/stop` ends with exit 137 (killed during shutdown).
  - 194.95 **kill node2**. 210.00 stop-marker WARN (`-1<…`). 226.09 **kill node2** again. 239.77 stop-marker WARN.
  - 260.81 **kill node3**. 271.31 node3 stop-marker WARN.
  - 284.46 eventually_durable_check starts. 288.21 node3 `node/stop` ends with exit 137, and node3 restarts with the stop-marker WARN at 294.99.
  - 290.20 first chunk passes. 307.3659 FAIL: rows of partitions 0 and 1 are missing via .11/.13 (plain reads).
- Kill before failure: yes. All three nodes restarted unclean before the check, and node3 restarted unsafely during it.
- Class: suspect (unsafe-startup confound).

## Failing: a plain read of a published register sees at least the version acknowledged before the read started / one client's successive plain reads of a single-writer register never go backwards (Guarantee 4, 38 / 30 counterexamples, same moment)
- Moment: input_hash -4017183637122572070, vtime 400.3295. Log: scratchbook/logs/hunt1--4017183637122572070.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNDAwLjMyOTUxMzg0MjcwNTY0In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii00MDE3MTgzNjM3MTIyNTcyMDcwIn1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjFkZWQ5ODg4NmJjOWQ0ZmQ1ODc2MTdiZTZkNDI5ZDE4LTYzLTEyIn0
- Details: key 3743953676013321700, published_floor 5, previous read 5 via .12 (node2). This read was a QUORUM plain read via **.13 (node3)** and returned `seen=null` (absent row). Other examples: CL ONE via node3, floor 4, seen null.
- Timeline:
  - Three node2 kills/restarts at 210–257 with stop-marker WARNs. 260.5 node1 stop ends with exit 137. 275.65 **kill node3** (stop-marker WARN 300.15). 297.3 node1 exit 137.
  - 331.4 node3 graceful stop. 351.3 node1 graceful stop.
  - 374.77 **kill node3**, restart 377.21. 383.42 node3 stop-marker WARN. 393.76 node3 Startup complete.
  - 389.03 node2 graceful stop and restart.
  - 400.3295 FAIL: node3 coordinated, 6.6 s after it finished an unsafe startup, while node2 was restarting.
- Related: "a plain read on a full-mode table returns the latest acknowledged write or a newer one" (19, first -6586953533457159301 @ 459.93, log not downloaded) fails only in this run. Guarantee 4 passes in hunt-2 (kills, no clock jumps) and hunt-4 (no kills). Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNDU5LjkzMzgxMDEwOTAzOTc3In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii02NTg2OTUzNTMzNDU3MTU5MzAxIn1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjFkZWQ5ODg4NmJjOWQ0ZmQ1ODc2MTdiZTZkNDI5ZDE4LTYzLTEyIn0
- Class: suspect (unsafe-startup confound). The symptom is a whole row absent (committed-rows-read-absent-shaped), not an older version.

## Failing: every node coordinated a transaction within 120 seconds after faults stopped (Guarantee 5, 41 counterexamples)
- Moment: input_hash -5994779628571608688, vtime 264.5290. Log: scratchbook/logs/hunt1--5994779628571608688.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjY0LjUyODk4NzM0ODU0NTM0In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii01OTk0Nzc5NjI4NTcxNjA4Njg4In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjFkZWQ5ODg4NmJjOWQ0ZmQ1ODc2MTdiZTZkNDI5ZDE4LTYzLTEyIn0
- Timeline:
  - 127.93 setup_complete. 130.30 **kill node3** (exit 137), restart 132.71.
  - 144.18 eventually_recovery_probe starts (faults stop). 144.99 node3 stop-marker WARN (`-1<1791488047425`). Journal replay finishes in under 1 s.
  - 153.29 node3 gossip settled. 153.30 `Catchup (NORMAL) with quorum...`. 157–191: most command stores report `caught-up`.
  - **rt_accounts** stores are still `remaining` at 254.99, and node3 never logs Startup complete.
  - 144–264: 40 probe attempts via node3, all `NoHostAvailable … Host has been marked down` (CQL not started). node1 and node2 succeed at 0.1 s.
  - 264.53 FAIL.
- Cause: node3 is blocked in Accord startup catch-up (`AccordService.catchup()`). The default `catchup_on_start_fail_latency` is **900 s** (AccordConfig.java:315), and this run logs `Catchup exceeded maximum latency of 900000000000ns; continuing to startup` 9 times (e.g. node1 @ 1179). The 120 s Guarantee 5 window is shorter than the SUT's own startup bound.
- Class: suspect (unsafe-startup confound + window shorter than the 900 s catch-up deadline). Compare hunt-2, where the same stall follows a *clean* restart.

## Failing: after faults stopped every transactional group holds the same token in every slot (Guarantee 2, 20 counterexamples)
- Moment: input_hash -8100350718065269108, vtime 1244.0413. The log is fetched from vtime 1100 ("Moment too deep" before that): scratchbook/logs/hunt1--8100350718065269108.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMTI0NC4wNDEzNDAwNjI2Mjc2In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii04MTAwMzUwNzE4MDY1MjY5MTA4In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjFkZWQ5ODg4NmJjOWQ0ZmQ1ODc2MTdiZTZkNDI5ZDE4LTYzLTEyIn0
- Details: coordinator .11 (node1), group 2: `pair_a:20=null, pair_a:21=null, pair_b:5020=pair_b:5021=28fceb1daba0d6c6-12…`. Both pair_a slots are absent, and the pair_b slots hold one token, so a whole table's rows for the group read as absent (committed-rows-read-absent shape). The same history fails "a conditional cross-table write read the same token in every slot of its group" at 1243.25.
- Timeline (from 1100):
  - JVM uptimes at 1100 show every node had already restarted (node1 72 s, node2 90 s, node3 167 s).
  - 1125.43 node1 `node/stop` ends with exit 137. 1130.68 node1 stop-marker WARN. 1144.98 node1 `Could not catchup with peers; continuing to startup`. 1151.40 Startup complete.
  - 1135.41 node2 stop ends with exit 137, and node2 restarts.
  - 1215.03 node2 graceful stop and restart.
  - 1243.25 conditional write FAIL. 1243.73 eventually_pair_check starts. 1244.04 FAIL via node1.
- Class: suspect (unsafe-startup confound): the coordinator node1 restarted unsafely and skipped a failed catch-up 100 s earlier.

## Failing defaults (not part of the brief, not investigated further)
- container: cassandra-accord-node3, exit code: 3 (37). node3 logs `Exception encountered during startup` at about 153.5 in many sibling timelines (the cause line was not captured by event search). node1 exit 3 (1) and node2 exit 134 (1, a JVM abort) look the same way. java (1) @ 173.34. Follow up with one log download if these recur.
