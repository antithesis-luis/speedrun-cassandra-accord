#!/usr/bin/env python3
"""Guarantee 4 driver: plain CQL writes and read-backs on single-writer version registers in a full-mode table.

Ordinary single-statement CQL (no BEGIN TRANSACTION) on the transactional_mode='full' table
fm_reg. This invocation owns 1-2 private keys (random 63-bit ids) and writes strictly increasing
versions 1, 2, 3, ... to them with plain UPDATE / INSERT, and sometimes with a conditional
INSERT IF NOT EXISTS / UPDATE ... IF ver < v (which also runs through Accord). After every write
it reads the key(s) back with a plain SELECT, usually through a different coordinator, at a
consistency level drawn from the levels Accord accepts. The session sends no client-side
timestamps and no statement uses USING TIMESTAMP, so Accord picks every write timestamp. Order
comes from execution order in this script: a read runs after the previous write returned.

Per key, the floor is the highest version acknowledged, or observed by an earlier read (an
observed version v linearizes after every write acknowledged before v was sent). A read may
return a version at or above the floor, a version whose write had an unknown outcome (such a
write may linearize anywhere later), or no row only while nothing was acknowledged or observed.

Modes (per invocation):
- persist: keep writing a key after an unknown outcome (exercises late-applying writes);
- retire: abandon a key after a write with an unknown outcome and start a new one; the key's
  versions then apply in order, so it is published to /ledger/fm_keys for
  parallel_driver_fm_readers, with the highest acknowledged version (written only after the ack).

Checks (Guarantee 4):
- Always: a plain read on a full-mode table returns the latest acknowledged write or a newer one.
- Always: a plain read on a full-mode table returns only versions that were written.
- Always: a declined conditional write reports a current version at least as new as every
  acknowledged one.
- Sometimes: a conditional single-statement write was applied; a plain write was read back
  through a different coordinator than the one that acknowledged it; a consistency-level ONE read
  right after an acknowledged plain write returned that write.
- Reachable: a plain write with an unknown outcome was later read back.
"""
import sys
import time

from cassandra import ConsistencyLevel

import helper_accord as h
import helper_fm as fm
from antithesis.assertions import always, reachable, sometimes

TAG = "fm_register"
G = {"guarantee": "G4", "property": "full-mode-linearizable"}


class Reg:
    def __init__(self, key):
        self.key = key
        self.issued = 0       # highest version sent
        self.floor = 0        # lowest version a later read may return (unless unknown)
        self.unknown = set()  # versions whose write outcome was unknown
        self.rejected = set() # versions whose conditional write was definitely not applied
        self.acked = 0

    def summary(self):
        return {"key": self.key, "issued": self.issued, "floor": self.floor,
                "unknown": sorted(self.unknown)[-10:], "rejected": sorted(self.rejected)[-10:]}


def valid_read(reg, ver):
    """(fresh, attempted) for one observed version."""
    if ver is None:
        return reg.floor == 0, True
    attempted = 1 <= ver <= reg.issued and ver not in reg.rejected
    fresh = ver >= reg.floor or ver in reg.unknown
    return fresh, attempted


def observe(reg, ver):
    if ver is not None and ver > reg.floor:
        reg.floor = ver


def main():
    cluster, session = h.connect(TAG, client_timestamps=False)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0
    mode = h.choice(["persist", "retire"])
    nkeys = 1 if mode == "retire" else h.choice([1, 1, 2])
    steps = h.choice([5, 20, 60])
    cond_weight = h.choice([0, 1, 3])  # how often (out of 8) a write is conditional
    regs = [Reg(h.unique_id63()) for _ in range(nkeys)]
    deadline = time.monotonic() + 180
    stats = {"acked": 0, "rejected": 0, "ambiguous": 0, "reads": 0, "retired": 0}
    h.log(TAG, f"mode={mode} keys={[r.key for r in regs]} steps={steps} cond_weight={cond_weight}")

    try:
        for step in range(steps):
            if time.monotonic() > deadline:
                break
            reg = h.choice(regs)
            ver = reg.issued + 1
            reg.issued = ver
            fresh_key = reg.floor == 0 and not reg.unknown
            if h.rand_int(8) < cond_weight:
                style = "insert_ine" if fresh_key else "update_if"
            else:
                style = h.choice(["update", "update", "insert"])
            wcl = h.choice(fm.WRITE_CLS)
            stmt, build, cond = fm.write_stmt(style, wcl)
            whost = fm.pick_host(cluster)
            wcoord = None
            acked = False
            try:
                rs = fm.execute(session, stmt, build(reg.key, ver, fm.pad()), host=whost)
                wcoord = h.coordinator_of(rs)
                if cond:
                    applied, cur = fm.lwt_outcome(rs)
                    details = dict(G, style=style, cl=fm.cl_name(wcl), version=ver,
                                   applied=applied, current=cur, coordinator=wcoord, **reg.summary())
                    sometimes(applied, "a conditional single-statement write on a full-mode table was applied",
                              details)
                    if applied:
                        acked = True
                    else:
                        # the returned row is a read that started after every earlier ack
                        fresh, attempted = valid_read(reg, cur)
                        always(fresh and attempted,
                               "a declined conditional write on a full-mode table reports a current version at least as new as every acknowledged one",
                               details)
                        reg.rejected.add(ver)
                        observe(reg, cur)
                        stats["rejected"] += 1
                else:
                    acked = True
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                stats["ambiguous"] += 1
                reg.unknown.add(ver)
                h.log(TAG, f"write k={reg.key} v={ver} {style} ambiguous: {type(e).__name__}")
                if mode == "retire":
                    regs[regs.index(reg)] = Reg(h.unique_id63())
                    stats["retired"] += 1
                    time.sleep(1)
                    continue
                time.sleep(1)

            if acked:
                reg.floor = max(reg.floor, ver)
                reg.acked = ver
                stats["acked"] += 1
                if mode == "retire":
                    fm.publish(reg.key, ver)

            # read back with a plain SELECT, preferably through another coordinator
            targets = [reg] if len(regs) == 1 or h.coin(1, 2) else list(regs)
            rcl = h.choice(fm.READ_CLS)
            rhost = fm.pick_host(cluster, avoid=wcoord)
            try:
                got, rcoord = fm.read_versions(session, [r.key for r in targets], rcl, host=rhost)
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                time.sleep(1)
                continue
            stats["reads"] += 1
            for r in targets:
                seen = got.get(r.key)
                fresh, attempted = valid_read(r, seen)
                details = dict(G, mode=mode, seen=seen, read_cl=fm.cl_name(rcl), write_cl=fm.cl_name(wcl),
                               write_style=style, write_coordinator=wcoord, read_coordinator=rcoord,
                               multi_key=len(targets) > 1, **r.summary())
                always(fresh,
                       "a plain read on a full-mode table returns the latest acknowledged write or a newer one",
                       details)
                always(attempted,
                       "a plain read on a full-mode table returns only versions that were written",
                       details)
                if r is reg:
                    sometimes(acked and rcoord is not None and wcoord is not None and rcoord != wcoord,
                              "a plain write was read back through a different coordinator than the one that acknowledged it",
                              details)
                    sometimes(acked and rcl == ConsistencyLevel.ONE and seen == ver,
                              "a consistency-level ONE read right after an acknowledged plain write returned that write",
                              details)
                if seen is not None and seen in r.unknown:
                    reachable("a plain write with an unknown outcome was later read back", details)
                observe(r, seen)

        h.log(TAG, f"done {stats}")
    finally:
        h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
