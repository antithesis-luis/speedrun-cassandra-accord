"""Shared code for Guarantee 3: the durable table, the per-writer ledger on the shared volume, the write styles, and the read-back every checker uses.

Table accord_ks.durable (k int, id bigint, v text, PRIMARY KEY (k, id)), transactional_mode='full'.
One logical write ("op") has a unique 63-bit id and inserts the row (k, id, v) into 1-3 partitions
k (the same id in each). v is derived from (id, pad), so a checker can verify the value.

Ledger: /ledger/durable-<writer>.jsonl, one append-only file per writer process, each line fsync'd:
  {"t": "attempt", "id": .., "ks": [..], "pad": .., "style": ..}   before sending
  {"t": "ack", "id": ..}                                           after success
  {"t": "ambiguous", "id": .., "err": ..}                          after an unknown outcome
An attempt with no outcome line (writer killed) has an unknown outcome. Only acknowledged ops must
be present. A torn last line (writer killed mid-append) is skipped. Order comes from structure: an
ack line is written only after the client saw success, so any read that starts after reading the
line started after the acknowledgement.

No assertions here: every assertion message is a literal at one callsite in a command file.
"""
import glob
import json
import os
import time

import helper_accord as h

TABLE = f"{h.KEYSPACE}.durable"
LEDGER_DIR = os.environ.get("LEDGER_DIR", "/ledger")

# Partition key spaces: writers share 0..63 (4 hot partitions), each read-back driver uses its own
# 100 partitions above READBACK_BASE (chosen per process) so nobody else writes there.
WRITER_KEYS = tuple(range(64))
HOT_KEYS = WRITER_KEYS[:4]
READBACK_BASE = 1_000_000

# value padding menu: empty suffix, one char, a typical short value, a 4 KiB value
PAD_MENU = (0, 1, 64, 4096)
# partitions per op: single-partition and multi-partition (2 and 3) transactions
SPREAD_MENU = (1, 1, 2, 3)

# write styles:
#  txn       BEGIN TRANSACTION with one INSERT per partition
#  txn_cas   BEGIN TRANSACTION that LET-reads the first row, returns it, inserts only if absent
#  plain     a plain INSERT (single partition; on a full-mode table this is an Accord txn)
STYLES = ("txn", "txn_cas", "plain")

# IN-list size for checker reads (no paging: well under the session fetch size)
IN_BATCH = 50
# txn read size: rows per BEGIN TRANSACTION read (one LET per row)
TXN_READ_MAX = 8


def value_of(op_id, pad):
    return format(op_id, "x") + "-" + ("x" * pad)


# ---------------------------------------------------------------------------------------------
# ledger


class Ledger:
    def __init__(self, writer):
        os.makedirs(LEDGER_DIR, exist_ok=True)
        self.path = os.path.join(LEDGER_DIR, f"durable-{writer}.jsonl")
        self.f = open(self.path, "a", encoding="utf-8")

    def _append(self, rec):
        self.f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self.f.flush()
        os.fsync(self.f.fileno())

    def attempt(self, op_id, ks, pad, style):
        self._append({"t": "attempt", "id": op_id, "ks": list(ks), "pad": pad, "style": style})

    def ack(self, op_id):
        self._append({"t": "ack", "id": op_id})

    def ambiguous(self, op_id, err):
        self._append({"t": "ambiguous", "id": op_id, "err": err})

    def close(self):
        try:
            self.f.close()
        except Exception:  # noqa: BLE001
            pass


def load_ledgers():
    """-> (ops, files). ops: id -> {"ks", "pad", "style", "state": acked|ambiguous|pending}."""
    ops = {}
    files = sorted(glob.glob(os.path.join(LEDGER_DIR, "durable-*.jsonl")))
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().split("\n")
        except OSError:
            continue
        for line in lines:
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue  # torn line from a writer killed mid-append
            op_id = rec.get("id")
            if rec.get("t") == "attempt":
                ops[op_id] = {"ks": rec["ks"], "pad": rec["pad"], "style": rec["style"], "state": "pending"}
            elif op_id in ops and rec.get("t") == "ack":
                ops[op_id]["state"] = "acked"
            elif op_id in ops and rec.get("t") == "ambiguous" and ops[op_id]["state"] != "acked":
                ops[op_id]["state"] = "ambiguous"
    return ops, files


# ---------------------------------------------------------------------------------------------
# writes


def write_cql(style, ks, op_id, pad):
    v = value_of(op_id, pad)
    if style == "plain":
        return f"INSERT INTO {TABLE} (k, id, v) VALUES ({ks[0]}, {op_id}, '{v}')"
    inserts = "".join(f"  INSERT INTO {TABLE} (k, id, v) VALUES ({k}, {op_id}, '{v}');\n" for k in ks)
    if style == "txn":
        return "BEGIN TRANSACTION\n" + inserts + "COMMIT TRANSACTION"
    # txn_cas: insert only if the first row is absent; returns what the LET read
    return ("BEGIN TRANSACTION\n"
            f"  LET r = (SELECT id FROM {TABLE} WHERE k = {ks[0]} AND id = {op_id});\n"
            "  SELECT r.id;\n"
            "  IF r IS NULL THEN\n" + inserts + "  END IF\n"
            "COMMIT TRANSACTION")


# ---------------------------------------------------------------------------------------------
# reads


