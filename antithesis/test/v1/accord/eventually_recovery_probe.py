#!/usr/bin/env python3
"""Guarantee 5 checker after faults stop: transactions succeed again, through every node, within 120 s.

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

Checks (Guarantee 5):
- Always: a transaction succeeded within 120 seconds after faults stopped.
- Always: every node coordinated a transaction within 120 seconds after faults stopped.
- Always: a plain write and read on a transactional table succeeded within 120 seconds.
- Sometimes: a transaction succeeded after the first attempt had failed; the first attempt
  succeeded; a node coordinated a transaction after earlier attempts through it failed.
"""
import socket
import sys
import time

import helper_accord as h
from antithesis.assertions import always, sometimes

TAG = "recovery_probe"
G = {"guarantee": "G5", "property": "recovers-after-faults"}
WINDOW_S = 120.0
PROBE_TIMEOUT_S = 15
SLEEP_S = 3.0
PLAIN_KEY_BASE = -1_000_000  # plain-probe keys: fresh per attempt, below this (kv.k is int)


def txn_keys(i):
    """Two kv keys reserved for the transaction probe through node i (disjoint from setup's -1..-3)."""
    return -1000 - 10 * i, -1001 - 10 * i


def txn_cql(i, pid):
    a, b = txn_keys(i)
    return ("BEGIN TRANSACTION\n"
            f"  LET r = (SELECT ver FROM {h.KEYSPACE}.kv WHERE k = {a});\n"
            "  SELECT r.ver;\n"
            f"  UPDATE {h.KEYSPACE}.kv SET ver = {pid} WHERE k = {a};\n"
            f"  UPDATE {h.KEYSPACE}.kv SET ver = {pid} WHERE k = {b};\n"
            "COMMIT TRANSACTION")


def find_host(cluster, name):
    """The driver Host for a node name, or (None, reason). Re-resolved every round: a restarted
    container may only become resolvable once it is running again."""
    try:
        ip = socket.gethostbyname(name)
    except OSError as e:
        return None, f"unresolvable: {e}"
    for host in cluster.metadata.all_hosts():
        if str(host.address) == ip:
            return host, None
    return None, f"{ip} not in driver metadata"


def err(e):
    return f"{type(e).__name__}: {str(e)[:160]}"


def main():
    start = time.monotonic()
    deadline = start + WINDOW_S

    def elapsed():
        return round(time.monotonic() - start, 1)

    nodes = {n: {"attempts": 0, "first_success_s": None, "last_error": None, "coordinator": None}
             for n in h.NODES}
    plain = {"attempts": 0, "first_success_s": None, "last_error": None}
    first_txn_attempt_failed = None  # outcome of the very first transaction attempt of this command

    cluster, session = h.connect(TAG, budget_s=WINDOW_S, request_timeout=PROBE_TIMEOUT_S,
                                 reconnect_delay_s=2.0)
    connected_s = elapsed() if session is not None else None
    rounds = 0
    while session is not None and time.monotonic() < deadline:
        rounds += 1
        for i, name in enumerate(h.NODES):
            st = nodes[name]
            if st["first_success_s"] is not None or time.monotonic() >= deadline:
                continue
            st["attempts"] += 1
            pid = h.unique_id63()
            host, why = find_host(cluster, name)
            ok = False
            if host is None:
                st["last_error"] = why
            else:
                try:
                    rs = session.execute(txn_cql(i, pid), host=host)
                    list(rs)
                    ok = time.monotonic() <= deadline
                    st["coordinator"] = h.coordinator_of(rs)
                    if not ok:
                        st["last_error"] = "completed after the window"
                except Exception as e:  # noqa: BLE001 - every outcome but success is "not yet"
                    st["last_error"] = err(e)
            if first_txn_attempt_failed is None:
                first_txn_attempt_failed = not ok
            if ok:
                st["first_success_s"] = elapsed()
                sometimes(st["attempts"] > 1,
                          "a node coordinated a transaction after earlier attempts through it failed",
                          dict(G, node=name, attempts=st["attempts"], at_s=st["first_success_s"]))
            else:
                h.log(TAG, f"txn via {name} attempt {st['attempts']} pid={pid} failed at "
                           f"{elapsed()}s: {st['last_error']}")

        if plain["first_success_s"] is None and time.monotonic() < deadline:
            plain["attempts"] += 1
            pid = h.unique_id63()
            key = PLAIN_KEY_BASE - 1 - h.rand_int(2_000_000_000 + PLAIN_KEY_BASE)
            try:
                session.execute(f"INSERT INTO {h.KEYSPACE}.kv (k, ver) VALUES ({key}, {pid})")
                if time.monotonic() >= deadline:
                    raise TimeoutError("window ended before the read")
                rows = list(session.execute(f"SELECT ver FROM {h.KEYSPACE}.kv WHERE k = {key}"))
                if time.monotonic() > deadline:
                    raise TimeoutError("read completed after the window")
                if len(rows) != 1 or rows[0].ver != pid:
                    raise ValueError(f"read back {[r.ver for r in rows]} after writing {pid}")
                plain["first_success_s"] = elapsed()
            except Exception as e:  # noqa: BLE001
                plain["last_error"] = err(e)
                h.log(TAG, f"plain write+read attempt {plain['attempts']} key={key} pid={pid} "
                           f"failed at {elapsed()}s: {plain['last_error']}")

        done = (all(st["first_success_s"] is not None for st in nodes.values())
                and plain["first_success_s"] is not None)
        if done:
            break
        time.sleep(min(SLEEP_S, max(0.0, deadline - time.monotonic())))

    any_txn = [st["first_success_s"] for st in nodes.values() if st["first_success_s"] is not None]
    details = dict(G, window_s=WINDOW_S, connected_s=connected_s, rounds=rounds, nodes=nodes,
                   plain=plain, ended_s=elapsed())

    always(bool(any_txn), "a transaction succeeded within 120 seconds after faults stopped", details)
    always(len(any_txn) == len(h.NODES),
           "every node coordinated a transaction within 120 seconds after faults stopped", details)
    always(plain["first_success_s"] is not None,
           "a plain write and read on a transactional table succeeded within 120 seconds after faults stopped",
           details)
    sometimes(bool(any_txn) and first_txn_attempt_failed is True,
              "a transaction succeeded after the first attempt once faults stopped had failed", details)
    sometimes(first_txn_attempt_failed is False,
              "the first transaction attempt once faults stopped succeeded", details)

    h.log(TAG, f"done in {elapsed()}s rounds={rounds} connected_s={connected_s} "
               f"txn_first_success={ {n: st['first_success_s'] for n, st in nodes.items()} } "
               f"plain_first_success={plain['first_success_s']}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
