#!/usr/bin/env python3
"""Guarantee 2 driver: write one fresh token to every row of a group across two tables, atomically.

A group is 2-4 partitions over two tables (helper_accord.group_slots). Each invocation picks a
shape (5, 15 or 40 operations, hot or spread groups, retry style) and runs a bounded mix of:
- an unconditional BEGIN TRANSACTION writing the token to every slot (INSERT or UPDATE);
- a conditional BEGIN TRANSACTION that LET-reads every slot, returns them, and writes only if the
  first slot still holds the token this client last saw (compare-and-set; other writers' tokens
  make it decline);
- a LOGGED BATCH writing the token to every slot of a batch-only group (checked at the end only,
  by eventually_pair_check);
- a read-back of a group in one transaction, especially after an unknown outcome.

Retry styles: explicit single attempts (FallthroughRetryPolicy), or the driver's auto-retry
profile for unconditional writes (a hidden retry rewrites the same token: applied once or more).
Every token is unique per logical write, so a write with an unknown outcome may show up in all
slots or in none, but never in only some.

Checks (Guarantee 2):
- Always: a read-back after a cross-table write saw the same token in every slot.
- Always: a conditional cross-table write read the same token in every slot of its group.
- Sometimes: a cross-table write of one token to four partitions was acknowledged; a read-back
  found a write of unknown outcome applied to every slot of its group; a conditional write was
  declined because another writer changed the group.
- Reachable: a cross-table write transaction ended with an unknown outcome.
"""
import sys
import time

import helper_accord as h
from antithesis.assertions import always, reachable, sometimes

TAG = "pair_writes"
G = {"guarantee": "G2", "property": "txn-all-or-nothing"}


def main():
    cluster, session = h.connect(TAG)
    if session is None:
        h.log(TAG, "cluster unreachable within budget; nothing to do")
        return 0

    writer = format(h.unique_id63(), "x")
    ops = h.choice([5, 15, 40])
    hot = h.coin(1, 3)
    auto = h.coin(1, 3)
    batch_pct = h.choice([0, 10, 30])
    cas_pct = h.choice([20, 50])
    wall_deadline = time.monotonic() + 180
    h.log(TAG, f"writer={writer} ops={ops} hot={hot} auto_retry={auto} batch_pct={batch_pct} cas_pct={cas_pct}")

    last_seen = {}   # group -> token this client last saw in the group's first slot
    unknown = {}     # group -> tokens whose write outcome is unknown, not yet read back
    stats = {"acked": 0, "declined": 0, "ambiguous": 0, "batches": 0, "readbacks": 0}
    seq = 0

    for _ in range(ops):
        if time.monotonic() > wall_deadline:
            break
        seq += 1
        tok = h.new_token(writer, seq)
        style = h.choice(["insert", "update"])
        roll = h.rand_int(100)

        # read back a group with an unknown write sometimes, or after every few ops
        if unknown and h.coin(1, 2):
            g = h.choice(sorted(unknown))
            slots = h.group_slots(g)
            try:
                row, coord = h.read_group(session, slots)
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                time.sleep(1)
                continue
            stats["readbacks"] += 1
            ok, view, distinct = h.group_view(slots, row)
            always(ok, "a read-back after a cross-table write saw the same token in every slot",
                   dict(G, group=g, slots=view, coordinator=coord,
                        unknown=[h.short_tok(t) for t in unknown[g]]))
            found = [t for t in unknown[g] if t in distinct]
            sometimes(ok and bool(found),
                      "a read-back found a write of unknown outcome applied to every slot of its group",
                      dict(G, group=g, slots=view))
            if ok:
                last_seen[g] = row[0] if row else None
            del unknown[g]
            continue

        if roll < batch_pct:
            g = h.choice(h.BATCH_GROUPS)
            slots = h.shuffled(h.group_slots(g))
            try:
                session.execute(h.group_batch_cql(slots, tok, style))
                stats["batches"] += 1
            except Exception as e:  # noqa: BLE001
                if h.classify(e) == "workload_bug":
                    raise
                stats["ambiguous"] += 1
                time.sleep(1)
            continue

        g = h.choice(h.HOT_TXN_GROUPS if hot else h.TXN_GROUPS)
        slots = h.shuffled(h.group_slots(g))
        cas = h.rand_int(100) < cas_pct
        try:
            if cas:
                expected = last_seen.get(g)
                rs = session.execute(h.group_cas_cql(slots, expected, tok, style))
            elif auto:
                rs = session.execute(h.group_write_cql(slots, tok, style),
                                     execution_profile=h.PROFILE_AUTO_RETRY)
            else:
                rs = session.execute(h.group_write_cql(slots, tok, style))
            rows = list(rs)
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            stats["ambiguous"] += 1
            unknown.setdefault(g, []).append(tok)
            reachable("a cross-table write transaction ended with an unknown outcome",
                      dict(G, group=g, cas=cas, auto_retry=auto, error=type(e).__name__,
                           msg=str(e)[:300]))
            time.sleep(1)
            continue

        if not cas:
            stats["acked"] += 1
            last_seen[g] = tok  # every slot now holds this token, or a later writer's
            sometimes(len(slots) == 4,
                      "a cross-table write of one token to four partitions was acknowledged",
                      dict(G, group=g, style=style, auto_retry=auto))
            continue

        row = rows[0] if rows else None
        ok, view, distinct = h.group_view(slots, row)
        always(ok, "a conditional cross-table write read the same token in every slot of its group",
               dict(G, group=g, slots=view, expected=h.short_tok(last_seen.get(g)),
                    coordinator=h.coordinator_of(rs)))
        # the condition is on r0, the first slot in this statement's (shuffled) order
        first = row[0] if row else None
        if first == last_seen.get(g):
            stats["acked"] += 1
            last_seen[g] = tok
        else:
            stats["declined"] += 1
            sometimes(first is not None and last_seen.get(g) is not None,
                      "a conditional cross-table write was declined because another writer changed the group",
                      dict(G, group=g, slots=view))
            last_seen[g] = first if ok else None

    h.log(TAG, f"done {stats}")
    h.shutdown(cluster)
    return 0


if __name__ == "__main__":
    sys.exit(main())
