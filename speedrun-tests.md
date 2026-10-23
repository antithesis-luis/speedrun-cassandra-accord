# How the tests work: Apache Cassandra 6.0-alpha2 with Accord

The workload that tested Cassandra's Accord transactions for the
[Apache Cassandra Accord report](speedrun-report.md). This page explains how it works as a whole,
then each command: what it does, what it checks, and where in the code each check is. Every command
also documents itself in its own docstring, shown under each entry.

## How a test run goes

1. **Setup.** Three Cassandra nodes start, each storing every key (replication factor 3). node1's
   helper grows the cluster-metadata service to all three nodes. The client container then runs
   [`client_setup.py`](#client_setup): it waits until the nodes see each other, creates the
   keyspace and every table `WITH transactional_mode='full'`, checks that a transaction succeeds
   through every node, seeds the twelve bank accounts in one conditional transaction, and tells
   Antithesis setup is done.
2. **Drivers, under faults.** Antithesis then runs the [drivers](#drivers) at random times, many
   at once, while it injects faults: network partitions, slowdowns and clogs, and in most runs
   node pauses, CPU throttling, node kills and stops with restart, and clock jumps. The drivers
   send transactions (`BEGIN TRANSACTION … COMMIT TRANSACTION`) and plain CQL, as applications
   would.
3. **Checkers during faults.** [`anytime_bank_audit.py`](#anytime_bank_audit) and
   [`anytime_durable_sample.py`](#anytime_durable_sample) run periodically while all that is going
   on.
4. **Checkers, after faults stop.** Antithesis stops the drivers and the faults, restarts any node
   it killed, then runs the [checkers](#checkers-that-run-after-faults-stop). Each one retries while
   the cluster recovers, then judges.

Antithesis explores many different timelines of this, so the same commands run in many orders, at
many moments, under many fault combinations.

## The ideas the commands share

- **Four kinds of data, one per safety guarantee.**
  - *The bank* ([Guarantee 1](speedrun-report.md#guarantee-1)): 12 accounts over two tables, 1,000
    each. A transfer is one transaction that reads both accounts, checks the balance with `IF`, and
    updates both rows, adding 1 to each row's transfer counter. Every consistent snapshot sums to
    12,000 and its counters sum to an even number, however many transfers applied, and however
    often. The two tables use different account ids, because Cassandra rejects a transaction that
    updates the same key and column names in two tables ([`helper_accord.py`](#helper_accord)).
  - *Token groups* ([Guarantee 2](speedrun-report.md#guarantee-2)): 2–4 rows over two tables. Each
    write puts one fresh token into every row of a group, so a read must see the same token in all
    of them, or none.
  - *Durable rows* ([Guarantee 3](speedrun-report.md#guarantee-3)): each write inserts a uniquely
    identified row into 1–3 partitions ([`helper_durable.py`](#helper_durable)).
  - *Single-writer registers* ([Guarantee 4](speedrun-report.md#guarantee-4)): one key per writer,
    with strictly increasing versions, written and read with plain CQL on a full-mode table
    ([`helper_fm.py`](#helper_fm)).
- **A record of what was acknowledged** (a ledger). The durable-write commands append every
  attempt, acknowledgement and unknown outcome to a file on a volume all commands share, flushed
  to disk before the next step ([`helper_durable.py`](#helper_durable)). A checker reads the ledger
  line before it reads the row, so the read always starts after the acknowledgement. Published
  registers work the same way ([`helper_fm.py`](#helper_fm)).
- **Unknown outcomes are never failures.** A request that times out or loses its connection may or
  may not have applied. Each check is written so that it holds either way: a transfer applied twice
  is still a whole transfer, a token write shows up in all rows or none, and an unknown write never
  raises the floor a later read must reach ([`helper_accord.py`](#helper_accord)).
- **Real-time order is checked from the client's own history.** A read that starts after a
  transaction was acknowledged, or after an earlier read completed, must see at least what that
  transaction wrote or that read saw (transfer counters, markers, register versions).
- **Two ways of sending each request.** Some commands send each request once and record its exact
  outcome. Others behave like a typical application: plain CQL strings, the driver's default retry
  policy (which may retry silently), and their own resubmits.
- **Varied coordinators and consistency levels.** Reads are often sent through a different node
  than the one that acknowledged the write, and plain reads use the consistency levels Accord
  accepts.
- **Randomness comes from the Antithesis SDK,** so Antithesis can steer every choice: which
  account, which group, how many operations, which retry style
  ([`helper_accord.py`](#helper_accord)).
- **Two kinds of assertion.** An `Always` assertion is a check that must hold every time. A
  `Sometimes` (or `Reachable`) assertion marks something interesting that must happen at least
  once, so we know the test reached it; Antithesis also uses them to steer towards those
  situations.

## Which commands check each guarantee

| Guarantee | Commands |
|---|---|
| [Guarantee 1](speedrun-report.md#guarantee-1): transactions behave as if run one at a time, in real-time order | [bank_transfers](#parallel_driver_bank_transfers), [bank_autoretry](#parallel_driver_bank_autoretry), [rt_marker](#parallel_driver_rt_marker), [anytime_bank_audit](#anytime_bank_audit), [eventually_bank_audit](#eventually_bank_audit) |
| [Guarantee 2](speedrun-report.md#guarantee-2): a transaction's writes are visible together or not at all | [pair_writes](#parallel_driver_pair_writes), [pair_reads](#parallel_driver_pair_reads), [pair_check](#eventually_pair_check) |
| [Guarantee 3](speedrun-report.md#guarantee-3): acknowledged writes survive crashes | [durable_writes](#parallel_driver_durable_writes), [durable_readback](#parallel_driver_durable_readback), [durable_sample](#anytime_durable_sample), [durable_check](#eventually_durable_check) |
| [Guarantee 4](speedrun-report.md#guarantee-4): plain CQL on full-mode tables is linearizable | [fm_register](#parallel_driver_fm_register), [fm_readers](#parallel_driver_fm_readers) |
| [Guarantee 5](speedrun-report.md#guarantee-5): the cluster recovers after faults stop | [recovery_probe](#eventually_recovery_probe) |

Antithesis's own default checks also run in every test, for example that no container exits
unexpectedly. One of them caught
[a node that can never restart after a kill during a journal append](speedrun-report.md#journal-unreadable-after-kill).

## Drivers

Run at random times, many at once, while Antithesis injects faults.

<a id="parallel_driver_bank_autoretry"></a>
### `parallel_driver_bank_autoretry.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 1](speedrun-report.md#guarantee-1) · **Code:** [parallel_driver_bank_autoretry.py](antithesis/test/v1/accord/parallel_driver_bank_autoretry.py)

[Guarantee 1](speedrun-report.md#guarantee-1) driver: bank transfers sent the way a typical application sends them, with silent driver retries and application resubmits.

<details><summary>The command's own description (its docstring)</summary>

Unlike parallel_driver_bank_transfers, statements are plain (unprepared) CQL strings, run with
the driver's default RetryPolicy (which may retry silently), and the application itself resubmits
a transfer whose outcome was unknown (up to 3 attempts). A resubmitted transfer may therefore
apply more than once. That is legal: each application is a separate money-conserving transfer,
so every check stays sound for "applied once or more". Audits run every 1, 3 or 10 transfers,
and at the end.

Checks ([Guarantee 1](speedrun-report.md#guarantee-1)):
- Always: an application-retried transfer reads both accounts with balances within the bank total.
- Always: an application-retried transfer reads every transfer this client saw complete before it
  (its counters are no lower than this client's floors: real-time order).
- Always (every audit, through helper_accord.check_audit): every seeded account is visible, the
  balances sum to the initial total, none is negative, the transfer counters sum to an even
  number, and no counter is below what this client saw acknowledged or observed.
- Sometimes: a transfer was acknowledged after resubmitting an attempt whose outcome was unknown.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| an application-retried transfer reads both accounts with balances within the bank total | `always` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 12](antithesis/test/v1/accord/parallel_driver_bank_autoretry.py#L12) |
| an application-retried transfer reads every transfer this client saw complete before it | `always` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 13](antithesis/test/v1/accord/parallel_driver_bank_autoretry.py#L13) |
| a transfer was acknowledged after resubmitting an attempt whose outcome was unknown | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 18](antithesis/test/v1/accord/parallel_driver_bank_autoretry.py#L18) |

<a id="parallel_driver_bank_transfers"></a>
### `parallel_driver_bank_transfers.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 1](speedrun-report.md#guarantee-1) · **Code:** [parallel_driver_bank_transfers.py](antithesis/test/v1/accord/parallel_driver_bank_transfers.py)

[Guarantee 1](speedrun-report.md#guarantee-1) driver: bank transfers between the twelve accounts, each sent once so its outcome is explicit, mixed with read-only audits.

<details><summary>The command's own description (its docstring)</summary>

Each invocation runs a bounded mix (8, 20, 40 or 80 operations) of conditional transfers
(BEGIN TRANSACTION with LET reads, an IF balance check, and two UPDATEs on two partitions,
possibly in two tables) and read-only audits over all twelve accounts. Statements are prepared
and run with FallthroughRetryPolicy, so every attempt's outcome is visible: acknowledged, or
unknown (it may or may not have applied). Some invocations concentrate on the hot accounts.

The checks are sound under unknown outcomes, because every transfer conserves money. Real-time
order is checked within this client: any read (an audit, or a transfer's LET reads) that starts
after a transfer was acknowledged, or after an earlier read completed, must see each account's
transfer counter at least at the value that transfer wrote or that read saw. Transfers with an
unknown outcome never raise these floors.

Checks ([Guarantee 1](speedrun-report.md#guarantee-1)):
- Always: a transfer transaction reads both of its accounts.
- Always: a transfer reads balances within the bank total.
- Always: a transfer reads every transfer acknowledged or observed before it started.
- Always (every audit, through helper_accord.check_audit): every seeded account is visible, the
  balances sum to the initial total, none is negative, the transfer counters sum to an even
  number, and no counter is below what this client saw acknowledged or observed.
- Sometimes: a transfer saw transfers committed by other clients since this client last looked;
  a transfer was declined because the source balance was too low; a transfer moved a source
  account's entire balance; an audit completed while an earlier transfer's outcome was unknown.
- Reachable: a transfer ended with an unknown outcome.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a transfer reads balances within the bank total | `always` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 18](antithesis/test/v1/accord/parallel_driver_bank_transfers.py#L18) |
| a transfer reads every transfer acknowledged or observed before it started | `always` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 19](antithesis/test/v1/accord/parallel_driver_bank_transfers.py#L19) |
| a transfer transaction reads both of its accounts | `always` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 17](antithesis/test/v1/accord/parallel_driver_bank_transfers.py#L17) |
| a transfer ended with an unknown outcome | `reachable` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 26](antithesis/test/v1/accord/parallel_driver_bank_transfers.py#L26) |
| a transfer moved a source account's entire balance | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 128](antithesis/test/v1/accord/parallel_driver_bank_transfers.py#L128) |
| a transfer saw transfers committed by other clients since this client last looked | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 23](antithesis/test/v1/accord/parallel_driver_bank_transfers.py#L23) |
| a transfer was declined because the source balance was too low | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 24](antithesis/test/v1/accord/parallel_driver_bank_transfers.py#L24) |
| an audit completed while an earlier transfer's outcome was still unknown | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 25](antithesis/test/v1/accord/parallel_driver_bank_transfers.py#L25) |

<a id="parallel_driver_durable_readback"></a>
### `parallel_driver_durable_readback.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 3](speedrun-report.md#guarantee-3) · **Code:** [parallel_driver_durable_readback.py](antithesis/test/v1/accord/parallel_driver_durable_readback.py)

[Guarantee 3](speedrun-report.md#guarantee-3) driver: write, then read the acknowledged write back with a new statement, preferably through another coordinator.

<details><summary>The command's own description (its docstring)</summary>

Works in its own partitions (a random block of 100 keys above READBACK_BASE that no other
command writes). Each of 3, 10 or 25 operations writes a fresh id (any of the write styles,
explicit or auto-retry) and records it in the ledger. Once the write is acknowledged, a new read
(a multi-partition BEGIN TRANSACTION read, or plain single-partition SELECTs with an IN list),
sent preferably to a different coordinator than the one that acknowledged the write, must return
every row with its value. Order comes from execution order in this script. A read that can't
complete within its budget counts as unknown, not as a loss: availability is judged by
[Guarantee 5](speedrun-report.md#guarantee-5).

Checks ([Guarantee 3](speedrun-report.md#guarantee-3)):
- Always: an acknowledged durable write is visible with its value to the next read.
- Sometimes: an acknowledged durable write was read back through a different coordinator.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| an acknowledged durable write is visible with its value to the next read | `always` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 14](antithesis/test/v1/accord/parallel_driver_durable_readback.py#L14) |
| an acknowledged durable write was read back through a different coordinator | `sometimes` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 15](antithesis/test/v1/accord/parallel_driver_durable_readback.py#L15) |

<a id="parallel_driver_durable_writes"></a>
### `parallel_driver_durable_writes.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 3](speedrun-report.md#guarantee-3) · **Code:** [parallel_driver_durable_writes.py](antithesis/test/v1/accord/parallel_driver_durable_writes.py)

[Guarantee 3](speedrun-report.md#guarantee-3) driver: write uniquely identified rows and record each outcome in a ledger on the shared volume.

<details><summary>The command's own description (its docstring)</summary>

Each operation inserts one fresh id into 1-3 partitions of accord_ks.durable, in one of three API
styles (BEGIN TRANSACTION, conditional BEGIN TRANSACTION, or a plain INSERT on the full-mode
table), with explicit single attempts or the driver's auto-retry profile. Inserting the same row
again is idempotent, so "applied once or more" is fine. The ledger
(/ledger/durable-<writer>.jsonl, helper_durable) records each attempt, acknowledgement and unknown
outcome; anytime_durable_sample and eventually_durable_check require every acknowledged row to be
present. Shape per invocation: 5, 20 or 50 operations, hot or spread partitions, retry style.

Checks ([Guarantee 3](speedrun-report.md#guarantee-3)):
- Always (or unreachable): a conditional insert of a fresh id found no existing row for it.
- Sometimes: a durable write transaction spanning three partitions was acknowledged.
- Reachable: a durable write ended with an unknown outcome.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a conditional insert of a fresh id found no existing row for it | `always_or_unreachable` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 13](antithesis/test/v1/accord/parallel_driver_durable_writes.py#L13) |
| a durable write ended with an unknown outcome | `reachable` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 15](antithesis/test/v1/accord/parallel_driver_durable_writes.py#L15) |
| a durable write transaction spanning three partitions was acknowledged | `sometimes` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 14](antithesis/test/v1/accord/parallel_driver_durable_writes.py#L14) |

<a id="parallel_driver_fm_readers"></a>
### `parallel_driver_fm_readers.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 4](speedrun-report.md#guarantee-4) · **Code:** [parallel_driver_fm_readers.py](antithesis/test/v1/accord/parallel_driver_fm_readers.py)

[Guarantee 4](speedrun-report.md#guarantee-4) driver: concurrent plain-CQL readers of registers that other writers have published.

<details><summary>The command's own description (its docstring)</summary>

parallel_driver_fm_register (retire mode) publishes keys in /ledger/fm_keys/<key>; each file
holds a version acknowledged before the file was last replaced, and the key's writer retires the
key after any write with an unknown outcome, so the key's versions apply in increasing order.
This command reads those keys with plain SELECTs (single key, or a small IN list) for 5, 20 or 50
rounds, through varying coordinators and at varying consistency levels, while their writers may
still be running. Order comes from structure: the floor file is read before the SELECT is sent,
and the file was replaced only after its version was acknowledged, so the SELECT started after
that acknowledgement.

Checks ([Guarantee 4](speedrun-report.md#guarantee-4)):
- Always: a plain read of a published register sees at least the version acknowledged before the
  read started (read-after-acknowledge across clients).
- Always: one client's successive plain reads of a single-writer register never go backwards
  (monotonic reads).
- Sometimes: a read returned a version newer than its published floor; a reader saw a published
  register advance between two of its reads.
- Reachable: a multi-key IN read of published registers completed.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a plain read of a published register sees at least the version acknowledged before the read started | `always` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 14](antithesis/test/v1/accord/parallel_driver_fm_readers.py#L14) |
| one client's successive plain reads of a single-writer register never go backwards | `always` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 16](antithesis/test/v1/accord/parallel_driver_fm_readers.py#L16) |
| a multi-key IN read of published registers completed | `reachable` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 20](antithesis/test/v1/accord/parallel_driver_fm_readers.py#L20) |
| a plain read of a published register returned a version newer than its published floor | `sometimes` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 114](antithesis/test/v1/accord/parallel_driver_fm_readers.py#L114) |
| a reader saw a published register advance between two of its plain reads | `sometimes` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 111](antithesis/test/v1/accord/parallel_driver_fm_readers.py#L111) |

<a id="parallel_driver_fm_register"></a>
### `parallel_driver_fm_register.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 4](speedrun-report.md#guarantee-4) · **Code:** [parallel_driver_fm_register.py](antithesis/test/v1/accord/parallel_driver_fm_register.py)

[Guarantee 4](speedrun-report.md#guarantee-4) driver: plain CQL writes and read-backs on single-writer version registers in a full-mode table.

<details><summary>The command's own description (its docstring)</summary>

Ordinary single-statement CQL (no BEGIN TRANSACTION) on the transactional_mode='full' table
fm_reg. This invocation owns 1-2 private keys (random 63-bit ids) and writes strictly increasing
versions 1, 2, 3, ... to them with plain UPDATE / INSERT, and sometimes with a conditional
INSERT IF NOT EXISTS / UPDATE ... IF ver < v (which also runs through Accord). After every write
it reads the key(s) back with a plain SELECT, usually through a different coordinator, at a
consistency level drawn from the levels Accord accepts. The session sends no client-side
timestamps and no statement uses USING TIMESTAMP, so Accord picks every write timestamp. Order
comes from execution order in this script: a read runs after the previous write returned.

Per key, the floor is the highest version acknowledged, or observed by an earlier read (an
observed version v linearizes after every write acknowledged before v was sent). A read may
return a version at or above the floor, a version whose write had an unknown outcome (such a
write may linearize anywhere later), or no row only while nothing was acknowledged or observed.

Modes (per invocation):
- persist: keep writing a key after an unknown outcome (exercises late-applying writes);
- retire: abandon a key after a write with an unknown outcome and start a new one; the key's
  versions then apply in order, so it is published to /ledger/fm_keys for
  parallel_driver_fm_readers, with the highest acknowledged version (written only after the ack).

Checks ([Guarantee 4](speedrun-report.md#guarantee-4)):
- Always: a plain read on a full-mode table returns the latest acknowledged write or a newer one.
- Always: a plain read on a full-mode table returns only versions that were written.
- Always: a declined conditional write reports a current version at least as new as every
  acknowledged one.
- Sometimes: a conditional single-statement write was applied; a plain write was read back
  through a different coordinator than the one that acknowledged it; a consistency-level ONE read
  right after an acknowledged plain write returned that write.
- Reachable: a plain write with an unknown outcome was later read back.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one | `always` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 121](antithesis/test/v1/accord/parallel_driver_fm_register.py#L121) |
| a plain read on a full-mode table returns only versions that were written | `always` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 25](antithesis/test/v1/accord/parallel_driver_fm_register.py#L25) |
| a plain read on a full-mode table returns the latest acknowledged write or a newer one | `always` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 25](antithesis/test/v1/accord/parallel_driver_fm_register.py#L25) |
| a plain write with an unknown outcome was later read back | `reachable` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 32](antithesis/test/v1/accord/parallel_driver_fm_register.py#L32) |
| a conditional single-statement write on a full-mode table was applied | `sometimes` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 113](antithesis/test/v1/accord/parallel_driver_fm_register.py#L113) |
| a consistency-level ONE read right after an acknowledged plain write returned that write | `sometimes` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 177](antithesis/test/v1/accord/parallel_driver_fm_register.py#L177) |
| a plain write was read back through a different coordinator than the one that acknowledged it | `sometimes` | [Guarantee 4](speedrun-report.md#guarantee-4) | [line 174](antithesis/test/v1/accord/parallel_driver_fm_register.py#L174) |

<a id="parallel_driver_pair_reads"></a>
### `parallel_driver_pair_reads.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 2](speedrun-report.md#guarantee-2) · **Code:** [parallel_driver_pair_reads.py](antithesis/test/v1/accord/parallel_driver_pair_reads.py)

[Guarantee 2](speedrun-report.md#guarantee-2) driver: concurrent readers that read a whole token group in one transaction.

<details><summary>The command's own description (its docstring)</summary>

Each read is one BEGIN TRANSACTION with a LET per slot of a group (2-4 partitions over two
tables), so it observes one consistent snapshot. Each invocation does 5, 20 or 60 reads, on hot
or spread groups, with the driver's auto-retry profile (reads are idempotent) or single attempts.
Logged-batch groups aren't read here: their atomicity is only promised eventually, and
eventually_pair_check judges them.

Checks ([Guarantee 2](speedrun-report.md#guarantee-2)):
- Always: a cross-table read transaction saw the same token in every slot of a group, or no
  token in any slot yet.
- Sometimes: a cross-table read saw a group rewritten since this reader's previous read.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a cross-table read transaction saw the same token in every slot of a group | `always` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 11](antithesis/test/v1/accord/parallel_driver_pair_reads.py#L11) |
| a cross-table read saw a group rewritten since this reader's previous read | `sometimes` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 13](antithesis/test/v1/accord/parallel_driver_pair_reads.py#L13) |

<a id="parallel_driver_pair_writes"></a>
### `parallel_driver_pair_writes.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 2](speedrun-report.md#guarantee-2) · **Code:** [parallel_driver_pair_writes.py](antithesis/test/v1/accord/parallel_driver_pair_writes.py)

[Guarantee 2](speedrun-report.md#guarantee-2) driver: write one fresh token to every row of a group across two tables, atomically.

<details><summary>The command's own description (its docstring)</summary>

A group is 2-4 partitions over two tables (helper_accord.group_slots). Each invocation picks a
shape (5, 15 or 40 operations, hot or spread groups, retry style) and runs a bounded mix of:
- an unconditional BEGIN TRANSACTION writing the token to every slot (INSERT or UPDATE);
- a conditional BEGIN TRANSACTION that LET-reads every slot, returns them, and writes only if the
  first slot still holds the token this client last saw (compare-and-set; other writers' tokens
  make it decline);
- a LOGGED BATCH writing the token to every slot of a batch-only group (checked at the end only,
  by eventually_pair_check);
- a read-back of a group in one transaction, especially after an unknown outcome.

Retry styles: explicit single attempts (FallthroughRetryPolicy), or the driver's auto-retry
profile for unconditional writes (a hidden retry rewrites the same token: applied once or more).
Every token is unique per logical write, so a write with an unknown outcome may show up in all
slots or in none, but never in only some.

Checks ([Guarantee 2](speedrun-report.md#guarantee-2)):
- Always: a read-back after a cross-table write saw the same token in every slot.
- Always: a conditional cross-table write read the same token in every slot of its group.
- Sometimes: a cross-table write of one token to four partitions was acknowledged; a read-back
  found a write of unknown outcome applied to every slot of its group; a conditional write was
  declined because another writer changed the group.
- Reachable: a cross-table write transaction ended with an unknown outcome.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a conditional cross-table write read the same token in every slot of its group | `always` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 21](antithesis/test/v1/accord/parallel_driver_pair_writes.py#L21) |
| a read-back after a cross-table write saw the same token in every slot | `always` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 20](antithesis/test/v1/accord/parallel_driver_pair_writes.py#L20) |
| a cross-table write transaction ended with an unknown outcome | `reachable` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 25](antithesis/test/v1/accord/parallel_driver_pair_writes.py#L25) |
| a conditional cross-table write was declined because another writer changed the group | `sometimes` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 148](antithesis/test/v1/accord/parallel_driver_pair_writes.py#L148) |
| a cross-table write of one token to four partitions was acknowledged | `sometimes` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 22](antithesis/test/v1/accord/parallel_driver_pair_writes.py#L22) |
| a read-back found a write of unknown outcome applied to every slot of its group | `sometimes` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 83](antithesis/test/v1/accord/parallel_driver_pair_writes.py#L83) |

<a id="parallel_driver_rt_marker"></a>
### `parallel_driver_rt_marker.py`

**Kind:** parallel driver · **Guarantees:** [Guarantee 1](speedrun-report.md#guarantee-1) · **Code:** [parallel_driver_rt_marker.py](antithesis/test/v1/accord/parallel_driver_rt_marker.py)

[Guarantee 1](speedrun-report.md#guarantee-1) driver: transfers in a private pair of accounts, each followed by a new read that must see it (real-time order).

<details><summary>The command's own description (its docstring)</summary>

Each invocation creates its own two-account "slot" (two partitions of rt_accounts, keyed by a
random 63-bit slot id), so no other client can disturb its checks. It then runs 3, 10 or 25
transfers between the two accounts; transfer i stamps marker seq = i on both rows, guarded by
`IF a.seq < i AND b.seq < i AND a.balance >= amount`, so a late-applying older transfer whose
outcome was unknown can never overwrite a newer marker. After each transfer, a NEW read-only
transaction over both partitions, usually through a different coordinator, reads the slot back.

Checks ([Guarantee 1](speedrun-report.md#guarantee-1)):
- Always: a read started after a transfer was acknowledged sees that transfer (both markers are
  at least every marker acknowledged or observed before the read started).
- Always: a read-back of a private slot sees one consistent transfer state (both rows carry the
  same marker, balances sum to 200, none is negative).
- Always: a private-slot transfer reads the markers acknowledged before it and none from later
  transfers.
- Sometimes: a transfer's effect was read back through a different coordinator; a private-slot
  transfer was declined for insufficient balance.
- Reachable: a transfer whose outcome was unknown was later seen applied.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a private-slot transfer reads the markers acknowledged before it and none from later transfers | `always` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 16](antithesis/test/v1/accord/parallel_driver_rt_marker.py#L16) |
| a read started after a transfer was acknowledged sees that transfer | `always` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 12](antithesis/test/v1/accord/parallel_driver_rt_marker.py#L12) |
| a read-back of a private slot sees one consistent transfer state | `always` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 14](antithesis/test/v1/accord/parallel_driver_rt_marker.py#L14) |
| a transfer whose outcome was unknown was later seen applied | `reachable` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 20](antithesis/test/v1/accord/parallel_driver_rt_marker.py#L20) |
| a private-slot transfer was declined for insufficient balance | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 144](antithesis/test/v1/accord/parallel_driver_rt_marker.py#L144) |
| a transfer's effect was read back through a different coordinator | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 18](antithesis/test/v1/accord/parallel_driver_rt_marker.py#L18) |

## Checkers that run during faults

Run periodically while the drivers and faults run.

<a id="anytime_bank_audit"></a>
### `anytime_bank_audit.py`

**Kind:** anytime · **Guarantees:** [Guarantee 1](speedrun-report.md#guarantee-1) · **Code:** [anytime_bank_audit.py](antithesis/test/v1/accord/anytime_bank_audit.py)

[Guarantee 1](speedrun-report.md#guarantee-1) checker during faults: a short series of read-only bank audits that run alongside the transfer drivers.

<details><summary>The command's own description (its docstring)</summary>

Each audit is one read-only transaction over all twelve accounts in the two bank tables. The
command runs 3, 10 or 20 of them back to back within 120 s, spaced a little apart, with or
without the driver's retry policy. Because each audit starts after the previous one completed,
no account's transfer counter may go backwards between them (real-time order).

Checks ([Guarantee 1](speedrun-report.md#guarantee-1)):
- Always (every audit, through helper_accord.check_audit): every seeded account is visible, the
  balances sum to the initial total, none is negative, the transfer counters sum to an even
  number, and no counter is below what an earlier audit by this client saw.
- Sometimes: consecutive audits by one client observed newly committed transfers.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| consecutive audits by one client observed newly committed transfers | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 13](antithesis/test/v1/accord/anytime_bank_audit.py#L13) |

<a id="anytime_durable_sample"></a>
### `anytime_durable_sample.py`

**Kind:** anytime · **Guarantees:** [Guarantee 3](speedrun-report.md#guarantee-3) · **Code:** [anytime_durable_sample.py](antithesis/test/v1/accord/anytime_durable_sample.py)

[Guarantee 3](speedrun-report.md#guarantee-3) checker during faults: sampled acknowledged writes are present while faults and writers run.

<details><summary>The command's own description (its docstring)</summary>

Reads the ledgers on the shared volume, samples up to 100 acknowledged operations, and reads
their rows by explicit key. An acknowledgement line is appended only after the client saw
success, and this command reads the line before it reads the row, so the read starts after the
acknowledgement (order from structure). Reads are retried for a short budget; a read that never
completes counts as unknown, not as a loss.

Checks ([Guarantee 3](speedrun-report.md#guarantee-3)):
- Always: an acknowledged durable write sampled during the run is present with its value.
- Sometimes: a check during the run verified sampled acknowledged durable writes.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| an acknowledged durable write sampled during the run is present with its value | `always` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 11](antithesis/test/v1/accord/anytime_durable_sample.py#L11) |
| a check during the run verified sampled acknowledged durable writes | `sometimes` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 12](antithesis/test/v1/accord/anytime_durable_sample.py#L12) |

## Checkers that run after faults stop

The drivers have stopped and faults are off. Each one judges the system once it has had a chance to recover.

<a id="eventually_bank_audit"></a>
### `eventually_bank_audit.py`

**Kind:** eventually · **Guarantees:** [Guarantee 1](speedrun-report.md#guarantee-1) · **Code:** [eventually_bank_audit.py](antithesis/test/v1/accord/eventually_bank_audit.py)

[Guarantee 1](speedrun-report.md#guarantee-1) checker after faults stop: audit the bank once the drivers have stopped.

<details><summary>The command's own description (its docstring)</summary>

Runs after the drivers were stopped, possibly mid-transfer, which leaves transactions for Accord
to recover. Retries for up to 180 s until up to two audits complete, then applies the snapshot
checks. Whether the cluster recovers in time is judged by [Guarantee 5](speedrun-report.md#guarantee-5)
(eventually_recovery_probe), not here: if no audit completes, this command just exits.

Checks ([Guarantee 1](speedrun-report.md#guarantee-1)):
- Always (every audit, through helper_accord.check_audit): every seeded account is visible, the
  balances sum to the initial total, none is negative, the transfer counters sum to an even
  number, and the second audit's counters are no lower than the first's.
- Sometimes: a final audit after faults stopped saw committed transfers.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a final audit after faults stopped saw committed transfers | `sometimes` | [Guarantee 1](speedrun-report.md#guarantee-1) | [line 13](antithesis/test/v1/accord/eventually_bank_audit.py#L13) |

<a id="eventually_durable_check"></a>
### `eventually_durable_check.py`

**Kind:** eventually · **Guarantees:** [Guarantee 3](speedrun-report.md#guarantee-3) · **Code:** [eventually_durable_check.py](antithesis/test/v1/accord/eventually_durable_check.py)

[Guarantee 3](speedrun-report.md#guarantee-3) checker after faults stop: every acknowledged write in every ledger is still there.

<details><summary>The command's own description (its docstring)</summary>

Loads every writer's ledger from the shared volume (/ledger/durable-\*.jsonl) and reads every row
of every acknowledged operation by explicit key (plain single-partition SELECTs with an IN list
on the clustering key, or multi-partition BEGIN TRANSACTION reads), checking presence and value.
Order comes from structure: eventually_ commands run after the drivers have stopped, so after
every acknowledgement. Rows of operations with an unknown outcome (or whose writer died before
recording one) may be present or absent. The cluster may still be recovering, so each read is
retried for up to 120 s; a chunk that never reads is logged as unknown on stdout, never reported
as a failed check.

Checks ([Guarantee 3](speedrun-report.md#guarantee-3)):
- Always: after faults stopped, every acknowledged durable write is present with its value.
- Sometimes: the final check verified acknowledged durable writes from the ledgers; it verified
  acknowledged multi-partition writes in every partition; it found a write of unknown outcome
  applied.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| after faults stopped every acknowledged durable write is present with its value | `always` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 59](antithesis/test/v1/accord/eventually_durable_check.py#L59) |
| a final check found a write of unknown outcome applied | `sometimes` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 85](antithesis/test/v1/accord/eventually_durable_check.py#L85) |
| a final check verified acknowledged durable writes from the ledgers | `sometimes` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 72](antithesis/test/v1/accord/eventually_durable_check.py#L72) |
| a final check verified acknowledged multi-partition durable writes in every partition | `sometimes` | [Guarantee 3](speedrun-report.md#guarantee-3) | [line 75](antithesis/test/v1/accord/eventually_durable_check.py#L75) |

<a id="eventually_pair_check"></a>
### `eventually_pair_check.py`

**Kind:** eventually · **Guarantees:** [Guarantee 2](speedrun-report.md#guarantee-2) · **Code:** [eventually_pair_check.py](antithesis/test/v1/accord/eventually_pair_check.py)

[Guarantee 2](speedrun-report.md#guarantee-2) checker after faults stop: every token group holds one token in every row, or none.

<details><summary>The command's own description (its docstring)</summary>

Runs after the drivers stopped, possibly mid-write: Accord must recover or invalidate each
in-flight transaction as a whole, and logged batches may still be replayed from the batchlog.
Each group, transactional or logged-batch, is read in one BEGIN TRANSACTION. Groups whose read
doesn't complete in the time budget are skipped: whether the cluster recovers is judged by
[Guarantee 5](speedrun-report.md#guarantee-5) (eventually_recovery_probe), not here.

Checks ([Guarantee 2](speedrun-report.md#guarantee-2)):
- Always: after faults stopped, every transactional group holds the same token in every slot.
- Always: after faults stopped, every logged-batch group holds the same token in every slot.
- Sometimes: the final check saw transactional groups written; it saw logged-batch groups written.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| after faults stopped every logged-batch group holds the same token in every slot | `always` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 50](antithesis/test/v1/accord/eventually_pair_check.py#L50) |
| after faults stopped every transactional group holds the same token in every slot | `always` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 54](antithesis/test/v1/accord/eventually_pair_check.py#L54) |
| a final check after faults stopped saw logged-batch groups written | `sometimes` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 59](antithesis/test/v1/accord/eventually_pair_check.py#L59) |
| a final check after faults stopped saw transactional groups written | `sometimes` | [Guarantee 2](speedrun-report.md#guarantee-2) | [line 57](antithesis/test/v1/accord/eventually_pair_check.py#L57) |

<a id="eventually_recovery_probe"></a>
### `eventually_recovery_probe.py`

**Kind:** eventually · **Guarantees:** [Guarantee 5](speedrun-report.md#guarantee-5) · **Code:** [eventually_recovery_probe.py](antithesis/test/v1/accord/eventually_recovery_probe.py)

[Guarantee 5](speedrun-report.md#guarantee-5) checker after faults stop: transactions succeed again, through every node, within 120 s.

<details><summary>The command's own description (its docstring)</summary>

Runs as an eventually_ command, after Antithesis has stopped injecting faults and restarted any
container it killed. The 120 s window starts when this command starts. The window is our
inference: Cassandra documents no recovery time (see properties/recovers-after-faults.md).

Probes, repeated in rounds with a 3 s pause until all succeed or the window ends:
- through EACH of the 3 nodes as coordinator (host-targeted execution): a small multi-partition
  read-write BEGIN TRANSACTION on two keys reserved for that node (table kv, full mode);
- a plain single-partition INSERT then SELECT at QUORUM on a fresh key, through any coordinator.
Each request has a 15 s client timeout (the server answers within its 10 s transaction deadline),
the driver reconnects to a down node every 2 s, and no request starts after the window, so the
command ends within about 150 s. Every error, timeout or unknown outcome counts as "not yet"; a
success counts only if it completed inside the window. Every attempt writes a fresh probe id. A
node still down at the end of the window is a failure, not a reason to skip: Antithesis restarts
every container it kills.

Checks ([Guarantee 5](speedrun-report.md#guarantee-5)):
- Always: a transaction succeeded within 120 seconds after faults stopped.
- Always: every node coordinated a transaction within 120 seconds after faults stopped.
- Always: a plain write and read on a transactional table succeeded within 120 seconds.
- Sometimes: a transaction succeeded after the first attempt had failed; the first attempt
  succeeded; a node coordinated a transaction after earlier attempts through it failed.

</details>

| Assertion | Type | Guarantee | Where |
|---|---|---|---|
| a plain write and read on a transactional table succeeded within 120 seconds after faults stopped | `always` | [Guarantee 5](speedrun-report.md#guarantee-5) | [line 22](antithesis/test/v1/accord/eventually_recovery_probe.py#L22) |
| a transaction succeeded within 120 seconds after faults stopped | `always` | [Guarantee 5](speedrun-report.md#guarantee-5) | [line 20](antithesis/test/v1/accord/eventually_recovery_probe.py#L20) |
| every node coordinated a transaction within 120 seconds after faults stopped | `always` | [Guarantee 5](speedrun-report.md#guarantee-5) | [line 21](antithesis/test/v1/accord/eventually_recovery_probe.py#L21) |
| a node coordinated a transaction after earlier attempts through it failed | `sometimes` | [Guarantee 5](speedrun-report.md#guarantee-5) | [line 24](antithesis/test/v1/accord/eventually_recovery_probe.py#L24) |
| a transaction succeeded after the first attempt once faults stopped had failed | `sometimes` | [Guarantee 5](speedrun-report.md#guarantee-5) | [line 23](antithesis/test/v1/accord/eventually_recovery_probe.py#L23) |
| the first transaction attempt once faults stopped succeeded | `sometimes` | [Guarantee 5](speedrun-report.md#guarantee-5) | [line 160](antithesis/test/v1/accord/eventually_recovery_probe.py#L160) |

## Setup

<a id="client_setup"></a>
### `client_setup.py`

**Kind:** setup, before any command · **Guarantees:** none · **Code:** [client_setup.py](antithesis/test/setup/client_setup.py)

Cluster bootstrap, run by the client container before any test command: schema, a probe through every node, the bank seed, then setup_complete.

<details><summary>The command's own description (its docstring)</summary>

Steps (deployment-topology.md, "Bootstrap sequence"):
  1. connect to all three nodes and wait until each sees the other two (all UN);
  2. wait for node1's cluster-metadata helper to finish `nodetool cms reconfigure 3`
     (/bootstrap/cms-ready);
  3. create the keyspace (replication factor 3) and every table WITH transactional_mode='full',
     at consistency QUORUM;
  4. probe: a read-write Accord transaction must succeed with every node as coordinator; then
     seed the twelve bank accounts for [Guarantee 1](speedrun-report.md#guarantee-1) in one conditional transaction (idempotent);
  5. emit setup_complete through the Antithesis SDK.
Idempotent: safe to rerun if the client container restarts.

No assertions here.

</details>

## Shared code

The `helper_*` files aren't commands: Antithesis ignores them. They hold what several commands share.

| Helper | What it holds |
|---|---|
| <a id="helper_accord"></a>[`helper_accord.py`](antithesis/test/v1/accord/helper_accord.py) | Shared helpers for the whole Accord workload: sessions, outcome classification, randomness, and the bank model. |
| <a id="helper_durable"></a>[`helper_durable.py`](antithesis/test/v1/accord/helper_durable.py) | Shared code for [Guarantee 3](speedrun-report.md#guarantee-3): the durable table, the per-writer ledger on the shared volume, the write styles, and the read-back every checker uses. |
| <a id="helper_fm"></a>[`helper_fm.py`](antithesis/test/v1/accord/helper_fm.py) | Shared helpers for [Guarantee 4](speedrun-report.md#guarantee-4): plain single-statement CQL (no BEGIN TRANSACTION) on the full-mode table fm_reg. |

