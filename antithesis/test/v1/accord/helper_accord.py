"""Shared helpers for the whole Accord workload: sessions, outcome classification, randomness, and the bank model.

- Session setup: consistency QUORUM / SERIAL, with FallthroughRetryPolicy (explicit outcomes) or
  the driver's default RetryPolicy (hidden retries), and a client timeout above
  native_transport_timeout (30 s). Connecting retries until the cluster answers or a budget ends.
- Outcome classification: a definite failure, versus an unknown outcome (the request may or may
  not have applied).
- Randomness: every random choice goes through the Antithesis SDK, so Antithesis can steer it.
- The bank model for Guarantee 1: twelve accounts in two tables (disjoint ids, since Cassandra
  rejects a transaction that updates the same key and column names in two tables), the transfer
  and audit transactions, and the shared audit check (check_audit), whose Always assertions every
  bank command uses.
- The token groups for Guarantee 2: which rows of the two pair tables form each group.

Files prefixed helper_ are ignored by Antithesis as commands, but are still cataloged for
assertions.

Checks (Guarantee 1, check_audit, called by every bank command):
- Always: every seeded bank account is visible to an audit transaction.
- Always: audited bank balances sum to the initial total.
- Always: no bank account balance is negative in an audit.
- Always: audited transfer counters sum to an even number.
- Always: an audit reflects every transfer acknowledged or observed before it started.
- Sometimes: an audit saw a bank account drained to exactly zero.
"""
import os
import socket
import sys
import time

from cassandra import (ConsistencyLevel, InvalidRequest, OperationTimedOut, ReadFailure,
                       ReadTimeout, Unauthorized, Unavailable, WriteFailure, WriteTimeout)
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile, NoHostAvailable
from cassandra.policies import (ConstantReconnectionPolicy, FallthroughRetryPolicy, RetryPolicy,
                               RoundRobinPolicy)
from cassandra.protocol import ConfigurationException, SyntaxException

from antithesis import random as arandom
from antithesis.assertions import always, sometimes

KEYSPACE = "accord_ks"
NODES = os.environ.get(
    "CASSANDRA_NODES", "cassandra-accord-node1,cassandra-accord-node2,cassandra-accord-node3"
).split(",")

# Client timeout must exceed native_transport_timeout (30 s) and the txn deadlines (10 s).
REQUEST_TIMEOUT = 45

# ---------------------------------------------------------------------------------------------
# logging / randomness


def log(tag, msg):
    print(f"{tag}: {msg}", flush=True)


def log_event(tag, event, details):
    """One structured JSON line on stdout for a noteworthy but non-failing condition (e.g. a
    read budget ran out under faults). Not an assertion: it must not be required to happen."""
    import json
    print(json.dumps({"tag": tag, "event": event, "details": details}, default=str), flush=True)


def rand_int(n):
    """Uniform-ish integer in [0, n) from Antithesis randomness."""
    return arandom.get_random() % n


def choice(items):
    return arandom.random_choice(list(items))


def coin(p_num=1, p_den=2):
    return rand_int(p_den) < p_num


def unique_id63():
    """A random positive 63-bit id (fits a CQL bigint)."""
    return (arandom.get_random() & ((1 << 63) - 1)) or 1


# ---------------------------------------------------------------------------------------------
# sessions

PROFILE_AUTO_RETRY = "auto_retry"


