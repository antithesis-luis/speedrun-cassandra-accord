# iterate-1 · e4947374c51cfdaaffd0d6ff6ae5dc10-63-12 · current@e874e3a9 · completed · 30 m
Report: https://honey-whale.antithesis.com/report/xrIBSxLwAHWhRf49AROCTaMK/yWwNglWJp3ThXiESihRapRCIs7Pwz7ROGJpTVNx0uxU.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE1OjA4OjE1LjkyNDI3NDUzOFoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoieVd3TmdsV0pwM1RoWGlFU2loUmFwUkNJczdQd3o3Uk9HSnBUVk54MHV4VS5odG1sIiwicmVwb3J0X2lkIjoieHJJQlN4THdBSFdoUmY0OUFST0NUYU1LIn19fVe7MBHDdXkUUFSrjqed0PclvzX2NZKVJ5I8PaDlT0I1lpSuezQCi6_TaC8jVV1BULZeH7_RwR2JEBhNfVArCw4

session_id: 3499d4a0813af4531453233c579cf593-63-12

Run: completed 2026-10-08T16:08:16Z, antithesis v63-12, network faults only. setup_complete observed at vtime 205.245 (antithesis_setup event), test commands start at 205.32.
Summary: 6 of 12 Guarantee 1 Always properties fail; all 13 Guarantee 1 Sometimes/Reachable pass; 1 failure outside Guarantee 1 (Antithesis default "Customer output volume"). No unexpected container exits/crashes.

| Property | Guarantee | Status | Examples | Counterexamples |
|---|---|---|---|---|
| a private-slot transfer reads the markers acknowledged before it and none from later transfers | Guarantee 1 (always) | Passing | 384 | 0 |
| a read started after a transfer was acknowledged sees that transfer | Guarantee 1 (always) | Passing | 381 | 0 |
| a read-back of a private slot sees one consistent transfer state | Guarantee 1 (always) | Passing | 381 | 0 |
| a transfer reads balances within the bank total | Guarantee 1 (always) | Passing | 151 | 0 |
| a transfer reads every transfer acknowledged or observed before it started | Guarantee 1 (always) | Passing | 151 | 0 |
| a transfer transaction reads both of its accounts | Guarantee 1 (always) | Failing | 151 | 4 |
| an application-retried transfer reads both accounts with balances within the bank total | Guarantee 1 (always) | Passing | 377 | 0 |
| an application-retried transfer reads every transfer this client saw complete before it | Guarantee 1 (always) | Failing | 377 | 5 |
| an audit reflects every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 1257 | 7 |
| audited bank balances sum to the initial total | Guarantee 1 (always) | Failing | 1171 | 96 |
| audited transfer counters sum to an even number | Guarantee 1 (always) | Failing | 1197 | 73 |
| every seeded bank account is visible to an audit transaction | Guarantee 1 (always) | Failing | 1254 | 3 |
| no bank account balance is negative in an audit | Guarantee 1 (always) | Passing | 1255 | 0 |
| a transfer ended with an unknown outcome | Guarantee 1 (reachable) | Passing | 141 | 0 |
| a transfer whose outcome was unknown was later seen applied | Guarantee 1 (reachable) | Passing | 29 | 0 |
| a final audit after faults stopped saw committed transfers | Guarantee 1 (sometimes) | Passing | 117 | 227 |
| a private-slot transfer was declined for insufficient balance | Guarantee 1 (sometimes) | Passing | 362 | 388 |
| a transfer moved a source account's entire balance | Guarantee 1 (sometimes) | Passing | 6 | 151 |
| a transfer saw transfers committed by other clients since this client last looked | Guarantee 1 (sometimes) | Passing | 109 | 132 |
| a transfer was acknowledged after resubmitting an attempt whose outcome was unknown | Guarantee 1 (sometimes) | Passing | 134 | 377 |
| a transfer was declined because the source balance was too low | Guarantee 1 (sometimes) | Passing | 122 | 154 |
| a transfer's effect was read back through a different coordinator | Guarantee 1 (sometimes) | Passing | 387 | 102 |
| an audit completed while an earlier transfer's outcome was still unknown | Guarantee 1 (sometimes) | Passing | 29 | 130 |
| an audit saw a bank account drained to exactly zero | Guarantee 1 (sometimes) | Passing | 66 | 1230 |
| consecutive audits by one client observed newly committed transfers | Guarantee 1 (sometimes) | Passing | 146 | 256 |
| Cassandra node startup complete | setup/bootstrap (reachable) | Passing | 3 | 0 |
| All commands were started at least once | setup/bootstrap | Passing | 1 | 0 |
| All commands were run to completion at least once | setup/bootstrap | Passing | 1 | 0 |
| Containers joined the Antithesis network | setup/bootstrap | Passing | 4 | 0 |
| Customer output volume | Antithesis default | Failing | 0 | 1 |
| Guarantee 2 assertions (12 in assertion-map) | Guarantee 2 | not in this workload | - | - |
| Guarantee 3 assertions (15) | Guarantee 3 | not in this workload | - | - |
| Guarantee 4 assertions (12) | Guarantee 4 | not in this workload | - | - |
| Guarantee 5 assertions (0 in assertion-map) | Guarantee 5 | not in this workload | - | - |

