#!/usr/bin/env python3
"""Guarantee 1 driver: bank transfers between the twelve accounts, each sent once so its outcome is explicit, mixed with read-only audits.

Each invocation runs a bounded mix (8, 20, 40 or 80 operations) of conditional transfers
(BEGIN TRANSACTION with LET reads, an IF balance check, and two UPDATEs on two partitions,
possibly in two tables) and read-only audits over all twelve accounts. Statements are prepared
and run with FallthroughRetryPolicy, so every attempt's outcome is visible: acknowledged, or
unknown (it may or may not have applied). Some invocations concentrate on the hot accounts.

The checks are sound under unknown outcomes, because every transfer conserves money. Real-time
order is checked within this client: any read (an audit, or a transfer's LET reads) that starts
after a transfer was acknowledged, or after an earlier read completed, must see each account's
transfer counter at least at the value that transfer wrote or that read saw. Transfers with an
unknown outcome never raise these floors.

Checks (Guarantee 1):
- Always: a transfer transaction reads both of its accounts.
- Always: a transfer reads balances within the bank total.
- Always: a transfer reads every transfer acknowledged or observed before it started.
- Always (every audit, through helper_accord.check_audit): every seeded account is visible, the
  balances sum to the initial total, none is negative, the transfer counters sum to an even
  number, and no counter is below what this client saw acknowledged or observed.
- Sometimes: a transfer saw transfers committed by other clients since this client last looked;
  a transfer was declined because the source balance was too low; a transfer moved a source
  account's entire balance; an audit completed while an earlier transfer's outcome was unknown.
- Reachable: a transfer ended with an unknown outcome.
"""
import sys
import time

from cassandra import ConsistencyLevel

import helper_accord as h
from antithesis.assertions import always, reachable, sometimes

TAG = "bank_transfers"
G = {"guarantee": "G1", "property": "txn-strict-serializable"}


def main():
    cluster, session = h.connect(TAG)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0

    ops = h.choice([8, 20, 40, 80])
    audit_pct = h.choice([10, 25, 50])
    hot = h.coin(1, 3)
    wall_deadline = time.monotonic() + 180
    h.log(TAG, f"ops={ops} audit_pct={audit_pct} hot={hot}")

    prepared = {}
    floors = {}  # account -> lowest xfers this client may still see
    stats = {"acked": 0, "declined": 0, "ambiguous": 0, "audits": 0, "audit_errors": 0}
    pending_ambiguous = 0  # ambiguous transfers since the last completed audit

    for _ in range(ops):
        if time.monotonic() > wall_deadline:
            break
        if h.rand_int(100) < audit_pct:
            try:
                snap, coord = h.run_audit(session)
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                stats["audit_errors"] += 1
                time.sleep(1)
                continue
            stats["audits"] += 1
            h.check_audit(snap, floors, TAG, {"coordinator": coord})
            sometimes(pending_ambiguous > 0,
                      "an audit completed while an earlier transfer's outcome was still unknown",
                      dict(G, pending_ambiguous=pending_ambiguous))
            pending_ambiguous = 0
            continue

        src, dst = h.pick_pair(hot)
        amount = h.pick_amount()
        key = (src[0], dst[0])
        try:
            if key not in prepared:
                ps = session.prepare(h.transfer_cql(src, dst, 0))
                ps.consistency_level = ConsistencyLevel.QUORUM
                ps.serial_consistency_level = ConsistencyLevel.SERIAL
                ps.is_idempotent = False
                prepared[key] = ps
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            time.sleep(1)
            continue

        floor_src, floor_dst = floors.get(src, 0), floors.get(dst, 0)
        try:
            rs = session.execute(prepared[key], h.transfer_bind(src, dst, amount))
            rows = list(rs)
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            stats["ambiguous"] += 1
            pending_ambiguous += 1
            reachable("a transfer ended with an unknown outcome",
                      dict(G, error=type(e).__name__, msg=str(e)[:300],
                           src=h.acct_name(src), dst=h.acct_name(dst), amount=amount))
            time.sleep(1)
            continue

        row = rows[0] if rows else (None, None, None, None)
        sb, sx, db, dx = row
        details = dict(G, src=h.acct_name(src), dst=h.acct_name(dst), amount=amount,
                       src_balance=sb, src_xfers=sx, dst_balance=db, dst_xfers=dx,
                       floor_src=floor_src, floor_dst=floor_dst, coordinator=h.coordinator_of(rs))
        complete = None not in (sb, sx, db, dx)
        always(complete, "a transfer transaction reads both of its accounts", details)
        if not complete:
            continue
        always(sx >= floor_src and dx >= floor_dst,
               "a transfer reads every transfer acknowledged or observed before it started", details)
        always(0 <= sb <= h.BANK_TOTAL and 0 <= db <= h.BANK_TOTAL,
               "a transfer reads balances within the bank total", details)
        sometimes(sx > floor_src or dx > floor_dst,
                  "a transfer saw transfers committed by other clients since this client last looked",
                  details)

        applied = sb >= amount
        sometimes(not applied, "a transfer was declined because the source balance was too low", details)
        sometimes(applied and amount > 0 and sb == amount,
                  "a transfer moved a source account's entire balance", details)
        if applied:
            stats["acked"] += 1
            floors[src] = max(floors.get(src, 0), sx + 1)
            floors[dst] = max(floors.get(dst, 0), dx + 1)
        else:
            stats["declined"] += 1
            floors[src] = max(floors.get(src, 0), sx)
            floors[dst] = max(floors.get(dst, 0), dx)

    h.log(TAG, f"done {stats}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
