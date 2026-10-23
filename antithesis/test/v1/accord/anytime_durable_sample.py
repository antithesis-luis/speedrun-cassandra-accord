#!/usr/bin/env python3
"""Guarantee 3 checker during faults: sampled acknowledged writes are present while faults and writers run.

Reads the ledgers on the shared volume, samples up to 100 acknowledged operations, and reads
their rows by explicit key. An acknowledgement line is appended only after the client saw
success, and this command reads the line before it reads the row, so the read starts after the
acknowledgement (order from structure). Reads are retried for a short budget; a read that never
completes counts as unknown, not as a loss.

Checks (Guarantee 3):
- Always: an acknowledged durable write sampled during the run is present with its value.
- Sometimes: a check during the run verified sampled acknowledged durable writes.
"""
import sys
import time

import helper_accord as h
import helper_durable as d
from antithesis.assertions import always, sometimes

TAG = "durable_sample"
G = {"guarantee": "G3", "property": "acked-txn-durable"}


def main():
    ops, _files = d.load_ledgers()
    acked = [(i, op) for i, op in ops.items() if op["state"] == "acked"]
    if not acked:
        h.log(TAG, "no acknowledged ops in the ledgers yet")
        return 0
    n = min(len(acked), h.choice([10, 100]))
    picked = {}
    while len(picked) < n:
        i, op = acked[h.rand_int(len(acked))]
        picked[i] = op
    cluster, session = h.connect(TAG, budget_s=60)
    if session is None:
        return 0
    deadline = time.monotonic() + 120
    expected = d.ops_rows(picked.items())
    verified = unreadable = 0
    for part, found, use_txn, coords in d.check_chunks(session, expected, deadline, 30, 10, TAG, chunk=20):
        if found is None:
            unreadable += len(part)
            continue
        missing, wrong = d.mismatches(part, found)
        always(not missing and not wrong,
               "an acknowledged durable write sampled during the run is present with its value",
               dict(G, txn_read=use_txn, coordinators=sorted(str(c) for c in coords),
                    missing=[f"{k}:{i}" for k, i in missing], wrong=wrong,
                    missing_ops={str(i): ops[i] for _, i in missing[:10]}))
        verified += len(part) - len(missing) - len(wrong)
    if unreadable:
        h.log_event(TAG, "a durability sample during the run could not read some rows within its time budget",
                    dict(G, unreadable_rows=unreadable, rows=len(expected)))
    sometimes(verified > 0, "a check during the run verified sampled acknowledged durable writes",
              dict(G, verified_rows=verified, rows=len(expected), acked_ops=len(acked)))
    h.log(TAG, f"done rows={len(expected)} verified={verified} unreadable={unreadable}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
