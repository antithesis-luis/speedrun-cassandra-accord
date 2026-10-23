# hunt-3 · c16f5775181c00d7a3ac9d8a7607de32-63-12 · current@e874e3a9 · completed · 360 m
Report: https://honey-whale.antithesis.com/report/xeFXBGscPgpTrEh3HgeiBn3r/ZXj-4QdSO3r-ImhAo-tFncJktsaXb_DSbBvEmgwtQGw.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA5VDAxOjI4OjEzLjg5MzA2MDk0NVoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiWlhqLTRRZFNPM3ItSW1oQW8tdEZuY0prdHNhWGJfRFNiQnZFbWd3dFFHdy5odG1sIiwicmVwb3J0X2lkIjoieGVGWEJHc2NQZ3BUckVoM0hnZWlCbjNyIn19fSdJ3KhdpBr-SnSTAwI4wfBSIzIOBLRhj70vJ-rqgY2vQBH3fQ21j3BM1XbZJNgZLDBQ_nC_jq4KZbpqZhE2kAU

Run: turbo, static IPs 10.231.17.11-13, all three nodes as seeds on restart. Full faults: network, pause, throttle, clock skip, and node kill/stop with restart. Created 2026-10-08T19:29:21Z, completed 2026-10-09T02:28:14Z, v63-12. SUT overrides as in hunt-1/2: `accord.journal.stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP`, periodic commitlog, PERIODIC journal, and `crc_failure_on_rebuild_policy` left at its default (FAIL).

Summary: **New finding: a node that is SIGKILLed while writing the Accord journal can never restart.** At 217.58 node2 was killed. On restart it found its active journal segment without a metadata component, rebuilt the metadata, hit a record whose size marker was written but whose CRC is 0, and threw `JournalReadError … InvalidCrc: Read 0` from `AccordService.localStartup`. That is exit code 3. All 45 "node2 exit code 3" counterexamples are this one event: 39 `JournalReadError in` events, all on node2, all on segment `log-1791488061546-1-1-1.data`, inherited by later branches. The first Guarantee 5 (any-node) failure follows from it: node2 is dead, and node1 and node3 are both restarting and wait about 125 s fetching epoch 38 from each other and from the dead node2, so neither opens CQL within 120 s. The Guarantee 1/Guarantee 3/Guarantee 4 failures match known signatures. The one Guarantee 2 failure has no kills or stops in its history, so it is the real committed-rows-read-absent family (as in hunt-4).