Notes: for Sometimes rows, "Counterexamples" is the count of evaluations where the condition was false (normal). All other Antithesis default properties pass (Always: Peak memory usage 5585/0, No unexpected crashes, No unexpected container exits, SDK minimum versions Java 1.7.0 / Python 0.4.0, all 5 commands exit 0: anytime_bank_audit 349, eventually_bank_audit 354, bank_autoretry 555, bank_transfers 235, rt_marker 515).

## Failing: a transfer transaction reads both of its accounts
- moment: input_hash=4829813570422657959 vtime=276.45783647568896
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjc2LjQ1NzgzNjQ3NTY4ODk2In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjQ4Mjk4MTM1NzA0MjI2NTc5NTkifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiMzQ5OWQ0YTA4MTNhZjQ1MzE0NTMyMzNjNTc5Y2Y1OTMtNjMtMTIifQ
- log: antithesis/scratchbook/logs/iter1-4829813570422657959.ndjson
- timeline:
  - 205.245 setup_complete; 205.32 test composer starts bank_autoretry, bank_transfers, rt_marker, anytime/eventually audits.
  - 212.53 / 223.74 [client] audits pass; all 12 seeded rows present, accounts_b:105=1000 at 223.74.
  - 241.0–273.6 [fault_injector] continuous network partitions (Jammed/Slowed/Stopped) and clogs over all nodes.
  - 244.73, 264.63 [node2] ERROR AccordResult.java:204 Unexpected exception, java.lang.NullPointerException.
  - 260–273 [node1/2/3] repeated WARN ShardDurability "Failed to agree RX ... : null"; 267.43 [node2] GlobalDurability "Failed to fetch DurableBefore from 1 due to timeout".
  - 268.37 [client pid 51, bank_transfers] Reachable "a transfer ended with an unknown outcome": accounts_b:103 -> accounts_b:105 amount 100, WriteTimeout (txn [37,1791473435015443,178(KW),2], SERIAL).
  - 271.07 last fault before failure (partition node2 | rest, 3.1s); no active faults at the failing moment.
  - 276.46 [client pid 51] FAIL: transfer accounts_b:105 -> accounts:2 amount 17 via coordinator 10.89.0.2 returned dst row (balance 1061, xfers 1) but src accounts_b:105 balance=null, xfers=null; the client's floor for accounts_b:105 was 1 (it had previously seen a committed transfer on that row). A seeded row read back as absent inside an Accord transaction.
- details: {"amount":17,"coordinator":"10.89.0.2:9042","dst":"accounts:2","dst_balance":1061,"dst_xfers":1,"floor_dst":1,"floor_src":1,"src":"accounts_b:105","src_balance":null,"src_xfers":null,"guarantee":"Guarantee 1","property":"txn-strict-serializable"}

