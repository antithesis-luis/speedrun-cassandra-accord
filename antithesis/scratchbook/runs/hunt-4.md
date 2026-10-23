# hunt-4 · 1d499fea4f9ce6971e413c613736faf2-63-12 · current@e874e3a9 · completed · 300 m
Report: https://honey-whale.antithesis.com/report/fsuUPPeUhgYCGq2LvZsJZ8d_/h5mxMMzBbn64mgpOwAlUeWFw6Qz1sXSt8CC8So_UiDc.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA5VDAwOjI0OjQ4LjM2MjY1ODEyM1oiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiaDVteE1NekJibjY0bWdwT3dBbFVlV0Z3NlF6MXNYU3Q4Q0M4U29fVWlEYy5odG1sIiwicmVwb3J0X2lkIjoiZnN1VVBQZVVoZ1lDR3EyTHZac0paOGRfIn19fXf3jvb122sZ-4y4nVBJTQcerBZo0DCvMeEV-7gJtIAYrllzdzZWaLw_Uw6xtClTY5HNIBY2xT7uaSGhz2pQEgc

Run: workload 63f7cc96e480, static IPs, turbo. Faults: network (partition/clog), node pause, CPU throttle. **No node kills or stops, no clock jumps.** Created 2026-10-08T19:29:24Z, completed 2026-10-09T01:24:49Z, v63-12.

Summary: Guarantee 3, Guarantee 4 and Guarantee 5 all pass. Their failures in hunt-1/hunt-2 only happen when node kills and restarts are present. Guarantee 2 fails in four Always properties: read-back 31, final check 33, in-transaction CAS read 26, cross-table read 41. In both examined histories the symptom is a **pair_b row read as absent while the group's pair_a slots hold a token**. That is a committed row read as missing, the committed-rows-read-absent signature ("committed rows read absent"). It is not a mix of two different non-null tokens, so there is no evidence of a partially applied write. No node restarted, so ALLOW_UNSAFE_STARTUP cannot be involved.