| Property | Guarantee (type) | Status | Examples | Counterexamples |
|---|---|---|---|---|
| a private-slot transfer reads the markers acknowledged before it and none from later transfers | Guarantee 1 (always) | Passing | 1336 | 0 |
| a read started after a transfer was acknowledged sees that transfer | Guarantee 1 (always) | Passing | 1309 | 0 |
| a read-back of a private slot sees one consistent transfer state | Guarantee 1 (always) | Passing | 1309 | 0 |
| a transfer reads balances within the bank total | Guarantee 1 (always) | Passing | 2136 | 0 |
| a transfer reads every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 2136 | 18 |
| a transfer transaction reads both of its accounts | Guarantee 1 (always) | Failing | 2136 | 5 |
| an application-retried transfer reads both accounts with balances within the bank total | Guarantee 1 (always) | Passing | 1373 | 0 |
| an application-retried transfer reads every transfer this client saw complete before it | Guarantee 1 (always) | Failing | 1373 | 18 |
| an audit reflects every transfer acknowledged or observed before it started | Guarantee 1 (always) | Failing | 7556 | 68 |
| audited bank balances sum to the initial total | Guarantee 1 (always) | Failing | 6976 | 634 |
| audited transfer counters sum to an even number | Guarantee 1 (always) | Failing | 7205 | 409 |
| every seeded bank account is visible to an audit transaction | Guarantee 1 (always) | Failing | 7557 | 22 |
| no bank account balance is negative in an audit | Guarantee 1 (always) | Passing | 7557 | 0 |
| a transfer ended with an unknown outcome | Guarantee 1 (reachable) | Passing | 1327 | 0 |
| a transfer whose outcome was unknown was later seen applied | Guarantee 1 (reachable) | Passing | 56 | 0 |
| a final audit after faults stopped saw committed transfers | Guarantee 1 (sometimes) | Passing | 244 | 576 |
| a private-slot transfer was declined for insufficient balance | Guarantee 1 (sometimes) | Passing | 1247 | 1253 |
| a transfer moved a source account's entire balance | Guarantee 1 (sometimes) | Passing | 80 | 2137 |
| a transfer saw transfers committed by other clients since this client last looked | Guarantee 1 (sometimes) | Passing | 1710 | 1859 |
| a transfer was acknowledged after resubmitting an attempt whose outcome was unknown | Guarantee 1 (sometimes) | Passing | 311 | 1361 |
| a transfer was declined because the source balance was too low | Guarantee 1 (sometimes) | Passing | 1765 | 2110 |
| a transfer's effect was read back through a different coordinator | Guarantee 1 (sometimes) | Passing | 1179 | 366 |
| an audit completed while an earlier transfer's outcome was still unknown | Guarantee 1 (sometimes) | Passing | 661 | 1866 |
| an audit saw a bank account drained to exactly zero | Guarantee 1 (sometimes) | Passing | 240 | 7502 |
| consecutive audits by one client observed newly committed transfers | Guarantee 1 (sometimes) | Passing | 1407 | 3279 |
| a conditional cross-table write read the same token in every slot of its group | Guarantee 2 (always) | Passing | 1393 | 0 |
| a cross-table read transaction saw the same token in every slot of a group | Guarantee 2 (always) | Failing | 1544 | 1 |
| a read-back after a cross-table write saw the same token in every slot | Guarantee 2 (always) | Passing | 423 | 0 |
| after faults stopped every logged-batch group holds the same token in every slot | Guarantee 2 (always) | Passing | 813 | 0 |
| after faults stopped every transactional group holds the same token in every slot | Guarantee 2 (always) | Passing | 813 | 0 |
| a cross-table write transaction ended with an unknown outcome | Guarantee 2 (reachable) | Passing | 611 | 0 |
| a conditional cross-table write was declined because another writer changed the group | Guarantee 2 (sometimes) | Passing | 350 | 824 |
| a cross-table read saw a group rewritten since this reader's previous read | Guarantee 2 (sometimes) | Passing | 197 | 1544 |
| a cross-table write of one token to four partitions was acknowledged | Guarantee 2 (sometimes) | Passing | 925 | 1467 |
| a final check after faults stopped saw logged-batch groups written | Guarantee 2 (sometimes) | Passing | 89 | 724 |
| a final check after faults stopped saw transactional groups written | Guarantee 2 (sometimes) | Passing | 136 | 677 |
| a read-back found a write of unknown outcome applied to every slot of its group | Guarantee 2 (sometimes) | Passing | 85 | 389 |
| after faults stopped every acknowledged durable write is present with its value | Guarantee 3 (always) | Failing | 238 | 33 |
| an acknowledged durable write is visible with its value to the next read | Guarantee 3 (always) | Passing | 1783 | 0 |
| an acknowledged durable write sampled during the run is present with its value | Guarantee 3 (always) | Failing | 1060 | 144 |
| a conditional insert of a fresh id found no existing row for it | Guarantee 3 (always_or_unreachable) | Passing | 2340 | 0 |
| a durable write ended with an unknown outcome | Guarantee 3 (reachable) | Passing | 957 | 0 |
| a check during the run verified sampled acknowledged durable writes | Guarantee 3 (sometimes) | Passing | 1203 | 195 |
| a durable write transaction spanning three partitions was acknowledged | Guarantee 3 (sometimes) | Passing | 2101 | 2384 |
| a final check found a write of unknown outcome applied | Guarantee 3 (sometimes) | Passing | 126 | 164 |
| a final check verified acknowledged durable writes from the ledgers | Guarantee 3 (sometimes) | Passing | 264 | 24 |
| a final check verified acknowledged multi-partition durable writes in every partition | Guarantee 3 (sometimes) | Passing | 238 | 50 |
| an acknowledged durable write was read back through a different coordinator | Guarantee 3 (sometimes) | Passing | 1500 | 640 |
| a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one | Guarantee 4 (always) | Passing | 39 | 0 |
| a plain read of a published register sees at least the version acknowledged before the read started | Guarantee 4 (always) | Failing | 243 | 5 |
| a plain read on a full-mode table returns only versions that were written | Guarantee 4 (always) | Passing | 1203 | 0 |
| a plain read on a full-mode table returns the latest acknowledged write or a newer one | Guarantee 4 (always) | Passing | 1203 | 0 |
| one client's successive plain reads of a single-writer register never go backwards | Guarantee 4 (always) | Failing | 243 | 5 |
| a multi-key IN read of published registers completed | Guarantee 4 (reachable) | Passing | 53 | 0 |
| a plain write with an unknown outcome was later read back | Guarantee 4 (reachable) | Passing | 59 | 0 |
| a conditional single-statement write on a full-mode table was applied | Guarantee 4 (sometimes) | Passing | 691 | 39 |
| a consistency-level ONE read right after an acknowledged plain write returned that write | Guarantee 4 (sometimes) | Passing | 1095 | 1192 |
| a plain read of a published register returned a version newer than its published floor | Guarantee 4 (sometimes) | Passing | 48 | 230 |
| a plain write was read back through a different coordinator than the one that acknowledged it | Guarantee 4 (sometimes) | Passing | 1074 | 905 |
| a reader saw a published register advance between two of its plain reads | Guarantee 4 (sometimes) | Passing | 37 | 243 |
| a plain write and read on a transactional table succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 808 | 18 |
| a transaction succeeded within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 808 | 18 |
| every node coordinated a transaction within 120 seconds after faults stopped | Guarantee 5 (always) | Failing | 774 | 52 |
| a node coordinated a transaction after earlier attempts through it failed | Guarantee 5 (sometimes) | Passing | 456 | 749 |
| a transaction succeeded after the first attempt once faults stopped had failed | Guarantee 5 (sometimes) | Passing | 269 | 557 |
| the first transaction attempt once faults stopped succeeded | Guarantee 5 (sometimes) | Passing | 539 | 287 |
| Customer output volume | Antithesis default/setup (-) | Failing | 0 | 1 |
| container: cassandra-accord-node2, exit code: 3 | Antithesis default/setup (-) | Failing | 0 | 45 |

