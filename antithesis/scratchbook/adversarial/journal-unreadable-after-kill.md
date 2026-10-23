# journal-unreadable-after-kill adversarial review: killed node cannot restart (Accord journal CRC) and Guarantee 5 timeout

Reviewer: a fresh sub-agent with no stake, whose brief was to defend the SUT. Source: Cassandra
e874e3a9 (`src/cassandra`). Run: hunt-3 `c16f5775181c00d7a3ac9d8a7607de32-63-12`, plus hunt-1 and
hunt-2.

The claim splits into two parts, and each gets its own verdict:
- **(a)** After a SIGKILL, node2 can never start again. Accord journal open fails with
  `JournalReadError … Crc$InvalidCrc: Read 0`, and the JVM exits with 3 on every attempt.
- **(b)** The cluster was unavailable for more than 120 s after faults stopped (Guarantee 5).

| Part | Verdict |
|---|---|
| (a) | **stands**, with a caveat on how to phrase it (see 1.3) |
| (b) | **harness-caused**: the faults go beyond Guarantee 5's promise, the 120 s window is tight, and the failure is not independent of (a) |

---

## (a) The journal cannot reopen a segment torn by a process kill

### 1. Harness intervention

None found.
- `sut/entrypoint.sh` only renders `cassandra.yaml` and the seeds. It never touches
  `/var/lib/cassandra` beyond `mkdir -p accord_journal`.
- There is no `LD_PRELOAD`, no shim and no recovery script.
- The data volume (`node2-data:/var/lib/cassandra`) persists across restarts.

### 1.2 Configuration: `stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP`

The CRC failure happens under every policy that lets startup continue. Code at
`AccordService.localStartup` (lines 530-575):
- Lines 538-556 compare the markers. If `stopMarker < startMarker`, then:
  - `EXIT` throws.
  - `ALLOW_UNSAFE_STARTUP` and `UNSAFE_STARTUP` log a WARN.
  - `REBOOTSTRAP` sets `rebootstrap = true`. It does not touch the journal.
- `journal.open(node)` comes next, at line 573, and runs unconditionally.
- `rebootstrap` is only consulted later, at lines 595 and 617-621, after the journal is open.

So `REBOOTSTRAP`, the documented automatic recovery for an unclean stop, hits the same
`Metadata.rebuild` → `InvalidCrc` path. Nothing under `service/accord/journal` clears the journal
for a rebootstrap. `ALLOW_UNSAFE_STARTUP` is not the cause; it only lets the run reach the
journal open.

### 1.3 Defence argument: with the default `EXIT`, a killed node never restarts anyway

This is true, and it is the strongest point for the SUT. With defaults, "a SIGKILLed node does not
come back on its own" is designed behaviour. The operator is told the vote log may be incomplete
and has to intervene.

It does not dissolve the bug, for three reasons:
1. **The documented intervention fails too.** The operator's remedy is to rebootstrap. That
   remedy, `REBOOTSTRAP`, opens the journal first and dies the same way (1.2). The other way out
   is `crc_failure_on_rebuild_policy`:
   - It is a field in `AccordConfig.java:399` (default `FAIL`).
   - It is not in `conf/cassandra.yaml`, and no docs mention it (grep of `doc/` and `conf/` is
     empty).
   - So an operator has no documented setting to recover with, short of deleting journal files by
     hand. That would lose the Accord votes the EXIT policy exists to protect.
2. **The code says it tolerates exactly this case.**
   - `ActiveSegment.allocateBytes` writes the size marker early, with the comment "this provides
     safe restart in the event the process terminates abruptly but the host remains stable".
   - `EntrySerializer.tryRead` has a comment and a branch for "If the node was shut down abruptly
     … a log that does not have an index or metadata".
   - `nonZeroCrc` reserves CRC 0 to mean "never written".
   - `RecoverableCrcFailurePolicy.IGNORE_CRC_ZERO_RECORDS` exists for exactly the `Read 0` record.

   The design intends to survive a process kill. The default policy plus
   `fsyncedLimit = Integer.MAX_VALUE` in `Metadata.rebuild` (Metadata.java:140) turn the torn
   record into a fatal error. In `handleReadException`, `bufferPosition <= fsyncedLimit` always
   rethrows, and `StaticSegment.java:462` is the `FAIL` branch. The size marker matched
   `knownLength`, so the error was classified as recoverable, and the policy then refused to
   recover it.
3. **The failure is permanent.** No METADATA component is ever persisted, because the rebuild
   throws before `persist`. So every later restart under any policy fails the same way.

Correct framing: "after a process kill during a journal append, the Accord journal cannot be
opened under any stop-marker policy, including REBOOTSTRAP, with default crc_failure_on_rebuild_policy".
Avoid the framing "killed node cannot restart". That one is also true under default EXIT, but for a documented reason.

### 1.4 Tuning

