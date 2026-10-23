# Guarantees: Apache Cassandra Accord

Written for the Cassandra / Accord engineers. Each row is a promise Cassandra-on-Accord makes to the
applications that use it, stated in plain technical language.
Ranked: faults/concurrency-sensitivity × business impact, with client-checkability as the tie-breaker.

Primary sources (Cassandra repo, Apache-2.0):
- D1 = `doc/modules/cassandra/pages/developing/cql/transactions.adoc` (trunk) — https://github.com/apache/cassandra/blob/trunk/doc/modules/cassandra/pages/developing/cql/transactions.adoc
- D2 = `doc/modules/cassandra/pages/managing/operating/onboarding-to-accord.adoc` (cassandra-6.0-alpha2) — https://github.com/apache/cassandra/blob/cassandra-6.0-alpha2/doc/modules/cassandra/pages/managing/operating/onboarding-to-accord.adoc
- D3 = CEP-15 General Purpose Transactions — https://cwiki.apache.org/confluence/display/CASSANDRA/CEP-15%3A+General+Purpose+Transactions

| ID | Guarantee | Source | Breaks under | Property slug | Type |
|---|---|---|---|---|---|
| G1 | Transactions (`BEGIN TRANSACTION … COMMIT TRANSACTION`) spanning several partitions and tables behave as if they ran one at a time, in an order that respects real time: a transaction that starts after another was acknowledged sees its effects, and no two concurrent transactions see each other's writes partially (strict serializability) | [D1](https://github.com/apache/cassandra/blob/trunk/doc/modules/cassandra/pages/developing/cql/transactions.adoc): "**Strict Serializability**: Transactions execute as if in a single, total order that respects real-time ordering" | partition, crash/restart of a replica or coordinator, message delay/reordering, concurrent conflicting transactions, clock skew | `txn-strict-serializable` | Safety |
| G2 | All writes of one transaction become visible together or not at all, across partitions and tables, even when the coordinator fails mid-commit (atomic commitment) | [D1](https://github.com/apache/cassandra/blob/trunk/doc/modules/cassandra/pages/developing/cql/transactions.adoc): "**Atomic Commitment**: All changes commit together or none at all"; "Multi-Table Atomicity: Ensure related changes across tables succeed or fail together" | coordinator crash during commit, partition between replicas, transaction recovery | `txn-all-or-nothing` | Safety |
| G3 | A transaction acknowledged to the client survives the crash and restart of a minority of replicas: its writes are still read afterwards (durability) | [D1](https://github.com/apache/cassandra/blob/trunk/doc/modules/cassandra/pages/developing/cql/transactions.adoc): "**Durable Writes**: Committed transactions survive node failures" | crash/restart, partition, journal replay | `acked-txn-durable` | Safety |
| G4 | On a table with `transactional_mode='full'`, ordinary single-statement CQL reads and writes are linearizable: a read that starts after a write was acknowledged returns that write or a newer one, whichever replica coordinates it (linearizability) | [D1](https://github.com/apache/cassandra/blob/trunk/doc/modules/cassandra/pages/developing/cql/transactions.adoc): "Normal CQL reads and writes become linearizable when `transactional_mode='full'`"; [D2](https://github.com/apache/cassandra/blob/cassandra-6.0-alpha2/doc/modules/cassandra/pages/managing/operating/onboarding-to-accord.adoc): "non-SERIAL operations are linearizable by default when migrated to Accord" | partition, crash/restart, coordinator change | `full-mode-linearizable` | Safety |
| G5 | Once failures stop, a transaction against the cluster succeeds again within 120 s (availability after recovery) | [D3](https://cwiki.apache.org/confluence/display/CASSANDRA/CEP-15%3A+General+Purpose+Transactions): "Optimal failure tolerance: latency and performance should be unaffected by any minority of replica failures"; window inferred (no documented recovery time; 120 s) | faults stopping | `recovers-after-faults` | Liveness |

## Notes per guarantee

### G1: txn-strict-serializable
- **The check, in one sentence:** Bank-style transfers between accounts on different partitions (LET/IF/UPDATE in one transaction) plus read-only transactions over all accounts: `Always` every snapshot read in one transaction sums to the fixed total and no balance is negative, and a read-only transaction started after a transfer was acknowledged reflects it (per-account monotonic transfer counters).
- **Inherited from:** Accord protocol (cassandra-accord library), surfaced through Cassandra CQL.
- **Why it matters:** this is the headline promise of CEP-15; a violation is lost or created money in exactly the use case the docs advertise (multi-partition transfers, inventory).

### G2: txn-all-or-nothing
- **The check, in one sentence:** Each transaction writes the same unique token to rows in two tables / partitions; `Always` any later read transaction sees the token in both places or in neither.
- **Inherited from:** Accord (commit/apply + recovery), Cassandra txn integration.
- **Why it matters:** partially-applied multi-table updates are the classic corruption Accord exists to prevent.

### G3: acked-txn-durable
- **The check, in one sentence:** Record every acknowledged transactional append (ledger on the shared volume); after faults stop, `Always` every acknowledged append is present when read through a transaction.
- **Inherited from:** Accord journal + Cassandra storage.
- **Why it matters:** acknowledged data loss is a severity-1 incident.

### G4: full-mode-linearizable
- **The check, in one sentence:** Plain INSERT/UPDATE/SELECT (no BEGIN TRANSACTION) on a `transactional_mode='full'` table using per-key version counters; `Always` a read started after an acknowledged write returns that version or newer, and versions read by one client never go backwards.
- **Inherited from:** Cassandra's CQL-on-Accord integration.
- **Why it matters:** this is the migration story ("as simple as enabling transactional_mode='full'"); stale reads break apps that relied on it.

### G5: recovers-after-faults
- **The check, in one sentence:** In an `eventually_` command after faults stop, retry a small read-write transaction until 120 s pass; `Always` it succeeds within the window; `Sometimes` a first attempt failed and a later one succeeded.
- **Inherited from:** Accord recovery / Cassandra TCM + CMS.
- **Why it matters:** a cluster stuck after failures (e.g. blocked dependencies, unrecovered transactions) is an outage.
