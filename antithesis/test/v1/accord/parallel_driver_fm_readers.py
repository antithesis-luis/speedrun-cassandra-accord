#!/usr/bin/env python3
"""Guarantee 4 driver: concurrent plain-CQL readers of registers that other writers have published.

parallel_driver_fm_register (retire mode) publishes keys in /ledger/fm_keys/<key>; each file
holds a version acknowledged before the file was last replaced, and the key's writer retires the
key after any write with an unknown outcome, so the key's versions apply in increasing order.
This command reads those keys with plain SELECTs (single key, or a small IN list) for 5, 20 or 50
rounds, through varying coordinators and at varying consistency levels, while their writers may
still be running. Order comes from structure: the floor file is read before the SELECT is sent,
and the file was replaced only after its version was acknowledged, so the SELECT started after
that acknowledgement.

Checks (Guarantee 4):
- Always: a plain read of a published register sees at least the version acknowledged before the
  read started (read-after-acknowledge across clients).
- Always: one client's successive plain reads of a single-writer register never go backwards
  (monotonic reads).
- Sometimes: a read returned a version newer than its published floor; a reader saw a published
  register advance between two of its reads.
- Reachable: a multi-key IN read of published registers completed.
"""
import os
import sys
import time

import helper_accord as h
import helper_fm as fm
from antithesis.assertions import always, reachable, sometimes

TAG = "fm_readers"
G = {"guarantee": "G4", "property": "full-mode-linearizable"}


def candidate_keys():
    """Recently updated published keys first (more likely to have a live writer)."""
    keys = fm.published_keys()

    def mtime(k):
        try:
            return os.path.getmtime(os.path.join(fm.PUBLISH_DIR, str(k)))
        except OSError:
            return 0.0

    keys.sort(key=mtime, reverse=True)
    return keys[:12]


def main():
    keys = candidate_keys()
    waits = 0
    while not keys and waits < 4:
        time.sleep(5)
        waits += 1
        keys = candidate_keys()
    if not keys:
        h.log(TAG, "no published registers yet; nothing to read")
        return 0

    cluster, session = h.connect(TAG, client_timestamps=False)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0
    rounds = h.choice([5, 20, 50])
    pause = h.choice([0.2, 1.0, 2.0])
    focus = h.coin(1, 3)  # read only one key for the whole invocation
    focus_key = h.choice(keys)
    last_seen = {}
    last_coord = None
    deadline = time.monotonic() + 180
    stats = {"reads": 0, "errors": 0, "advanced": 0}
    h.log(TAG, f"keys={len(keys)} rounds={rounds} pause={pause} focus={focus}")

    try:
        for _ in range(rounds):
            if time.monotonic() > deadline:
                break
            if focus:
                batch = [focus_key]
            elif h.coin(1, 4) and len(keys) > 1:
                batch = h.shuffled(keys)[:1 + h.rand_int(min(3, len(keys)))]
            else:
                batch = [h.choice(keys)]
            # floors are read BEFORE the query is sent
            floors = {k: fm.published_floor(k) for k in batch}
            rcl = h.choice(fm.READ_CLS)
            rhost = fm.pick_host(cluster, avoid=last_coord)
            try:
                got, coord = fm.read_versions(session, batch, rcl, host=rhost)
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                stats["errors"] += 1
                time.sleep(1)
                continue
            stats["reads"] += 1
            for k in batch:
                seen = got.get(k)
                floor = floors[k]
                prev = last_seen.get(k)
                details = dict(G, key=k, seen=seen, published_floor=floor, previous=prev,
                               read_cl=fm.cl_name(rcl), coordinator=coord, previous_coordinator=last_coord,
                               multi_key=len(batch) > 1)
                if floor is not None:
                    always(seen is not None and seen >= floor,
                           "a plain read of a published register sees at least the version acknowledged before the read started",
                           details)
                always(prev is None or (seen is not None and seen >= prev),
                       "one client's successive plain reads of a single-writer register never go backwards",
                       details)
                sometimes(prev is not None and seen is not None and seen > prev,
                          "a reader saw a published register advance between two of its plain reads",
                          details)
                sometimes(floor is not None and seen is not None and seen > floor,
                          "a plain read of a published register returned a version newer than its published floor",
                          details)
                if prev is not None and seen is not None and seen > prev:
                    stats["advanced"] += 1
                if seen is not None and (prev is None or seen > prev):
                    last_seen[k] = seen
            if len(batch) > 1:
                reachable("a multi-key IN read of published registers completed", {**G, "keys": len(batch)})
            last_coord = coord
            time.sleep(pause)
        h.log(TAG, f"done {stats}")
    finally:
        h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
