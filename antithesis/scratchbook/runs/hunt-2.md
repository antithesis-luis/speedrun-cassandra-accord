# hunt-2 · a0534fbf86e5081d495f8d15d9ccf329-63-12 · current@e874e3a9 · completed · 300 m
Report: https://honey-whale.antithesis.com/report/Yrr8xPIhKvFwB5cxwbUjo71N/Tm3uCc675KWtl0XjMrwy-dUm6jzy_CBpF7n9t6Abiac.html?auth=v2.public.eyJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiVG0zdUNjNjc1S1d0bDBYak1yd3ktZFVtNmp6eV9DQnBGN245dDZBYmlhYy5odG1sIiwicmVwb3J0X2lkIjoiWXJyOHhQSWhLdkZ3QjVjeHdiVWpvNzFOIn19LCJuYmYiOiIyMDI2LTEwLTA5VDAwOjUxOjEzLjYzNDE5NjA3NloifVZ8QpGpm__rQ6n-dlgWEtEZ7XGKnMDfCqEmwwxwDmgxYqPfOKeW-AW2lt_3S8p9YYsaHUvE6MqbNI69FpADSwI

Run: workload 63f7cc96e480, static IPs, multi-seed on restart, turbo. Full faults **without clock jumps** (network, pause, throttle, node kill/stop + restart). Created 2026-10-08T19:29:06Z, completed 2026-10-09T01:51:14Z, v63-12. Same SUT overrides as hunt-1 (ALLOW_UNSAFE_STARTUP, periodic commitlog, PERIODIC journal).

Summary: the Guarantee 2 read-back and the two Guarantee 3 failures come after unclean (SIGKILL) restarts, with the restarted node coordinating or serving the read, so they are `suspect (unsafe-startup confound)`. **Guarantee 5 is different.** Its first counterexample follows a single *graceful* stop of node1: clean shutdown, `Written safe replay markers`, no stop-marker warning on restart, and no other node faults. node1 then sits in Accord startup catch-up for the accounts/accounts_b command stores for more than 100 s on an otherwise quiet cluster, and never opens CQL within the 120 s window. Guarantee 4 passes in this run.