109 properties reported, 17 not passing. Antithesis default properties not listed above are Passing.

## Failing: container: cassandra-accord-node2, exit code: 3 (default, 45 counterexamples)
- Moment: input_hash -8545236388639200513, vtime 224.7138. Log: scratchbook/logs/hunt3--8545236388639200513.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjI0LjcxMzc3NzIxMTk2MDQifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiLTg1NDUyMzYzODg2MzkyMDA1MTMifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiN2U3MGYyOTc0NjI1NGM1MDRiM2Y4ZmRiYWEyYTk4MDEtNjMtMTIifQ
- Events: `snouty --json runs events c16f5775181c00d7a3ac9d8a7607de32-63-12 -m "JournalReadError in"` returns 39 events, all `cassandra-accord-node2`, all on `/var/lib/cassandra/accord_journal/log-1791488061546-1-1-1.data`, earliest 224.19 (scratchbook/logs/hunt3-events-journalreaderror.ndjson). This is one failure that later branches inherit, not 45 separate ones.
- Timeline:
  - 54/86/102: first boot of node1/node2/node3. node2 start marker 1791488061537, and its first journal segment is `log-1791488061546-…`.
  - 141.43 faults start. Before node2's death: node1 kill at 163.42 and 188.69, clock skips, pauses, throttles and partitions. No earlier fault on node2 except pause and throttle.
  - 217.43 `node/stop node1`, **217.58 `node/kill node2`** (SIGKILL), 222.39 `node/kill node1`.
  - 219.80 node2 `boot=restart seeds=node1,node2,node3`. 224.13 `Log replay complete, 534 replayed mutations` (commitlog is fine). 224.13 `Starting accord with nodeId 2`.
  - 224.18 `WARN AccordService.java:549 - Stop marker is older than start marker (-1<1791488061537) … Continuing to startup as configured.`
  - 224.19:
    ```
    Exception (org.apache.cassandra.journal.JournalReadError) encountered during startup: org.apache.cassandra.utils.Crc$InvalidCrc: Read 0, Computed -1358688540
    JournalReadError in /var/lib/cassandra/accord_journal/log-1791488061546-1-1-1.data
      at o.a.c.journal.StaticSegment$SequentialReader.doAdvance(StaticSegment.java:462)
      at o.a.c.journal.StaticSegment$SequentialReader.advance(StaticSegment.java:429)
      at o.a.c.journal.Metadata.rebuild(Metadata.java:142)
      at o.a.c.journal.Metadata.rebuildAndPersist(Metadata.java:158)
      at o.a.c.journal.StaticSegment.open(StaticSegment.java:121)
      at o.a.c.journal.Journal.open(Journal.java:219)
      at o.a.c.service.accord.journal.AccordJournal.open(AccordJournal.java:126)
      at o.a.c.service.accord.AccordService.localStartup(AccordService.java:573)
      at o.a.c.service.CassandraDaemon.setup(CassandraDaemon.java:364)
    Caused by: org.apache.cassandra.utils.Crc$InvalidCrc: Read 0, Computed -1358688540
      at o.a.c.journal.EntrySerializer.validateCRC(EntrySerializer.java:259)
      at o.a.c.journal.EntrySerializer.tryRead(EntrySerializer.java:144)
    ERROR [main] CassandraDaemon.java:1023 - Exception encountered during startup
    ```
    The JVM exits with 3. node2 never comes back in this branch: later restarts of node1 and node3 log `Seed provider couldn't lookup host cassandra-accord-node2`.
