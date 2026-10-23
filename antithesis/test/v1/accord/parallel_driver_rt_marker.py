#!/usr/bin/env python3
"""Guarantee 1 driver: transfers in a private pair of accounts, each followed by a new read that must see it (real-time order).

Each invocation creates its own two-account "slot" (two partitions of rt_accounts, keyed by a
random 63-bit slot id), so no other client can disturb its checks. It then runs 3, 10 or 25
transfers between the two accounts; transfer i stamps marker seq = i on both rows, guarded by
`IF a.seq < i AND b.seq < i AND a.balance >= amount`, so a late-applying older transfer whose
outcome was unknown can never overwrite a newer marker. After each transfer, a NEW read-only
transaction over both partitions, usually through a different coordinator, reads the slot back.

Checks (Guarantee 1):
- Always: a read started after a transfer was acknowledged sees that transfer (both markers are
  at least every marker acknowledged or observed before the read started).
- Always: a read-back of a private slot sees one consistent transfer state (both rows carry the
  same marker, balances sum to 200, none is negative).
- Always: a private-slot transfer reads the markers acknowledged before it and none from later
  transfers.
- Sometimes: a transfer's effect was read back through a different coordinator; a private-slot
  transfer was declined for insufficient balance.
- Reachable: a transfer whose outcome was unknown was later seen applied.
"""
import sys
import time

from cassandra import ConsistencyLevel

import helper_accord as h
from antithesis.assertions import always, reachable, sometimes

TAG = "rt_marker"
G = {"guarantee": "G1", "property": "txn-strict-serializable"}
T = f"{h.KEYSPACE}.rt_accounts"
SLOT_TOTAL = 200
AMOUNTS = (0, 1, 50, 99, 100, 101, 199, 200, 201)

INIT = (
    "BEGIN TRANSACTION\n"
    f"  LET r = (SELECT seq FROM {T} WHERE slot = ? AND acct = 0);\n"
    "  SELECT r.seq;\n"
    "  IF r IS NULL THEN\n"
    f"    INSERT INTO {T} (slot, acct, balance, seq) VALUES (?, 0, 100, 0);\n"
    f"    INSERT INTO {T} (slot, acct, balance, seq) VALUES (?, 1, 100, 0);\n"
    "  END IF\n"
    "COMMIT TRANSACTION"
)

XFER = (
    "BEGIN TRANSACTION\n"
    f"  LET a = (SELECT balance, seq FROM {T} WHERE slot = ? AND acct = ?);\n"
    f"  LET b = (SELECT balance, seq FROM {T} WHERE slot = ? AND acct = ?);\n"
    "  SELECT a.balance, a.seq, b.balance, b.seq;\n"
    "  IF a.seq < ? AND b.seq < ? AND a.balance >= ? THEN\n"
    f"    UPDATE {T} SET balance -= ?, seq = ? WHERE slot = ? AND acct = ?;\n"
    f"    UPDATE {T} SET balance += ?, seq = ? WHERE slot = ? AND acct = ?;\n"
    "  END IF\n"
    "COMMIT TRANSACTION"
)

READ = ("BEGIN TRANSACTION\n"
        f"  SELECT acct, balance, seq FROM {T} WHERE slot = %d AND acct IN (0, 1);\n"
        "COMMIT TRANSACTION")


def prepare(session, cql):
    ps = session.prepare(cql)
    ps.consistency_level = ConsistencyLevel.QUORUM
    ps.serial_consistency_level = ConsistencyLevel.SERIAL
    ps.is_idempotent = False
    return ps


def read_slot(session, cluster, slot, avoid):
    """Read the slot in a new transaction, preferring a coordinator other than `avoid`."""
    hosts = [x for x in cluster.metadata.all_hosts() if x.is_up and str(x.endpoint) != avoid
             and str(x) != avoid]
    target = h.choice(hosts) if hosts and h.coin(3, 4) else None
    rs = session.execute(READ % slot, host=target) if target is not None else session.execute(READ % slot)
    return {r.acct: (r.balance, r.seq) for r in rs}, h.coordinator_of(rs)


