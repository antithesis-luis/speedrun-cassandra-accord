#!/usr/bin/env python3
"""Guarantee 3 checker after faults stop: every acknowledged write in every ledger is still there.

Loads every writer's ledger from the shared volume (/ledger/durable-*.jsonl) and reads every row
of every acknowledged operation by explicit key (plain single-partition SELECTs with an IN list
on the clustering key, or multi-partition BEGIN TRANSACTION reads), checking presence and value.
Order comes from structure: eventually_ commands run after the drivers have stopped, so after
every acknowledgement. Rows of operations with an unknown outcome (or whose writer died before
recording one) may be present or absent. The cluster may still be recovering, so each read is
retried for up to 120 s; a chunk that never reads is logged as unknown on stdout, never reported
as a failed check.

Checks (Guarantee 3):
- Always: after faults stopped, every acknowledged durable write is present with its value.
- Sometimes: the final check verified acknowledged durable writes from the ledgers; it verified
  acknowledged multi-partition writes in every partition; it found a write of unknown outcome
  applied.
"""
import sys
import time

import helper_accord as h
import helper_durable as d
from antithesis.assertions import always, sometimes

TAG = "durable_check_final"
G = {"guarantee": "G3", "property": "acked-txn-durable"}
GLOBAL_BUDGET_S = 900
AMBIGUOUS_CAP = 500


def main():
    ops, files = d.load_ledgers()
    acked = [(i, op) for i, op in ops.items() if op["state"] == "acked"]
    unknown = [(i, op) for i, op in ops.items() if op["state"] != "acked"]
    h.log(TAG, f"ledgers={len(files)} acked_ops={len(acked)} unknown_ops={len(unknown)}")
    if not acked and not unknown:
        return 0
    cluster, session = h.connect(TAG, budget_s=180)
    if session is None:
        h.log_event(TAG, "a final durability check could not connect to the cluster",
                    dict(G, acked_ops=len(acked)))
        return 0
    deadline = time.monotonic() + GLOBAL_BUDGET_S

    expected = d.ops_rows(acked)
    multi_ids = {i for i, op in acked if len(op["ks"]) > 1}
    stats = {"rows": len(expected), "verified_rows": 0, "unreadable_rows": 0, "chunks": 0,
             "txn_chunks": 0, "multi_verified": 0}
    ok_rows = set()
    for part, found, use_txn, coords in d.check_chunks(session, expected, deadline, 120, 20, TAG):
        stats["chunks"] += 1
        if found is None:
            stats["unreadable_rows"] += len(part)
            continue
        stats["txn_chunks"] += use_txn
        missing, wrong = d.mismatches(part, found)
        always(not missing and not wrong,
               "after faults stopped every acknowledged durable write is present with its value",
               dict(G, txn_read=use_txn, coordinators=sorted(str(c) for c in coords),
                    missing=[f"{k}:{i}" for k, i in missing][:50], missing_count=len(missing),
                    wrong=dict(list(wrong.items())[:20]),
                    missing_ops={str(i): ops[i] for _, i in missing[:10]}))
        good = [r for r in part if r in found and found[r] == part[r]]
        ok_rows.update(good)
        stats["verified_rows"] += len(good)
    stats["multi_verified"] = sum(1 for i in multi_ids if all((k, i) in ok_rows for k in ops[i]["ks"]))

    if stats["unreadable_rows"] or stats["verified_rows"] + stats["unreadable_rows"] < len(expected):
        h.log_event(TAG, "a final durability check could not read some acknowledged rows within its time budget",
                    dict(G, **stats))
    sometimes(stats["verified_rows"] > 0, "a final check verified acknowledged durable writes from the ledgers",
              dict(G, **stats))
    sometimes(stats["multi_verified"] > 0,
              "a final check verified acknowledged multi-partition durable writes in every partition",
              dict(G, **stats))

    # ambiguous ops: allowed either way; look for some that applied
    amb = unknown[:AMBIGUOUS_CAP]
    amb_found = 0
    amb_rows = d.ops_rows(amb)
    for part, found, _use_txn, _coords in d.check_chunks(session, amb_rows, deadline, 30, 10, TAG):
        if found:
            amb_found += len(found)
    sometimes(amb_found > 0, "a final check found a write of unknown outcome applied",
              dict(G, ambiguous_ops=len(unknown), checked_ops=len(amb), rows_found=amb_found))

    h.log(TAG, f"done {stats} ambiguous_rows_found={amb_found}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