| Property | Guarantee (type) | Status | Examples | Counterexamples |
|---|---|---|---|---|
| a private-slot transfer reads the markers acknowledged before it and none from later transfers | Guarantee 1 (always) | Failing | 2271 | 19 |
| a read started after a transfer was acknowledged sees that transfer | Guarantee 1 (always) | Failing | 2257 | 21 |
| a read-back of a private slot sees one consistent transfer state | Guarantee 1 (always) | Passing | 2257 | 0 |
| a transfer reads balances within the bank total | Guarantee 1 (always) | Passing | 1263 | 0 |
| a transfer reads every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 1263 | 21 |
| a transfer transaction reads both of its accounts | Guarantee 1 (always) | Passing | 1263 | 0 |
| an application-retried transfer reads both accounts with balances within the bank total | Guarantee 1 (always) | Passing | 1402 | 0 |
| an application-retried transfer reads every transfer this client saw complete before it | Guarantee 1 (always) | Failing | 1402 | 22 |
| an audit reflects every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 4819 | 67 |
| audited bank balances sum to the initial total | Guarantee 1 (always) | Failing | 4663 | 220 |
| audited transfer counters sum to an even number | Guarantee 1 (always) | Failing | 4752 | 132 |
| every seeded bank account is visible to an audit transaction | Guarantee 1 (always) | Failing | 4813 | 24 |
| no bank account balance is negative in an audit | Guarantee 1 (always) | Passing | 4819 | 0 |
| a transfer ended with an unknown outcome | Guarantee 1 (reachable) | Passing | 528 | 0 |
| a transfer whose outcome was unknown was later seen applied | Guarantee 1 (reachable) | Passing | 111 | 0 |
| a final audit after faults stopped saw committed transfers | Guarantee 1 (sometimes) | Passing | 210 | 455 |
| a private-slot transfer was declined for insufficient balance | Guarantee 1 (sometimes) | Passing | 2118 | 2178 |
| a transfer moved a source account's entire balance | Guarantee 1 (sometimes) | Passing | 60 | 1263 |
| a transfer saw transfers committed by other clients since this client last looked | Guarantee 1 (sometimes) | Passing | 932 | 1162 |
| a transfer was acknowledged after resubmitting an attempt whose outcome was unknown | Guarantee 1 (sometimes) | Passing | 323 | 1413 |
| a transfer was declined because the source balance was too low | Guarantee 1 (sometimes) | Passing | 1042 | 1261 |
| a transfer's effect was read back through a different coordinator | Guarantee 1 (sometimes) | Passing | 1805 | 869 |
| an audit completed while an earlier transfer's outcome was still unknown | Guarantee 1 (sometimes) | Passing | 223 | 1133 |
| an audit saw a bank account drained to exactly zero | Guarantee 1 (sometimes) | Passing | 218 | 4732 |
| consecutive audits by one client observed newly committed transfers | Guarantee 1 (sometimes) | Passing | 449 | 1427 |
| a conditional cross-table write read the same token in every slot of its group | Guarantee 2 (always) | Failing | 1158 | 16 |
| a cross-table read transaction saw the same token in every slot of a group | Guarantee 2 (always) | Failing | 1663 | 21 |
| a read-back after a cross-table write saw the same token in every slot | Guarantee 2 (always) | Failing | 313 | 12 |
| after faults stopped every logged-batch group holds the same token in every slot | Guarantee 2 (always) | Passing | 585 | 0 |
| after faults stopped every transactional group holds the same token in every slot | Guarantee 2 (always) | Passing | 585 | 0 |
| a cross-table write transaction ended with an unknown outcome | Guarantee 2 (reachable) | Passing | 475 | 0 |
| a conditional cross-table write was declined because another writer changed the group | Guarantee 2 (sometimes) | Passing | 261 | 698 |
| a cross-table read saw a group rewritten since this reader's previous read | Guarantee 2 (sometimes) | Passing | 147 | 1663 |
| a cross-table write of one token to four partitions was acknowledged | Guarantee 2 (sometimes) | Passing | 787 | 1187 |
| a final check after faults stopped saw logged-batch groups written | Guarantee 2 (sometimes) | Passing | 44 | 541 |
| a final check after faults stopped saw transactional groups written | Guarantee 2 (sometimes) | Passing | 81 | 504 |
| a read-back found a write of unknown outcome applied to every slot of its group | Guarantee 2 (sometimes) | Passing | 64 | 282 |
| after faults stopped every acknowledged durable write is present with its value | Guarantee 3 (always) | Failing | 165 | 24 |
| an acknowledged durable write is visible with its value to the next read | Guarantee 3 (always) | Passing | 1707 | 0 |
| an acknowledged durable write sampled during the run is present with its value | Guarantee 3 (always) | Failing | 537 | 37 |
| a conditional insert of a fresh id found no existing row for it | Guarantee 3 (always_or_unreachable) | Passing | 1102 | 0 |
| a durable write ended with an unknown outcome | Guarantee 3 (reachable) | Passing | 457 | 0 |
| a check during the run verified sampled acknowledged durable writes | Guarantee 3 (sometimes) | Passing | 587 | 68 |
| a durable write transaction spanning three partitions was acknowledged | Guarantee 3 (sometimes) | Passing | 929 | 1129 |
| a final check found a write of unknown outcome applied | Guarantee 3 (sometimes) | Passing | 64 | 136 |
| a final check verified acknowledged durable writes from the ledgers | Guarantee 3 (sometimes) | Passing | 185 | 13 |
| a final check verified acknowledged multi-partition durable writes in every partition | Guarantee 3 (sometimes) | Passing | 169 | 29 |
| an acknowledged durable write was read back through a different coordinator | Guarantee 3 (sometimes) | Passing | 1661 | 484 |
| a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one | Guarantee 4 (always) | Passing | 27 | 0 |
| a plain read of a published register sees at least the version acknowledged before the read started | Guarantee 4 (always) | Passing | 156 | 0 |
| a plain read on a full-mode table returns only versions that were written | Guarantee 4 (always) | Passing | 928 | 0 |
| a plain read on a full-mode table returns the latest acknowledged write or a newer one | Guarantee 4 (always) | Passing | 928 | 0 |
| one client's successive plain reads of a single-writer register never go backwards | Guarantee 4 (always) | Passing | 156 | 0 |
| a multi-key IN read of published registers completed | Guarantee 4 (reachable) | Passing | 39 | 0 |
| a plain write with an unknown outcome was later read back | Guarantee 4 (reachable) | Passing | 26 | 0 |
| a conditional single-statement write on a full-mode table was applied | Guarantee 4 (sometimes) | Passing | 525 | 27 |
| a consistency-level ONE read right after an acknowledged plain write returned that write | Guarantee 4 (sometimes) | Passing | 876 | 915 |
| a plain read of a published register returned a version newer than its published floor | Guarantee 4 (sometimes) | Passing | 38 | 152 |
| a plain write was read back through a different coordinator than the one that acknowledged it | Guarantee 4 (sometimes) | Passing | 808 | 738 |
| a reader saw a published register advance between two of its plain reads | Guarantee 4 (sometimes) | Passing | 44 | 156 |
| a plain write and read on a transactional table succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Passing | 577 | 0 |
| a transaction succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Passing | 577 | 0 |
| every node coordinated a transaction within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 539 | 38 |
| a node coordinated a transaction after earlier attempts through it failed | Guarantee 5 (sometimes) | Passing | 311 | 542 |
| a transaction succeeded after the first attempt once faults stopped had failed | Guarantee 5 (sometimes) | Passing | 223 | 354 |
| the first transaction attempt once faults stopped succeeded | Guarantee 5 (sometimes) | Passing | 354 | 223 |
| Customer output volume | Antithesis default/setup (-) | Failing | 0 | 1 |
| container: cassandra-accord-node3, exit code: 3 | Antithesis default/setup (-) | Failing | 0 | 1 |