def main():
    cluster, session = h.connect(TAG)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0
    steps = h.choice([3, 10, 25])
    deadline = time.monotonic() + 180
    slot = h.unique_id63()
    h.log(TAG, f"slot={slot} steps={steps}")

    try:
        init_ps, xfer_ps = None, None
        while init_ps is None or xfer_ps is None:
            if time.monotonic() > deadline:
                return 0
            try:
                init_ps, xfer_ps = prepare(session, INIT), prepare(session, XFER)
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                time.sleep(2)

        # create the slot (conditional, so resubmitting after an unknown outcome is safe)
        while True:
            if time.monotonic() > deadline:
                h.log(TAG, "could not create slot in time")
                return 0
            try:
                session.execute(init_ps, (slot, slot, slot))
                break
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                time.sleep(2)

        floor = 0       # lowest marker any later read may see
        issued = 0      # highest marker ever sent
        unknown = []    # markers whose transfer outcome was unknown
        stats = {"acked": 0, "declined": 0, "ambiguous": 0, "reads": 0}
        for i in range(1, steps + 1):
            if time.monotonic() > deadline:
                break
            src = h.rand_int(2)
            dst = 1 - src
            amt = h.choice(AMOUNTS)
            issued = i
            write_coord = None
            try:
                rs = session.execute(xfer_ps, (slot, src, slot, dst, i, i, amt,
                                               amt, i, slot, src, amt, i, slot, dst))
                write_coord = h.coordinator_of(rs)
                rows = list(rs)
                sb, sseq, db, dseq = rows[0] if rows else (None, None, None, None)
                details = dict(G, slot=slot, step=i, amount=amt, src=src, src_balance=sb,
                               src_seq=sseq, dst_balance=db, dst_seq=dseq, floor=floor,
                               coordinator=write_coord)
                ok = None not in (sb, sseq, db, dseq)
                always(ok and floor <= min(sseq, dseq) and max(sseq, dseq) < i,
                       "a private-slot transfer reads the markers acknowledged before it and none from later transfers",
                       details)
                if ok:
                    applied = sseq < i and dseq < i and sb >= amt
                    sometimes(not applied and sb < amt,
                              "a private-slot transfer was declined for insufficient balance", details)
                    if applied:
                        floor = max(floor, i)
                        stats["acked"] += 1
                    else:
                        floor = max(floor, sseq, dseq)
                        stats["declined"] += 1
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                stats["ambiguous"] += 1
                unknown.append(i)
                time.sleep(1)

            # read back in a NEW transaction
            try:
                got, read_coord = read_slot(session, cluster, slot, write_coord)
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                time.sleep(1)
                continue
            stats["reads"] += 1
            r0, r1 = got.get(0), got.get(1)
            details = dict(G, slot=slot, step=i, floor=floor, issued=issued, rows={str(k): v for k, v in got.items()},
                           write_coordinator=write_coord, read_coordinator=read_coord, unknown=unknown[-10:])
            complete = r0 is not None and r1 is not None and None not in r0 + r1
            always(complete and min(r0[1], r1[1]) >= floor,
                   "a read started after a transfer was acknowledged sees that transfer", details)
            if not complete:
                continue
            always(r0[1] == r1[1] and r0[0] + r1[0] == SLOT_TOTAL and min(r0[0], r1[0]) >= 0
                   and max(r0[1], r1[1]) <= issued,
                   "a read-back of a private slot sees one consistent transfer state", details)
            sometimes(read_coord is not None and write_coord is not None and read_coord != write_coord,
                      "a transfer's effect was read back through a different coordinator", details)
            seen = max(r0[1], r1[1])
            if seen in unknown:
                reachable("a transfer whose outcome was unknown was later seen applied", details)
            floor = max(floor, seen)

        h.log(TAG, f"done {stats}")
    finally:
        h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
