# System under test: Apache Cassandra with Accord

**Decision:** Apache Cassandra @ `cassandra-6.0-alpha2` (`e874e3a90b1942b945477e6d9ba03880b4f4a19d`, peeled; annotated tag object `0552d0d84c9718ec10b677329462547d5e216ddc`), built from source including its `modules/accord` submodule at `fff32de2e915772fbc70d16b1c32346313877838` (apache/cassandra-accord). Chosen by **rank 0**: the customer's own software, open-source (Apache-2.0) and buildable.

Run it with `accord.enabled: true`, keyspaces/tables `WITH transactional_mode='full'`, and clients using `BEGIN TRANSACTION … COMMIT TRANSACTION` plus plain CQL.

## Why the Accord engineers will recognize this

Accord is a library with no release tags of its own. Users only get it inside Apache Cassandra, where `modules/accord` is pinned as a git submodule and exposed through `BEGIN TRANSACTION` CQL and `transactional_mode='full'` tables. `cassandra-6.0-alpha2` is the newest Cassandra release that ships Accord. Its submodule commit `fff32de` ("Inherit pom from apache parent", 2026-05-31) sits on the tip of the cassandra-accord history at that point and contains every Accord fix up to CASSANDRA-21440. So testing a 3-node Cassandra 6.0-alpha2 cluster tests the exact Accord code (coordination, recovery, journal, CommandsForKey, durability scheduling) that the cassandra-accord committers ship, running inside the integration they maintain.

## Guarantee coverage on Cassandra 6.0-alpha2 + Accord

| ID | Expressible? | How / why not |
|---|---|---|
| G1 | yes | Multi-partition `BEGIN TRANSACTION` transfers (LET/IF/UPDATE) plus read-only snapshot transactions over a `transactional_mode='full'` table |
| G2 | yes | One transaction writes the same token to two tables/partitions, and later transactions read both |
| G3 | yes | Acknowledged transactional appends are recorded client-side and read back after kill/restart of a minority of nodes |
| G4 | yes | Plain INSERT/UPDATE/SELECT on a `transactional_mode='full'` table, coordinated by any node |
| G5 | yes | `eventually_` retry loop of a small read-write transaction after faults stop |

Every guarantee is in the OSS build. There is no enterprise-only edition.

## Candidates considered

| Candidate | Rank | Buildable + licence | Topology ≤4+1 | ≥2 of top-3 guarantees | Control candidate | Runs in Antithesis | Verdict |
|---|---|---|---|---|---|---|---|
| Cassandra `cassandra-6.0-alpha2` (`e874e3a9`) + accord `fff32de` | 0 | ☑ ant + JDK 11 (default; 11/17/21 supported), Apache-2.0 | ☑ 3 nodes + 1 client | ☑ G1–G5 | ☑ CASSANDRA-21440 (+2 more, below) | ☑ no cloud or hardware deps | **Chosen**: latest release that ships Accord |
| Cassandra `trunk` HEAD (`fb7fe354`) | 0 | ☑ | ☑ | ☑ | ☑ same candidates | ☑ | Viable but rejected: not a release, and it moves during the trial |
| Cassandra `cassandra-6.0-alpha1` (`1ee7ed7d`, accord `93d78be`) | 0 | ☑ | ☑ | ☑ | ☑ (CASSANDRA-21440 still unfixed there) | ☑ | Rejected as current because it's older and lacks ~11 Accord fix commits. Could serve as a release-tagged pre-fix if P6b wants one, but it muddies the comparison (it also predates CASSANDRA-21355/21361/21835) |

## Machine estimate

Per build: builder image with JDK 11, ant and the accord gradle wrapper is about 1.2 GB. The maven/gradle dependency cache is about 1.5 GB and is shared if cached. A built tree (build/, modules/accord/accord-core/build) is about 1.5–2.5 GB. The runtime image (JRE 11 + Cassandra lib) is about 0.6 GB. A build takes about 15–25 min on 16 CPUs and peaks at 3–5 GB RAM.

For about 4 builds (current, pre-fix, 2 fix-verifies) with shared caches: roughly 1.2 + 1.5 + 4×(2 + 0.6) ≈ 13 GB worst case, or about 6 GB if builder stages are pruned after each build. That fits in the ~35 GB free, but pruning dangling builder layers is advised because other workspaces share the disk.

Run: 3 nodes × (1–2 GB heap + ~1 GB off-heap/JVM) ≈ 6–9 GB RAM, plus a client of about 0.5 GB. That fits the 62 GB machine. No S12.

## Positive-control candidates (handed to P6b)

All three were fixed in apache/cassandra-accord and picked up by a Cassandra submodule bump that is an ancestor of `cassandra-6.0-alpha2`. P3 evaluated six bug candidates in total (see "Rejected" below).