109 properties reported; 16 not passing. Antithesis default properties not listed above are Passing.

## Failing: every node coordinated a transaction within 120 seconds after faults stopped (Guarantee 5, 38 counterexamples)
- Moment: input_hash -7253961278733688370, vtime 267.8125. Log: scratchbook/logs/hunt2--7253961278733688370.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjY3LjgxMjUyOTkxMzg0ODI3In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii03MjUzOTYxMjc4NzMzNjg4MzcwIn1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjBiYTM1NTgwYThjMzZkYjQ0OTE3NTJkYjRjNjc1MTM1LTYzLTEyIn0
- Timeline:
  - 134.40 setup_complete. Faults before the probe: network only (134.56 restore). **No kill, stop, pause or throttle before 147.**
  - 145.99–148.11 node1 orderly shutdown: `Stopping Accord` → `Written safe replay markers` → `Accord Shutdown` → `Cassandra shutdown complete`.
  - 147.67 eventually_recovery_probe starts. 148.51 `node/stop node1` is logged, exit 143 at 148.96, restart at 150.96. This is the only node fault in the history.
  - 154.15 node1 journal replay finishes in 0.06 s, with **no** stop-marker WARN (safe startup).
  - 162.41 `Catchup (NORMAL) with quorum...`. By 168.12 every store is `fully caught-up` (durable, fm_reg, kv, ledger, pair_a, pair_b, rt_accounts) **except accounts (tid:1a) and accounts_b (tid:1b)**.
  - Last accounts progress line is at 170.08. No WARN or ERROR from node1 after that, and no Startup complete before the failure.
  - 147.7–267.8: 40 probe attempts via node1, all `NoHostAvailable … marked down`. node2 and node3 succeed at once.
  - 267.81 FAIL.
- Assessment: this is not kill-dependent. The restart was clean, and ALLOW_UNSAFE_STARTUP was not exercised. Catch-up blocks startup until `catchup_on_start_fail_latency` (default 900 s, AccordConfig.java:315), and hunt-1 shows it reaching that limit. So by the SUT's own configuration a restarting node may legitimately stay unavailable up to 15 min, and the Guarantee 5 120 s window is stricter than that (checklist 3, timeout tighter than the SUT's bound). The stores that never catch up are the two bank tables, where acked-transfer-overwritten/committed-rows-read-absent activity is concentrated. That makes it a credible liveness lead: catch-up on a clean restart does not converge for some stores.
- Class: suspect (not kill-dependent; probe window 120 s < 900 s default catch-up deadline). To tighten, log the catch-up state and lengthen the window, or assert "a clean restart finishes startup within catchup_on_start_fail_latency".