- Mechanism (code at e874e3a9, src/cassandra/src/java/org/apache/cassandra/journal/):
  - `ActiveSegment.allocate` writes the next-entry size marker (`buffer.putInt(prev, next)`, ActiveSegment.java:433) when the space is reserved. The record body and CRC are written later, in `Allocation.write → EntrySerializer.write` (CRC at EntrySerializer.java:74/77). If the process is killed between the two steps, the mmap'd page cache holds a record with a valid size marker and CRC = 0. Because writers are concurrent, such a hole can sit before fully written records.
  - A killed node never writes the segment's METADATA component, so `StaticSegment.open` calls `Metadata.rebuild`. Rebuild uses `fsyncedLimit = Integer.MAX_VALUE` (Metadata.java:140), so the whole segment counts as "synced", and `handleReadException` rethrows instead of treating the error as end of segment. `SequentialReader.doAdvance` then applies `crcFailureOnRebuildPolicy`, which defaults to **FAIL** (AccordConfig.java:399). The `IGNORE_CRC_ZERO_RECORDS` and `IGNORE_ALL_ZERO_RECORDS` modes exist for exactly this "Read 0" case but are not the default. `Metadata.rebuild` only tolerates EOFException, so the error propagates out of `localStartup`.
  - Because the METADATA file is never persisted, every later restart fails the same way, so the node is permanently down.
- Is ALLOW_UNSAFE_STARTUP responsible? **No, not as the cause.** That policy only downgrades the stop-marker check (AccordService.java:540-555) to a WARN. `journal.open` (line 573) runs afterwards under every policy that continues: ALLOW_UNSAFE_STARTUP, UNSAFE_STARTUP and **REBOOTSTRAP**. With the default EXIT the node would also refuse to start after any kill, for a different reason. So the torn record is a property of SIGKILL during an append, not of the unsafe policy. The policy only lets the run reach the journal open. Antithesis kills the process, not the kernel, so the page cache survives. This is the most benign crash model, and the journal still cannot open its own tail.
- Not every kill triggers it. Elsewhere in this run node2 is killed at 331.66 and starts cleanly (hash 2526996890917044422), and node1 survives several kills. The kill has to land between allocate and write.
- Harness ruled out: the entrypoint, seeds and config were fine. Commitlog replay completed, TCM came up (`hasBootedBefore = true`), and the failure is inside Accord journal open. In the same branch node1 (killed at 222.39) restarts at 224.54 and gets past journal open (stop-marker WARN 227.74, `Waiting for command stores to quiesce` 228.46).
- hunt-1 "node3 exit code 3 (37), startup exception at about 153.5" and hunt-2 "node3 exit 3 @ 157.46 / node2 Exception during startup @ 642.37" are very likely the same failure. The cause line was not captured then, so this is not verified.
- Class: **real (SUT bug candidate, crash recovery/liveness)**: "Accord journal cannot reopen an active segment torn by a process kill; with the default crc_failure_on_rebuild_policy=FAIL the node fails startup permanently (exit 3)". Moment 224.19, input_hash -8545236388639200513 (first event hash 8903570532516572783).

