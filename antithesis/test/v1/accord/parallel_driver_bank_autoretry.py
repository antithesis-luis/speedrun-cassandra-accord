#!/usr/bin/env python3
"""Guarantee 1 driver: bank transfers sent the way a typical application sends them, with silent driver retries and application resubmits.

Unlike parallel_driver_bank_transfers, statements are plain (unprepared) CQL strings, run with
the driver's default RetryPolicy (which may retry silently), and the application itself resubmits
a transfer whose outcome was unknown (up to 3 attempts). A resubmitted transfer may therefore
apply more than once. That is legal: each application is a separate money-conserving transfer,
so every check stays sound for "applied once or more". Audits run every 1, 3 or 10 transfers,
and at the end.

Checks (Guarantee 1):
- Always: an application-retried transfer reads both accounts with balances within the bank total.
- Always: an application-retried transfer reads every transfer this client saw complete before it
  (its counters are no lower than this client's floors: real-time order).
- Always (every audit, through helper_accord.check_audit): every seeded account is visible, the
  balances sum to the initial total, none is negative, the transfer counters sum to an even
  number, and no counter is below what this client saw acknowledged or observed.
- Sometimes: a transfer was acknowledged after resubmitting an attempt whose outcome was unknown.
"""
import sys
import time

import helper_accord as h
from antithesis.assertions import always, sometimes

TAG = "bank_autoretry"
G = {"guarantee": "G1", "property": "txn-strict-serializable"}
MAX_ATTEMPTS = 3


def audit(session, floors, resubmitted_since):
    try:
        snap, coord = h.run_audit(session, profile=h.PROFILE_AUTO_RETRY)
    except Exception as e:  # noqa: BLE001
        if h.classify(e) == "workload_bug":
            raise
        return False
    h.check_audit(snap, floors, TAG, {"coordinator": coord, "resubmitted_since_last_audit": resubmitted_since})
    return True


def main():
    cluster, session = h.connect(TAG)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0

    transfers = h.choice([5, 15, 30])
    audit_every = h.choice([1, 3, 10])
    hot = h.coin(1, 2)
    wall_deadline = time.monotonic() + 180
    h.log(TAG, f"transfers={transfers} audit_every={audit_every} hot={hot}")

    floors = {}
    stats = {"acked": 0, "gave_up": 0, "resubmitted": 0, "audits": 0}
    resubmitted_since_audit = 0

    for n in range(transfers):
        if time.monotonic() > wall_deadline:
            break
        src, dst = h.pick_pair(hot)
        amount = h.pick_amount()
        stmt = h.transfer_cql(src, dst, amount, literal=True)
        floor_src, floor_dst = floors.get(src, 0), floors.get(dst, 0)
        row = None
        attempts = 0
        last_err = None
        while attempts < MAX_ATTEMPTS and time.monotonic() < wall_deadline:
            attempts += 1
            try:
                rows = list(session.execute(stmt, execution_profile=h.PROFILE_AUTO_RETRY))
                row = rows[0] if rows else (None, None, None, None)
                break
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                last_err = e
                time.sleep(1 + h.rand_int(3))
        if attempts > 1:
            stats["resubmitted"] += 1
            resubmitted_since_audit += 1
        if row is None:
            stats["gave_up"] += 1
            h.log(TAG, f"gave up on transfer after {attempts} attempts: {type(last_err).__name__}")
            continue

        sb, sx, db, dx = row
        details = dict(G, src=h.acct_name(src), dst=h.acct_name(dst), amount=amount, attempts=attempts,
                       src_balance=sb, src_xfers=sx, dst_balance=db, dst_xfers=dx,
                       floor_src=floor_src, floor_dst=floor_dst)
        complete = None not in (sb, sx, db, dx)
        always(complete and 0 <= sb <= h.BANK_TOTAL and 0 <= db <= h.BANK_TOTAL,
               "an application-retried transfer reads both accounts with balances within the bank total",
               details)
        if not complete:
            continue
        always(sx >= floor_src and dx >= floor_dst,
               "an application-retried transfer reads every transfer this client saw complete before it",
               details)
        sometimes(attempts > 1,
                  "a transfer was acknowledged after resubmitting an attempt whose outcome was unknown",
                  details)
        stats["acked"] += 1
        applied = sb >= amount
        floors[src] = max(floors.get(src, 0), sx + (1 if applied else 0))
        floors[dst] = max(floors.get(dst, 0), dx + (1 if applied else 0))

        if (n + 1) % audit_every == 0:
            if audit(session, floors, resubmitted_since_audit):
                stats["audits"] += 1
                resubmitted_since_audit = 0

    if audit(session, floors, resubmitted_since_audit):
        stats["audits"] += 1
    h.log(TAG, f"done {stats}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
