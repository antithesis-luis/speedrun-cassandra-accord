# A node killed during an Accord journal append can never restart

- **Finding name:** `journal-unreadable-after-kill`
- **Guarantee:** [Guarantee 5](../../../speedrun-report.md#guarantee-5): "Once failures stop, a
  transaction against the cluster succeeds again within 120 s (availability after recovery)". The
  promise this rests on is CEP-15's "latency and performance should be unaffected by any minority
  of replica failures": a node that can never come back turns every later fault into a majority
  failure.
- **Version:** Apache Cassandra cassandra-6.0-alpha2, [`e874e3a9`][c-commit], with Accord
  [`fff32de2`][a-commit]. The journal code is in Cassandra itself.
- **Summary in the report:** [the finding](../../../speedrun-report.md#journal-unreadable-after-kill)
- **The proposed fix:** [journal-unreadable-after-kill.patch](../../fixes/journal-unreadable-after-kill.patch)
  ([Fix](#fix))
- **Evidence:** [the adversarial review](../adversarial/journal-unreadable-after-kill.md)

**Status: root cause established**, with high confidence: the stack trace matches the source line
for line, and the on-disk bytes of the failing entry were reconstructed exactly from the logged
checksum.

**Where it failed.** Found by Antithesis's default "container exit code" check in the longest
hunt ([`c16f5775`][r-c16f5775], 360 minutes, all fault types): 45 failing examples, all from one
event. The same failure happened in all three default-configuration hunts with node kills. The
log links open the Antithesis logs explorer at that moment (they need a login to the tenant).

| Timeline | Run, build | Failure | Log |
|---|---|---|---|
| [Timeline A](#timeline-a) | [`c16f5775`][r-c16f5775], current | node2 exits with code 3 at vtime 224.71, and on every later restart | [log][l-journal-c16f] |
| [Timeline B](#timeline-b) | [`72728337`][r-72728337], current + the proposed fix | the same kind of torn entry on node2 at vtime 395.25; the patch treats it as the end of the segment and startup continues | [log][l-journal-fix] |

## Symptom

In Timeline A, Antithesis killed node2 (SIGKILL) at vtime 217.58. On restart, Cassandra replayed
its commit log, then failed to open the Accord journal, and the container exited with code 3:

```text
224.1250  node2  CommitLog.java:211 - Log replay complete, 534 replayed mutations in 151 ms
224.1906  node2  Exception (org.apache.cassandra.journal.JournalReadError) encountered during startup:
                 org.apache.cassandra.utils.Crc$InvalidCrc: Read 0, Computed -1358688540
                 JournalReadError in /var/lib/cassandra/accord_journal/log-1791488061546-1-1-1.data
                   at org.apache.cassandra.journal.StaticSegment$SequentialReader.doAdvance(StaticSegment.java:462)
                   at org.apache.cassandra.journal.Metadata.rebuild(Metadata.java:142)
                   at org.apache.cassandra.journal.StaticSegment.open(StaticSegment.java:121)
                   at org.apache.cassandra.service.accord.AccordService.localStartup(AccordService.java:573)
                 Caused by: … EntrySerializer.validateCRC(EntrySerializer.java:259)
                            … EntrySerializer.tryRead(EntrySerializer.java:144)
224.7137  containers_meta  container died cassandra-accord-node2 exit=3
```

"Read 0" means the entry's header checksum on disk is zero. The bytes stay on disk, so every later
start reads them again and fails the same way: node2 is gone for good.

## How the tests got there

| vtime | What happened | Command |
|---|---|---|
| ~71 | node2 starts and creates journal segment `log-1791488061546-1-1-1` (1 MiB segments in this setup) | (Cassandra) |
| 217.35–217.43 | node3 is throttled; node1 is stopped | fault injector |
| **217.58** | **node2 is killed** (exit 137) while that segment is still the active one | fault injector |
| 220.21 | node2's container restarts | (Antithesis restarts every container it kills) |
| 224.13 | Commit-log replay succeeds; Accord starts; our restart setting lets it past the stop-marker check | (Cassandra) |
| **224.19** | Opening the journal fails with `InvalidCrc: Read 0`; exit 3 at 224.71 | (Cassandra) |
| 222.39, 234.95 | node1 and node3 are killed too, so the cluster runs without a majority for a while | fault injector |

No test command took part: the failure is in node startup, and Antithesis's default check caught
it. The workload's writes (all commands) are what keep the journal busy.

## What the logs show

<a id="timeline-a"></a>
### Timeline A: node2 never comes back

[Timeline A in the logs explorer][l-journal-c16f], at the exit.

```text
217.5777  fault_injector   FAULT node/kill nodes=cassandra-accord-node2 max=2.0s
217.5879  containers_meta  container died cassandra-accord-node2 exit=137
220.2129  containers_meta  container start cassandra-accord-node2
224.1252  node2  AccordService.java:460 - Starting accord with nodeId 2
224.1799  node2  WARN AccordService.java:549 - Stop marker is older than start marker (-1<1791488061537), so cannot
                 assume we have a complete log of our votes in any consensus groups. Continuing to startup as configured.
224.1910  node2  ERROR CassandraDaemon.java:1023 - Exception encountered during startup
                 org.apache.cassandra.journal.JournalReadError: org.apache.cassandra.utils.Crc$InvalidCrc: Read 0, Computed -1358688540
224.7137  containers_meta  container died cassandra-accord-node2 exit=3
```

What this shows:
- **The kill is an ordinary process kill.** The host and its page cache survive; only the Cassandra
  process dies.
- **The failure is in opening the journal**, after the commit log replayed fine.
- **The restart setting isn't the cause.** The WARN at 224.18 is our unsafe restart setting letting
  startup continue. Under the documented safe setting, `REBOOTSTRAP`, the journal is opened first
  too, and fails the same way ([adversarial review](../adversarial/journal-unreadable-after-kill.md)).

**The on-disk bytes, reconstructed.** Every checksum here starts from the same seed bytes, and the
header checksum covers the entry's 4-byte next-offset and its 25-byte key. Searching every
next-offset in [0, 64 MiB) with an all-zero key gives exactly one value that produces
`-1358688540`: **376460**. So the failing entry has a valid length marker pointing about 367 KiB
into the 1 MiB segment, followed by a zero key and a zero checksum: its space was reserved, and
nothing was written into it.

**Across the runs.** In this run, `Read 0, Computed` appears at 39 distinct moments between
224.19 and 231.73, all on node2, all naming the same file with the same computed checksum: every
timeline that branches after the kill inherits it, which fits a persistent on-disk state. By
contrast, the warning that marks a restart after a kill appears at more than 980 moments on all
three nodes, and most of those restarts succeed, so the kill has to land inside the append. The
same `Read 0` failure happened on node3 in hunt [`42229a5d`][r-42229a5d] (from vtime 153.51; on
node1 too, where the checksum again matches "length marker plus zero key" exactly, at offset
130318) and on node3 in hunt [`a0534fbf`][r-a0534fbf] (vtime 156.66).

<a id="timeline-b"></a>
### Timeline B: the same torn entry, with the proposed fix

[Timeline B in the logs explorer][l-journal-fix], at the patch's warning.

```text
387.7858  fault_injector   FAULT node/kill nodes=cassandra-accord-node2 max=2.0s
387.9630  containers_meta  container died cassandra-accord-node2 exit=137
390.2129  containers_meta  container start cassandra-accord-node2
395.2533  node2  WARN StaticSegment.java:475 - Unfinished journal entry at offset 277678 in
                 /var/lib/cassandra/accord_journal/log-1791515045562-1-1-1.data, segment was active at crash;
                 treating it as end of segment
395.3311  node2  INFO AccordService.java:418 - Starting journal replay.
395.4328  node2  INFO Replay.java:114 - Completed replay of [accord_ks.accounts|tid:16|0,0,2]
```

What this shows: the same signature (a zero checksum after a consistent length marker) recurred on
node2, the patch recognised it, and node2 went on into journal replay without error. This branch
of the timeline ends at 395.43, before Cassandra logs "Startup complete".

## Root cause

**In plain language.** The Accord journal appends entries to a memory-mapped file in two steps. It
first reserves space by writing the entry's length, then writes the body and, last, the
checksums. A checksum of 0 is reserved to mean "never written". If the process is killed between
the two steps, the file holds a slot with a valid length and a zero checksum. That entry was never
flushed to disk and never acknowledged. On restart, the segment that was active at the kill has no
metadata file, so the journal rebuilds it by scanning the data file. The scan treats the whole file
as if it had been flushed, so it can't tell an unfinished tail from real corruption. With the
default `crc_failure_on_rebuild_policy = FAIL`, startup aborts. The metadata is never written, so
every restart repeats the same scan and fails.

**Precisely, at the tested commit:**
- **Write path: length first, checksums last.** `ActiveSegment.allocateBytes` writes the new
  entry's length marker immediately on allocation ([`ActiveSegment.java:433`][c-activesegment-433]),
  by design, "to allow restart after an abrupt process exit". `EntrySerializer.write` then writes
  the key and body, and the header and record checksums last
  ([`EntrySerializer.java:74-77`][c-entryserializer-74]); a written checksum is never 0
  ([`nonZeroCrc`][c-entryserializer-250]). Several threads can hold allocations at once, so entry N
  can still be empty while entry N+1 is complete.
- **Durability never passes an unfinished entry.** `fsync` only advances to the point every
  allocation before it has finished writing, so an entry with a zero checksum, and everything after
  it, was never synced or acknowledged.
- **Metadata is written only when a segment closes.** The segment active at the kill has a data
  file but no metadata file.
- **Startup.** `StaticSegment.open` finds no metadata ([`StaticSegment.java:107`][c-staticsegment-107])
  and calls `Metadata.rebuild` ([line 121][c-staticsegment-121]), which scans with the synced limit
  set to `Integer.MAX_VALUE` ([`Metadata.java:140`][c-metadata-140]): the whole file counts as
  synced. The header checksum check fails ([`EntrySerializer.java:144`][c-entryserializer-144]); an
  error inside the synced limit is always rethrown, and the default policy's `FAIL` branch throws
  `JournalReadError` ([`StaticSegment.java:462`][c-staticsegment-462]). The default is set in
  [`AccordConfig.java:399`][c-accordconfig-399]. The error reaches `AccordService.localStartup`
  ([`AccordService.java:573`][c-accordservice-573]) and the daemon exits with code 3.
- **Every stop-marker policy reaches this.** `localStartup` compares the stop and start markers,
  then opens the journal unconditionally; `REBOOTSTRAP` is consulted only after the journal is
  open. The way out, `crc_failure_on_rebuild_policy`, isn't in `cassandra.yaml` or the docs.

The class comment of the reader says errors "in unsynced portions of segments are treated as
segment EOF". During a rebuild the unsynced portion is never identified, so a torn tail that is
harmless by design becomes fatal.

## Fix

**The patch:** [journal-unreadable-after-kill.patch](../../fixes/journal-unreadable-after-kill.patch)
(`StaticSegment.java` and `Metadata.java`, +49/−6)

Recognise the crash-torn tail precisely and treat it as the end of the log, without relaxing
checksum checking anywhere else:
1. In `StaticSegment.open`, mark a segment whose metadata file is **absent** as active at the
   crash. Only a segment that was never closed can have a torn tail. A present-but-unreadable
   metadata file still takes the strict path.
2. Pass that through the rebuild to the sequential reader.
3. In the reader, after the existing length-marker consistency check, an entry with a zero checksum
   in such a segment logs a WARN and ends the segment. The rebuild records that offset as the synced
   limit and persists it, so later readers and later restarts never look past it.

**Why it's safe.** A zero checksum can't come from a completed write, and the synced position never
passes an unfinished allocation, so everything dropped was never synced and never reported durable.
Closed segments, corrupt metadata, non-zero checksum mismatches and inconsistent length markers stay
fatal. The cost: complete-but-unsynced entries after the hole are dropped too, which matches the
journal's periodic durability contract. A config-only alternative,
`crc_failure_on_rebuild_policy: IGNORE_CRC_ZERO_RECORDS`, applies to every rebuild, including
corrupt metadata on closed segments, so it's less precise. Torn pages after a power loss, where the
checksum slot could hold garbage, remain fatal by design.

**How it was checked: verified, with a caveat.** Run [`72728337`][r-72728337] (120 minutes, the
same fault types as the run that found it) built current [`e874e3a9`][c-commit] plus this patch.
The torn tail recurred on node2 after a kill (vtime 386.46 or 387.79, depending on the branch), in four sibling timelines
(394.52–395.25), and the patch logged its warning each time ([Timeline B](#timeline-b)). The run had
**no journal-error exits, against 45 in the unpatched run that found the bug.** Caveat: the
downloaded branch ends during journal replay, before "Startup complete", so full startup wasn't
observed on that branch. The run's one remaining exit 3 is a different failure: a node killed during
compaction failed to start with "inconsistent disk state" in Cassandra's table-file transaction log,
not the Accord journal. The patch was not compiled locally (no JDK); it compiled in the image build.
It has no unit test yet. A suggested one: in `SegmentTest`, leave an allocation unwritten, delete the
metadata and index files, open the segment, and expect the synced limit at that allocation's start
with every earlier record readable; with metadata present, or a non-zero bad checksum, it must still
throw.

## Comparison with upstream

Compared with Cassandra trunk at [`36d2433d`][c-trunk], read but not built or run.

- **Already known? Not as a bug.** The building blocks are known:
  [CASSANDRA-21355](https://issues.apache.org/jira/browse/CASSANDRA-21355) added the opt-in
  `IGNORE_CRC_ZERO_RECORDS` policy for exactly this zero-checksum case, but it applies to every
  rebuild, isn't in `cassandra.yaml` or the docs, and the default stays `FAIL`. Related, resolved:
  [CASSANDRA-20661](https://issues.apache.org/jira/browse/CASSANDRA-20661) (checksum errors in the
  journal), [CASSANDRA-20717](https://issues.apache.org/jira/browse/CASSANDRA-20717) (journal
  corruption detection), [CASSANDRA-20702](https://issues.apache.org/jira/browse/CASSANDRA-20702)
  (unsafe startup; it doesn't cover this path). Open:
  [CASSANDRA-21692](https://issues.apache.org/jira/browse/CASSANDRA-21692) changes error-position
  handling in `EntrySerializer`, which doesn't help here because the rebuild treats every position
  as synced.
- **Present on trunk? Yes, from reading.** The four journal files involved are byte-identical
  between the tested commit and trunk, and the default is still `FAIL`. The only trunk commit in the
  journal package since, [`4da20e07`][c-4da20e07] (Improve Rebootstrap), touches compaction only.
  The patch should apply to trunk unchanged (not re-checked).
- **Suggested upstream issue (not filed).** *Accord journal: a process kill during an append leaves
  an unfinished entry (checksum 0) that makes Metadata.rebuild fail startup permanently.*
  > `ActiveSegment.allocateBytes` writes an entry's length marker before its payload and checksums.
  > A SIGKILL in that window leaves a slot with a valid marker and a zero checksum in the active
  > segment, which has no metadata file. On restart, `Metadata.rebuild` scans with the synced limit
  > at `Integer.MAX_VALUE`, so this never-synced, never-acknowledged entry is treated as corruption,
  > and the default `crc_failure_on_rebuild_policy = FAIL` aborts startup on every attempt, under
  > every stop-marker policy including REBOOTSTRAP. Seen 3 times under Antithesis node-kill faults.
  > Proposed: for segments without persisted metadata, treat the first entry with a valid marker and
  > a zero checksum as the end of the segment, and persist that limit.
- **Caveat:** the root cause was worked out before searching upstream, but the model may have seen
  related code or reports in its training data.

[c-commit]: https://github.com/apache/cassandra/commit/e874e3a90b1942b945477e6d9ba03880b4f4a19d
[a-commit]: https://github.com/apache/cassandra-accord/commit/fff32de2e915772fbc70d16b1c32346313877838
[c-trunk]: https://github.com/apache/cassandra/commit/36d2433dfb2fd26fb8719716edf1b5f3232df8d3
[c-4da20e07]: https://github.com/apache/cassandra/commit/4da20e07e8c00675875a47e3d0ee758e3a269e80
[c-activesegment-433]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/journal/ActiveSegment.java#L408-L437
[c-entryserializer-74]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/journal/EntrySerializer.java#L46-L78
[c-entryserializer-250]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/journal/EntrySerializer.java#L250-L254
[c-entryserializer-144]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/journal/EntrySerializer.java#L144
[c-staticsegment-107]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/journal/StaticSegment.java#L107
[c-staticsegment-121]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/journal/StaticSegment.java#L121
[c-staticsegment-462]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/journal/StaticSegment.java#L446-L472
[c-metadata-140]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/journal/Metadata.java#L136-L154
[c-accordconfig-399]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/config/AccordConfig.java#L399
[c-accordservice-573]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/service/accord/AccordService.java#L530-L575

[r-c16f5775]: https://honey-whale.antithesis.com/report/xeFXBGscPgpTrEh3HgeiBn3r/ZXj-4QdSO3r-ImhAo-tFncJktsaXb_DSbBvEmgwtQGw.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA5VDAxOjI4OjEzLjg5MzA2MDk0NVoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiWlhqLTRRZFNPM3ItSW1oQW8tdEZuY0prdHNhWGJfRFNiQnZFbWd3dFFHdy5odG1sIiwicmVwb3J0X2lkIjoieGVGWEJHc2NQZ3BUckVoM0hnZWlCbjNyIn19fSdJ3KhdpBr-SnSTAwI4wfBSIzIOBLRhj70vJ-rqgY2vQBH3fQ21j3BM1XbZJNgZLDBQ_nC_jq4KZbpqZhE2kAU
[l-journal-c16f]: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjI0LjcxMzc3NzIxMTk2MDQifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiLTg1NDUyMzYzODg2MzkyMDA1MTMifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiN2U3MGYyOTc0NjI1NGM1MDRiM2Y4ZmRiYWEyYTk4MDEtNjMtMTIifQ
[r-72728337]: https://honey-whale.antithesis.com/report/P_R9YbTsqw1km0R8_OuKPW9a/3WKRRGDGU2s5GEzzNXEnyJkDvHQuDK6jdxs85Pc_4N0.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA5VDA0OjM0OjU5LjE1MjkxMDA1MFoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiM1dLUlJHREdVMnM1R0V6ek5YRW55SmtEdkhRdURLNmpkeHM4NVBjXzROMC5odG1sIiwicmVwb3J0X2lkIjoiUF9SOVliVHNxdzFrbTBSOF9PdUtQVzlhIn19fRomXZHON3xxI53t10DadoDAbjC5JHXyVKX81mFUjz75a6IDVaDhI9ZvnLi6ioaJHHotzmBnNvxUXsITP09izAY
[l-journal-fix]: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMzk1LjI1MzMxMTg5ODMyNjUifV0sIm8iOiJvciJ9LHsiaCI6W3siYyI6Im1vbWVudC5pbnB1dF9oYXNoIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiLTQ1NDk5NjU1MDMxMzEwNTYzOTIifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiNmY3NDg2ZDI2ZDBlM2QyOWYzMjdjNGQ0YzAwNjJhMWMtNjMtMTIifQ
[r-42229a5d]: https://honey-whale.antithesis.com/report/NktZzXJr0UO579BjgdL5Mfs8/WahXSL5t4V92DlKQs1q_ypABQrL0eoB0t4m9lTR2aRQ.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA5VDAwOjQ1OjUwLjE3MzY4NTQyNloiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiV2FoWFNMNXQ0VjkyRGxLUXMxcV95cEFCUXJMMGVvQjB0NG05bFRSMmFSUS5odG1sIiwicmVwb3J0X2lkIjoiTmt0WnpYSnIwVU81NzlCamdkTDVNZnM4In19fWrNFp5DNmFdjXAMDyLShAIiDFVbFBq3o-ivCj39i3X6r5xWrcK63PhPBBMfCW9XFdEfA-U-ykSWQds9ci3dMAE
[r-a0534fbf]: https://honey-whale.antithesis.com/report/Yrr8xPIhKvFwB5cxwbUjo71N/Tm3uCc675KWtl0XjMrwy-dUm6jzy_CBpF7n9t6Abiac.html?auth=v2.public.eyJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiVG0zdUNjNjc1S1d0bDBYak1yd3ktZFVtNmp6eV9DQnBGN245dDZBYmlhYy5odG1sIiwicmVwb3J0X2lkIjoiWXJyOHhQSWhLdkZ3QjVjeHdiVWpvNzFOIn19LCJuYmYiOiIyMDI2LTEwLTA5VDAwOjUxOjEzLjYzNDE5NjA3NloifVZ8QpGpm__rQ6n-dlgWEtEZ7XGKnMDfCqEmwwxwDmgxYqPfOKeW-AW2lt_3S8p9YYsaHUvE6MqbNI69FpADSwI