- `segment_size` is 1 MiB (default 32 MiB). This gives more segments and rollovers, but the torn
  record sits in an ordinary active segment. A larger segment changes how often it happens, not
  whether it can happen.
- `compaction_period` is 10 s. It plays no part, because the failing path is open and rebuild of
  a segment with no metadata, not compaction.
- `flush_mode` is the production default (PERIODIC). It plays no part in the kill-without-fsync
  ordering, because the record is torn in memory before any flush.

### 2. Faults beyond the promise

No. Antithesis `node/kill` is a SIGKILL of the container process, and the page cache survives.

The on-disk state proves it. The record's size marker is present and nonzero, while its header
CRC is 0. If unsynced pages had been dropped (power-loss semantics), a fresh mmap'd tail would
read as zeros. Then `endOffset == 0` would take the clean end-of-segment path
(EntrySerializer.java:120-125) and no error would occur.

The state is a plain crash-consistent process kill: an allocation was reserved and its write
never finished. Even under power-loss semantics, a torn tail is a legitimate crash state. By
comparison, the commitlog tolerates it:
- `CommitLogReader` takes `tolerateTruncation`.
- `CommitLogReplayer.shouldSkipSegmentOnError` skips `permissible` errors "likely due to
  incomplete flush to disk".

In the same branch the commitlog replayed fine ("534 replayed mutations").

### 4. Checker

Not involved. Part (a) is detected by Antithesis's default "container exit code 3" property,
from the JVM's own startup exception, not by the workload.

### 5. Reproduction

The failure reproduced in 3 of 3 hunt runs, on different nodes, with the same signature (`Read 0`
plus a varying computed CRC):

| Run | Node | Time | Detail |
|---|---|---|---|
| hunt-3 `c16f5775…` | node2 | 224.19 | 39 events, segment `log-1791488061546-1-1-1.data`, `Computed -1358688540` |
| hunt-1 `42229a5d…` | node3 | 153.51-153.68 | 50 or more `InvalidCrc` events, all `Read 0, Computed -1028273009` (snouty, this review) |
| hunt-2 `a0534fbf…` | node3 | 156.66 | `JournalReadError … encountered during startup: Crc$InvalidCrc: Read 0, Computed 829902583` (snouty, this review) |

**Verdict (a): stands.** No harness, configuration or checker explanation fits. The only harness
choice involved, `ALLOW_UNSAFE_STARTUP`, is not on the causal path, and `REBOOTSTRAP` would fail
identically.

Residual doubt: all three runs use the same 1 MiB segment and the same harness. A default-size
segment would hit the window less often. This affects frequency only.

---

## (b) Guarantee 5: no transaction within 120 s after faults stopped

Timeline from `logs/hunt3--3323740369927200736.log`:

| vtime | Event |
|---|---|
| 217.43 | stop node1 |
| 217.58 | kill node2 |
| 222.39 | kill node1 |
| 234.95 | kill node3 |
| 236.72 | Faults paused and the `eventually_recovery_probe` starts, 1.8 s after node3 was killed |
| 224.54 | node1 restarts |
| 236.93 | node3 restarts |
| ~239-353 | Both nodes cycle `ACCORD_FETCH_TOPOLOGY_REQ` to each other and to the dead node2 |
| 353.24 | node1 logs `Failed to fetch epochs [38, 38]`, after about 114 s |
| 355.46 | node3 is "fully caught-up with quorums" |
| 358.05 | The probe gives up after 41 connection attempts. CQL never opened on node1 or node3 |

Defence:
- **The faults go beyond Guarantee 5's promise.** Guarantee 5 cites CEP-15's "any minority of replica failures".
  Here every one of the three nodes was killed within 17.5 s, and the last kill was 1.8 s before
  the recovery window opened. That is a whole-cluster restart, not a minority failure.
- **The stall is a bounded, designed retry.** `AccordService.fetchTopologies` (lines 898-933)
  retries the peers, gives up after the retry spec is exhausted, and then "allow[s] Accord to
  start up". Each restarting node waits on its peers, which are also in `localStartup` and do not
  answer. It ended after about 114 s, close to the 120 s window.
- **The 120 s window is not documented.** guarantees.md says "window inferred". Documented
  start-up catch-up bounds are much larger: `catchup_on_start_success_latency` is 60 s and
  `catchup_on_start_fail_latency` is 900 s (AccordConfig.java:314-315).
- **(b) depends on (a).** If node2 had restarted, it would have answered the topology fetch and
  given the restarting nodes their peer. The extra outage is (a) combined with a whole-cluster
  kill. It is not a second, independent availability bug.

A lead worth noting, but not a violation of the stated guarantee: two nodes that restart at the
same time block each other's topology fetch for about 2 minutes. That is a liveness quirk to
investigate separately, with all three nodes healthy.

**Verdict (b): harness-caused.** The fault schedule goes beyond the minority-failure promise, the
window is tight and undocumented, and the failure follows from (a). Report only (a) as journal-unreadable-after-kill.
