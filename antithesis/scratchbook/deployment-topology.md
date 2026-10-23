---
sut_path: /home/exedev/cassandra/cassandra-accord/src/cassandra
commit: e874e3a90b1942b945477e6d9ba03880b4f4a19d
updated: 2026-10-08
external_references:
  - path: https://github.com/apache/cassandra/blob/cassandra-6.0-alpha2/doc/modules/cassandra/pages/managing/operating/onboarding-to-accord.adoc
    why: accord yaml settings and transactional_mode
  - path: /home/exedev/cassandra/cassandra-accord/src/cassandra/test/distributed/org/apache/cassandra/distributed/test/accord/AccordTestBase.java
    why: the project's own Accord cluster config (vnodes off, timeouts, shard counts)
---

# Deployment topology

4 containers in total: 3 SUT, 1 client, no dependencies, no monitor.

```text
                 +-------------------------------+
                 | cassandra-accord-client       |
                 | Python workload, cassandra-   |
                 | driver + antithesis SDK,      |
                 | test template, nodetool (opt) |
                 +---------------+---------------+
                                 | CQL 9042 (all 3 nodes as contact points)
          +----------------------+----------------------+
          v                      v                      v
+-------------------+  +-------------------+  +-------------------+
| cassandra-accord- |<>| cassandra-accord- |<>| cassandra-accord- |
| node1 (seed)      |  | node2             |  | node3             |
| CMS member        |  | CMS member        |  | CMS member        |
+-------------------+  +-------------------+  +-------------------+
       internode 7000 (Accord messages, TCM/CMS Paxos, gossip)
```

## Components

| Container (= hostname) | Image | Role | Runs | Network |
|---|---|---|---|---|
| `cassandra-accord-node1` | new Dockerfile: builder (JDK 11, ant) builds Cassandra `e874e3a9` including `modules/accord` @ `fff32de`, then the runtime stage is JRE 11 + the built tarball | **SUT** (seed) | `cassandra -f` (one JVM) | 7000 internode, 9042 CQL, 7199 JMX |
| `cassandra-accord-node2` | same image | **SUT** | `cassandra -f` | same |
| `cassandra-accord-node3` | same image | **SUT** | `cassandra -f` | same |
| `cassandra-accord-client` | new Dockerfile: python:3.11-slim + `cassandra-driver` + `antithesis` Python SDK. Optionally copy the Cassandra `bin/nodetool`+`lib/` from the SUT image for the CMS reconfigure and status checks | **Workload** | entrypoint: setup script, then `setup_complete`, then sleep. Test template at `/opt/antithesis/test/v1/accord/` (helpers prefixed `helper_`) | CQL to all 3 nodes; JMX 7199 to nodes (optional) |

A shared named volume `ledger` is mounted at `/ledger` in the client. Today only the client writes
it. It holds the records of acknowledged and ambiguous operations (for G3), and it survives client
restarts (workload-guidance §6). The SUT does not need it.

Roles for `launchers.roles`: SUT = node1, node2, node3. Workload = client: network faults yes,
node faults no. Monitors: none. A sidecar is not needed because every check runs as a test
command against the cluster, and the ledger lives on a volume.

## Node configuration (all three identical except addresses)

- `cluster_name: accord-test`, `num_tokens: 1` (as the project's Accord dtests do,
  `AccordTestBase.withoutVNodes()`), `partitioner: Murmur3Partitioner`, `endpoint_snitch:
  SimpleSnitch` (DC `datacenter1`).
- `seed_provider … seeds: "__SEEDS__"`, rendered by sut/entrypoint.sh: first boot (no
  /var/lib/cassandra/data/system) `cassandra-accord-node1` only (keeps node1 → node2 → node3 bootstrap
  order); restart: all three names (SimpleSeedProvider skips unresolvable names, so a node restarting
  while node1 is down still has itself as a seed). `listen_address`/`rpc_address` = own hostname.
- Static addresses: network `accord` (bridge, subnet 10.231.17.0/24): node1 .11, node2 .12, node3 .13,
  client .20, so a restarted node keeps its IP (TCM/CMS membership is address-keyed). Antithesis docs
  say restarted nodes "may change IP addresses" and do not document `ipv4_address`; whether it holds
  across Antithesis restarts must be checked in the next run.
  `broadcast_rpc_address` = hostname.
- `accord:` block (required to turn Accord on):
  ```yaml
  accord:
    enabled: true
    journal_directory: /var/lib/cassandra/accord_journal
    default_transactional_mode: full   # safety net; tables also say it explicitly
  ```
  plus the tuning rows in `tuning.md`.
- Data, commitlog, hints, saved_caches and accord_journal live on the container's own filesystem
  under `/var/lib/cassandra`. They must persist across a container kill/restart: no tmpfs, and no
  wiping in the entrypoint. G3 depends on this.