def _read_plain(session, k, ids, host=None):
    """One single-partition SELECT with an IN list on the clustering key."""
    q = f"SELECT id, v FROM {TABLE} WHERE k = {k} AND id IN ({', '.join(str(i) for i in ids)})"
    rs = session.execute(q, host=host) if host is not None else session.execute(q)
    return {(k, r.id): r.v for r in rs}, h.coordinator_of(rs)


def _read_txn(session, rows, host=None):
    """One read-only transaction with a LET per (k, id) row (a full Accord read across
    partitions)."""
    lets = "".join(f"  LET r{n} = (SELECT v FROM {TABLE} WHERE k = {k} AND id = {i});\n"
                   for n, (k, i) in enumerate(rows))
    cols = ", ".join(f"r{n}.v" for n in range(len(rows)))
    q = "BEGIN TRANSACTION\n" + lets + f"  SELECT {cols};\nCOMMIT TRANSACTION"
    rs = session.execute(q, host=host) if host is not None else session.execute(q)
    out = list(rs)
    vals = list(out[0]) if out else [None] * len(rows)
    return {row: v for row, v in zip(rows, vals) if v is not None}, h.coordinator_of(rs)


def read_rows(session, rows, use_txn, host=None):
    """Read the given (k, id) rows. use_txn: one transaction per <= TXN_READ_MAX rows; else one
    plain SELECT per partition with an IN list. Returns (found {(k,id): v}, coordinators). Raises
    on the first failed statement (caller retries)."""
    found, coords = {}, set()
    if use_txn:
        for s in range(0, len(rows), TXN_READ_MAX):
            got, c = _read_txn(session, rows[s:s + TXN_READ_MAX], host)
            found.update(got)
            coords.add(c)
    else:
        by_k = {}
        for k, i in rows:
            by_k.setdefault(k, []).append(i)
        for k, ids in by_k.items():
            for s in range(0, len(ids), IN_BATCH):
                got, c = _read_plain(session, k, ids[s:s + IN_BATCH], host)
                found.update(got)
                coords.add(c)
    return found, coords


def read_with_budget(session, rows, use_txn, budget_s, tag):
    """Retry read_rows until it completes or budget_s passes. Returns (found, coords) or
    (None, last_error) if no attempt completed: that is unknown, never evidence of loss."""
    deadline = time.monotonic() + budget_s
    last = None
    while True:
        try:
            return read_rows(session, rows, use_txn)
        except Exception as e:  # noqa: BLE001
            if h.classify(e) == "workload_bug":
                raise
            last = f"{type(e).__name__}: {str(e)[:200]}"
            if time.monotonic() + 3 > deadline:
                h.log(tag, f"read of {len(rows)} rows gave up: {last}")
                return None, last
            time.sleep(3)


def mismatches(rows_expected, found):
    """rows_expected: {(k,id): v}. -> (missing [(k,id)], wrong {(k,id): (seen, expected)})."""
    missing = [r for r in rows_expected if r not in found]
    wrong = {f"{r[0]}:{r[1]}": (h.short_tok(found[r]), h.short_tok(v))
             for r, v in rows_expected.items() if r in found and found[r] != v}
    return missing, wrong


def expected_rows(op_id, op):
    v = value_of(op_id, op["pad"])
    return {(k, op_id): v for k in op["ks"]}



def do_write(session, ledger, ks, style, auto):
    """One logical write with a fresh id, recorded in the ledger around the call.
    -> (op_id, pad, outcome, rows_or_err, coordinator_host). outcome: 'acked' | 'ambiguous'.
    rows_or_err: the result rows if acked, else the error text. Raises on workload bugs."""
    op_id = h.unique_id63()
    pad = h.choice(PAD_MENU)
    ledger.attempt(op_id, ks, pad, style)
    q = write_cql(style, ks, op_id, pad)
    try:
        if auto:
            rs = session.execute(q, execution_profile=h.PROFILE_AUTO_RETRY)
        else:
            rs = session.execute(q)
        rows = list(rs)
    except Exception as e:  # noqa: BLE001
        if h.classify(e) == "workload_bug":
            raise
        err = f"{type(e).__name__}: {str(e)[:200]}"
        ledger.ambiguous(op_id, err)
        return op_id, pad, "ambiguous", err, None
    ledger.ack(op_id)
    host = None
    try:
        host = rs.response_future.coordinator_host
    except Exception:  # noqa: BLE001
        pass
    return op_id, pad, "acked", rows, host


def ops_rows(op_items):
    """[(op_id, op)] -> {(k, id): v} for every row of every op, ordered by partition."""
    rows = {}
    for op_id, op in op_items:
        rows.update(expected_rows(op_id, op))
    return dict(sorted(rows.items()))


def check_chunks(session, expected, deadline, first_budget_s, later_budget_s, tag, chunk=IN_BATCH):
    """Read `expected` ({(k,id): v}) in chunks; yields (chunk_expected, found, use_txn, coords)
    per chunk, with found=None when the chunk could not be read in its budget (unknown). After
    one chunk gives up, later chunks get later_budget_s. Stops at `deadline` (remaining chunks
    are not yielded; the caller counts them)."""
    items = list(expected.items())
    budget = first_budget_s
    for s in range(0, len(items), chunk):
        if time.monotonic() > deadline:
            return
        part = dict(items[s:s + chunk])
        use_txn = h.coin(1, 4)
        b = max(5.0, min(budget, deadline - time.monotonic()))
        found, coords = read_with_budget(session, list(part), use_txn, b, tag)
        if found is None:
            budget = later_budget_s
        else:
            budget = first_budget_s
        yield part, found, use_txn, coords
