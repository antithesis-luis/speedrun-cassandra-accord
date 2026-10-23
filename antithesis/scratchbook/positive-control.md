# Positive control: CASSANDRA-21440, "Accord: CommandChanges.shouldCleanup must maintain EXPUNGE result after data expunged" (upstream commit title: "Expunged records may be resurrected")

- **Public reference:** https://issues.apache.org/jira/browse/CASSANDRA-21440 (Apache JIRA, filed 2026-06-08, status still "Triage Needed", no fixVersion set). The JIRA text: "`CommandChanges.shouldCleanup` short-circuits to `NO` if there is no data, but this is incorrect as `Cleanup.EXPUNGE` may have dropped the data and the record must report cleanup `EXPUNGE`, and be read as an `ERASED` command. **This can lead to linearizability violations.**"
- **Kind:** historical (a real bug that shipped in 6.0-alpha1), not a mutation.
- **Violates:** G1, "Transactions (`BEGIN TRANSACTION … COMMIT TRANSACTION`) spanning several partitions and tables behave as if they ran one at a time, in an order that respects real time … (strict serializability)". It can also show up as a G4 stale read. The control is scored on G1 only.
- **Mechanism (from the fix diff, accord `66cab49f`, `accord-core/.../impl/CommandChange.java`):** once a replica's GC bounds (`RedundantBefore`/`DurableBefore`) pass a txnId, full journal compaction/purge expunges that txn's records. On a later load of that txnId, `Builder.shouldCleanup` returned `NO` because the builder had no data (`!hasUpdate`), and `Builder.construct` returned `null`. `AccordSafeCommand.preExecute` maps `null` to `Command.NotDefined.uninitialised`. So the replica treats a transaction that was decided, applied and erased as one it has **never heard of**, when it should load it as `Erased`/truncated. The fix keeps `EXPUNGE` and returns `Command.Truncated.erased(txnId)`. The upstream regression tests (`AccordExpungeTest`, `AccordJournalConsistentExpungeTest`, both in cassandra `3d40c882`) assert exactly `NotDefined` → `Erased` on `loadCommand` after `journal().purge(...)`.
- **Trigger:** the replica must (1) advance GC/durability bounds past a transaction and run full journal compaction/purge for it, then (2) **load that txnId again**: from a late, delayed or duplicated protocol message for it (PreAccept/Accept/Commit/recovery), from a recovery coordinator querying it, or because the command was evicted from cache, or the node restarted and reloads from the journal. If the replica then answers as "NotDefined", it can, for example, let a recovery coordinator invalidate or re-decide a transaction that was already applied elsewhere, or accept a fresh vote on it. **Honest assessment:** this needs a long-ish run so that several shard-durability/GC cycles and journal compactions complete, **plus** message delay/reordering or a partition that delivers a stale message for an old txnId, or a node pause/kill+restart that leaves a lagging replica to catch up. Upstream does not describe a concrete end-to-end client-visible reproduction; "can lead to linearizability violations" is the author's own statement. The expected time to trigger is therefore uncertain and probably long.
- **Expected symptom (client-observable, as the G1 checker sees it):** a `G1 txn-strict-serializable` `Always` assertion fails after a period with network faults and/or node pause/restart. Specifically one of:
  1. a read-only snapshot transaction over all accounts sees a total ≠ the fixed total, or a negative balance (a transfer applied twice, or applied on only part of its keys, because a replica re-decided an already-erased txn);
  2. a read-only transaction that started after a transfer was acknowledged does not reflect it (a per-account transfer counter is lower than an acknowledged value: a real-time order / stale-read violation), and the acknowledged effect does not reappear later.
  Not a match: timeouts or `WriteTimeout/ReadTimeout` errors, G5 liveness failures, node crash or `AssertionError`/`Invariants` failures in logs on their own, unless accompanied by (1) or (2). Note that `66cab49f` also bundles liveness fixes (ComplexListener notification deadlock, `tryExecuteListening` termination, `SynchronousRecoverAwait` reentrancy). The pre-fix build lacks these too, so a pre-fix G5 failure is **not** evidence for this control.
