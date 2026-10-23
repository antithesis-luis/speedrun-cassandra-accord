"""Shared helpers for Guarantee 4: plain single-statement CQL (no BEGIN TRANSACTION) on the full-mode table fm_reg.

Table fm_reg (k bigint PRIMARY KEY, ver bigint, pad text), transactional_mode='full'.

Each key has exactly one writer (a random 63-bit key owned by one command invocation) that writes
strictly increasing versions 1, 2, 3, ... Sessions run with client-side timestamps disabled
(helper_accord.connect(client_timestamps=False)) and no statement uses USING TIMESTAMP, so Accord
assigns every write timestamp.

Published keys (single-writer keys whose writer retires the key after any write with an unknown
outcome) live in /ledger/fm_keys/<key>; the file holds the highest version acknowledged before the
file was last replaced, so a reader that reads the file and then the key must see at least that
version.

No assertions here: every assertion message is a literal at one callsite in a command file.
"""
import os

from cassandra import ConsistencyLevel
from cassandra.query import SimpleStatement

import helper_accord as h

TABLE = f"{h.KEYSPACE}.fm_reg"
PUBLISH_DIR = os.environ.get("FM_PUBLISH_DIR", "/ledger/fm_keys")

# Consistency levels Accord accepts (IAccordService.SUPPORTED_*). In full mode Accord ignores them
# (ONE commits at QUORUM), so every one must give the same linearizable answer. ANY is accepted for
# commits but not documented for full mode, so it is left out; LOCAL_*, TWO, THREE are rejected.
WRITE_CLS = (ConsistencyLevel.ONE, ConsistencyLevel.QUORUM, ConsistencyLevel.ALL)
READ_CLS = (ConsistencyLevel.ONE, ConsistencyLevel.QUORUM, ConsistencyLevel.ALL,
            ConsistencyLevel.ONE, ConsistencyLevel.QUORUM, ConsistencyLevel.SERIAL)

# pad sizes: none, one char, short, 4 KiB (a larger mutation)
PAD_MENU = (0, 1, 64, 4096)


def cl_name(cl):
    return ConsistencyLevel.value_to_name.get(cl, str(cl))


def pad():
    n = h.choice(PAD_MENU)
    return "p" * n


def up_hosts(cluster):
    return [x for x in cluster.metadata.all_hosts() if x.is_up]


def pick_host(cluster, avoid=None):
    """A live host other than `avoid` (a coordinator string), or None to let the load balancer
    choose. Prefers a different node 3 times out of 4."""
    hosts = [x for x in up_hosts(cluster) if str(x) != avoid and str(x.endpoint) != avoid]
    if hosts and h.coin(3, 4):
        return h.choice(hosts)
    return None


def execute(session, stmt, params=None, host=None):
    if host is not None:
        return session.execute(stmt, params, host=host)
    return session.execute(stmt, params)


def write_stmt(style, cl):
    """-> (statement, param builder(k, ver, pad), conditional?)."""
    if style == "update":
        cql = f"UPDATE {TABLE} SET ver = %s, pad = %s WHERE k = %s"
        build = lambda k, v, p: (v, p, k)  # noqa: E731
        cond = False
    elif style == "insert":
        cql = f"INSERT INTO {TABLE} (k, ver, pad) VALUES (%s, %s, %s)"
        build = lambda k, v, p: (k, v, p)  # noqa: E731
        cond = False
    elif style == "insert_ine":
        cql = f"INSERT INTO {TABLE} (k, ver, pad) VALUES (%s, %s, %s) IF NOT EXISTS"
        build = lambda k, v, p: (k, v, p)  # noqa: E731
        cond = True
    elif style == "update_if":
        cql = f"UPDATE {TABLE} SET ver = %s, pad = %s WHERE k = %s IF ver < %s"
        build = lambda k, v, p: (v, p, k, v)  # noqa: E731
        cond = True
    else:
        raise ValueError(style)
    st = SimpleStatement(cql, consistency_level=cl, serial_consistency_level=ConsistencyLevel.SERIAL,
                         is_idempotent=False)
    return st, build, cond


def lwt_outcome(rs):
    """-> (applied, current ver or None) for a conditional statement's result."""
    rows = list(rs)
    if not rows:
        return False, None
    row = rows[0]
    applied = bool(row[0])
    ver = getattr(row, "ver", None) if not applied else None
    return applied, ver


def read_stmt(keys, cl):
    """Single-key SELECT (EphemeralRead) or an IN list (full Accord Read), never paged."""
    if len(keys) == 1:
        cql = f"SELECT k, ver FROM {TABLE} WHERE k = {int(keys[0])}"
    else:
        cql = f"SELECT k, ver FROM {TABLE} WHERE k IN ({', '.join(str(int(k)) for k in keys)})"
    return SimpleStatement(cql, consistency_level=cl, fetch_size=1000)


def read_versions(session, keys, cl, host=None):
    """-> ({k: ver or None}, coordinator). Raises on error."""
    rs = execute(session, read_stmt(keys, cl), host=host)
    got = {k: None for k in keys}
    for r in rs:
        got[r.k] = r.ver
    return got, h.coordinator_of(rs)


# ---------------------------------------------------------------------------------------------
# publication of single-writer keys for concurrent readers (shared /ledger volume)


def publish(key, floor):
    """Atomically record that `floor` was acknowledged for `key` (called only after the ack)."""
    try:
        os.makedirs(PUBLISH_DIR, exist_ok=True)
        tmp = os.path.join(PUBLISH_DIR, f".{key}.tmp")
        with open(tmp, "w") as f:
            f.write(str(int(floor)))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, os.path.join(PUBLISH_DIR, str(key)))
    except OSError as e:
        h.log("fm", f"publish {key} failed: {e}")


def published_keys():
    try:
        return [int(n) for n in os.listdir(PUBLISH_DIR) if n.isdigit()]
    except OSError:
        return []


def published_floor(key):
    """Highest version acknowledged before the file was last replaced, or None."""
    try:
        with open(os.path.join(PUBLISH_DIR, str(key))) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None