## Failing: a transaction succeeded within 120 seconds after faults stopped (Guarantee 5, 18 counterexamples; same moment for "a plain write and read on a transactional table…")
- Moment: input_hash -3323740369927200736, vtime 358.0517. Log: scratchbook/logs/hunt3--3323740369927200736.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzU4LjA1MTY3NTY5MTczNSJ9XSwibyI6Im9yIn0seyJoIjpbeyJjIjoibW9tZW50LmlucHV0X2hhc2giLCJmIjoiZ2VuZXJhbC5jdXN0b20iLCJvIjoibWF0Y2hlcyIsInYiOiItMzMyMzc0MDM2OTkyNzIwMDczNiJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiI3ZTcwZjI5NzQ2MjU0YzUwNGIzZjhmZGJhYTJhOTgwMS02My0xMiJ9
- Timeline (same prefix as above up to 224):
  - 217.58 kill node2. **224.46 node2 `JournalReadError … log-1791488061546-1-1-1.data`, exit 3, permanently dead.**
  - 222.39 kill node1, restart at 224.54, stop-marker WARN 227.74, `Waiting for command stores to quiesce` 228.46. Then a 125 s silence on main while `ACCORD_FETCH_TOPOLOGY_REQ` to [node3, node2] fails ("Exhausted iterator … attempt #0…#11+").
  - 234.95 kill node3, restart at 236.93, stop-marker WARN 240.44, quiesce at 241.24. node3 likewise cycles `ACCORD_FETCH_TOPOLOGY_REQ` to [node2, node1] up to attempt #47 at 352.23.
  - 236.71 eventually_recovery_probe starts (faults stopped). Every connect attempt gets `ConnectionRefused` on both 10.231.17.11:9042 and .13:9042 (node2 has no address).
  - 353.24 node1 `AccordService.java:929 - Failed to fetch epochs [38, 38] from [/10.231.17.13:7000, /10.231.17.12:7000]`, then `Catchup (NORMAL) with quorum…` (`2 is considered faulty`). 353.77–355.46 node3 stores report `fully caught-up with quorums`. Neither node reaches `Startup complete` before 358.05.
  - 358.05 `recovery_probe: cluster unreachable after 41 connect attempts`, FAIL for all three Guarantee 5 always properties.
- Node state at the failure: node1 **in startup** (just past the 125 s topology fetch, in catch-up), node2 **exited 3** (journal CRC), node3 **in startup** (in catch-up). There is no CMS problem: both log `hasAnyEpoch = true, hasBootedBefore = true`, and `Initializing as non CMS node` is normal.
- Assessment: this coincides with node2's death and is caused by it. With one replica permanently gone, the two survivors that restart together block each other on the epoch fetch until the retry budget runs out (about 125 s), which overruns the 120 s window by itself. If node2 had been alive, the fetch would have succeeded right away. The window is also below `catchup_on_start_fail_latency` (900 s) and the epoch-fetch retry budget. Primary cause: the journal bug above. Secondary: the window is tighter than the SUT's startup bounds.
- Class: **real (consequence of the node2 journal-CRC startup failure)**. It is not an independent finding: report it under the same bug. The 120 s window alone would make it suspect, but here one node is permanently down, so the cluster cannot reach full health at all.

## Failing: every node coordinated a transaction within 120 seconds after faults stopped (Guarantee 5, 52 counterexamples)
- Moment: input_hash 3560554671341624394, vtime 319.8908. Not downloaded. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzE5Ljg5MDgyNzI4ODE1MjY1In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjM1NjA1NTQ2NzEzNDE2MjQzOTQifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiN2U3MGYyOTc0NjI1NGM1MDRiM2Y4ZmRiYWEyYTk4MDEtNjMtMTIifQ
- Assessment: this superset includes the 18 any-node failures and branches where only one node (a restarting one, or the permanently dead node2) never coordinated. node2's death from 224 onward makes "every node" impossible in every inherited branch. Other counterexamples have the hunt-1/2 shape (a restart blocked in catch-up beyond 120 s).
- Class: suspect (window 120 s < 900 s catch-up deadline; plus node2 permanently dead from the journal bug in inherited branches). Not verified for this exact hash.

## Failing: Guarantee 1 (bank and rt_marker always properties)
- "audited bank balances sum to the initial total" (634) @ 178.98 hash -2690812733156017893 (link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMTc4Ljk3NjYwNzAzODQwNjY2In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii0yNjkwODEyNzMzMTU2MDE3ODkzIn1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjdlNzBmMjk3NDYyNTRjNTA0YjNmOGZkYmFhMmE5ODAxLTYzLTEyIn0), "audited transfer counters sum to an even number" (409), "an audit reflects every transfer…" (68), "a transfer reads every transfer…" (18), "an application-retried transfer reads every transfer…" (18): **acked-transfer-overwritten signature** (lost update / double execution). Not re-investigated.
- "every seeded bank account is visible to an audit transaction" (22) and "a transfer transaction reads both of its accounts" (5, @ 505.12 hash 3281494624633910314, link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNTA1LjEyMjE2NTAyNjYwODg1In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjMyODE0OTQ2MjQ2MzM5MTAzMTQifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiN2U3MGYyOTc0NjI1NGM1MDRiM2Y4ZmRiYWEyYTk4MDEtNjMtMTIifQ): **committed-rows-read-absent signature** (absent rows). Same as hunt-1/hunt-4. Not re-investigated.
- Class: real (known acked-transfer-overwritten/committed-rows-read-absent).

