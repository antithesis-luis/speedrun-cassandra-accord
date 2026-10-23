#!/usr/bin/env python3
"""Guarantee 3 driver: write uniquely identified rows and record each outcome in a ledger on the shared volume.

Each operation inserts one fresh id into 1-3 partitions of accord_ks.durable, in one of three API
styles (BEGIN TRANSACTION, conditional BEGIN TRANSACTION, or a plain INSERT on the full-mode
table), with explicit single attempts or the driver's auto-retry profile. Inserting the same row
again is idempotent, so "applied once or more" is fine. The ledger
(/ledger/durable-<writer>.jsonl, helper_durable) records each attempt, acknowledgement and unknown
outcome; anytime_durable_sample and eventually_durable_check require every acknowledged row to be
present. Shape per invocation: 5, 20 or 50 operations, hot or spread partitions, retry style.

Checks (Guarantee 3):
- Always (or unreachable): a conditional insert of a fresh id found no existing row for it.
- Sometimes: a durable write transaction spanning three partitions was acknowledged.
- Reachable: a durable write ended with an unknown outcome.
"""
import sys
import time

import helper_accord as h
import helper_durable as d
from antithesis.assertions import always_or_unreachable, reachable, sometimes

TAG = "durable_writes"
G = {"guarantee": "G3", "property": "acked-txn-durable"}


def main():
    cluster, session = h.connect(TAG)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0
    writer = format(h.unique_id63(), "x")
    ledger = d.Ledger(writer)
    ops = h.choice([5, 20, 50])
    hot = h.coin(1, 3)
    auto = h.coin(1, 3)
    wall_deadline = time.monotonic() + 180
    stats = {"acked": 0, "ambiguous": 0, "multi": 0}
    h.log(TAG, f"writer={writer} ops={ops} hot={hot} auto_retry={auto}")

    for _ in range(ops):
        if time.monotonic() > wall_deadline:
            break
        style = h.choice(d.STYLES)
        pool = d.HOT_KEYS if hot else d.WRITER_KEYS
        n = 1 if style == "plain" else min(h.choice(d.SPREAD_MENU), len(pool))
        ks = h.shuffled(pool)[:n]
        use_auto = auto and style != "txn_cas"
        op_id, pad, outcome, res, _host = d.do_write(session, ledger, ks, style, use_auto)
        if outcome == "ambiguous":
            stats["ambiguous"] += 1
            reachable("a durable write ended with an unknown outcome",
                      dict(G, id=op_id, ks=ks, style=style, auto_retry=use_auto, error=res))
            time.sleep(1)
            continue
        stats["acked"] += 1
        if style == "txn_cas":
            seen = res[0][0] if res else None
            always_or_unreachable(seen is None,
                                  "a conditional insert of a fresh id found no existing row for it",
                                  dict(G, id=op_id, k=ks[0], seen=seen))
        if len(ks) > 1:
            stats["multi"] += 1
        sometimes(len(ks) == 3, "a durable write transaction spanning three partitions was acknowledged",
                  dict(G, id=op_id, ks=ks, style=style, pad=pad, auto_retry=use_auto))

    ledger.close()
    h.log(TAG, f"done {stats} ledger={ledger.path}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
