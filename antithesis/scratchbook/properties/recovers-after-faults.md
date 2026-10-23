# recovers-after-faults (G5)

## Claim
- D3 (CEP-15): "Optimal failure tolerance: latency and performance should be unaffected by any
  minority of replica failures."
- The 120 s window is our inference. Cassandra documents no recovery time.

## Documented and coded recovery behaviour
- **No leader election.** Any node coordinates. With 1 of 3 down, a simple quorum of 2 remains,
  and the slow path continues. The fast-path electorate is reconfigured after
  `fast_path_update_delay` (5 s per `conf/cassandra.yaml:2826–2827`; `AccordConfig.java:239`).
- **Stalled txns** from dead coordinators: the progress log (`A/impl/progresslog/DefaultProgressLog.java:88`;
  `accord-architecture.adoc:157–172`) triggers `MaybeRecover` → `Recover`
  (`A/coordinate/Recover.java:106`).
  - Delay: `AccordAgent.slowCoordinatorDelay` (`C/service/accord/api/AccordAgent.java:309`) uses
    `accord.recover_txn`, default `"5s*attempts <= 60s"` (`AccordConfig.java:219`); `tuning.md`
    sets `1s*attempts <= 10s`.
  - Coordination expiry: `accord.expire_txn`, default `"5s*attempts <= 60s"` (:223).
  - A txn blocked behind an unrecovered dependency waits for that recovery.
- **Restart:** the journal is replayed (`C/service/accord/journal/Replay.java:53`), followed by
  `catchup_on_start` (default `NORMAL`; success latency 60 s, fail latency 900 s, max 5 attempts,
  does not exit on failure; `AccordConfig.java:314–320`). A restarting node is not needed for
  quorum unless 2 nodes are down.
- **Sync points and durability:** `retry_syncpoint`/`retry_durability` default
  `"10s*attempt <= 600s"` (`AccordConfig.java:231–232`). These matter for GC, not for user-txn
  progress.
- **CMS:** with 3 CMS members (setup step 4 in `deployment-topology.md`), metadata stays
  committable with 1 node down. `cms_await_timeout` is 120 s (`Config.java:198`), but only
  metadata operations wait on it. User txns do not.
- **Failure detector:** `phi_convict_threshold` 8 (`Config.java:248`). Detection takes seconds.

## Client timeouts relevant to the window
| Setting | Default | Tuned (`tuning.md`) | Effect |
|---|---|---|---|
| `write_request_timeout` | 2000 ms (Config.java:158); 10000 ms in shipped conf/cassandra.yaml | 10 s | Accord deadline for write txns (`AccordService.java:1158`) |
| `read_request_timeout` | 5000 ms | 10 s | Accord deadline for read txns |
| `native_transport_timeout` | 12 s (Config.java:1616) | 30 s (`AccordTestBase.java:390`) | server-side queue timeout |
| driver `request_timeout` | 10 s | 35 s for normal commands, 15 s for the probe (the server answers within 10 s) | client-side `OperationTimedOut` |
| `accord.recover_txn` | 5s×attempts ≤ 60 s | 1s×attempts ≤ 10 s | how fast a stuck txn is recovered |

Window: **120 s**, measured from the first probe attempt after faults stop. Fastest expected path:
an immediate success. Slow path: one or two attempts time out at 10 s while recovery of blocking
txns (≤10 s per attempt with the tuned value) and node restarts finish. 120 s exceeds the SUT's
own recovery timescales above, apart from `catchup_on_start_fail_latency` (900 s). That setting
only delays a node's own catch-up and does not block quorum txns on the other two nodes.

## Client semantics the checker must respect
- Probe at CL `QUORUM`. Use a session with all 3 contact points and the default load balancing
  (`RoundRobin`/`DCAware`), so that the driver skips a dead coordinator.
- Probe write failures are ambiguous. That doesn't matter for liveness, because only "some
  attempt succeeded within 120 s" is asserted.
- If the probe writes an incrementing counter, an ambiguous attempt may have applied. Do not assert
  on the counter value here.
- Do not assert liveness while faults are still active, or while ≥2 nodes are deliberately down.

## Known closed issues
- CASSANDRA-20641, "Accord: journal replay rejected startup": a restart liveness failure.
- CASSANDRA-21440's fix commit also fixed "Avoid deadlock when notifying ComplexListener(s)" and
  "maybeExecute must invoke either notWaiting or notifyWaiting to ensure tryExecuteListening
  terminates". Both are liveness bugs (accord `66cab49`).

## Implementation (P6)
- Command: `antithesis/test/v1/accord/eventually_recovery_probe.py` (eventually_, so it runs after
  Antithesis stops injecting faults and restarts killed containers). Window: 120 s from command start,
  including the connect. No request starts after the window; a success only counts if it completed
  inside it. Worst-case runtime is about 135 s (measured locally: 126 s with one node paused throughout).
- Probes per round (3 s sleep between rounds, no busy-wait): through **each** node as coordinator
  (`session.execute(..., host=)`), `BEGIN TRANSACTION LET r = (SELECT ver FROM kv WHERE k=A); SELECT r.ver;
  UPDATE kv SET ver=<pid> WHERE k=A; UPDATE kv SET ver=<pid> WHERE k=B; COMMIT TRANSACTION`, with node-reserved
  keys A=-1000-10i, B=-1001-10i and a fresh 63-bit probe id each attempt. Also a plain QUORUM `INSERT` then
  `SELECT` on a fresh `kv` key (any coordinator), which counts as a success only if it reads back its own id.
- Every error, timeout or other ambiguous outcome counts as "not yet succeeded". Nothing asserts on
  probe values beyond the plain read-back.
- **Two availability Always assertions:** "a transaction succeeded within 120 seconds after faults
  stopped" (any coordinator, the literal G5 claim), and "every node coordinated a transaction within
  120 seconds after faults stopped". The second one is reasonable because Antithesis restarts every
  container it kills. So a node still down, or unable to coordinate, 120 s after faults stop is a
  failure (guarantees.md: never skip because a server is down). Plus "a plain write and read on a
  transactional table succeeded within 120 seconds after faults stopped".
- Details: per-node attempts, first-success second, last error, coordinator; plain-probe attempts and
  first success; connect time; rounds.
- Driver settings: `request_timeout` 15 s; `ConstantReconnectionPolicy(2 s)`. The driver's default
  exponential backoff (up to 600 s) would hide a restarted node for the whole window.
- Local check: on a healthy cluster everything succeeded in 0.3 s. With node2 paused for 45 s, node2
  was marked down (NoHostAvailable every 3 s) and coordinated at 46 s ("after earlier attempts" Sometimes
  hit). With node3 paused throughout, "every node coordinated" was false and the any-node and plain
  checks were true. The command ended at 126 s.