- **Refs:** `prefix_ref` = `c9ffe116457384200851939e3687f81c00015e02` (= `fix_ref^`, the first parent; its `modules/accord` = `0a10cd056794c05588114f45ce86d49d6d6538db`, which lacks the fix), `fix_ref` = `3d40c8825c8b06bcbd8378d698f6d2f3bf5dc25e` (Cassandra commit bumping `modules/accord` to accord `66cab49f1c9af471795339a5fdf9522e6e73b691`; committed directly, so there's no PR. Links: https://github.com/apache/cassandra/commit/3d40c8825c8b06bcbd8378d698f6d2f3bf5dc25e, https://github.com/apache/cassandra-accord/commit/66cab49f1c9af471795339a5fdf9522e6e73b691)
- **Fix absent at prefix (checked):** at accord `0a10cd0`, `CommandChange.Builder.shouldCleanup` still begins `if (!hasUpdate) return NO;` (line 361) and `construct` still begins `if (!hasUpdate) return null;` (line 600) with `case EXPUNGE: return null;`. At current `fff32de2` both are gone, and the comment "we cannot short-circuit !hasUpdate, as we might have been expunged and should return Erased" (line 603) is present. `git diff 0a10cd0 fff32de2 -- CommandChange.java` contains only the fix hunk.
- **Affected releases:** cassandra-6.0-alpha1 (accord `93d78be`) and every 6.0/trunk build before `3d40c882` (2026-06-18). Fixed in cassandra-6.0-alpha2.
- **Build:** ok (first attempt, 3m13s for the ant step). Toolchain `eclipse-temurin:11-jdk` + Apache Ant 1.10.14 (binary tarball) + accord's bundled `gradlew`. Log: `antithesis/scratchbook/logs/build-prefix-21440.txt`. Dockerfile: `antithesis/scratchbook/logs/p6b/Dockerfile`.

## Run mode: pre-fix commit (chosen) vs fix reverted on current

**Chosen: `prefix-commit`, with `prefix_ref = c9ffe116` (= fix^).**

What lies between `prefix_ref` and current (`cassandra-6.0-alpha2`, `e874e3a9`):
- **Cassandra:** 97 commits in `c9ffe116..e874e3a9`, of which 51 are non-merge and one is the fix itself. Of the 50 non-merge commits after the fix, only one touches `src/java/org/apache/cassandra/service/accord` (`e1e56e5d` "Add CMS membership directly to ClusterMetadata", 4+/2− lines there). The rest are 4.0/4.1/5.0 merge-ups, release prep, nodetool/cqlsh/doc/test changes and a few storage/TCM changes (`44ee9d61` TCM log catch-up with gaps, `9a896cba` CMS host policy, `b1f30e94` longer TCM timeouts, `1df3a8ce` async transformation before internode request, `d46b8a82` cancelled read → TIMEOUT, `9ddfe0fb` response streamId, `251b0e9b` CBUtil length bound).
- **Accord submodule:** `0a10cd0..fff32de2` = 3 commits: `2cdda7f` "(BTree)?ReducingRangeMap fixes and improvements" (latent BTree foldl bug), `66cab49` (the fix plus its bundled fixes), and `fff32de` (pom-only).

Why the pre-fix commit:
- It is exactly `fix^`, the state that really existed upstream. No hand-made patch, so there's no risk that a revert silently fails to bring back the bug.
- It is close to current. The non-Accord drift is small, and the only other Accord-library difference is `2cdda7f`.
- The build path is identical to current (same JDK 11, ant, gradle), so the build check below covers it.

Why not "fix reverted on current", though it's viable and kept as the fallback:
- `git apply --check -R` of the `CommandChange.java` hunk of `66cab49` applies cleanly on `fff32de2`. `CommandChange.java` is unchanged between `66cab49` and `fff32de2`, and between `0a10cd0` and `fff32de2` it differs only by the fix. So a single-file revert on current would reproduce the pre-fix bug path exactly, and would also isolate it from the bundled liveness fixes and `2cdda7f`.
- But it needs a submodule patch in the harness's PATCH_SET. The fix commit also bundles ~10 other changes across 24 accord files and 33 Cassandra files, so "current minus one hunk" is a code state that never shipped.
- **Switch to it** if pre-fix runs are dominated by unrelated pre-fix liveness failures (G5) that stop the G1 check from running long enough.

## Fault needs

| Fault | Needed for | In the standard `boost_test` set? |
|---|---|---|
| Network delay / reordering / partition between SUT nodes | late or stale messages for an already-GC'd txnId; recovery by another coordinator | yes (network faults) |
| Node pause (SIGSTOP) | a replica lags behind while the others advance GC bounds, then catches up with stale state/messages | yes (node pause) |
| Node termination + restart | reload of commands from the journal after expunge | yes (node termination). The harness must restart the killed Cassandra container |
| CPU throttle | not required; it can widen timing windows | yes (node throttle) |
| Clock jumps | not required | n/a |

No missing fault type, so no "Missing fault type" message is needed.

## Class-level tuning proposed for `SB/tuning.md` (judged by workload-guidance section 4)

- Make **durability and GC cycles frequent**: a short `accord.shard_durability_cycle` (upstream's own expunge test uses `20s`) and a short global durability cycle, so that `RedundantBefore`/`DurableBefore` GC bounds advance many times per run. This is a general class, "transactions being retired/garbage-collected", which matters for every guarantee (G1–G5), not just this bug.
- Make **Accord journal compaction/purge frequent** (small journal segment size / frequent compaction), the general class "data being flushed and compacted on disk".
- Possibly a **smaller Accord command cache**, so that commands are reloaded from the journal rather than served from memory (the class "cold loads from persistent state"). It's borderline. Only adopt it if it's justified for G3 durability in its own right.

## Considered and not used

- Scripting a sequence that waits for `minGcBefore` to pass a txnId and then replays a message for it (bug-specific trigger, forbidden).
- Calling `journal().purge(...)` or nodetool/JMX to force a purge for specific txnIds (bug-specific, and a fault mechanism outside the client API).
- Reducing replication or topology just to make a lagging replica more likely (topology chosen only for this bug's preconditions).
- Disabling `accord.ephemeral_reads` because the upstream test does (bug-specific; it doesn't change a class of behaviour that the other guarantees need).

## Criteria

| | Criterion | Evidence |
|---|---|---|
| a | Violates a T2 guarantee | The JIRA says "can lead to linearizability violations". The mechanism makes an applied+erased txn look `NotDefined` to a replica, which can lead to it being re-decided or invalidated: a G1 breach (lost or duplicated transfer, stale read). |
| b | Needs faults/concurrency | It needs GC bounds to advance and the journal to be purged, **then** a late/duplicated message, recovery, or restart reload for that txnId. That means network delay/partition, pause or kill/restart over a long run. A single-threaded unit test only catches it with the explicit purge call that upstream added. |
| c | Public and recognizable | Weak-to-moderate: a public Apache JIRA by the Accord author (Benedict Elliott Smith), reviewed by Alan Wang and Alex Petrov. There's no Jepsen report, CVE or postmortem. It's the most recent Accord fix in the chosen release, and the only candidate whose public text names a client-visible anomaly. |
| d | Cheap to build | `fix^` is 4 months old, uses the same toolchain as current (JDK 11, ant, accord gradlew), and its dependencies resolve. Build result is below. |

## Local build check

- **Result: ok, on the first attempt** (2026-10-08). `docker build` of `logs/p6b/Dockerfile` (it clones apache/cassandra with `--filter=blob:none`, checks out `c9ffe116`, and runs `git submodule update --init modules/accord`) was tagged `cassandra-accord-cassandra:c9ffe116-p6b`.
- The submodule checked out at `0a10cd056794c05588114f45ce86d49d6d6538db`, which is the pre-fix accord.
- `ant -Dno-checkstyle=true -Drat.skip=true jar`: BUILD SUCCESSFUL in 3m13s. It produced `build/apache-cassandra-6.0-alpha2-SNAPSHOT.jar` (15.3 MB) and `build/lib/jars/cassandra-accord-6.0-alpha2-SNAPSHOT.jar` (2.2 MB). Accord was built via `_build-accord` → `gradlew clean build -x test …`.
- Toolchain: `eclipse-temurin:11-jdk`, Apache Ant 1.10.14, and accord's bundled Gradle wrapper. All dependencies resolved from Maven Central.
- The `-p6b` image was removed afterwards (`docker rmi`). Builder cache was not pruned, because the cache this build created can't be targeted on its own.

## Other candidates considered

- **CASSANDRA-20325** "Accord: Fix recovery when one shard is committed/stable and another is preaccepted" (G1/G2; fix cassandra `64c4aa88`, pre-fix `3fb23e02`): not chosen. Its pre-fix tree is ~16 months behind current (JDK 11/17 only), so many since-fixed Accord bugs would muddy attribution, and its public text names no client-visible anomaly.
- **CASSANDRA-20292** "Accord: Various fixes" (fast-path must still wait for earlier txns; G1; pre-fix `080d6c63`): not chosen. It's an omnibus patch, hard to attribute, and the tree is old.
- **Injected mutation** (fallback): not needed while a historical candidate builds.
