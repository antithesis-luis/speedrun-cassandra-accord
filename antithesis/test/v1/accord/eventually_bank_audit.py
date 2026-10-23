#!/usr/bin/env python3
"""Guarantee 1 checker after faults stop: audit the bank once the drivers have stopped.

Runs after the drivers were stopped, possibly mid-transfer, which leaves transactions for Accord
to recover. Retries for up to 180 s until up to two audits complete, then applies the snapshot
checks. Whether the cluster recovers in time is judged by Guarantee 5
(eventually_recovery_probe), not here: if no audit completes, this command just exits.

Checks (Guarantee 1):
- Always (every audit, through helper_accord.check_audit): every seeded account is visible, the
  balances sum to the initial total, none is negative, the transfer counters sum to an even
  number, and the second audit's counters are no lower than the first's.
- Sometimes: a final audit after faults stopped saw committed transfers.
"""
import sys
import time

import helper_accord as h
from antithesis.assertions import sometimes

TAG = "bank_audit_final"
G = {"guarantee": "G1", "property": "txn-strict-serializable"}


def main():
    cluster, session = h.connect(TAG, budget_s=180)
    if session is None:
        return 0
    deadline = time.monotonic() + 180
    floors = {}
    completed = 0
    while time.monotonic() < deadline and completed < 2:
        try:
            snap, coord = h.run_audit(session)
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            h.log(TAG, f"audit failed: {type(e).__name__}: {str(e)[:200]}")
            time.sleep(3)
            continue
        completed += 1
        h.check_audit(snap, floors, TAG, {"coordinator": coord, "final_audit": completed})
        total_xfers = sum(x for _, x in snap.values() if x is not None)
        sometimes(total_xfers > 0, "a final audit after faults stopped saw committed transfers",
                  dict(G, total_xfers=total_xfers))
        time.sleep(1)
    h.log(TAG, f"done completed={completed}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