def connect(tag, budget_s=120.0, client_timestamps=True, request_timeout=REQUEST_TIMEOUT,
            reconnect_delay_s=None):
    """Connect with both profiles; returns (cluster, session) or (None, None) if the cluster
    could not be reached within budget_s (expected under faults; the caller exits 0).

    client_timestamps=False sets session.use_client_timestamp = False, so the driver sends no
    protocol-level default timestamp and the server (Accord, on transactional_mode='full' tables)
    picks every write timestamp. Linearizability checks on plain CQL (Guarantee 4) need this: the docs say a
    write with a client timestamp is applied in order but the merged result may not look
    linearizable to readers.

    EXEC_PROFILE_DEFAULT: FallthroughRetryPolicy, so each execute() is exactly one attempt and
    the caller sees every outcome. PROFILE_AUTO_RETRY: the driver's default RetryPolicy, which can
    retry silently (as real applications do); only use it where the check tolerates
    "applied once or more".

    request_timeout overrides the per-request client timeout; reconnect_delay_s (optional) makes the
    driver retry a down node every reconnect_delay_s seconds instead of its default exponential
    backoff (up to 10 min), so a probe notices a restarted node promptly."""
    def profile(retry_policy):
        return ExecutionProfile(
            load_balancing_policy=RoundRobinPolicy(),
            retry_policy=retry_policy,
            consistency_level=ConsistencyLevel.QUORUM,  # Accord rejects LOCAL_ONE (driver default)
            serial_consistency_level=ConsistencyLevel.SERIAL,
            request_timeout=request_timeout,
        )

    deadline = time.monotonic() + budget_s
    attempt = 0
    while True:
        attempt += 1
        cluster = None
        try:
            # Cluster() itself resolves the contact points and raises UnresolvableContactPoints
            # when none resolve (e.g. every node is down or restarting), so it is inside the try.
            cluster = Cluster(
                NODES,
                execution_profiles={
                    EXEC_PROFILE_DEFAULT: profile(FallthroughRetryPolicy()),
                    PROFILE_AUTO_RETRY: profile(RetryPolicy()),
                },
                connect_timeout=10,
                control_connection_timeout=10,
                **({"reconnection_policy": ConstantReconnectionPolicy(reconnect_delay_s, None)}
                   if reconnect_delay_s else {}),
            )
            session = cluster.connect()
            if not client_timestamps:
                session.use_client_timestamp = False
            session.default_fetch_size = 1000  # audits must fit in one page (no paging)
            return cluster, session
        except Exception as e:  # noqa: BLE001 - cluster may be partially down under faults
            log(tag, f"connect attempt {attempt} failed: {type(e).__name__}: {e}")
            if cluster is not None:
                try:
                    cluster.shutdown()
                except Exception:  # noqa: BLE001
                    pass
            if time.monotonic() > deadline:
                log(tag, f"cluster unreachable after {attempt} connect attempts; giving up")
                return None, None
            time.sleep(3)


def shutdown(cluster):
    if cluster is not None:
        try:
            cluster.shutdown()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------------------------
# outcome classification

DEFINITE_BUG = (SyntaxException, InvalidRequest, Unauthorized, ConfigurationException)
AMBIGUOUS = (WriteTimeout, ReadTimeout, WriteFailure, ReadFailure, OperationTimedOut,
             NoHostAvailable, Unavailable)


def classify(exc):
    """'workload_bug' for errors that mean the statement itself is wrong (re-raise),
    otherwise 'ambiguous': for a write, it may or may not have applied (timeouts, failures,
    connection resets, unavailable, overloaded, bootstrapping ...). Treating every other error
    as ambiguous is always sound: the checks never assume an unacknowledged write did not apply."""
    if isinstance(exc, DEFINITE_BUG):
        return "workload_bug"
    return "ambiguous"


def coordinator_of(result_set):
    try:
        host = result_set.response_future.coordinator_host
        return str(host) if host is not None else None
    except Exception:  # noqa: BLE001
        return None


def node_name_of(coordinator):
    """Map a coordinator address ("ip" or "ip:port") to its node hostname, for assertion details.
    Resolves the node names now (addresses are static in the harness); None if unknown."""
    if not coordinator:
        return None
    ip = str(coordinator).rsplit(":", 1)[0] if str(coordinator).count(":") == 1 else str(coordinator)
    for name in NODES:
        try:
            if socket.gethostbyname(name) == ip:
                return name
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------------------------
# bank model (txn-strict-serializable, Guarantee 1)
#
# Twelve accounts on twelve partitions across two tables. Every transfer conserves money and
# increments the transfer counter `xfers` of both accounts it touches, so for any consistent
# snapshot: sum(balance) == TOTAL, every balance >= 0, sum(xfers) is even.

