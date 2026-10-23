# iterate-3 · 126cbacda11c1e49afda49c425a00f31-63-12 · current@e874e3a9 (6.0-alpha2 + Accord), workload 772c2f7e081f · completed · 30 m
Report: https://honey-whale.antithesis.com/report/zmTGhQqT5crjapLTREVHyQo1/n3y3NkFh_T7O71fouh6SAB89DacwGkLqFUeQBBl_wCo.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE2OjUzOjMzLjk3NTkyMjEyNFoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoibjN5M05rRmhfVDdPNzFmb3VoNlNBQjg5RGFjd0drTHFGVWVRQkJsX3dDby5odG1sIiwicmVwb3J0X2lkIjoiem1UR2hRcVQ1Y3JqYXBMVFJFVkh5UW8xIn19fZ9r5g_OdCrQRJ1zvWuRLOwh7d9AV5C31dgO2snRuRecDcJHw4OVlwbwiP-DOd020EI0bf0g6QnVoq97K4lZmAk

Run: completed 2026-10-08T17:53:34Z, antithesis v63-12. First run with the FULL fault set: network faults, node pause, CPU throttle, node kill/stop + restart (node1..3), clock jumps. setup_complete was observed at about 133.4 vtime (the test composer started at 133.42).
Summary: 12 properties fail. Two are harness/environment problems: exit code 3 comes from the single seed (`seeds: cassandra-accord-node1`) not resolving while node1 is down, and the Guarantee 5 failures come from container IPs changing on restart, which deadlocks the TCM CMS. The 9 command-exit failures all come from `cassandra.UnresolvableContactPoints` raised outside the retry loop in `helper_accord.connect`. 1 safety failure (Guarantee 2) is real, in the acked-transfer-overwritten/committed-rows-read-absent family (one transactional read saw an in-flight writer's token in one slot and a committed row as absent in the other). It happened in a history with no node kill/stop/restart. The 3 unhit Guarantee 4/Guarantee 2 markers come from low throughput while the cluster was wedged. All other properties pass (Always 0 counterexamples), including Guarantee 1, Guarantee 3 and Guarantee 4 safety.

| Property | Guarantee (type) | Status | Examples | Counterexamples |
|---|---|---|---|---|
| container: cassandra-accord-node2, exit code: 3 | Antithesis default/setup (-) | Failing | 0 | 8 |
| container: cassandra-accord-node3, exit code: 3 | Antithesis default/setup (-) | Failing | 0 | 8 |
| All commands were run to completion at least once | Antithesis default/setup (-) | Passing | 1 | 0 |
| All commands were started at least once | Antithesis default/setup (-) | Passing | 1 | 0 |
| Always: Peak memory usage | Antithesis default/setup (-) | Passing | 5300 | 0 |
| Always: Unreachable | Antithesis default/setup (-) | Passing | 0 | 0 |
| Cassandra node startup complete | Antithesis default/setup (-) | Passing | 51 | 0 |
| Containers joined the Antithesis network | Antithesis default/setup (-) | Passing | 4 | 0 |
| Customer output volume | Antithesis default/setup (-) | Passing | 1 | 0 |
| Invalid paths found during Antithesis instrumention | Antithesis default/setup (-) | Passing | 1 | 0 |
| Language name: Java, sdk version: 1.7.0 | Antithesis default/setup (-) | Passing | 51 | 0 |
| Language name: Python, sdk version: 0.4.0 | Antithesis default/setup (-) | Passing | 3411 | 0 |
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
| a durability sample during the run could not read some rows within its time budget | Antithesis default/setup (-) | Passing | 24 | 0 |
| a final durability check could not connect to the cluster | Antithesis default/setup (-) | Passing | 1 | 0 |
| a final durability check could not read some acknowledged rows within its time budget | Antithesis default/setup (-) | Passing | 3 | 0 |
| a read-back of an acknowledged durable write did not complete in its time budget | Antithesis default/setup (-) | Passing | 17 | 0 |
| a final audit after faults stopped saw committed transfers | Guarantee 1 (sometimes) | Passing | 14 | 41 |
| a private-slot transfer reads the markers acknowledged before it and none from later transfers | Guarantee 1 (always) | Passing | 247 | 0 |
| a private-slot transfer was declined for insufficient balance | Guarantee 1 (sometimes) | Passing | 227 | 244 |
| a read started after a transfer was acknowledged sees that transfer | Guarantee 1 (always) | Passing | 247 | 0 |
| a read-back of a private slot sees one consistent transfer state | Guarantee 1 (always) | Passing | 247 | 0 |
| a transfer ended with an unknown outcome | Guarantee 1 (reachable) | Passing | 40 | 0 |
| a transfer moved a source account's entire balance | Guarantee 1 (sometimes) | Passing | 10 | 148 |
| a transfer reads balances within the bank total | Guarantee 1 (always) | Passing | 148 | 0 |
| a transfer reads every transfer acknowledged or observed before it started | Guarantee 1 (always) | Passing | 148 | 0 |
| a transfer saw transfers committed by other clients since this client last looked | Guarantee 1 (sometimes) | Passing | 109 | 146 |
| a transfer transaction reads both of its accounts | Guarantee 1 (always) | Passing | 148 | 0 |
| a transfer was acknowledged after resubmitting an attempt whose outcome was unknown | Guarantee 1 (sometimes) | Passing | 16 | 113 |
| a transfer was declined because the source balance was too low | Guarantee 1 (sometimes) | Passing | 106 | 148 |
| a transfer whose outcome was unknown was later seen applied | Guarantee 1 (reachable) | Passing | 6 | 0 |
| a transfer's effect was read back through a different coordinator | Guarantee 1 (sometimes) | Passing | 246 | 36 |
| an application-retried transfer reads both accounts with balances within the bank total | Guarantee 1 (always) | Passing | 115 | 0 |
| an application-retried transfer reads every transfer this client saw complete before it | Guarantee 1 (always) | Passing | 115 | 0 |
| an audit completed while an earlier transfer's outcome was still unknown | Guarantee 1 (sometimes) | Passing | 20 | 126 |
| an audit reflects every transfer acknowledged or observed before it started | Guarantee 1 (always) | Passing | 403 | 0 |
| an audit saw a bank account drained to exactly zero | Guarantee 1 (sometimes) | Passing | 17 | 399 |
| audited bank balances sum to the initial total | Guarantee 1 (always) | Passing | 403 | 0 |
| audited transfer counters sum to an even number | Guarantee 1 (always) | Passing | 403 | 0 |
| consecutive audits by one client observed newly committed transfers | Guarantee 1 (sometimes) | Passing | 20 | 105 |
| every seeded bank account is visible to an audit transaction | Guarantee 1 (always) | Passing | 403 | 0 |
| no bank account balance is negative in an audit | Guarantee 1 (always) | Passing | 403 | 0 |
| a conditional cross-table write read the same token in every slot of its group | Guarantee 2 (always) | Failing | 118 | 2 |
| a cross-table read saw a group rewritten since this reader's previous read | Guarantee 2 (sometimes) | Failing | 0 | 143 |
| a conditional cross-table write was declined because another writer changed the group | Guarantee 2 (sometimes) | Passing | 41 | 67 |
| a cross-table read transaction saw the same token in every slot of a group | Guarantee 2 (always) | Passing | 143 | 0 |
| a cross-table write of one token to four partitions was acknowledged | Guarantee 2 (sometimes) | Passing | 77 | 114 |
| a cross-table write transaction ended with an unknown outcome | Guarantee 2 (reachable) | Passing | 74 | 0 |
| a final check after faults stopped saw logged-batch groups written | Guarantee 2 (sometimes) | Passing | 7 | 63 |
| a final check after faults stopped saw transactional groups written | Guarantee 2 (sometimes) | Passing | 9 | 61 |
| a read-back after a cross-table write saw the same token in every slot | Guarantee 2 (always) | Passing | 29 | 0 |
| a read-back found a write of unknown outcome applied to every slot of its group | Guarantee 2 (sometimes) | Passing | 5 | 28 |
| after faults stopped every logged-batch group holds the same token in every slot | Guarantee 2 (always) | Passing | 67 | 0 |
| after faults stopped every transactional group holds the same token in every slot | Guarantee 2 (always) | Passing | 66 | 0 |
| a check during the run verified sampled acknowledged durable writes | Guarantee 3 (sometimes) | Passing | 95 | 24 |
| a conditional insert of a fresh id found no existing row for it | Guarantee 3 (always_or_unreachable) | Passing | 119 | 0 |
| a durable write ended with an unknown outcome | Guarantee 3 (reachable) | Passing | 64 | 0 |
| a durable write transaction spanning three partitions was acknowledged | Guarantee 3 (sometimes) | Passing | 106 | 132 |
| a final check found a write of unknown outcome applied | Guarantee 3 (sometimes) | Passing | 9 | 14 |
| a final check verified acknowledged durable writes from the ledgers | Guarantee 3 (sometimes) | Passing | 20 | 4 |
| a final check verified acknowledged multi-partition durable writes in every partition | Guarantee 3 (sometimes) | Passing | 20 | 4 |
| after faults stopped every acknowledged durable write is present with its value | Guarantee 3 (always) | Passing | 20 | 0 |
| an acknowledged durable write is visible with its value to the next read | Guarantee 3 (always) | Passing | 66 | 0 |
| an acknowledged durable write sampled during the run is present with its value | Guarantee 3 (always) | Passing | 95 | 0 |
| an acknowledged durable write was read back through a different coordinator | Guarantee 3 (sometimes) | Passing | 65 | 9 |
| a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one | Guarantee 4 (always) | Failing | 0 | 0 |
| a multi-key IN read of published registers completed | Guarantee 4 (reachable) | Failing | 0 | 0 |
| a conditional single-statement write on a full-mode table was applied | Guarantee 4 (sometimes) | Passing | 42 | 0 |
| a consistency-level ONE read right after an acknowledged plain write returned that write | Guarantee 4 (sometimes) | Passing | 64 | 72 |
| a plain read of a published register returned a version newer than its published floor | Guarantee 4 (sometimes) | Passing | 2 | 24 |
| a plain read of a published register sees at least the version acknowledged before the read started | Guarantee 4 (always) | Passing | 22 | 0 |
| a plain read on a full-mode table returns only versions that were written | Guarantee 4 (always) | Passing | 73 | 0 |
| a plain read on a full-mode table returns the latest acknowledged write or a newer one | Guarantee 4 (always) | Passing | 73 | 0 |
| a plain write was read back through a different coordinator than the one that acknowledged it | Guarantee 4 (sometimes) | Passing | 72 | 48 |
| a plain write with an unknown outcome was later read back | Guarantee 4 (reachable) | Passing | 5 | 0 |
| a reader saw a published register advance between two of its plain reads | Guarantee 4 (sometimes) | Passing | 5 | 22 |
| one client's successive plain reads of a single-writer register never go backwards | Guarantee 4 (always) | Passing | 22 | 0 |
| a plain write and read on a transactional table succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 73 | 3 |
| a transaction succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 73 | 3 |
| every node coordinated a transaction within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 73 | 3 |
| a node coordinated a transaction after earlier attempts through it failed | Guarantee 5 (sometimes) | Passing | 33 | 72 |
| a transaction succeeded after the first attempt once faults stopped had failed | Guarantee 5 (sometimes) | Passing | 21 | 55 |
| the first transaction attempt once faults stopped succeeded | Guarantee 5 (sometimes) | Passing | 52 | 24 |
| accord/anytime_durable_sample.py | command exit (-) | Failing | 444 | 4 |
| accord/parallel_driver_durable_writes.py | command exit (-) | Failing | 131 | 4 |
| accord/parallel_driver_pair_writes.py | command exit (-) | Failing | 168 | 1 |
| accord/anytime_bank_audit.py | command exit (-) | Passing | 118 | 0 |
| accord/eventually_bank_audit.py | command exit (-) | Passing | 59 | 0 |
| accord/eventually_durable_check.py | command exit (-) | Passing | 85 | 0 |
| accord/eventually_pair_check.py | command exit (-) | Passing | 71 | 0 |
| accord/eventually_recovery_probe.py | command exit (-) | Passing | 76 | 0 |
| accord/parallel_driver_bank_autoretry.py | command exit (-) | Passing | 145 | 0 |
| accord/parallel_driver_bank_transfers.py | command exit (-) | Passing | 147 | 0 |
| accord/parallel_driver_durable_readback.py | command exit (-) | Passing | 116 | 0 |
| accord/parallel_driver_fm_readers.py | command exit (-) | Passing | 191 | 0 |
| accord/parallel_driver_fm_register.py | command exit (-) | Passing | 93 | 0 |
| accord/parallel_driver_pair_reads.py | command exit (-) | Passing | 114 | 0 |
| accord/parallel_driver_rt_marker.py | command exit (-) | Passing | 252 | 0 |

Note: Antithesis default/setup rows include "Software was instrumented", SDK minimum versions, peak memory and so on. All of them pass except the two container exit-code-3 rows. For Sometimes/Reachable rows, "Counterexamples" counts the evaluations where the condition was false, which is normal.

## Failing: container: cassandra-accord-node3, exit code: 3 (also node2, 8 each)
- moment: input_hash=-3183840148574514038 vtime=142.36948019941337 (node2's first: -3490806286172312970 @ 181.1195016792044)
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMTQyLjM2OTQ4MDE5OTQxMzM3In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii0zMTgzODQwMTQ4NTc0NTE0MDM4In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjhhNjc1Yjk4MjU4MGQwNWNhNDIxNGJlMzJmZmRlNjQzLTYzLTEyIn0
- log: antithesis/scratchbook/logs/iter3-m3183840148574514038.log
- timeline:
  - 138.84 [fault_injector] node/stop node3; 139.12 node3 exit=143. 140.96 node3 entrypoint restarts (`boost: host=cassandra-accord-node3 …`).
  - 141.12 [containers_meta] container kill node1; 141.21 FAULT node/kill node1; 141.62 node1 exit=137, so node1's container (and its DNS name) is gone.
  - 142.05 [node3] `ERROR CassandraDaemon.java:1023 - Exception encountered during startup: The seed provider lists no seeds.` (ConfigurationException, DatabaseDescriptor.java:1661).
  - 142.37 node3 container died exit=3. The container is not restarted again, so node3 stays down for the rest of this history.
- details: `SimpleSeedProvider` resolves `cassandra-accord-node1`. That name is unresolvable while node1's container is stopped, so it is skipped ("not fatal… DD will bark if there end up being zero seeds"), the seed list is empty, and startup aborts with exit 3. In both runs every exit-3 event has this message: run A 8 node2 + 8 node3, run B 6 node2 + 4 node3, which matches the counterexample counts exactly. Harness code never exits 3 (entrypoint.sh just `exec`s `cassandra -f`). On a restart the node has `hasAnyEpoch=true` and boots in NORMAL mode, so it only needs a non-empty seed list. Class: **false-positive** (checklist 3, configuration/topology: the cluster has one seed, and a restarted node depends on it being up). It also directly lowers availability: an exited node never comes back in that history, which feeds into the Guarantee 5 and command-exit failures.

## Failing: a transaction succeeded within 120 seconds after faults stopped (also "every node coordinated a transaction …" and "a plain write and read … succeeded …", 3 counterexamples each, same moments)
- moment: input_hash=-9161517995650739017 vtime=263.7104486739263
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjYzLjcxMDQ0ODY3MzkyNjMifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiLTkxNjE1MTc5OTU2NTA3MzkwMTcifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiOGE2NzViOTgyNTgwZDA1Y2E0MjE0YmUzMmZmZGU2NDMtNjMtMTIifQ
- log: antithesis/scratchbook/logs/iter3-m9161517995650739017.log
- timeline:
  - Original addresses: node1 10.89.0.2, node2 10.89.0.3, node3 10.89.0.4. The CMS was reconfigured to 3 members (nodes 1, 2, 3) during setup.
  - 140.97 FAULT node/kill node2 (exit 137 at 141.37), restarted 143.37. 143.54 FAULT node/kill node3 (exit 137 at 143.62), restarted 145.87.
  - 146.92 [node2] `Listening on address: (cassandra-accord-node2/10.89.0.6:7000)`. 149.79 [node3] listens on **10.89.0.7**. Both restarted containers got new IPs.
  - 148.86 [node1] `Could not find Node.Id for endpoint /10.89.0.6:7000` (Accord EndpointMapping). Every node keeps dialling the old .3/.4 addresses (`->/10.89.0.4:7000 … failed to connect`, `dropping message of type TCM_FETCH_C…/ACCORD_FETC…`).
  - 167.03 [node1] `DistributedMetadataLogKeyspace.java:158 - Caught an exception while trying to CAS: UnavailableException: Cannot achieve consistency level SERIAL 2 > 1`. The CMS (3 members, 2 of them at stale addresses) has no quorum. The restarted nodes' `Startup` transformation (the address change) can never commit, so the directory never learns the new IPs. The cluster is deadlocked.
  - 143.32 onward: eventually_recovery_probe runs every 3 s. `txn via node1` gets WriteTimeout. `txn via node2/node3` gets `10.89.0.6/10.89.0.7 not in driver metadata`. Plain write+read gets WriteTimeout. After 119.2 s (attempt 34, 262.86) the probe gives up. FAIL ×3 at 263.71. Containers stay healthy (port 9042 open) throughout.
- details: The same mechanism shows up in run B (fix-verify-acked-transfer-overwritten-2): node1 and node2 restart about 13 s apart with new IPs (.6/.7). node1 commits `STARTUP` only after its catch-up times out (158.8), when node2 is already re-addressed, so node3 logs `Cannot achieve consistency level SERIAL 2 > 1`. Antithesis documents that "restarted nodes may change IP addresses upon rejoining the network" (fault_types, Node termination). Production Cassandra nodes normally keep stable addresses, and when a majority of the CMS members change address before the change commits, TCM cannot recover without an operator. Class: **false-positive** (checklist 3, topology/environment: IP churn from container restarts). Fix: give each node a static address (see fixes). Possible SUT lead, not a violation: "TCM cannot commit an address change once a majority of CMS members have re-IP'd" is an availability limitation worth one line in the method notes.

## Failing: a conditional cross-table write read the same token in every slot of its group
- moment: input_hash=2137002785411178762 vtime=204.56820029346272
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjA0LjU2ODIwMDI5MzQ2MjcyIn1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjIxMzcwMDI3ODU0MTExNzg3NjIifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiOGE2NzViOTgyNTgwZDA1Y2E0MjE0YmUzMmZmZGU2NDMtNjMtMTIifQ
- log: antithesis/scratchbook/logs/iter3-2137002785411178762.log (+ .ndjson from 133 s, .tail.ndjson)
- timeline:
  - 10.9–104.1 nodes 1–3 and the client start. In this history there is **no node kill, stop or restart** at any point (only `container start` events). Faults: network clog/partition, node/throttle (CPU) on all nodes, clock/skip +0.8–1.6 s on all nodes (153.5, 160.6, 180.6, 198.1).
  - 170.76 [client pid 135] group 0 CAS read: pair_a:0 = pair_b:5000 = `18d41f043e482f5e-10x` (consistent).
  - 189.91 [pid 67] unconditional write to group 0 → WriteTimeout (Reachable "unknown outcome", txn [35,1791479940938143,178(KW),3]).
  - 196.01 [pid 67] group-0 read-back: both slots = `607282d3e9d32342-3x…` (consistent). 196.70 [pid 91] CAS declined: both slots = `607282d3e9d32342-7x…` (consistent).
  - 152.91 [client pid 75] pair_writes writer `18d41f043e482f5e` starts (ops=40, auto_retry=True, so its unconditional writes use the driver's RetryPolicy). Its last logged event is at 196.46. Its seq-21 write to group 0 (token `18d41f043e482f5e-21x`) produces no ack marker, so at 204.57 it is still in flight (or being retried by the driver).
  - 197.41 [client pid 231] writer `42e19a478dc145cd` starts (auto_retry=False, cas_pct=50). 204.57 [pid 231] its first CAS on group 0 (never seen, so expected=None, `IF r0 IS NULL`). **FAIL**: CAS transaction on group 0 via coordinator 10.89.0.3 (node2) returned `pair_a:0 = "18d41f043e482f5e-21x"`, `pair_b:5000 = null`. Active faults: network clog, node2 throttle.
- details: `{"coordinator":"10.89.0.3:9042","expected":null,"group":0,"slots":{"pair_a:0":"18d41f043e482f5e-21x","pair_b:5000":null}}`. pair_a:0 already shows the in-flight seq-21 token of another writer (pid 75), while pair_b:5000 in the **same** transactional read is null. Every write puts the same unique token in all slots of the group, so a transaction-consistent read can show `18d41f…-21x` in both slots or in neither, never in one. On top of that, pair_b:5000 held `607282d3e9d32342-7x…` 8 s earlier (196.70), and no command deletes rows, TTLs them or writes null, so null is not any committed state of that slot. Taken together, the read saw part of a concurrent transaction's writes (an atomicity/isolation break, the acked-transfer-overwritten lost-update/re-execution family) and a committed row as absent (the committed-rows-read-absent symptom: iterate-1 and the acked-transfer-overwritten fix check, "seeded row read as null"; committed-rows-read-absent blinded RCA: the coordinator's local read returns only command-store-0's rows). Run B (with acked-transfer-overwritten.patch) shows no Guarantee 2 failure. Checklist: clean. (1) It is one BEGIN TRANSACTION with LET point reads by full key. (2) Every write puts the same unique token in every slot, so an ambiguous write can't produce token+null. (3) The tables are `transactional_mode='full'`. (4) No orchestration. (5) The check compares the returned LET values directly. A node restart did not precede it, so `stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP` is not involved. Class: **real** (acked-transfer-overwritten/committed-rows-read-absent family. Run A has neither patch. Not a new mechanism, so no new violation entry is needed; attach it to acked-transfer-overwritten/committed-rows-read-absent as further evidence). The second counterexample was not downloaded.

## Failing: accord/parallel_driver_durable_writes.py (4), accord/anytime_durable_sample.py (4), accord/parallel_driver_pair_writes.py (1)
- moment: input_hash=6400642402339339425 vtime=504.3118120767176 (durable_writes). Others: durable_sample 3566524124483354532 @ 406.36758305947296, pair_writes -6742307498290920615 @ 394.692554510897
- log link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNTA0LjMxMTgxMjA3NjcxNzYifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNjQwMDY0MjQwMjMzOTMzOTQyNSJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiI4YTY3NWI5ODI1ODBkMDVjYTQyMTRiZTMyZmZkZTY0My02My0xMiJ9 · https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNDA2LjM2NzU4MzA1OTQ3Mjk2In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjM1NjY1MjQxMjQ0ODMzNTQ1MzIifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiOGE2NzViOTgyNTgwZDA1Y2E0MjE0YmUzMmZmZGU2NDMtNjMtMTIifQ · https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzk0LjY5MjU1NDUxMDg5NyJ9XSwibyI6Im9yIn0seyJoIjpbeyJjIjoibW9tZW50LmlucHV0X2hhc2giLCJmIjoiZ2VuZXJhbC5jdXN0b20iLCJvIjoibWF0Y2hlcyIsInYiOiItNjc0MjMwNzQ5ODI5MDkyMDYxNSJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiI4YTY3NWI5ODI1ODBkMDVjYTQyMTRiZTMyZmZkZTY0My02My0xMiJ9
- log: antithesis/scratchbook/logs/iter3-6400642402339339425.log
- timeline: 460–504 repeated kills/stops of node1 and node3. 469.12 node3 exit=3 ("seed provider lists no seeds"). 504.12 node1 exit=137, so no node container is running and none of the three hostnames resolves. 504.31 [client] traceback: `helper_accord.py line 98, in connect → cluster = Cluster(` → `cassandra.UnresolvableContactPoints: {}`. Exit 1 after 77.9 s (the command had been retrying `cluster.connect()`, and the next `Cluster(...)` construction raised).
- details: A run-wide `snouty runs events -m UnresolvableContactPoints` finds 9 events in run A, which matches 4+4+1 non-zero exits exactly. `Cluster.__init__` resolves the contact points eagerly and raises when none resolve. The constructor sits outside the `try` in `connect()`, so the documented "returns (None, None) … caller exits 0" path is bypassed. Class: **false-positive** (checklist 1/3: the harness does not handle a documented transient driver error).

## Unhit: a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one (Guarantee 4 Always, 0/0), a multi-key IN read of published registers completed (Guarantee 4 Reachable, 0/0), a cross-table read saw a group rewritten since this reader's previous read (Guarantee 2 Sometimes, 0/143)
- All three are hit in iter-2 (83ddaf…, 5/7/4 examples) and in run B (4/7/8), so the markers are not broken. In run A the cluster spent much of the run wedged or partially down: Guarantee 5 IP/CMS deadlock, nodes that exited 3 and never came back, and an unreachable cluster. fm_register/fm_readers ran 93/191 times but only 22 plain register reads succeeded (vs. hundreds in B), so the rare declined-CAS and multi-key IN paths were never reached. Class: harness-gap that follows from the false-positives above. It should clear once the seed, static-IP and connect fixes are in.
