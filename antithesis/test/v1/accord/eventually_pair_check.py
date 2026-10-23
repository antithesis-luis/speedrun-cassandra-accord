#!/usr/bin/env python3
"""Guarantee 2 checker after faults stop: every token group holds one token in every row, or none.

Runs after the drivers stopped, possibly mid-write: Accord must recover or invalidate each
in-flight transaction as a whole, and logged batches may still be replayed from the batchlog.
Each group, transactional or logged-batch, is read in one BEGIN TRANSACTION. Groups whose read
doesn't complete in the time budget are skipped: whether the cluster recovers is judged by
Guarantee 5 (eventually_recovery_probe), not here.

Checks (Guarantee 2):
- Always: after faults stopped, every transactional group holds the same token in every slot.
- Always: after faults stopped, every logged-batch group holds the same token in every slot.
- Sometimes: the final check saw transactional groups written; it saw logged-batch groups written.
"""
import sys
import time

import helper_accord as h
from antithesis.assertions import always, sometimes

TAG = "pair_check_final"
G = {"guarantee": "G2", "property": "txn-all-or-nothing"}


def main():
    cluster, session = h.connect(TAG, budget_s=180)
    if session is None:
        return 0
    deadline = time.monotonic() + 180
    todo = list(h.TXN_GROUPS) + list(h.BATCH_GROUPS)
    written = {"txn": 0, "batch": 0}
    checked = 0
    while todo and time.monotonic() < deadline:
        g = todo[0]
        slots = h.shuffled(h.group_slots(g))
        try:
            row, coord = h.read_group(session, slots)
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            h.log(TAG, f"group {g} read failed: {type(e).__name__}: {str(e)[:200]}")
            todo.append(todo.pop(0))  # try the other groups first
            time.sleep(3)
            continue
        todo.pop(0)
        checked += 1
        ok, view, distinct = h.group_view(slots, row)
        tok = next(iter(distinct)) if ok else None
        if g in h.BATCH_GROUPS:
            always(ok, "after faults stopped every logged-batch group holds the same token in every slot",
                   dict(G, group=g, slots=view, coordinator=coord))
            written["batch"] += tok is not None
        else:
            always(ok, "after faults stopped every transactional group holds the same token in every slot",
                   dict(G, group=g, slots=view, coordinator=coord))
            written["txn"] += tok is not None
    sometimes(written["txn"] > 0, "a final check after faults stopped saw transactional groups written",
              dict(G, written=written, checked=checked))
    sometimes(written["batch"] > 0, "a final check after faults stopped saw logged-batch groups written",
              dict(G, written=written, checked=checked))
    h.log(TAG, f"done checked={checked} written={written} unchecked={todo}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
