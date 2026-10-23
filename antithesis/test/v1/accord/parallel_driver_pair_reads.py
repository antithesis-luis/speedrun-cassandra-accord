#!/usr/bin/env python3
"""Guarantee 2 driver: concurrent readers that read a whole token group in one transaction.

Each read is one BEGIN TRANSACTION with a LET per slot of a group (2-4 partitions over two
tables), so it observes one consistent snapshot. Each invocation does 5, 20 or 60 reads, on hot
or spread groups, with the driver's auto-retry profile (reads are idempotent) or single attempts.
Logged-batch groups aren't read here: their atomicity is only promised eventually, and
eventually_pair_check judges them.

Checks (Guarantee 2):
- Always: a cross-table read transaction saw the same token in every slot of a group, or no
  token in any slot yet.
- Sometimes: a cross-table read saw a group rewritten since this reader's previous read.
"""
import sys
import time

import helper_accord as h
from antithesis.assertions import always, sometimes

TAG = "pair_reads"
G = {"guarantee": "G2", "property": "txn-all-or-nothing"}


def main():
    cluster, session = h.connect(TAG)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0
    reads = h.choice([5, 20, 60])
    hot = h.coin(1, 3)
    auto = h.coin(1, 3)
    profile = h.PROFILE_AUTO_RETRY if auto else h.EXEC_PROFILE_DEFAULT
    wall_deadline = time.monotonic() + 180
    h.log(TAG, f"reads={reads} hot={hot} auto_retry={auto}")
    stats = {"ok": 0, "errors": 0, "written": 0}
    prev = {}  # group -> token seen by the previous read of that group in this invocation

    for _ in range(reads):
        if time.monotonic() > wall_deadline:
            break
        g = h.choice(h.HOT_TXN_GROUPS if hot else h.TXN_GROUPS)
        slots = h.shuffled(h.group_slots(g))
        try:
            row, coord = h.read_group(session, slots, profile)
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            stats["errors"] += 1
            time.sleep(1)
            continue
        stats["ok"] += 1
        ok, view, distinct = h.group_view(slots, row)
        always(ok, "a cross-table read transaction saw the same token in every slot of a group",
               dict(G, group=g, slots=view, coordinator=coord, auto_retry=auto))
        tok = next(iter(distinct)) if ok else None
        if tok is not None:
            stats["written"] += 1
        sometimes(ok and tok is not None and g in prev and prev[g] != tok,
                  "a cross-table read saw a group rewritten since this reader's previous read",
                  dict(G, group=g, slots=view))
        prev[g] = tok
        if h.coin(1, 4):
            time.sleep(0.5)

    h.log(TAG, f"done {stats}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
