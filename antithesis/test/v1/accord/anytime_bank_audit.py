#!/usr/bin/env python3
"""Guarantee 1 checker during faults: a short series of read-only bank audits that run alongside the transfer drivers.

Each audit is one read-only transaction over all twelve accounts in the two bank tables. The
command runs 3, 10 or 20 of them back to back within 120 s, spaced a little apart, with or
without the driver's retry policy. Because each audit starts after the previous one completed,
no account's transfer counter may go backwards between them (real-time order).

Checks (Guarantee 1):
- Always (every audit, through helper_accord.check_audit): every seeded account is visible, the
  balances sum to the initial total, none is negative, the transfer counters sum to an even
  number, and no counter is below what an earlier audit by this client saw.
- Sometimes: consecutive audits by one client observed newly committed transfers.
"""
import sys
import time

import helper_accord as h
from antithesis.assertions import sometimes

TAG = "bank_audit"
G = {"guarantee": "G1", "property": "txn-strict-serializable"}


def main():
    cluster, session = h.connect(TAG)
    if session is None:
        return 0
    audits = h.choice([3, 10, 20])
    profile = h.PROFILE_AUTO_RETRY if h.coin(1, 2) else None
    deadline = time.monotonic() + 120
    floors = {}
    done = 0
    prev = None
    while done < audits and time.monotonic() < deadline:
        try:
            snap, coord = h.run_audit(session, profile=profile) if profile else h.run_audit(session)
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            time.sleep(2)
            continue
        done += 1
        h.check_audit(snap, floors, TAG, {"coordinator": coord, "audit_index": done})
        if prev is not None:
            changed = sum(1 for a in snap if snap[a][1] is not None and prev[a][1] is not None
                          and snap[a][1] > prev[a][1])
            sometimes(changed >= 2,
                      "consecutive audits by one client observed newly committed transfers",
                      dict(G, accounts_changed=changed, coordinator=coord))
        prev = snap
        time.sleep(0.5 + h.rand_int(3))
    h.log(TAG, f"done audits={done}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