| Property | Guarantee (type) | Status | Examples | Counterexamples |
|---|---|---|---|---|
| a private-slot transfer reads the markers acknowledged before it and none from later transfers | Guarantee 1 (always) | Failing | 5905 | 37 |
| a read started after a transfer was acknowledged sees that transfer | Guarantee 1 (always) | Failing | 6053 | 29 |
| a read-back of a private slot sees one consistent transfer state | Guarantee 1 (always) | Passing | 6053 | 0 |
| a transfer reads balances within the bank total | Guarantee 1 (always) | Passing | 4133 | 0 |
| a transfer reads every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 4133 | 28 |
| a transfer transaction reads both of its accounts | Guarantee 1 (always) | Failing | 4133 | 38 |
| an application-retried transfer reads both accounts with balances within the bank total | Guarantee 1 (always) | Failing | 4618 | 28 |
| an application-retried transfer reads every transfer this client saw complete before it | Guarantee 1 (always) | Passing | 4618 | 0 |
| an audit reflects every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 16645 | 75 |
| audited bank balances sum to the initial total | Guarantee 1 (always) | Failing | 15301 | 1747 |
| audited transfer counters sum to an even number | Guarantee 1 (always) | Failing | 15683 | 1350 |
| every seeded bank account is visible to an audit transaction | Guarantee 1 (always) | Failing | 16597 | 44 |
| no bank account balance is negative in an audit | Guarantee 1 (always) | Passing | 16596 | 0 |
| a transfer ended with an unknown outcome | Guarantee 1 (reachable) | Passing | 1771 | 0 |
| a transfer whose outcome was unknown was later seen applied | Guarantee 1 (reachable) | Passing | 792 | 0 |
| a final audit after faults stopped saw committed transfers | Guarantee 1 (sometimes) | Passing | 509 | 1216 |
| a private-slot transfer was declined for insufficient balance | Guarantee 1 (sometimes) | Passing | 5926 | 5742 |
| a transfer moved a source account's entire balance | Guarantee 1 (sometimes) | Passing | 198 | 4127 |
| a transfer saw transfers committed by other clients since this client last looked | Guarantee 1 (sometimes) | Passing | 3387 | 3756 |
| a transfer was acknowledged after resubmitting an attempt whose outcome was unknown | Guarantee 1 (sometimes) | Passing | 1253 | 4670 |
| a transfer was declined because the source balance was too low | Guarantee 1 (sometimes) | Passing | 3488 | 4150 |
| a transfer's effect was read back through a different coordinator | Guarantee 1 (sometimes) | Passing | 5971 | 1977 |
| an audit completed while an earlier transfer's outcome was still unknown | Guarantee 1 (sometimes) | Passing | 1101 | 3698 |
| an audit saw a bank account drained to exactly zero | Guarantee 1 (sometimes) | Passing | 768 | 16373 |
| consecutive audits by one client observed newly committed transfers | Guarantee 1 (sometimes) | Passing | 2106 | 5945 |
| a conditional cross-table write read the same token in every slot of its group | Guarantee 2 (always) | Failing | 5210 | 26 |
| a cross-table read transaction saw the same token in every slot of a group | Guarantee 2 (always) | Failing | 3572 | 41 |
| a read-back after a cross-table write saw the same token in every slot | Guarantee 2 (always) | Failing | 2584 | 31 |
| after faults stopped every logged-batch group holds the same token in every slot | Guarantee 2 (always) | Passing | 1759 | 0 |
| after faults stopped every transactional group holds the same token in every slot | Guarantee 2 (always) | Failing | 1758 | 33 |
| a cross-table write transaction ended with an unknown outcome | Guarantee 2 (reachable) | Passing | 2112 | 0 |
| a conditional cross-table write was declined because another writer changed the group | Guarantee 2 (sometimes) | Passing | 2441 | 3304 |
| a cross-table read saw a group rewritten since this reader's previous read | Guarantee 2 (sometimes) | Passing | 607 | 3572 |
| a cross-table write of one token to four partitions was acknowledged | Guarantee 2 (sometimes) | Passing | 3718 | 5535 |
| a final check after faults stopped saw logged-batch groups written | Guarantee 2 (sometimes) | Passing | 294 | 1469 |
| a final check after faults stopped saw transactional groups written | Guarantee 2 (sometimes) | Passing | 383 | 1380 |
| a read-back found a write of unknown outcome applied to every slot of its group | Guarantee 2 (sometimes) | Passing | 609 | 2430 |
| after faults stopped every acknowledged durable write is present with its value | Guarantee 3 (always) | Passing | 536 | 0 |
| an acknowledged durable write is visible with its value to the next read | Guarantee 3 (always) | Passing | 4615 | 0 |
| an acknowledged durable write sampled during the run is present with its value | Guarantee 3 (always) | Passing | 2423 | 0 |
| a conditional insert of a fresh id found no existing row for it | Guarantee 3 (always_or_unreachable) | Passing | 5397 | 0 |
| a durable write ended with an unknown outcome | Guarantee 3 (reachable) | Passing | 1767 | 0 |
| a check during the run verified sampled acknowledged durable writes | Guarantee 3 (sometimes) | Passing | 2385 | 86 |
| a durable write transaction spanning three partitions was acknowledged | Guarantee 3 (sometimes) | Passing | 4826 | 5565 |
| a final check found a write of unknown outcome applied | Guarantee 3 (sometimes) | Passing | 305 | 309 |
| a final check verified acknowledged durable writes from the ledgers | Guarantee 3 (sometimes) | Passing | 596 | 14 |
| a final check verified acknowledged multi-partition durable writes in every partition | Guarantee 3 (sometimes) | Passing | 544 | 66 |
| an acknowledged durable write was read back through a different coordinator | Guarantee 3 (sometimes) | Passing | 4607 | 759 |
| a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one | Guarantee 4 (always) | Passing | 202 | 0 |
| a plain read of a published register sees at least the version acknowledged before the read started | Guarantee 4 (always) | Passing | 1020 | 0 |
| a plain read on a full-mode table returns only versions that were written | Guarantee 4 (always) | Passing | 5652 | 0 |
| a plain read on a full-mode table returns the latest acknowledged write or a newer one | Guarantee 4 (always) | Passing | 5652 | 0 |
| one client's successive plain reads of a single-writer register never go backwards | Guarantee 4 (always) | Passing | 1020 | 0 |
| a multi-key IN read of published registers completed | Guarantee 4 (reachable) | Passing | 396 | 0 |
| a plain write with an unknown outcome was later read back | Guarantee 4 (reachable) | Passing | 434 | 0 |
| a conditional single-statement write on a full-mode table was applied | Guarantee 4 (sometimes) | Passing | 3281 | 202 |
| a consistency-level ONE read right after an acknowledged plain write returned that write | Guarantee 4 (sometimes) | Passing | 5239 | 5615 |
| a plain read of a published register returned a version newer than its published floor | Guarantee 4 (sometimes) | Passing | 172 | 1005 |
| a plain write was read back through a different coordinator than the one that acknowledged it | Guarantee 4 (sometimes) | Passing | 5602 | 4198 |
| a reader saw a published register advance between two of its plain reads | Guarantee 4 (sometimes) | Passing | 154 | 1020 |
| a plain write and read on a transactional table succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Passing | 1759 | 0 |
| a transaction succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Passing | 1759 | 0 |
| every node coordinated a transaction within 120 seconds after faults stopped | Guarantee 5 (always) | Passing | 1759 | 0 |
| a node coordinated a transaction after earlier attempts through it failed | Guarantee 5 (sometimes) | Passing | 517 | 1752 |
| a transaction succeeded after the first attempt once faults stopped had failed | Guarantee 5 (sometimes) | Passing | 368 | 1391 |
| the first transaction attempt once faults stopped succeeded | Guarantee 5 (sometimes) | Passing | 1391 | 368 |
| Orchestrator backend command fails | Antithesis default/setup (-) | Failing | 0 | 1 |
| container: antithesis-orchestrator-1, exit code: 1 | Antithesis default/setup (-) | Failing | 0 | 1 |