# Ids are disjoint across the two tables: Cassandra rejects a transaction that updates the same
# primary key and column names in two different tables ("Transaction contains multiple updates to
# the same key and fields", TransactionStatement.validateOnlyModifyPrimaryKeyColumnPairOnce keys on
# partition key + clustering only), which would reject cross-table transfers between equal ids.
BANK_TABLES = ("accounts", "accounts_b")
BANK_IDS = tuple(range(6))
BANK_B_OFFSET = 100
BANK_ACCOUNTS = tuple([("accounts", i) for i in BANK_IDS] + [("accounts_b", BANK_B_OFFSET + i) for i in BANK_IDS])
BANK_INITIAL = 1000
BANK_TOTAL = BANK_INITIAL * len(BANK_ACCOUNTS)

# Amount menu: boundaries around zero, an account's initial balance, the whole bank.
AMOUNT_MENU = (0, 1, 2, 7, 100, BANK_INITIAL - 1, BANK_INITIAL, BANK_INITIAL + 1,
               BANK_TOTAL - 1, BANK_TOTAL, BANK_TOTAL + 1)


def acct_name(acct):
    return f"{acct[0]}:{acct[1]}"


def pick_pair(hot):
    """Two distinct accounts. hot=True restricts to a 3-account hot set (high contention)."""
    pool = list(BANK_ACCOUNTS[:2]) + [BANK_ACCOUNTS[len(BANK_IDS)]] if hot else list(BANK_ACCOUNTS)
    src = choice(pool)
    dst = choice([a for a in pool if a != src])
    return src, dst


def pick_amount():
    if coin(1, 3):
        return choice(AMOUNT_MENU)
    return 1 + rand_int(150)


def transfer_cql(src, dst, amount, literal=False):
    """Conditional transfer. Returns the pre-transfer balance/xfers of both accounts.
    literal=False gives a statement with bind markers (src_id, dst_id, amount, amount, src_id,
    amount, dst_id)."""
    if literal:
        s, d, a = str(src[1]), str(dst[1]), str(amount)
    else:
        s = d = a = "?"
    return (
        "BEGIN TRANSACTION\n"
        f"  LET src = (SELECT balance, xfers FROM {KEYSPACE}.{src[0]} WHERE id = {s});\n"
        f"  LET dst = (SELECT balance, xfers FROM {KEYSPACE}.{dst[0]} WHERE id = {d});\n"
        "  SELECT src.balance, src.xfers, dst.balance, dst.xfers;\n"
        f"  IF src.balance >= {a} THEN\n"
        f"    UPDATE {KEYSPACE}.{src[0]} SET balance -= {a}, xfers += 1 WHERE id = {s};\n"
        f"    UPDATE {KEYSPACE}.{dst[0]} SET balance += {a}, xfers += 1 WHERE id = {d};\n"
        "  END IF\n"
        "COMMIT TRANSACTION"
    )


def transfer_bind(src, dst, amount):
    return (src[1], dst[1], amount, amount, src[1], amount, dst[1])


def audit_cql(order):
    """One read-only transaction over every account (12 partitions, 2 tables): a full Accord
    Read, never an EphemeralRead. `order` is a permutation of BANK_ACCOUNTS."""
    lets = []
    cols = []
    for n, (t, i) in enumerate(order):
        lets.append(f"  LET r{n} = (SELECT balance, xfers FROM {KEYSPACE}.{t} WHERE id = {i});\n")
        cols.append(f"r{n}.balance, r{n}.xfers")
    return "BEGIN TRANSACTION\n" + "".join(lets) + "  SELECT " + ", ".join(cols) + ";\nCOMMIT TRANSACTION"


def random_order():
    order = list(BANK_ACCOUNTS)
    for k in range(len(order) - 1, 0, -1):
        j = rand_int(k + 1)
        order[k], order[j] = order[j], order[k]
    return order