1. **CASSANDRA-21440, "Accord: CommandChanges.shouldCleanup must maintain EXPUNGE result after data expunged" (leading).** Link: https://issues.apache.org/jira/browse/CASSANDRA-21440. The JIRA text says: "the record must report cleanup EXPUNGE, and be read as an ERASED command. **This can lead to linearizability violations.**"
   - Violates **G1** (could also surface as a G4 stale read).
   - Fix: accord `66cab49f1c9af471795339a5fdf9522e6e73b691` ("Expunged records may be resurrected"). Cassandra submodule bump `3d40c8825c8b06bcbd8378d698f6d2f3bf5dc25e` (2026-06-04).
   - **Pre-fix Cassandra commit:** `c9ffe116457384200851939e3687f81c00015e02`, whose submodule is accord `0a10cd0`.
   - Affected: everything before the fix, including 6.0-alpha1.
   - Trigger: a transaction record is garbage-collected (expunged) from the Accord journal after durability/GC bounds advance. Later, a late, delayed or retried message, or a reload after restart, for that txnId reads back as `NotDefined` rather than `Erased`. The replica then treats an already-decided transaction as unknown, which can feed a wrong decision into recovery.
   - Reachable with network delay/partition plus node restart over a long enough run for GC/durability cycles to pass. It needs no special scripted sequence.
   - Fault types: network delay/partition, node kill/restart. Nothing beyond the default set.
   - Caveats: JIRA has status "Triage Needed" with no fixVersion, but the fix is in the alpha2 tree. The same commit bundles other fixes, including a deadlock in ComplexListener notification, which is G5-relevant.
   - Revert option: the core hunk in `accord-core/src/main/java/accord/impl/CommandChange.java` (`shouldCleanup`) is small, so the revert-on-current path is plausible.

2. **CASSANDRA-20325, "Accord: Fix recovery when one shard is committed/stable and another is preaccepted".** Link: https://issues.apache.org/jira/browse/CASSANDRA-20325.
   - Violates **G1/G2**: recovery of a multi-shard transaction fails to "create a correct edge with recovery of earlier transactions", so the ordering is wrong.
   - Fix: accord `1542da5d8acf08b8226227c91d4f81c64ed9762c`. Cassandra `64c4aa88f56da790d6a96e23828a8b162a905e2b` (2025-02-13).
   - **Pre-fix Cassandra commit:** `3fb23e0247d73c1e1e8e0e9a3ee2d2a41cb405cb`. That build supports JDK 11/17 only.
   - Trigger: the coordinator crashes or is partitioned mid-commit of a multi-shard transaction, and another node recovers it.
   - Downside: the pre-fix tree is about 16 months behind current, so other since-fixed bugs may fire first.

3. **CASSANDRA-20292, "Accord: Various fixes".** The relevant item is "Even if we can decide autonomously that we took the fast path, we must still wait for earlier transactions to decide themselves". Link: https://issues.apache.org/jira/browse/CASSANDRA-20292.
   - Violates **G1** (execution order or dependency violation).
   - Fix: accord `344c20b6d22898ea2bf272c8f20a720bb9c35979`. Cassandra `d7ed1ad3915c6e83d78086a5f781306a028937ea` (2025-02-05).
   - **Pre-fix Cassandra commit:** `080d6c633d3c0d27a0f612a8015eeb4e7dde93ac`.
   - Trigger: concurrent conflicting transactions combined with fast-path/recovery races under message delay or partition.
   - Downside: it is an omnibus patch and the pre-fix tree is old.

**Recognizability (criterion c):** none of these has a Jepsen report or CVE. All are public Apache JIRA issues by the Accord authors, which is the normal public record for this project. CASSANDRA-21440 is the only one whose public text names a client-visible anomaly ("linearizability violations"). **Mutation fallback** is also available, because the SUT is built from source.

### Rejected
- CASSANDRA-20089 (Accord double apply, fixed before alpha1): the JIRA description is thin, mostly about SAI and interop tests, and doesn't establish a fault-triggered client anomaly.
- CASSANDRA-20427 (omnibus "various fixes", including "Fast path stable commits must not override recovery propose/commit decisions"): plausible G1, but it is bundled with ~20 unrelated changes, so it's hard to attribute.
- CASSANDRA-20641 (journal replay rejected startup): a restart-liveness failure (G5) that may be fast to hit. Kept as a G5 backup idea only.

### Pinned refs
- current: `e874e3a90b1942b945477e6d9ba03880b4f4a19d` (cassandra-6.0-alpha2)
- accord submodule at current: `fff32de2e915772fbc70d16b1c32346313877838`
- Reading clones: `src/cassandra` checked out at current, and `src/cassandra-accord` checked out at `fff32de` (both `--filter=blob:none`).