109 properties reported; 15 not passing. Antithesis default properties not listed above are Passing.

## Failing: a read-back after a cross-table write saw the same token in every slot (Guarantee 2, 31 counterexamples)
- Moment: input_hash 4577676815520121205, vtime 332.8363. Log: scratchbook/logs/hunt4-4577676815520121205.log (+ events in scratchbook/logs/ev/h4-readback.ndjson). Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzMyLjgzNjI3MjIzMTc2ODgifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNDU3NzY3NjgxNTUyMDEyMTIwNSJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiI0YWM1MmE2OWNjZmY4MDk2Y2ZjZmY3NmYyOTJhMGIwZi02My0xMiJ9
- Timeline:
  - 54/87/118 nodes start, once only. 207.50 setup_complete.
  - Faults in this history: network clog/partition (22+13), 3 node/pause, 14 node/throttle. **No kill, stop or restart.**
  - 309.17 group 0 CAS declined. It saw `pair_a:0 = pair_b:5000 = 59205f61ae1b88b9-3x`, so both tables answer reads normally.
  - 317.83 read-back of group 1 finds `pair_a:10 = pair_a:11 = pair_b:5010 = 5cce3941c44057d7-6x` (all three slots, consistent).
  - 330.28 a pair_writes driver finishes with 4 ambiguous writes.
  - 332.7808 FAIL "a conditional cross-table write read the same token in every slot of its group" via **.13 (node3)**, writer 5cce…, expected `-6x`: `pair_a:10=pair_a:11=5cce…-6x`, `pair_b:5010=null`.
  - 332.8363 FAIL read-back via node3, group 1: `pair_a:10=pair_a:11=630b4874a6da026d-9x`, `pair_b:5010=null`. The unknown write being read back was `25873aef5e5650ee-6`.
- Analysis: pair_b:5010 held a token at 317.83. Nothing deletes rows, sets a TTL or writes null, and every write puts one token into every slot of the group. So `null` at 332.78 and 332.84 means a row that exists was read as absent through node3, while pair_a moved on normally (`-6x` → `630b…-9x`). This is the committed-rows-read-absent mechanism (rows of one table / CommandStore read as absent), not a partially applied transaction: the unknown writes `25873aef…-6` and `5cce…` do not appear partially.
- Class: real, committed-rows-read-absent family (already reported). Not kill-dependent. Not a new mechanism.

## Failing: after faults stopped every transactional group holds the same token in every slot (Guarantee 2, 33 counterexamples)
- Moment: input_hash 8156848711228608486, vtime 316.4562. Log: scratchbook/logs/hunt4-8156848711228608486.log (+ scratchbook/logs/ev/h4-final.ndjson). Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzE2LjQ1NjIyNjk5NTkxMzMifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiODE1Njg0ODcxMTIyODYwODQ4NiJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiI0YWM1MmE2OWNjZmY4MDk2Y2ZjZmY3NmYyOTJhMGIwZi02My0xMiJ9
- Timeline:
  - No kills, stops or clock faults, only network, pause and throttle.
  - 309.17–311.6 group writes acknowledged (groups 0, 1, 4, 5). In the read-back history above (4577676815520121205), a CAS at 309.17 saw group 0 = `59205f61ae1b88b9-3x` in both slots, and a read-back at 330.34 saw `59205f61…-5x` in both.
  - 313.58 eventually_pair_check starts, and the composer **cancels running parallel_driver_pair_writes drivers** (pids 8122, 8216, 8292, 8390).
  - 316.4562 FAIL via .12 (node2): group 0 `pair_a:0=630b4874a6da026d-2`, `pair_b:5000=null`.
- Analysis: the driver cancellations only make some writes ambiguous. An ambiguous write is all or nothing, and pair_b:5000 already held a token (seen in the sibling history; every acknowledged group-0 write in this one writes both slots), so `null` is again a present row read as absent (committed-rows-read-absent). It is the same writer family (630b…) and the same table (pair_b) as the read-back failure.
- Class: real, committed-rows-read-absent family (already reported). Not kill-dependent.

## Other failing assertions
- Guarantee 1 (bank, rt_marker): known acked-transfer-overwritten/committed-rows-read-absent signatures, not re-investigated.
- Guarantee 2 "a conditional cross-table write read the same token in every slot of its group" (26, first -7650925368450143626 @ 332.68) and "a cross-table read transaction saw the same token in every slot of a group" (41, first -8516562408643639056 @ 519.97): the same committed-rows-read-absent shape (see 332.78 above).
- Orchestrator backend command fails (1) / container: antithesis-orchestrator-1, exit code: 1 (1) @ about 40.6: Antithesis platform orchestrator, before setup_complete. Not SUT and not harness. Recurring-warning candidate if it repeats.