- Memory: `MAX_HEAP_SIZE=1536M` per node. G1 is the default on JDK 11
  (`conf/jvm11-server.options:63`), so `HEAP_NEWSIZE` must stay unset (`conf/cassandra-env.sh:114–137`).
  Accord's cache defaults to 10% of heap and its working set to 5%
  (`DatabaseDescriptor.java:1035–1054`), which is fine at this size. There is no documented hard
  minimum. 1 GiB also boots, but 1.5 GiB leaves headroom for journal replay after restart. Budget
  is about 2.5 GiB RSS per node, about 8 GiB in total including the client.
- JMX: if the client runs `nodetool` remotely, set `LOCAL_JMX=no` and disable JMX auth for the
  test (`-Dcom.sun.management.jmxremote.authenticate=false`). Alternatively, run the one-time
  reconfigure from inside node1's entrypoint as a background helper.

## Bootstrap sequence (what must be true before `setup_complete`)

1. **node1 starts first.** It is the only seed. Its address is not loopback, so it boots in `VOTE`
   mode (`tcm/Startup.java:605–626`). Discovery finds only itself, it nominates itself, and it
   becomes the **single CMS member** automatically (`Startup.java:232–281`). **No
   `nodetool cms initialize`**: that command is for upgrading a gossip-mode cluster
   (`tools/nodetool/CMSAdmin.java:95`).
2. **node2, then node3** start once node1 answers on 9042. Their entrypoint waits for
   `cassandra-accord-node1:9042`. Starting them one after another avoids racing joins. Each
   discovers the existing CMS and joins through `BootstrapAndJoin`.
3. **The client waits** until all 3 nodes are `UN`. It can poll `nodetool -h node1 status`, or
   query `system.peers_v2` on each node through CQL until every node sees the other two.
4. **Client reconfigures the CMS to 3 members:** `nodetool -h cassandra-accord-node1 cms
   reconfigure 3`, then polls `nodetool cms reconfigure --status` / `nodetool cms describe` until
   3 members are listed. Without this the CMS stays at RF 1: joins re-apply the current meta RF
   (`ClusterMetadataService.java:514`, `DistributedMetadataLogKeyspace.java:253`), and losing node1
   would freeze schema and topology changes.
5. **The client creates the schema** at CL QUORUM:
   ```sql
   CREATE KEYSPACE accord_ks WITH replication = {'class':'NetworkTopologyStrategy','datacenter1':3};
   CREATE TABLE accord_ks.accounts (id int PRIMARY KEY, balance bigint, xfers bigint) WITH transactional_mode='full';
   CREATE TABLE accord_ks.pair_a  (k int PRIMARY KEY, token text) WITH transactional_mode='full';
   CREATE TABLE accord_ks.pair_b  (k int PRIMARY KEY, token text) WITH transactional_mode='full';
   CREATE TABLE accord_ks.ledger  (k int, seq int, v text, PRIMARY KEY (k, seq)) WITH transactional_mode='full';
   CREATE TABLE accord_ks.kv      (k int PRIMARY KEY, ver bigint) WITH transactional_mode='full';
   ```
   (The exact tables belong to the workload phase. These are illustrative.)
6. **Readiness probe:** retry a trivial read-write txn (`BEGIN TRANSACTION UPDATE … ; COMMIT
   TRANSACTION`) on each node as coordinator until all three succeed. This also proves that the
   Accord topology has caught up to the TCM epoch carrying the new tables (compare
   `AccordTestBase.java:184`). Then seed the initial account rows in one txn.
7. Emit `setup_complete`.

## Why this topology keeps quorum after one failure

- **Data and Accord:** RF=3 on 3 nodes, so every node replicates every key. Accord needs a simple
  quorum of 2 for Accept/Commit/recovery. With one node down, the remaining two form a quorum. The
  fast-path electorate is reconfigured after `fast_path_update_delay`, and until then txns take the
  slow path. Any surviving node can coordinate, because there is no leader. Recovery of a dead
  coordinator's txns runs on survivors (progress log → `MaybeRecover`).
- **CMS/TCM:** after step 4 the CMS has 3 members on a Paxos-backed log, so 2 of 3 can still
  commit metadata changes. Steady-state txns do not need the CMS at all.
- **Spare capacity:** there is nowhere to move replicas (RF = node count). The system's own
  availability mechanism is quorum plus leaderless coordination, not re-replication, so this is
  the documented minimum for "tolerate one failure" with RF=3. Nothing is pinned. The client
  spreads requests over all three nodes (driver round-robin with all three contact points), so
  losing any one node only removes one coordinator.
- **Not tolerated** (by design, not a bug): two nodes down at once loses quorum and txns time out.
  G5 is measured only after faults stop.

## SDKs

- Client: `antithesis` Python SDK (assertions, lifecycle `setup_complete`) and `cassandra-driver`
  (DataStax/Apache, protocol v5).
- SUT: no instrumentation is required. Java instrumentation of the Cassandra/Accord jars is
  optional for coverage, and the setup phase decides on it.
