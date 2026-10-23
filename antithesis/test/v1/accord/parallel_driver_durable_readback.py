#!/usr/bin/env python3
"""Guarantee 3 driver: write, then read the acknowledged write back with a new statement, preferably through another coordinator.

Works in its own partitions (a random block of 100 keys above READBACK_BASE that no other
command writes). Each of 3, 10 or 25 operations writes a fresh id (any of the write styles,
explicit or auto-retry) and records it in the ledger. Once the write is acknowledged, a new read
(a multi-partition BEGIN TRANSACTION read, or plain single-partition SELECTs with an IN list),
sent preferably to a different coordinator than the one that acknowledged the write, must return
every row with its value. Order comes from execution order in this script. A read that can't
complete within its budget counts as unknown, not as a loss: availability is judged by
Guarantee 5.

Checks (Guarantee 3):
- Always: an acknowledged durable write is visible with its value to the next read.
- Sometimes: an acknowledged durable write was read back through a different coordinator.
"""
import sys
import time

import helper_accord as h
import helper_durable as d
from antithesis.assertions import always, sometimes

TAG = "durable_readback"
G = {"guarantee": "G3", "property": "acked-txn-durable"}


def other_host(cluster, acking):
    hosts = [x for x in cluster.metadata.all_hosts() if x.is_up and x != acking]
    return h.choice(hosts) if hosts else None


def read_back(session, cluster, rows, use_txn, acking, budget_s):
    """Read rows via another coordinator first, then any coordinator, retrying until budget_s.
    -> (found, coords) or (None, last_error)."""
    deadline = time.monotonic() + budget_s
    last = None
    while True:
        host = other_host(cluster, acking) if last is None else None
        try:
            return d.read_rows(session, rows, use_txn, host=host)
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            last = f"{type(e).__name__}: {str(e)[:200]}"
            if time.monotonic() + 2 > deadline:
                return None, last
            time.sleep(2)


def main():
    cluster, session = h.connect(TAG)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0
    writer = format(h.unique_id63(), "x")
    ledger = d.Ledger(writer)
    base = d.READBACK_BASE + h.rand_int(10000) * 100
    keys = tuple(range(base, base + 100))
    ops = h.choice([3, 10, 25])
    auto = h.coin(1, 3)
    use_txn_pref = h.choice([None, True, False])  # None: vary per op
    wall_deadline = time.monotonic() + 180
    stats = {"acked": 0, "ambiguous": 0, "verified": 0, "unknown_reads": 0}
    h.log(TAG, f"writer={writer} base={base} ops={ops} auto_retry={auto} txn_read={use_txn_pref}")

    for _ in range(ops):
        if time.monotonic() > wall_deadline:
            break
        style = h.choice(d.STYLES)
        n = 1 if style == "plain" else h.choice(d.SPREAD_MENU)
        ks = h.shuffled(keys)[:n]
        use_auto = auto and style != "txn_cas"
        op_id, pad, outcome, res, acking = d.do_write(session, ledger, ks, style, use_auto)
        if outcome == "ambiguous":
            stats["ambiguous"] += 1
            time.sleep(1)
            continue
        stats["acked"] += 1
        expected = d.expected_rows(op_id, {"ks": ks, "pad": pad})
        use_txn = h.coin(1, 2) if use_txn_pref is None else use_txn_pref
        found, coords = read_back(session, cluster, list(expected), use_txn, acking, 60)
        if found is None:
            stats["unknown_reads"] += 1
            h.log_event(TAG, "a read-back of an acknowledged durable write did not complete in its time budget",
                        dict(G, id=op_id, ks=ks, error=coords))
            continue
        missing, wrong = d.mismatches(expected, found)
        coords = sorted(str(c) for c in coords)
        always(not missing and not wrong,
               "an acknowledged durable write is visible with its value to the next read",
               dict(G, id=op_id, ks=ks, style=style, auto_retry=use_auto, txn_read=use_txn,
                    write_coordinator=str(acking), read_coordinators=coords,
                    missing=[f"{k}:{i}" for k, i in missing], wrong=wrong))
        stats["verified"] += 1
        sometimes(acking is not None and str(acking) not in coords,
                  "an acknowledged durable write was read back through a different coordinator",
                  dict(G, id=op_id, write_coordinator=str(acking), read_coordinators=coords))

    ledger.close()
    h.log(TAG, f"done {stats}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
