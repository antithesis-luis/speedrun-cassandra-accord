# Committed rows are read as absent

- **Finding name:** `committed-rows-read-absent`
- **Guarantee:** [Guarantee 1](../../../speedrun-report.md#guarantee-1): "Transactions spanning
  several partitions and tables behave as if they ran one at a time, in an order that respects
  real time: a transaction that starts after another was acknowledged sees its effects (strict
  serializability)". The same symptom also breaks [Guarantee 2](../../../speedrun-report.md#guarantee-2)'s
  checks, as one row of a group read as absent.
- **Version:** Apache Cassandra cassandra-6.0-alpha2, [`e874e3a9`][c-commit], with Accord
  [`fff32de2`][a-commit]
- **Summary in the report:** [the finding](../../../speedrun-report.md#committed-rows-read-absent)
- **The patch:** [committed-rows-read-absent.patch](../../fixes/committed-rows-read-absent.patch)
  ([Fix](#fix)). It is a diagnostic with a fail-safe, not a fix, and it never fired.
- **Evidence:** [the adversarial review](../adversarial/committed-rows-read-absent.md)

**Status: partial root cause.** Which rows go missing, and on which node, is established with high
confidence. The faulty code line is not established, and the replica-side hypotheses were ruled
out by the fix check.

**Where it failed.** Four independent occurrences in three runs, all under network faults only,
with three different coordinators. Each was replayed in a few sibling timelines; one per
occurrence is listed. The log links open the Antithesis logs explorer at the failing check (they
need a login to the tenant).

| Timeline | Run, build | Coordinator, transaction | Failure | Log |
|---|---|---|---|---|
| [Timeline A](#timeline-a) | [`83ddaf62`][r-83ddaf62], current | node2, a 12-account audit | 7 of 12 rows absent at vtime 155.44 | [log][l-rows-83dd] |
| [Timeline B](#timeline-b) | [`e4947374`][r-e4947374], current | node1, a transfer `accounts_b:105` → `accounts:2` | the source row absent at vtime 276.46 | [log][l-rows-e494-xfer] |
| [Timeline C](#timeline-c) | [`e4947374`][r-e4947374], current | node2, a 12-account audit | the same 7 rows absent at vtime 285.33 | [log][l-rows-e494-audit] |
| [Timeline D](#timeline-d) | [`0b77f2b9`][r-0b77f2b9], current + the [transfer finding's patch](acked-transfer-overwritten.md#fix) | node3, a transfer `accounts_b:102` → `accounts:0` | the source row absent at vtime 253.57 | [log][l-rows-0b77] |

## Symptom

The workload seeds 12 rows before testing starts, in one conditional transaction: `accounts` ids
0–5 and `accounts_b` ids 100–105. Nothing deletes them, sets a TTL or writes nulls. Later, read
transactions get null columns for rows that exist. In Timeline C, an audit coordinated by node2:

```text
285.3325  bank_audit  FAIL Always "every seeded bank account is visible to an audit transaction"
            coordinator=10.89.0.3:9042 (node2)
            missing: accounts:3, accounts_b:105, accounts_b:100, accounts_b:104, accounts_b:103, accounts_b:101, accounts_b:102
            balances: accounts:0=186 accounts:1=1686 accounts:2=943 accounts:4=200 accounts:5=1002
```

Earlier audits in the same timelines saw all 12 rows. At 284.65 a transfer through node2 read
`accounts_b:100` = 1076 normally; 0.7 s later this audit, also through node2, lost that row. The
same 7-row set went missing in Timeline A, in a different run.

## How the tests got there

The audits come from [`anytime_bank_audit.py`](../../../speedrun-tests.md#anytime_bank_audit) and
the bank drivers; the failing transfers from
[`parallel_driver_bank_transfers.py`](../../../speedrun-tests.md#parallel_driver_bank_transfers).
The seed comes from [`client_setup.py`](../../../speedrun-tests.md#client_setup).

In [Timeline D](#timeline-d):

| vtime | What happened | Command |
|---|---|---|
| 139.52 | The seed transaction commits; setup completes at 139.53 | [`client_setup.py`](../../../speedrun-tests.md#client_setup) |
| 153.90, 166.18 | Audits see all 12 rows, including `accounts_b:102` | bank audits |
| 171.84 | A transfer to `accounts_b:102` times out (unknown outcome). It's an UPDATE either way, and can't remove a row | [`parallel_driver_bank_transfers.py`](../../../speedrun-tests.md#parallel_driver_bank_transfers) |
| throughout | Network clogs and partitions; heavy message drops; node3 repeatedly fails to agree durability sync points | fault injector |
| 251.21, 251.44 | node3 completes its first shard-durability round for `accounts` and `accounts_b` | (Cassandra) |
| 253.57 | A transfer through node3 reads `accounts_b:102` as absent, while its other account reads normally (1000/0): FAIL | [`parallel_driver_bank_transfers.py`](../../../speedrun-tests.md#parallel_driver_bank_transfers) |

## What the logs show

<a id="timeline-a"></a>
### Timeline A: an audit through node2 loses 7 rows

[Timeline A in the logs explorer][l-rows-83dd], at the failing check.

```text
146.3441  fault_injector  FAULT network/partition Stopped asymmetric nodes=ALL max=3.8s
148.1439  fault_injector  FAULT network/clog Jammed max=4.3s
149.6886  fault_injector  FAULT network/clog Jammed nodes=cassandra-accord-client,cassandra-accord-node1 max=4.4s
155.4363  client          FAIL Always "every seeded bank account is visible to an audit transaction"
                          (missing accounts:3 and accounts_b:100–105; coordinator node2)
```

What this shows: only network faults before the failure, and no error from any node near it.
Journal compaction ran on node1 and node3 at 150.95, node3 completed durability rounds at 154.86,
and node2 started compacting at 155.32, 0.1 s before the audit failed.

<a id="timeline-b"></a>
### Timeline B: a transfer through node1 loses its source row

[Timeline B in the logs explorer][l-rows-e494-xfer], at the failing check.

```text
276.4578  client  FAIL Always "a transfer transaction reads both of its accounts"
                  src=accounts_b:105 src_balance=None src_xfers=None
                  dst=accounts:2 dst_balance=1061 dst_xfers=1   coordinator=10.89.0.2:9042 (node1)
```

What this shows: the server returned a row in which one account's columns are null and the
other's are present, so this is not an empty result. A transfer had timed out at 268.37, shortly
before.

<a id="timeline-c"></a>
### Timeline C: the same 7 rows, in another run

[Timeline C in the logs explorer][l-rows-e494-audit], at the failing check. The log lines are in
[Symptom](#symptom). A transfer timed out at 285.02, 0.3 s before. After 285.5, node2 coordinated
38 passing audits against 1 more failure (288.33), so the loss looks transient.

<a id="timeline-d"></a>
### Timeline D: on a build with the transfer finding's patch

[Timeline D in the logs explorer][l-rows-0b77], at the failing check.

```text
253.5724  client  FAIL Always "a transfer transaction reads both of its accounts"
                  src=accounts_b:102 src_balance=None src_xfers=None
                  dst=accounts:0 dst_balance=1000 dst_xfers=0   coordinator=10.89.0.4:9042 (node3)
```

What this shows: the symptom persists on a build where the fast-read bypass is disabled. The last
unknown outcome in this timeline was 55 s earlier (198.55), so a preceding ambiguous write is not
established as a cause.

## Root cause

**In plain language.** Each node splits the keys it stores across several Accord internal shards
(command stores), and a read asks each one for its share. In every failing read, only the first
command store's rows reached the client. The rows owned by the node's other command stores were
dropped without being reported as unavailable, so the coordinator treated them as absent instead
of fetching them from another replica.

**Established (high confidence):**
1. **The missing set is exactly "every command store except store 0".** The server's durability
   log lines give each store's ranges: store 0 = `accounts` (−∞, −1], store 1 = `accounts`
   (−1, +∞), store 2 = `accounts_b` (−∞, −1], store 3 = `accounts_b` (−1, +∞). Computing Murmur3
   tokens (they match the server's own decorated keys): `accounts` 0, 1, 2, 4 and 5 have negative
   tokens, so they're in store 0, and they were all present; `accounts:3` is in store 1 and every
   `accounts_b` key is in store 2 or 3, and they were all missing. Both transfer failures fit too:
   the destination in store 0 was present, the source in store 2 or 3 was missing. That's why two
   runs lost the identical 7-row set: tokens and the store split are deterministic. A per-key
   storage problem is ruled out: stores 0 and 1 read the same table, yet `accounts:0` was present
   and `accounts:3` missing.
2. **The read is served by the coordinator's own replica.** With replication factor 3 on 3 nodes,
   the coordinator always executes locally ([`ExecuteTxn.java:231`][a-executetxn-231]), and a
   local reply that reports nothing unavailable is approved for every shard
   ([`ReadTracker.java:88`][a-readtracker-88]). Keys missing from the data become null columns.
3. **The fast-read bypass is not the cause:** Timeline D's build disables it.
4. **Cassandra's result merging is not the cause:** merging is lossless for key values, and the
   query result doesn't filter by key.

**Hypotheses that the fix check ruled out.** Two replica-side paths could produce a reply that
omits owned keys without marking them unavailable: (a) `ReadData.read` moves keys the store's
partial transaction doesn't cover into `unavailable` only in one branch
([`ReadData.java:524`][a-readdata-524]); otherwise `Txn.read` skips them silently
([`Txn.java:458`][a-txn-458]); (b) a store that owns keys in scope is never selected, or reads
nothing. The diagnostic patch checks both, and neither check fired while the failure recurred.

**What remains.** The key is either read by a local store and comes back empty from the data layer,
dropped on the coordinator side (`ExecuteTxn`, `ReadTracker` or the result merge), or read at a
timestamp or epoch where the row isn't visible. In the two failures examined closely (Timelines A
and D), a durability or journal-compaction round on the coordinator came shortly before the read:
a lead, not a proven cause. The next step is to log, per key, which reply supplied each row, and
compare the data against `unavailable`.

## Fix

**The patch:** [committed-rows-read-absent.patch](../../fixes/committed-rows-read-absent.patch)
(diagnostic and fail-safe, in `ReadData.java` only)

Without the faulty line, a targeted fix can't be justified. The patch:
1. records which participants each local store actually issued a read for;
2. closes hypothesis (a): keys the partial transaction doesn't cover are logged at ERROR and
   reported unavailable in every branch;
3. checks coverage before replying: if any key the node owns in scope was neither read nor marked
   unavailable, it logs ERROR and reports those ranges unavailable.

Marking more ranges unavailable is always safe: the coordinator then reads those keys from another
replica, or fails the read, instead of answering "row absent".

**How it was checked: the fix failed.** Run [`ccc9549e`][r-ccc9549e] (30 minutes, network faults)
built current [`e874e3a9`][c-commit] plus [the transfer finding's
patch](../../fixes/acked-transfer-overwritten.patch) plus this patch. A run-wide search for both
new ERROR lines returned 0 events, while a control search confirmed server output was indexed. Yet
committed rows were still read as absent: "a transfer transaction reads both of its accounts"
failed once (vtime 180.78, through node3, `accounts_b:100` absent) and "every seeded bank account
is visible" twice (from 236.21). So the loss is not in the replica's `ReadData` reply. The patch is
harmless, since it never changed a reply, but it is not a fix and shouldn't be shipped as one.

Separately, at vtime 334–339 in that run, nodes 1 and 2 printed stack traces from an existing
Accord internal check ("… not waiting on store …", in `ReadData.onOneSuccessInternal`). The check
is upstream code, not something the patch added. It wasn't investigated.

## Comparison with upstream

Compared with Cassandra trunk at [`36d2433d`][c-trunk] (Accord [`56b7710a`][a-trunk]), read but
not built or run.

- **Already known?** No matching report or fix in Apache JIRA or the commit history.
- **Present on trunk? Probably, from reading only.** The coordinator paths (`ReadTracker`, store
  selection, `Txn.read`) are unchanged in substance. Because the faulty line isn't identified,
  "present" rests on the unchanged paths and the absence of a related fix.
- **Suggested upstream issue (not filed).** *Accord: committed rows returned as absent; the
  coordinator-local read result contains only one command store's keys.*
  > With replication factor 3 on 3 nodes and network faults only (no restarts or topology changes),
  > multi-key Accord read transactions on 6.0-alpha2 sometimes return null for seeded rows that
  > were never deleted. Every missing key belongs to one of the coordinator's local command stores
  > 1–3; keys in store 0 are always present. The local reply carries no unavailable ranges, so the
  > read tracker approves it. A replica-side coverage check never fired in a reproduction, so the
  > loss is likely in local data reads, the coordinator merge, or read visibility. Antithesis runs
  > and logs are available.
- **Caveat:** the root cause was worked out before searching upstream, but the model may have seen
  related code or reports in its training data.

[c-commit]: https://github.com/apache/cassandra/commit/e874e3a90b1942b945477e6d9ba03880b4f4a19d
[a-commit]: https://github.com/apache/cassandra-accord/commit/fff32de2e915772fbc70d16b1c32346313877838
[c-trunk]: https://github.com/apache/cassandra/commit/36d2433dfb2fd26fb8719716edf1b5f3232df8d3
[a-trunk]: https://github.com/apache/cassandra-accord/commit/56b7710afaf3ac1492e50669f8ef5c0985654586
[a-executetxn-231]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/coordinate/ExecuteTxn.java#L231
[a-readtracker-88]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/coordinate/tracking/ReadTracker.java#L88
[a-readdata-524]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/messages/ReadData.java#L524-L532
[a-txn-458]: https://github.com/apache/cassandra-accord/blob/fff32de2e915772fbc70d16b1c32346313877838/accord-core/src/main/java/accord/primitives/Txn.java#L458

[r-83ddaf62]: https://honey-whale.antithesis.com/report/2kEKMku2Ei7pS75t3iDKhVbx/j8fGuFgyCTLqn_ZYwhVR_WR9aLOJKc0MbEjI8xCgQpw.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE2OjAyOjE1LjQzNjY0OTA1MVoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiajhmR3VGZ3lDVExxbl9aWXdoVlJfV1I5YUxPSktjME1iRWpJOHhDZ1Fwdy5odG1sIiwicmVwb3J0X2lkIjoiMmtFS01rdTJFaTdwUzc1dDNpREtoVmJ4In19fUDXnp8uHRyAkW1TKXuyGEnf5ad6JXRwY8XbPjTPaWFDERrThAM_peYjzYhAFaUy6lhTRHwLZtnIwHTvA_ljagM
[l-rows-83dd]: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMTU1LjQzNjMzMDE3NDA5NTkzIn1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii0zMzU5MjE3ODcwNDI3NjIwODY5In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjQ1NjExMTQwOWIyZjIzZDhjNmJkZWJlNWEyZGRkMjQ3LTYzLTEyIn0
[r-e4947374]: https://honey-whale.antithesis.com/report/xrIBSxLwAHWhRf49AROCTaMK/yWwNglWJp3ThXiESihRapRCIs7Pwz7ROGJpTVNx0uxU.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE1OjA4OjE1LjkyNDI3NDUzOFoiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoieVd3TmdsV0pwM1RoWGlFU2loUmFwUkNJczdQd3o3Uk9HSnBUVk54MHV4VS5odG1sIiwicmVwb3J0X2lkIjoieHJJQlN4THdBSFdoUmY0OUFST0NUYU1LIn19fVe7MBHDdXkUUFSrjqed0PclvzX2NZKVJ5I8PaDlT0I1lpSuezQCi6_TaC8jVV1BULZeH7_RwR2JEBhNfVArCw4
[l-rows-e494-xfer]: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjc2LjQ1NzgzNjQ3NTY4ODk2In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjQ4Mjk4MTM1NzA0MjI2NTc5NTkifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiMzQ5OWQ0YTA4MTNhZjQ1MzE0NTMyMzNjNTc5Y2Y1OTMtNjMtMTIifQ
[l-rows-e494-audit]: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjg1LjMzMjQ2Mjc4ODMyNjY3In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6Ii04ODQxNTIxMDEzMDQ1NDI1NDA0In1dLCJvIjoib3IifV0sIm8iOiJhbmQifSwidCI6eyJnIjpmYWxzZSwibSI6IiJ9LCJ5Ijoibm9uZSJ9fSwicyI6IjM0OTlkNGEwODEzYWY0NTMxNDUzMjMzYzU3OWNmNTkzLTYzLTEyIn0
[r-0b77f2b9]: https://honey-whale.antithesis.com/report/IwjECCMMfn8ttNe3O2q6VpBk/y70rTIP4TaJV1syBnP0RWh6mhWeMzW2cVqkkqXDWRYA.html?auth=v2.public.eyJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoieTcwclRJUDRUYUpWMXN5Qm5QMFJXaDZtaFdlTXpXMmNWcWtrcVhEV1JZQS5odG1sIiwicmVwb3J0X2lkIjoiSXdqRUNDTU1mbjh0dE5lM08ycTZWcEJrIn19LCJuYmYiOiIyMDI2LTEwLTA4VDE2OjA0OjAwLjU0NTAzNzI4N1oifVgqM5p8JmpqTrJNfXkHe-u_7Wk_pfTWpvRceqnBiyttiopD_3bctLgkMbRlQc1q5E3EUWrASgjoGQxllwKrMwc
[l-rows-0b77]: https://honey-whale.antithesis.com/search?search=v6veyJxIjp7Im4iOnsiciI6eyJoIjpbeyJoIjpbeyJjIjoibW9tZW50LnZ0aW1lIiwiZiI6ImdlbmVyYWwuY3VzdG9tIiwibyI6Im1hdGNoZXMiLCJ2IjoiMjUzLjU3MjQ5OTU0Mzg5NDA4In1dLCJvIjoib3IifSx7ImgiOlt7ImMiOiJtb21lbnQuaW5wdXRfaGFzaCIsImYiOiJnZW5lcmFsLmN1c3RvbSIsIm8iOiJtYXRjaGVzIiwidiI6IjY3MTg2NTY4MjY2NTUzMzQyNDQifV0sIm8iOiJvciJ9XSwibyI6ImFuZCJ9LCJ0Ijp7ImciOmZhbHNlLCJtIjoiIn0sInkiOiJub25lIn19LCJzIjoiODUxZmJkNzFmOGYzNTU0MTFjMWQwMzhkNDZiZDIzNGEtNjMtMTIifQ
[r-ccc9549e]: https://honey-whale.antithesis.com/report/KfY7B2UuKvIX6-mUzOaSxMLD/ISGa8Ar3YHqzNOLEqCKFE9EbNKaW6MSN8s9nJeOA5_Y.html?auth=v2.public.eyJuYmYiOiIyMDI2LTEwLTA4VDE3OjQ4OjAwLjYyMDk3MDEwN1oiLCJzY29wZSI6eyJSZXBvcnRTY29wZVYxIjp7ImFzc2V0IjoiSVNHYThBcjNZSHF6Tk9MRXFDS0ZFOUViTkthVzZNU044czluSmVPQTVfWS5odG1sIiwicmVwb3J0X2lkIjoiS2ZZN0IyVXVLdklYNi1tVXpPYVN4TUxEIn19fYHSb1vJZI8JwTCuQ9ZVhszgoXnANQW1WQmRA6j643Q0TlgzZfuZSh7oot8SsxgMJ1F9JY2RuT2LiNcqCTdqMw8
