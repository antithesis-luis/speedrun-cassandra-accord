# An acknowledged transfer is overwritten, and the bank total stops adding up

- **Finding name:** `acked-transfer-overwritten`
- **Guarantee:** [Guarantee 1](../../../speedrun-report.md#guarantee-1): "Transactions spanning
  several partitions and tables behave as if they ran one at a time, in an order that respects
  real time: a transaction that starts after another was acknowledged sees its effects (strict
  serializability)"
- **Version:** Apache Cassandra cassandra-6.0-alpha2, [`e874e3a9`][c-commit], with Accord
  [`fff32de2`][a-commit]
- **Summary in the report:** [the finding](../../../speedrun-report.md#acked-transfer-overwritten)
- **The proposed fix:** [acked-transfer-overwritten.patch](../../fixes/acked-transfer-overwritten.patch)
  ([Fix](#fix)). It did not prevent the failure.
- **Evidence:** [the adversarial review](../adversarial/acked-transfer-overwritten.md)

**Status: partial root cause.** That one transaction was executed twice, with two different
reads, and that both write sets were stored, is established from the data with high confidence.
Which Accord code path performs the second, stale execution is not established; [Root
cause](#root-cause) ranks the two hypotheses.

**Where it failed.** First seen in the first 30-minute run with the Guarantee 1 commands
([`e4947374`][r-e4947374]), under network faults only: partitions, slowdowns and clogs, with no
node restarts. It was spotted while that run was still in progress. Two of the failing timelines
are examined here. The log links open the Antithesis logs explorer at the failing check (they
need a login to the tenant).

| Timeline | What the audit saw | Failure | Log |
|---|---|---|---|
| [Timeline A](#timeline-a) | total 11,992, transfer counters summing to 15 | the bank-total and even-counter checks failed at vtime 238.69 | [log][l-xfer-a] |
| [Timeline B](#timeline-b) | total 11,938; an acknowledged credit missing; a transfer reading a balance from before an acknowledged transfer | four checks failed at vtime 249.58 | [log][l-xfer-b] |

## Symptom

The bank holds 12 accounts in two tables, seeded at 1,000 each, so every consistent snapshot
sums to 12,000. Every transfer adds 1 to the transfer counter of both its accounts, so the
counters always sum to an even number. Both hold for any set of whole transfers, applied any
number of times. In Timeline B, at vtime 249.577, one read-only audit transaction coordinated by
node2 returned:

```text
249.5770  bank_autoretry  FAIL Always "audited bank balances sum to the initial total"
            total=11938 expected=12000
            balances: accounts:0=1013 accounts:1=938 accounts:3=1063 accounts_b:100=987 accounts_b:103=937 …
249.5770  bank_autoretry  FAIL Always "audited transfer counters sum to an even number"   xfer_sum=5
249.5770  bank_autoretry  FAIL Always "an audit reflects every transfer acknowledged or observed before it started"
            regressions: accounts_b:105 floor 1, seen 0
```

No set of whole transfers can produce an odd counter sum. `accounts:1` = 938/1 shows the debit of
an acknowledged transfer of 62 from `accounts:1` to `accounts_b:105`, but `accounts_b:105` =
1000/0 is missing its credit. In the same history the credit appears later. So an acknowledged
effect is missing from a later transaction (real-time order is broken), and the stored state
doesn't conserve money.

## How the tests got there

The transfers and audits come from
[`parallel_driver_bank_autoretry.py`](../../../speedrun-tests.md#parallel_driver_bank_autoretry):
unprepared CQL, the driver's default retry policy, and up to 3 application resubmits after an
unknown outcome. Only one bank driver ran in these histories, so every value can be attributed.
The hot accounts were `accounts:0`, `accounts:1` and `accounts_b:100`.

In [Timeline B](#timeline-b), transfer by transfer (the per-transfer values come from the
assertion details, reconstructed with `snouty runs logs` across the branches that share this
history):

| vtime | What happened | Command |
|---|---|---|
| 205–227 | Network partitions, slowdowns and clogs over all nodes; gossip marks nodes down | fault injector |
| 241.3–247.4 | An Accord fast-path reconfiguration creates epoch 38: node3 enacts it at 241.26, node2 at 243.82, node1 only at 247.36 | (Cassandra) |
| 243.354 | Transfer **T144** (`accounts_b:100` → `accounts:0`, 144) is acknowledged after 3 attempts. It read 1000/0 on both, so it writes 856/1 and 1144/1 | [`parallel_driver_bank_autoretry.py`](../../../speedrun-tests.md#parallel_driver_bank_autoretry) |
| 248.270 | Transfer **T13** (`accounts_b:100` → `accounts:0`, 13) is acknowledged. It read **856/1 and 1144/1**, so it saw T144, and should write 843/2 and 1157/2 | same |
| 249.577 | A transfer of 100 from `accounts_b:100` reads **987/1**, below this client's floor of 2: FAIL. An audit sees `accounts:0` = **1013/1** and `accounts_b:100` = **987/1**: FAIL | same |
| 251.386 | In a later branch of the same history, an audit sees `accounts:0` = **1157/2**. No transfer touched `accounts:0` in between | same |

987/1 and 1013/1 are 1000 − 13 and 1000 + 13: **a write set of T13 computed from the state before
T144**. T144's effect is gone. 1157/2 is T13's original write set, which shows up later. So T13
produced two different write sets, and both reached storage.

In [Timeline A](#timeline-a), at 232.376, a transfer of 8 from `accounts:1` to `accounts_b:100`
was acknowledged on its second attempt. It read `accounts:1` = 992/1 (its own first attempt had
already debited it) and `accounts_b:100` = 856/1 (= 1000 − 144). The first attempt's credit on
`accounts_b:100` had been overwritten by a write of one of the 144-transfer's attempts computed
from 1000/0. The audit at 238.69 sums to 11,992: short by exactly 8.

## What the logs show

<a id="timeline-a"></a>
### Timeline A: the bank total is short by 8

[Timeline A in the logs explorer][l-xfer-a], at the failing check.

```text
227.2520  node1   Starting local commit of ReconfigureAccordFastPath{node=2, status=UNAVAILABLE, …}
230.1244  node2   Committed ReconfigureAccordFastPath{node=3, status=UNAVAILABLE, …}. New epoch is Epoch{epoch=38}
235.7348  fault_injector  FAULT network/partition Slowed asymmetric latency=2134ms±385 nodes=ALL max=2.5s
237.4890  fault_injector  FAULT network/partition Stopped nodes=ALL max=2.6s
238.1856  node1   Committed ReconfigureAccordFastPath{node=2, status=UNAVAILABLE, …}. New epoch is Epoch{epoch=39}
238.6926  client  HIT  Always "every seeded bank account is visible to an audit transaction"
238.6926  client  FAIL Always "audited bank balances sum to the initial total"       (total=11992)
238.6926  client  FAIL Always "audited transfer counters sum to an even number"      (xfer_sum=15)
```

What this shows:
- **The faults are network faults only.** Every fault line before the failure is a partition,
  slowdown or clog. No container was stopped, killed or restarted.
- **Two fast-path reconfigurations** (epochs 38 and 39) take effect during the partitions, at
  230.12 and 238.19. The audit fails half a second after the second.
- **Every row is present** ("every seeded bank account is visible" holds), yet the total is short
  and the counters sum to an odd number.

<a id="timeline-b"></a>
### Timeline B: one transfer, two write sets

[Timeline B in the logs explorer][l-xfer-b], at the first failing check.

```text
248.2697  client  Sometimes "a transfer was acknowledged after resubmitting an attempt whose outcome was unknown"
            (not this time: attempts=1) src=accounts_b:100 src_balance=856 src_xfers=1
            dst=accounts:0 dst_balance=1144 dst_xfers=1 amount=13
249.5768  client  FAIL Always "an application-retried transfer reads every transfer this client saw complete before it"
            src=accounts_b:100 src_balance=987 src_xfers=1 floor_src=2 (amount=100, dst=accounts:1)
249.5770  client  FAIL Always "audited bank balances sum to the initial total"          total=11938
249.5770  client  FAIL Always "audited transfer counters sum to an even number"         xfer_sum=5
249.5770  client  FAIL Always "an audit reflects every transfer acknowledged or observed before it started"
            regressions {accounts_b:105: floor 1, seen 0}
```

What this shows:
- **T13 was acknowledged having read T144's effect** (248.27: 856/1 and 1144/1).
- **1.3 s later the stored state is T13 applied to the state before T144** (249.58: 987/1 on
  `accounts_b:100`, 1013/1 on `accounts:0`). The same client's next transfer reads it, and so does
  an audit through node2.
- **The loss is stored, not a client artefact.** Across the run, the bad state was read through
  all three nodes as coordinators, by separate client processes, including single-attempt audits
  from other commands ([adversarial review](../adversarial/acked-transfer-overwritten.md)).

**Across the run.** Five failing timelines in three branches that diverge around vtime 228 were
examined. In 5 of 5, a fast-path reconfiguration (a new epoch) and at least one timed-out,
resubmitted transfer on the same hot account came before the first failure. In 3 of 3 branches,
a stored write is inconsistent with a committed read. A full cross-timeline count in the logs
explorer wasn't made.

A separate defect appears in this run: at 235.33 in another branch, node1 logged a
`NullPointerException` in `TxnAdapter.persist`, called from `ExecuteTxn.onDone` when a read-only
transaction fails. It's absent from Timeline A, which fails first, and reachable only for
read-only transactions, which write nothing. Its effect is that a failed audit reaches the client
as a server error instead of a timeout. It's not the cause of this finding.

## Root cause

**In plain language (established).** Under message delay, a transfer whose client had already
been told "committed" was executed a second time by another code path. That second execution read
the accounts without a transfer that had committed just before it, computed its writes from that
stale snapshot, and stored them. The original writes were stored too, at a different timestamp.
Each key ends up with whichever version has the higher timestamp, so credits and debits vanish and
reappear, and counters go odd. Accord fixes a transaction's write values when it executes
(`balance -= a` is computed inside Accord from the transaction's own read), so two different value
sets for one transaction can only come from two executions with different reads.

**What makes a second execution possible (established from the code at the tested commits):**
1. **Acknowledge, then persist.** The coordinator replies to the client
   ([`CoordinationAdapter.java:291`][a-coordadapter-291]) before `PersistTxn` sends `Apply`
   ([line 296][a-coordadapter-296]).
2. **No Stable messages on the fast path.** With Accord's default `sendStableMessages` and
   Cassandra's default fast read and write execution, `MAY_BYPASS_SAFESTORE`
   ([`AccordService.java:282-288`][c-accordservice-282]), a fast-path transaction sends no Stable
   messages ([`ExecuteTxn.java:284`][a-executetxn-284]). Its read runs through
   `ReadData.applyFastRead` ([`ReadData.java:343`][a-readdata-343]), which reads storage directly
   on the strength of a "ready to execute" flag captured at PreAccept time.
3. **Recovery re-executes.** When `Apply` is lost under a partition, other replicas hold the
   transaction only as PreAccepted. Recovery re-executes it
   ([`Recover.java:366-372`][a-recover-366]) and persists its own freshly computed writes.
4. **Late original Apply messages still write.** With the ready flag and a maximal Apply,
   `Apply` calls `applyDirect` ([`Apply.java:133-137`][a-apply-133]), which writes storage before
   `Commands.apply` checks the command's state. The race with recovery is detected only afterwards
   ([`Commands.java:631`][a-commands-631]), and the fast path skips waiting
   ([`Commands.java:580`][a-commands-580], which carries the comment `TODO (required): validate safe
   to fast apply against local state`).

So both write sets of one transaction can reach storage, which is what Timeline B shows.

**Not established: why the second execution read without T144.** T144 was acknowledged before T13
started, so T13's committed dependencies must include it, and any re-execution of T13 must wait for
T144 to be applied. Two hypotheses, ranked:
- **The fast-read bypass read a stale snapshot (leading, medium-low confidence).** One of the
  executions read through `applyFastRead` on a replica that hadn't applied T144 yet: its readiness
  flag from PreAccept was stale by the time the read ran, after the epoch change and concurrent
  recovery of T144's three attempts. Nothing re-checks dependency state at read time.
- **Recovery rebuilt dependencies without T144.** Recovery of an in-flight transfer that sent no
  Stable messages rebuilt its dependencies without T144, for example because T144's decision was
  known only to a partitioned coordinator and one voter, or because a replica was still on the
  previous epoch (node1 lagged epoch 38 by about 6 s in Timeline B).

The fast-path reconfigurations don't change who votes (the default strategy ignores
availability); they coincide with the partitions. The correlation is 5 of 5, but causation is
unproven. The next diagnostic step is Accord TRACE logging on `Recover`, `Apply` and `ReadData`
for the hot keys, which would name both executions of T13.

## Fix

**The patch:** [acked-transfer-overwritten.patch](../../fixes/acked-transfer-overwritten.patch)

Two changes:
1. **The secondary crash (certain).** In `ExecuteTxn.onDone`
   ([`ExecuteTxn.java:464-466`][a-executetxn-464]), stop calling `persist` with null writes and
   result for a failed read-only transaction. That call threw the `NullPointerException` and turned
   a read timeout into a client-visible server error. Failed reads now take the same path as other
   failed executions.
2. **A mitigation for the leading hypothesis.** Default Cassandra's fast read and write execution
   to Accord's own default, `MAY_BYPASS_COMMANDSFORKEY`, instead of `MAY_BYPASS_SAFESTORE`
   ([`AccordService.java:282-288`][c-accordservice-282]). This removes the only two paths that read
   or write storage without the per-command state machine confirming, at that moment, that
   dependencies are applied. Operators can opt back in through the existing YAML keys.

A complete fix, once tracing identifies the second execution, needs either `applyDirect` to
validate through `Commands.apply` before writing and `applyFastRead` to re-check dependency state,
or, if recovery is the cause, recovery of a no-Stable fast-path transaction to merge the
dependencies of every fast-path voter. Either way, a second write set must never be stored for a
transaction whose outcome is already decided.

**How it was checked: not verified.** Each check ran current [`e874e3a9`][c-commit] plus the patch
for 30 minutes. Counts are failing / passing examples of "audited bank balances sum to the initial
total":

| Run | Build | Faults | Bank total |
|---|---|---|---|
| [`e4947374`][r-e4947374] | current | network | 96 failing |
| [`83ddaf62`][r-83ddaf62] | current | network | 11 / 605 |
| [`0b77f2b9`][r-0b77f2b9] | current + this patch | network | **0 / 682** |
| [`0e194950`][r-0e194950] | current + this patch | all fault types | 1 / 345 (a suspect failure right after its coordinator restarted under a new address) |
| [`ccc9549e`][r-ccc9549e] | current + this patch + the [committed-rows diagnostic patch](committed-rows-read-absent.md#fix) | network | **38 / 730** |

The first clean run was luck: 30-minute network-only runs vary by about 10× even without the
patch (11 and 96). In [`ccc9549e`][r-ccc9549e], the final audit at vtime 199.01 summed to 11,966 with an odd
counter sum: one account's update was missing, the same signature. The other patch in that build
never activated, so it can't explain the failures. Switching the execution mode, plus the crash
fix, doesn't prevent the lost update, so the leading hypothesis is at most incomplete.

## Comparison with upstream

Compared with Cassandra trunk at [`36d2433d`][c-trunk] (which pins Accord [`56b7710a`][a-trunk]),
read but not built or run.

- **Already known?** No upstream report or fix matches the double execution. Apache JIRA searches
  for `MAY_BYPASS_SAFESTORE`, `applyFastRead`, `RaceWithRecovery`, "accord serializability
  violation" and "accord recovery deps" found nothing related.
  - [CASSANDRA-21662](https://issues.apache.org/jira/browse/CASSANDRA-21662) (Accord
    [`ffb19843`][a-ffb1984]) fixes the secondary `NullPointerException` as a side change: it
    doesn't touch the lost update.
  - [CASSANDRA-21687](https://issues.apache.org/jira/browse/CASSANDRA-21687) (Accord
    [`f114529f`][a-f114529]) fixes nearby dependency and execution-order bookkeeping; judged not a
    fix for this finding.
  - [CASSANDRA-21250](https://issues.apache.org/jira/browse/CASSANDRA-21250) is about read barriers
    in mixed mode: a different mechanism.
- **Present on trunk? Yes, from reading.** Trunk still sets `MAY_BYPASS_SAFESTORE` for fast reads
  and writes; `applyFastRead` still has no read-time re-check; `Apply` still writes through
  `applyDirect` before `Commands.apply` validates; the coordinator still acknowledges before it
  sends `Apply`.
- **Suggested upstream issue (not filed).** *Accord: an acknowledged transaction can be executed
  twice with different reads under partition (lost update) with fast_read/write_execution =
  MAY_BYPASS_SAFESTORE.*
  > Under network partitions and an epoch change, a bank-transfer workload on 6.0-alpha2 (code
  > unchanged on trunk) sees one acknowledged transaction store two different write sets: one from
  > the read it returned to the client, one from a read that missed an earlier acknowledged
  > conflicting transaction. Balances stop summing to the initial total.
  > `applyDirect` writes before `Commands.apply` can detect a race with recovery, while recovery
  > re-executes a fast-path transaction that sent no Stable messages. Switching to
  > MAY_BYPASS_COMMANDSFORKEY did not prevent it. An Antithesis reproduction is available.
- **Caveat:** the root cause was worked out before searching upstream, but the model may have seen
  related code or reports in its training data.

[c-commit]: https://github.com/apache/cassandra/commit/e874e3a90b1942b945477e6d9ba03880b4f4a19d
[a-commit]: https://github.com/apache/cassandra-accord/commit/fff32de2e915772fbc70d16b1c32346313877838
[c-trunk]: https://github.com/apache/cassandra/commit/36d2433dfb2fd26fb8719716edf1b5f3232df8d3
[a-trunk]: https://github.com/apache/cassandra-accord/commit/56b7710afaf3ac1492e50669f8ef5c0985654586
[a-ffb1984]: https://github.com/apache/cassandra-accord/commit/ffb1984367dd2b5888d7afeef2ce5c3991372263
[a-f114529]: https://github.com/apache/cassandra-accord/commit/f114529f56bccd079ebb9537f17b7b48e57cd9a0
[a-coordadapter-291]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/coordinate/CoordinationAdapter.java#L291
[a-coordadapter-296]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/coordinate/CoordinationAdapter.java#L296
[c-accordservice-282]: https://github.com/apache/cassandra/blob/e874e3a90b1942b945477e6d9ba03880b4f4a19d/src/java/org/apache/cassandra/service/accord/AccordService.java#L282-L288
[a-executetxn-284]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/coordinate/ExecuteTxn.java#L284
[a-executetxn-464]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/coordinate/ExecuteTxn.java#L464-L466
[a-readdata-343]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/messages/ReadData.java#L343
[a-recover-366]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/coordinate/Recover.java#L366-L372
[a-apply-133]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/messages/Apply.java#L133-L137
[a-commands-631]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/local/Commands.java#L631
[a-commands-580]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/local/Commands.java#L580

[r-e4947374]: https://honey-whale.antithesis.com/report/xrIBSxLwAHWhRf49AROCTaMK/yWwNglWJp3ThXiESihRapRCIs7Pwz7ROGJpTVNx0uxU.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE1OjA4OjE1LjkyNDI3NDUzOFoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoieVd3TmdsV0pwM1RoWGlFU2loUmFwUkNJczdQd3o3Uk9HSnBUVk54MHV4VS5odG1sIiwicmVwb3J0X2lkIjoieHJJQlN4THdBSFdoUmY0OUFST0NUYU1LIn19fVe7MBHDdXkUUFSrjqed0PclvzX2NZKVJ5I8PaDlT0I1lpSuezQCi6_TaC8jVV1BULZeH7_RwR2JEBhNfVArCw4
[l-xfer-a]: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjM4LjY5MjYwOTk1NTc4OTUyIn1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjMxMTU3MDcxMDk2Mjc4NjQwMTkifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiMzQ5OWQ0YTA4MTNhZjQ1MzE0NTMyMzNjNTc5Y2Y1OTMtNjMtMTIifQ
[l-xfer-b]: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjQ5LjU3Njc4MjcwNzM1Nzc4In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii01NzA5MDUxNjM1ODMwMTI4MDM4In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjM0OTlkNGEwODEzYWY0NTMxNDUzMjMzYzU3OWNmNTkzLTYzLTEyIn0
[r-83ddaf62]: https://honey-whale.antithesis.com/report/2kEKMku2Ei7pS75t3iDKhVbx/j8fGuFgyCTLqn_ZYwhVR_WR9aLOJKc0MbEjI8xCgQpw.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE2OjAyOjE1LjQzNjY0OTA1MVoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiajhmR3VGZ3lDVExxbl9aWXdoVlJfV1I5YUxPSktjME1iRWpJOHhDZ1Fwdy5odG1sIiwicmVwb3J0X2lkIjoiMmtFS01rdTJFaTdwUzc1dDNpREtoVmJ4In19fUDXnp8uHRyAkW1TKXuyGEnf5ad6JXRwY8XbPjTPaWFDERrThAM_peYjzYhAFaUy6lhTRHwLZtnIwHTvA_ljagM
[r-0b77f2b9]: https://honey-whale.antithesis.com/report/IwjECCMMfn8ttNe3O2q6VpBk/y70rTIP4TaJV1syBnP0RWh6mhWeMzW2cVqkkqXDWRYA.html?auth=v2.public.eyJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoieTcwclRJUDRUYUpWMXN5Qm5QMFJXaDZtaFdlTXpXMmNWcWtrcVhEV1JZQS5odG1sIiwicmVwb3J0X2lkIjoiSXdqRUNDTU1mbjh0dE5lM08ycTZWcEJrIn19LCJuYmYiOiIyMDI2LTEwLTA4VDE2OjA0OjAwLjU0NTAzNzI4N1oifVgqM5p8JmpqTrJNfXkHe-u_7Wk_pfTWpvRceqnBiyttiopD_3bctLgkMbRlQc1q5E3EUWrASgjoGQxllwKrMwc
[r-0e194950]: https://honey-whale.antithesis.com/report/1m1Ur9qEIU4qMIV6bVIJALEA/TZXCICByv8d1_9cYxLwOit-JGi3xkzPHbasNfHMMLcE.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE2OjUzOjMzLjg0MzAwNTQ2MloiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiVFpYQ0lDQnl2OGQxXzljWXhMd09pdC1KR2kzeGt6UEhiYXNOZkhNTUxjRS5odG1sIiwicmVwb3J0X2lkIjoiMW0xVXI5cUVJVTRxTUlWNmJWSUpBTEVBIn19fYRMwrkd2H--hy32gsQF2UrB5cW93Y848VKOv1g5hnJSqlsgMIE2PmVkcLF8QqXEllbUn3BJk5KjacXN5k-TeQg
[r-ccc9549e]: https://honey-whale.antithesis.com/report/KfY7B2UuKvIX6-mUzOaSxMLD/ISGa8Ar3YHqzNOLEqCKFE9EbNKaW6MSN8s9nJeOA5_Y.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE3OjQ4OjAwLjYyMDk3MDEwN1oiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiSVNHYThBcjNZSHF6Tk9MRXFDS0ZFOUViTkthVzZNU044czluSmVPQTVfWS5odG1sIiwicmVwb3J0X2lkIjoiS2ZZN0IyVXVLdklYNi1tVXpPYVN4TUxEIn19fYHSb1vJZI8JwTCuQ9ZVhszgoXnANQW1WQmRA6j643Q0TlgzZfuZSh7oot8SsxgMJ1F9JY2RuT2LiNcqCTdqMw8