## Failing: a read-back after a cross-table write saw the same token in every slot (Guarantee 2, 12 counterexamples)
- Moment: input_hash 351202264714247094, vtime 709.5286. Log: scratchbook/logs/hunt2-351202264714247094.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNzA5LjUyODU1NTI4NDQ4NzEifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzUxMjAyMjY0NzE0MjQ3MDk0In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjBiYTM1NTgwYThjMzZkYjQ0OTE3NTJkYjRjNjc1MTM1LTYzLTEyIn0
- Details: coordinator .12 (node2), group 1: `pair_a:10=pair_a:11=fb50162672852c9-27…`, `pair_b:5010=null`. The unknown writes being read back were `15058a4e68b19a8a-4x`, `-5`. One table's slot is absent and the other table's slots agree, the same committed-rows-read-absent shape as hunt-4.
- Timeline: 196.48 **kill node2** (stop-marker WARN 204.77). After that there are kills or exit-137 stops of every node: node2 at 281.8, 432, 551, 599.8; node1 at 354.8, 444.8, 485.9, 510.8, 608.1; node3 at 216.1, 441.9, 653.7. Stop-marker WARNs for node2 at 299.66, 451.98, 574.56 and 608.19. node2 `Could not catchup with peers; continuing to startup` 616.89, Startup complete 618.24. 653.67 kill node3, Startup complete 679.79. 709.53 FAIL via node2.
- Class: suspect (unsafe-startup confound): the coordinator node2 had repeated unsafe startups and a failed catch-up 90 s earlier.

## Failing: an acknowledged durable write sampled during the run is present with its value (Guarantee 3, 37 counterexamples)
- Moment: input_hash -4681640254575183705, vtime 423.6731. Log: scratchbook/logs/hunt2--4681640254575183705.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNDIzLjY3MzExMzAyOTY4MyJ9XSwibyI6Im9yIn0seyJoIjpbeyJjIjoibW9tZW50LmlucHV0X2hhc2giLCJmIjoiZ2VuZXJhbC5jdXN0b20iLCJvIjoibWF0Y2hlcyIsInYiOiItNDY4MTY0MDI1NDU3NTE4MzcwNSJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiIwYmEzNTU4MGE4YzM2ZGI0NDkxNzUyZGI0YzY3NTEzNS02My0xMiJ9
- Details: plain read via .11 (node1). `1:6389436302485321765` (a txn_cas over ks [17,1,7]) is missing. A sibling at 424.55 also misses rows in partitions 6, 7, 10, 17 and 20.
- Timeline: samples at 193.64, 200.58, 215.79 and 236.55 verify everything they read. Kills: node2 179.35, node3 230.68 and 260.25 (each followed by a stop-marker WARN), node1 338.8 (exit 137), node2 343.6 (exit 137), node3 364.31 (WARN 378.09), node1 385.23 (exit 137, WARN 394.23). 423.67 FAIL via node1, 29 s after its unsafe startup.
- Class: suspect (unsafe-startup confound).

## Failing: after faults stopped every acknowledged durable write is present with its value (Guarantee 3, 24 counterexamples)
- Moment: input_hash -1097305872963186429, vtime 447.0635. Log not downloaded (10-download cap). Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNDQ3LjA2MzQ3OTQ3MzExNTkifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiLTEwOTczMDU4NzI5NjMxODY0MjkifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiMGJhMzU1ODBhOGMzNmRiNDQ5MTc1MmRiNGM2NzUxMzUtNjMtMTIifQ
- Details: txn reads via .11/.13. 8 rows of partitions 0 and 1 are missing (txn, txn_cas and plain ops), wrong={}.
- Class: suspect (unsafe-startup confound). Reasons: same run and same family as the sample failure above, every downloaded hunt-2 history has unsafe restarts before 300, and **Guarantee 3 never fails in hunt-4 (no kills)**. This is not verified for this exact history.

## Other failing assertions
- Guarantee 1 (bank, rt_marker) and the Guarantee 2 in-transaction checks ("a conditional cross-table write…", "a cross-table read transaction…") have the known acked-transfer-overwritten/committed-rows-read-absent signatures (see rca/acked-transfer-overwritten.md, rca/committed-rows-read-absent.md). Not re-investigated.
- container: cassandra-accord-node3, exit code: 3 (1) @ 157.46; node2 also logs `Exception encountered during startup` @ 642.37. Default property, not investigated.
- Customer output volume (1): default, not investigated.