def parse_audit(order, row):
    """-> {acct: (balance, xfers)}; missing accounts map to (None, None)."""
    vals = list(row)
    return {acct: (vals[2 * n], vals[2 * n + 1]) for n, acct in enumerate(order)}


def run_audit(session, profile=EXEC_PROFILE_DEFAULT):
    """Execute one audit; returns (snapshot, coordinator). Raises on error."""
    order = random_order()
    rs = session.execute(audit_cql(order), execution_profile=profile)
    rows = list(rs)
    if len(rows) != 1:
        return {acct: (None, None) for acct in BANK_ACCOUNTS}, coordinator_of(rs)
    return parse_audit(order, rows[0]), coordinator_of(rs)


def check_audit(snap, floors, source, extra=None):
    """Correctness checks on one audit snapshot. `floors` maps account -> lowest xfers value this
    client may see, from transfers it saw acknowledged and audits it saw complete before this
    audit started (real-time order). Updates floors in place. Returns True if all checks held."""
    missing = [acct_name(a) for a, (b, x) in snap.items() if b is None or x is None]
    present = {a: v for a, v in snap.items() if v[0] is not None and v[1] is not None}
    total = sum(b for b, _ in present.values())
    min_bal = min((b for b, _ in present.values()), default=0)
    xfer_sum = sum(x for _, x in present.values())
    regress = {acct_name(a): {"seen": present[a][1], "floor": f}
               for a, f in floors.items() if a in present and present[a][1] < f}
    base = {"guarantee": "G1", "property": "txn-strict-serializable", "source": source,
            "balances": {acct_name(a): v[0] for a, v in present.items()},
            "xfers": {acct_name(a): v[1] for a, v in present.items()}}
    if extra:
        base.update(extra)
    if "coordinator" in base:
        base["coordinator_node"] = node_name_of(base["coordinator"])

    always(not missing, "every seeded bank account is visible to an audit transaction",
           dict(base, missing=missing))
    always(bool(missing) or total == BANK_TOTAL, "audited bank balances sum to the initial total",
           dict(base, total=total, expected=BANK_TOTAL))
    always(min_bal >= 0, "no bank account balance is negative in an audit",
           dict(base, min_balance=min_bal))
    always(bool(missing) or xfer_sum % 2 == 0, "audited transfer counters sum to an even number",
           dict(base, xfer_sum=xfer_sum))
    always(not regress, "an audit reflects every transfer acknowledged or observed before it started",
           dict(base, regressions=regress))

    sometimes(any(b == 0 for b, _ in present.values()),
              "an audit saw a bank account drained to exactly zero", base)

    for a, (_, x) in present.items():
        if x > floors.get(a, 0):
            floors[a] = x
    return not missing and total == BANK_TOTAL and min_bal >= 0 and not regress


# ---------------------------------------------------------------------------------------------
# token groups (txn-all-or-nothing, Guarantee 2)
#
# A group is a fixed set of 2-4 slots (partitions) spread over two tables, pair_a and pair_b
# (k int PRIMARY KEY, tok text). Every write to a group writes one fresh unique token to every
# slot of the group in one atomic unit, so in any consistent snapshot all slots of a group hold
# the same token, or none holds one yet. Partition keys are disjoint across the two tables
# (a txn may not update the same key + column names in two tables).
#
# Transactional groups are written with BEGIN TRANSACTION and may be read at any time.
# Logged-batch groups are written with BEGIN BATCH (on transactional_mode='full' tables the
# batch's mutations go into one Accord txn); Cassandra documents only eventual all-or-nothing
# application for logged batches (batchlog replay), so those groups are only checked by the
# eventually_ command.

PAIR_TABLES = ("pair_a", "pair_b")
PAIR_B_OFFSET = 5000
# slot layouts (slots in pair_a, slots in pair_b): 2, 3 or 4 partitions
PAIR_LAYOUTS = ((1, 1), (2, 1), (2, 2), (1, 3))
TXN_GROUPS = tuple(range(8))
BATCH_GROUPS = tuple(range(100, 104))
HOT_TXN_GROUPS = TXN_GROUPS[:2]

