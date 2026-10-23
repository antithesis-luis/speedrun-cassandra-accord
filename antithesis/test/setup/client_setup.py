#!/usr/bin/env python3
"""Cluster bootstrap, run by the client container before any test command: schema, a probe through every node, the bank seed, then setup_complete.

Steps (deployment-topology.md, "Bootstrap sequence"):
  1. connect to all three nodes and wait until each sees the other two (all UN);
  2. wait for node1's cluster-metadata helper to finish `nodetool cms reconfigure 3`
     (/bootstrap/cms-ready);
  3. create the keyspace (replication factor 3) and every table WITH transactional_mode='full',
     at consistency QUORUM;
  4. probe: a read-write Accord transaction must succeed with every node as coordinator; then
     seed the twelve bank accounts for Guarantee 1 in one conditional transaction (idempotent);
  5. emit setup_complete through the Antithesis SDK.
Idempotent: safe to rerun if the client container restarts.

No assertions here.
"""
import os
import sys
import time

from cassandra import ConsistencyLevel
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile
from cassandra.policies import RoundRobinPolicy
from cassandra.protocol import SyntaxException

from antithesis.lifecycle import setup_complete

NODES = os.environ.get(
    "CASSANDRA_NODES", "cassandra-accord-node1,cassandra-accord-node2,cassandra-accord-node3"
).split(",")
CMS_READY = os.environ.get("CMS_READY_FILE", "/bootstrap/cms-ready")
KEYSPACE = "accord_ks"

SCHEMA = [
    f"CREATE KEYSPACE IF NOT EXISTS {KEYSPACE} WITH replication = "
    "{'class': 'NetworkTopologyStrategy', 'datacenter1': 3}",
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.accounts (id int PRIMARY KEY, balance bigint, xfers bigint) "
    "WITH transactional_mode='full'",
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.accounts_b (id int PRIMARY KEY, balance bigint, xfers bigint) "
    "WITH transactional_mode='full'",
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.rt_accounts (slot bigint, acct int, balance bigint, seq bigint, "
    "PRIMARY KEY ((slot, acct))) WITH transactional_mode='full'",
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.pair_a (k int PRIMARY KEY, tok text) WITH transactional_mode='full'",
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.pair_b (k int PRIMARY KEY, tok text) WITH transactional_mode='full'",
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.ledger (k int, seq int, v text, PRIMARY KEY (k, seq)) "
    "WITH transactional_mode='full'",
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.kv (k int PRIMARY KEY, ver bigint) WITH transactional_mode='full'",
    # full-mode-linearizable (Guarantee 4): single-writer version registers written with plain CQL; see helper_fm.py
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.fm_reg (k bigint PRIMARY KEY, ver bigint, pad text) "
    "WITH transactional_mode='full'",
    # acked-txn-durable (Guarantee 3): one row per (partition, unique op id); see helper_durable.py
    f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.durable (k int, id bigint, v text, PRIMARY KEY (k, id)) "
    "WITH transactional_mode='full'",
]


def log(msg):
    print(f"client-setup: {msg}", flush=True)


def retry(what, fn, delay=3.0):
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except SyntaxException:
            raise  # a bug in this script, not a transient cluster condition
        except Exception as e:  # noqa: BLE001 - bootstrap retries everything else
            log(f"{what}: attempt {attempt} failed: {type(e).__name__}: {e}")
            time.sleep(delay)


def connect():
    profile = ExecutionProfile(
        load_balancing_policy=RoundRobinPolicy(),
        consistency_level=ConsistencyLevel.QUORUM,  # Accord rejects LOCAL_ONE (the driver default)
        serial_consistency_level=ConsistencyLevel.SERIAL,
        request_timeout=60,
    )
    # Cluster() resolves the contact points itself (UnresolvableContactPoints if none resolve);
    # the caller's retry() loop retries any exception from here.
    cluster = Cluster(NODES, execution_profiles={EXEC_PROFILE_DEFAULT: profile}, connect_timeout=10)
    try:
        return cluster, cluster.connect()
    except Exception:
        cluster.shutdown()
        raise


def all_nodes_up(cluster, session):
    hosts = {h.address: h for h in cluster.metadata.all_hosts()}
    if len(hosts) < len(NODES) or not all(h.is_up for h in hosts.values()):
        raise RuntimeError(f"driver sees {len(hosts)} hosts, up={[h.is_up for h in hosts.values()]}")
    for h in hosts.values():
        peers = list(session.execute("SELECT peer FROM system.peers_v2", host=h))
        if len(peers) < len(NODES) - 1:
            raise RuntimeError(f"{h.address} sees {len(peers)} peers")
    return hosts


def wait_cms_ready():
    while not os.path.exists(CMS_READY):
        log(f"waiting for {CMS_READY} (node1 CMS reconfigure helper)")
        time.sleep(5)


def create_schema(cluster, session):
    for stmt in SCHEMA:
        retry(f"schema [{stmt[:60]}...]", lambda s=stmt: session.execute(s, timeout=120))

    def agree():
        if not cluster.control_connection.wait_for_schema_agreement(wait_time=60):
            raise RuntimeError("no schema agreement")

    retry("schema agreement", agree)


def probe(session, hosts):
    for i, h in enumerate(sorted(hosts.values(), key=lambda x: str(x.address))):
        stmt = (
            "BEGIN TRANSACTION "
            f"UPDATE {KEYSPACE}.kv SET ver = 0 WHERE k = {-1 - i}; "
            "COMMIT TRANSACTION"
        )
        retry(f"probe txn via {h.address}", lambda s=stmt, host=h: session.execute(s, host=host, timeout=60))
        log(f"probe transaction committed with coordinator {h.address}")


# Bank accounts for txn-strict-serializable (Guarantee 1); must match helper_accord.BANK_* in the template.
# Ids are disjoint across tables (a txn may not update the same key + column names in two tables).
BANK_ACCOUNTS = [("accounts", i) for i in range(6)] + [("accounts_b", 100 + i) for i in range(6)]
BANK_INITIAL = 1000


def seed_bank(session):
    """Insert the bank accounts once, atomically, only if they do not exist yet (safe to rerun and
    safe to resubmit after an unknown outcome)."""
    inserts = "".join(
        f"    INSERT INTO {KEYSPACE}.{t} (id, balance, xfers) VALUES ({i}, {BANK_INITIAL}, 0);\n"
        for t, i in BANK_ACCOUNTS
    )
    stmt = (
        "BEGIN TRANSACTION\n"
        f"  LET s = (SELECT balance FROM {KEYSPACE}.accounts WHERE id = 0);\n"
        "  SELECT s.balance;\n"
        "  IF s IS NULL THEN\n" + inserts + "  END IF\n"
        "COMMIT TRANSACTION"
    )
    retry("seed bank accounts", lambda: session.execute(stmt, timeout=60))


def main():
    log(f"nodes={NODES}")
    cluster, session = retry("connect", connect)
    hosts = retry("all nodes up", lambda: all_nodes_up(cluster, session))
    log(f"all {len(hosts)} nodes up and peered")
    wait_cms_ready()
    log("CMS reconfigured to 3 members")
    create_schema(cluster, session)
    log("schema created")
    probe(session, hosts)
    seed_bank(session)
    log("bank accounts seeded")
    cluster.shutdown()
    setup_complete({"message": "3-node Accord cluster ready", "nodes": NODES})
    log("setup_complete emitted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