## Failing: a cross-table read transaction saw the same token in every slot of a group (Guarantee 2, 1 counterexample)
- Moment: input_hash 7210116645916882353, vtime 241.7851. Log: scratchbook/logs/hunt3-7210116645916882353.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjQxLjc4NTA3OTE4MzUyMjYifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNzIxMDExNjY0NTkxNjg4MjM1MyJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiI3ZTcwZjI5NzQ2MjU0YzUwNGIzZjhmZGJhYTJhOTgwMS02My0xMiJ9
- Faults in history: 31 network/partition, 6 node/pause, 1 network/restore. **No kill, stop or clock fault.** All three nodes are from first boot.
- Class: real (committed-rows-read-absent family, not kill-dependent; same as the hunt-4 entry). Details were not captured in the log (only via the report).

## Failing: an acknowledged durable write sampled during the run is present with its value (Guarantee 3, 144) / after faults stopped every acknowledged durable write is present (Guarantee 3, 33)
- Sample moment: input_hash -8846845851714316707, vtime 269.6464. Log: scratchbook/logs/hunt3--8846845851714316707.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjY5LjY0NjQ2MzMxMTA0NDUifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiLTg4NDY4NDU4NTE3MTQzMTY3MDcifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiN2U3MGYyOTc0NjI1NGM1MDRiM2Y4ZmRiYWEyYTk4MDEtNjMtMTIifQ
- Timeline: kills of node1 at 143.15 and 196.63, node3 at 157.36 and 249.21, node2 at 177.15 and 247.33. node1 stop at 176.33, node2 stop at 198.79. Each kill is followed by a stop-marker WARN (unsafe startup). node2 and node3 finish startup at 265.41 and 266.68, and the check FAILs at 269.65, 3 s later.
- Final-check moment: 6645925599041797345 @ 443.94, not downloaded. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNDQzLjk0Mzg3NTcyNzAxMDkifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiNjY0NTkyNTU5OTA0MTc5NzM0NSJ9XSwibyI6Im9yIn1dLCJvIjoiYW5kIn0sInQiOnsiZyI6ZmFsc2UsIm0iOiIifSwieSI6Im5vbmUifX0sInMiOiI3ZTcwZjI5NzQ2MjU0YzUwNGIzZjhmZGJhYTJhOTgwMS02My0xMiJ9
- Class: suspect (unsafe-startup confound), the same as hunt-1/hunt-2.

## Failing: a plain read of a published register sees at least the version acknowledged before the read started / one client's successive plain reads … never go backwards (Guarantee 4, 5 + 5)
- Moment: input_hash 2526996890917044422, vtime 377.6906. Log: scratchbook/logs/hunt3-2526996890917044422.log. Link: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzc3LjY5MDYwNTI4MzQ4MiJ9XSwibyI6Im9yIn0seyJoIjpbeyJjIjoibW9tZW50LmlucHV0X2hhc2giLCJmIjoiZ2VuZXJhbC5jdXN0b20iLCJvIjoibWF0Y2hlcyIsInYiOiIyNTI2OTk2ODkwOTE3MDQ0NDIyIn1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjdlNzBmMjk3NDYyNTRjNTA0YjNmOGZkYmFhMmE5ODAxLTYzLTEyIn0
- Timeline: kills/stops of all nodes 143–338. node1 `Could not catchup with peers; continuing to startup` at 244.49. **331.66 kill node2**, stop-marker WARN at 338.08, Startup complete 348.93. node3 stopped at 332.66 and 336.17, Startup complete 357.00. FAIL at 377.69, 20–29 s after two restarts.
- Class: suspect (unsafe-startup confound), the same as hunt-1.

## Failing: Customer output volume (default)
- 158,401 MB over 638 test-hours, which is 248 MB/core-hour against the 200 recommended. The cause is the 6 h turbo run with verbose JVM GC logging (`gc+heap=trace` region dumps on every GC) plus JSON+text duplicate Cassandra logs. Class: harness/noise (not a SUT issue). Lower the GC log level if it matters.