## Failing: an application-retried transfer reads every transfer this client saw complete before it
- moment: input_hash=-5709051635830128038 vtime=249.57678270735778
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjQ5LjU3Njc4MjcwNzM1Nzc4In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii01NzA5MDUxNjM1ODMwMTI4MDM4In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjM0OTlkNGEwODEzYWY0NTMxNDUzMjMzYzU3OWNmNTkzLTYzLTEyIn0
- log: antithesis/scratchbook/logs/iter1-m5709051635830128038.ndjson (downloaded at the same history's 249.5770385893993 moment, which covers this one)
- timeline:
  - 205.32 workload commands start; 214.9–224.9 [fault_injector] network partitions/clogs; last fault event in this history at 224.88 (Slowed partition, ~3s).
  - 230.18 [client pid 51, bank_autoretry] transfer accounts_b:103 -> accounts:3 amount 63 acked (reads 1000/0).
  - 241.13, 246.26 [node1, node3] CasWriteTimeoutException (1 of 2 responses); 241.26–247.36 nodes enact ReconfigureAccordFastPath{node=3, UNAVAILABLE}, epoch 38; 246.62/247.17 connection timeout/reset on node1/node3.
  - 243.35 [client pid 57] transfer accounts_b:100 -> accounts:0 amount 144 acked after 3 attempts (read 1000/0 -> writes b100=856 xfers1, a0=1144 xfers1).
  - 248.27 [client pid 57] transfer b100 -> a0 amount 13 acked; read b100=856 xfers1, a0=1144 xfers1 (144-transfer visible). Floor for b100 becomes 2.
  - 249.577 [client pid 57] FAIL: transfer b100 -> accounts:1 amount 100 reads b100 balance 987, xfers 1 (floor_src 2) - i.e. state equals "1000 minus 13", the 144 debit is gone.
  - 249.577 [client pid 51] audit (coordinator 10.89.0.3) fails sum (11938), even-counter (sum 5) and real-time checks in the same instant: a0=1013 xfers1, b100=987 xfers1, b105=1000 xfers0.
- details: {"amount":100,"attempts":1,"dst":"accounts:1","dst_balance":938,"dst_xfers":1,"floor_dst":0,"floor_src":2,"src":"accounts_b:100","src_balance":987,"src_xfers":1}

## Failing: an audit reflects every transfer acknowledged or observed before it started
- moment: input_hash=-5709051635830128038 vtime=249.5770385893993
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjQ5LjU3NzAzODU4OTM5OTMifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiLTU3MDkwNTE2MzU4MzAxMjgwMzgifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiMzQ5OWQ0YTA4MTNhZjQ1MzE0NTMyMzNjNTc5Y2Y1OTMtNjMtMTIifQ
- log: antithesis/scratchbook/logs/iter1-m5709051635830128038.ndjson
- timeline: same history as above. Key points:
  - 230.18 [client pid 51] acked transfers raise this process's floor for accounts_b:105 to 1 (an acked transfer that wrote b105.xfers=1).
  - 241–247 fast-path reconfiguration (node3 UNAVAILABLE, epoch 38), CAS write timeouts on node1/node3; no fault events after 224.88.
  - 249.577 [client pid 51, bank_autoretry audit via 10.89.0.3] FAIL: regressions {accounts_b:105: floor 1, seen 0}; total 11938, xfer sum 5 (odd). Audit started strictly after the ack, so this is a stale read.
- details: {"regressions":{"accounts_b:105":{"floor":1,"seen":0}},"total(balances)":11938,"balances":{"accounts:0":1013,"accounts:1":938,"accounts:2":1000,"accounts:3":1063,"accounts:4":1000,"accounts:5":1000,"accounts_b:100":987,"accounts_b:101":1000,"accounts_b:102":1000,"accounts_b:103":937,"accounts_b:104":1000,"accounts_b:105":1000},"coordinator":"10.89.0.3:9042","resubmitted_since_last_audit":0,"source":"bank_autoretry"}

## Failing: audited bank balances sum to the initial total
- moment: input_hash=3115707109627864019 vtime=238.69260995578952
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjM4LjY5MjYwOTk1NTc4OTUyIn1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjMxMTU3MDcxMDk2Mjc4NjQwMTkifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiMzQ5OWQ0YTA4MTNhZjQ1MzE0NTMyMzNjNTc5Y2Y1OTMtNjMtMTIifQ
- log: antithesis/scratchbook/logs/iter1-3115707109627864019.log (reused, previously reviewed; see false-positives.md iter-1)
- timeline:
  - 205.32 workload starts; 227.25–229.66 gossip DOWN/UP of 10.89.0.3 / 10.89.0.4.
  - 231.61 [fault_injector] partition Stopped ALL 2.6s; 235.71 clog Slowed node2/client/node3; 235.73 partition Slowed asymmetric; 237.49 partition Stopped ALL 2.6s.
  - 232.38, 237.61 [client bank_autoretry] transfers acked after resubmitting an attempt whose outcome was unknown.
  - 238.37 [node2] gossip: 10.89.0.4 is now UP.
  - 238.69 [client bank_autoretry audit] FAIL: total 11992 (a0=1222, a1=1162, b100=608, others 1000).
  - 238.81 a different client process via a different coordinator reads the same bad state (FAIL again), so the bad state is stored.
- details: total=11992, expected=12000 (per false-positives.md review of this moment; text log has no details field).

## Failing: audited transfer counters sum to an even number
- moment: input_hash=3115707109627864019 vtime=238.69263333454728
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjM4LjY5MjYzMzMzNDU0NzI4In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjMxMTU3MDcxMDk2Mjc4NjQwMTkifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiMzQ5OWQ0YTA4MTNhZjQ1MzE0NTMyMzNjNTc5Y2Y1OTMtNjMtMTIifQ
- log: antithesis/scratchbook/logs/iter1-3115707109627864019.log (reused)
- timeline: same audit as the balance-sum failure above (238.69, bank_autoretry audit, after the 231.6–240 partition/clog burst). xfers a0=5, a1=5, b100=5, others 0, sum 15 (odd). Every transfer adds +1 to both accounts in one transaction, so an odd sum means a partial apply, lost update, or non-snapshot read.
- details: xfer_sum=15 (a0=5, a1=5, b100=5).

## Failing: every seeded bank account is visible to an audit transaction
- moment: input_hash=-8841521013045425404 vtime=285.33246278832667
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjg1LjMzMjQ2Mjc4ODMyNjY3In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii04ODQxNTIxMDEzMDQ1NDI1NDA0In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjM0OTlkNGEwODEzYWY0NTMxNDUzMjMzYzU3OWNmNTkzLTYzLTEyIn0
- log: antithesis/scratchbook/logs/iter1-m8841521013045425404.ndjson
- timeline:
  - 252.67–281.43 [fault_injector] dense clogs/partitions (e.g. 262.63 client isolated, 264.10 node1 isolated, 268.65–278.14 repeated clogs over all nodes).
  - 270.42–272.60 [client bank_audit / bank_transfers] connect attempts fail NoHostAvailable (all coordinators OperationTimedOut).
  - 272.60 [node1] WARN Unknown exception in client networking with peer 10.89.0.5.
  - 281.26 [node1] gossip: 10.89.0.3 DOWN; 283.87 10.89.0.3 UP. 282.07 / 283.14 anytime_bank_audit commands finish rc=0.
  - 285.02 [client pid 96, bank_transfers] Reachable unknown outcome: accounts:1 -> accounts_b:100 amount 91, WriteTimeout (txn [37,1791473451089380,178(KW),3]).
  - 285.33 [client pid 116, bank_audit, audit_index 1, coordinator 10.89.0.3] FAIL: the 12-LET read-only audit transaction returned only 5 of 12 seeded rows; missing accounts:3 and all six accounts_b rows.
- details: {"audit_index":1,"balances":{"accounts:0":186,"accounts:1":1686,"accounts:2":943,"accounts:4":200,"accounts:5":1002},"coordinator":"10.89.0.3:9042","missing":["accounts:3","accounts_b:105","accounts_b:100","accounts_b:104","accounts_b:103","accounts_b:101","accounts_b:102"],"source":"bank_audit","xfers":{"accounts:0":10,"accounts:1":7,"accounts:2":4,"accounts:4":5,"accounts:5":1}}

## Failing: Customer output volume (Antithesis default)
- moment: none (telemetry property; no log)
- details: {"session_id":"3499d4a0813af4531453233c579cf593-63-12","total_output_mb":7920.93,"total_test_hours":24.30,"total_output_rate":325.9 MB/test-hour}. Output volume is above the threshold; nodes log at DEBUG (AccordCommandStore, ShardDurability RX warnings) - a harness/logging concern, not a Guarantee 1 result.

## Sometimes not hit: none
All 11 Guarantee 1 Sometimes and 2 Guarantee 1 Reachable assertions were hit (lowest: "a transfer moved a source account's entire balance" 6 hits; "a transfer whose outcome was unknown was later seen applied" 29; "an audit completed while an earlier transfer's outcome was still unknown" 29).