# token payload padding menu: none, one char, a typical short value, a 4 KiB value
PAD_MENU = (0, 1, 64, 4096)


def group_slots(g):
    """-> [(table, key)] for group g, fixed for the whole run."""
    na, nb = PAIR_LAYOUTS[g % len(PAIR_LAYOUTS)]
    return ([("pair_a", g * 10 + j) for j in range(na)]
            + [("pair_b", PAIR_B_OFFSET + g * 10 + j) for j in range(nb)])


def slot_name(slot):
    return f"{slot[0]}:{slot[1]}"


def new_token(writer, seq):
    pad = choice(PAD_MENU)
    return f"{writer}-{seq}" + ("x" * pad if pad else "")


def short_tok(tok):
    if tok is None:
        return None
    return tok if len(tok) <= 40 else tok[:40] + f"...(len={len(tok)})"


def shuffled(items):
    items = list(items)
    for k in range(len(items) - 1, 0, -1):
        j = rand_int(k + 1)
        items[k], items[j] = items[j], items[k]
    return items


def group_read_cql(slots):
    """One read-only transaction returning every slot's token (>=2 keys, so a full Accord read)."""
    lets = "".join(f"  LET r{n} = (SELECT tok FROM {KEYSPACE}.{t} WHERE k = {k});\n"
                   for n, (t, k) in enumerate(slots))
    cols = ", ".join(f"r{n}.tok" for n in range(len(slots)))
    return "BEGIN TRANSACTION\n" + lets + f"  SELECT {cols};\nCOMMIT TRANSACTION"


def _write_stmt(t, k, tok, style):
    if style == "insert":
        return f"INSERT INTO {KEYSPACE}.{t} (k, tok) VALUES ({k}, '{tok}');\n"
    return f"UPDATE {KEYSPACE}.{t} SET tok = '{tok}' WHERE k = {k};\n"


def group_write_cql(slots, tok, style):
    """Unconditional transaction writing tok to every slot. style: 'insert' | 'update'."""
    return ("BEGIN TRANSACTION\n"
            + "".join("  " + _write_stmt(t, k, tok, style) for t, k in slots)
            + "COMMIT TRANSACTION")


def group_cas_cql(slots, expected, tok, style):
    """Conditional transaction: reads every slot (returned), writes tok to every slot only if
    the first slot still holds `expected` (None = never written)."""
    lets = "".join(f"  LET r{n} = (SELECT tok FROM {KEYSPACE}.{t} WHERE k = {k});\n"
                   for n, (t, k) in enumerate(slots))
    cols = ", ".join(f"r{n}.tok" for n in range(len(slots)))
    cond = "r0 IS NULL" if expected is None else f"r0.tok = '{expected}'"
    return ("BEGIN TRANSACTION\n" + lets + f"  SELECT {cols};\n  IF {cond} THEN\n"
            + "".join("    " + _write_stmt(t, k, tok, style) for t, k in slots)
            + "  END IF\nCOMMIT TRANSACTION")


def group_batch_cql(slots, tok, style):
    return ("BEGIN BATCH\n"
            + "".join("  " + _write_stmt(t, k, tok, style) for t, k in slots)
            + "APPLY BATCH")


def group_view(slots, row):
    """-> (consistent, tokens dict, distinct tokens). Consistent iff every slot holds the same
    token or no slot holds one (never written)."""
    toks = list(row) if row is not None else [None] * len(slots)
    distinct = set(toks)
    consistent = len(distinct) == 1
    view = {slot_name(s): short_tok(v) for s, v in zip(slots, toks)}
    return consistent, view, distinct


def read_group(session, slots, profile=EXEC_PROFILE_DEFAULT):
    """Read every slot of a group in one transaction; returns (row, coordinator). Raises."""
    rs = session.execute(group_read_cql(slots), execution_profile=profile)
    rows = list(rs)
    return (rows[0] if rows else None), coordinator_of(rs)
