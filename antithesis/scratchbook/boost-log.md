2026-10-08T13:31:08Z P0 pending→done preflight ok; disk pruned 26→35GB (build cache >12h); deadline 2026-10-09 08:00 ET (invocation)
2026-10-08T13:36:00Z P1 pending→running customer-research sub-agent
2026-10-08T13:34:08Z P2 pending→done 5 guarantees (G1 strict-serializable, G2 atomic, G3 durable, G4 full-mode linearizable, G5 recovery 120s)
2026-10-08T13:45:00Z P3 pending→running SUT/control sub-agent (candidate #0 Cassandra 6.0-alpha2 + accord)
2026-10-08T13:50:00Z P1 running→done brief written (accord-core + Cassandra service/accord integration)
2026-10-08T14:05:00Z P3 running→done SUT cassandra@6.0-alpha2 e874e3a9; control lead CASSANDRA-21440 (G1)
2026-10-08T14:08:00Z P4 pending→running research sub-agent
2026-10-08T14:08:00Z P6b pending→running control confirm+build sub-agent (21440 lead)
2026-10-08T14:30:00Z P6b running→done 21440 confirmed on paper; prefix c9ffe116 builds (3m); revert-on-current kept as fallback
2026-10-08T14:40:00Z P4 running→done research layer written; DECISION kept journal/commitlog flush at production PERIODIC (rejected BATCH proposal: would mask production durability behaviour)
2026-10-08T14:42:00Z P5 pending→running antithesis-setup sub-agent (attempt 1)
2026-10-08T14:55:00Z NOTE earlier P4/P5 log timestamps were estimated, not read from the clock; P5 setup sub-agent actually ran ~13:50-14:52
2026-10-08T14:55:00Z P5 DECISION accept accord.journal.stop_marker_failure_policy=ALLOW_UNSAFE_STARTUP (documented setting; default EXIT => killed node never restarts; REBOOTSTRAP stuck locally = G5 lead)
2026-10-08T14:56:30Z P5 launch setup-1 d86774c9146cbd065a327fe82351ccd0-63-12 (5m, network only)
2026-10-08T14:58:00Z P6 pending→running G1 txn-strict-serializable (attempt 1)
2026-10-08T15:18:00Z P5 running→done smoke run green, SUT instrumented (163547 locations)
2026-10-08T15:21:00Z P6 G1 done (validate 1 cycle, workload 4246884a53c3)
2026-10-08T15:22:00Z P8 pending→running launch iter-1 e4947374c51cfdaaffd0d6ff6ae5dc10-63-12 (30m, network, G1 only)
2026-10-08T15:24:00Z P6 G2 txn-all-or-nothing attempt 1 started
2026-10-08T15:24:00Z P7 pending→running prefix image built (c9ffe116); render+same-workload check pending final workload
2026-10-08T15:33:00Z P6 G2 done (workload 9e888dc8732a); G3 started
2026-10-08T15:37:00Z P8 live check iter-1: G1 Always failures (audit sum != total at vtime ~238s, network faults only); FP review sub-agent started
2026-10-08T15:43:18Z P8 FP review iter-1 live G1 failures: real (4 props); V1 recorded; adversarial check started (suspect: driver client timestamps on autoretry path)
2026-10-08T15:46:29Z P6 G3 done (workload 8919e9023f60); G4 started
2026-10-08T15:50:05Z V1 adversarial: stands (client timestamps discarded by Accord executeAt; single-attempt audits also fail). control.moot=true
2026-10-08T15:50:05Z P10 pending→running blinded RCA V1 sub-agent
2026-10-08T16:04:07Z P6 G4 done (workload a8291d426cf0); G5 started
2026-10-08T16:11:19Z P10 V1 blinded RCA returned; blind_hash 1c4cd312c07e9049; hypothesis: fast-path bypass (MAY_BYPASS_SAFESTORE) lets an acked txn re-execute with stale reads
2026-10-08T16:12:00Z P8 iter-1 completed; triage sub-agent started; fix-verify V1 image build started
2026-10-08T16:13:31Z P10 V1 step B: not known upstream; still present on trunk (reading check)
2026-10-08T16:15:18Z P8 iter-1 triaged: 6 G1 props fail (real, V1); output volume 7.9GB → logback org.apache.cassandra INFO (harness fix)
2026-10-08T16:20:30Z P6 running→done all 5 guarantees implemented (workload 772c2f7e081f)
2026-10-08T16:20:30Z P8 launch iter-2 83ddaf621438954613d378b310199d39-63-12 (30m, network, G1-G5)
2026-10-08T16:20:30Z P10 launch fixverify-V1 0b77f2b9a794d868ae0d8e6cca24880e-63-12 (30m, network)
2026-10-08T16:20:35Z P7 running→skipped control moot; no pre-fix runs
2026-10-08T17:11:43Z P8 iter-2 done: G2-G5 pass, G1 fails (V1). fixverify-V1-1: V1 conservation props pass; missing-row persists -> V2. green(network) for harness purposes
2026-10-08T17:11:43Z launch iter-3 126cbacda11c1e49afda49c425a00f31-63-12 (full faults) + fixverify-V1-2 0e1949506e0ec5407eb17348c627c8a3-63-12 (full faults)
2026-10-08T17:12:17Z P8 fix invocation 1: G3 bad-path Reachables made non-must-hit; FP review V2 started
2026-10-08T17:15:16Z V2 FP review: real (seeded row read absent; workload sound; persists with V1 patch); adversarial V2 started
2026-10-08T17:20:10Z V2 adversarial: stands (no restarts; V1 patch not involved; identical missing set in 2 unpatched audits); blinded RCA V2 started
2026-10-08T17:23:09Z workload fix 1 done: ccc68eedd897; fixverify-V1 config re-rendered
2026-10-08T17:37:07Z P10 V2 blinded RCA returned (blind_hash e17249845e4080a7): coordinator local read returns only command-store-0 rows; other stores' keys dropped without unavailable; patch = diagnostic+fail-safe in ReadData
2026-10-08T18:02:58Z iter-3 + fixverify-V1-2 (full faults) completed: node2/3 exit code 3 after kills, G5 fails, workload commands exit nonzero, G2 conditional cross-table failure (2), fixverify-V1 G1 conservation 1; triage+FP review started
2026-10-08T18:02:58Z launch fixverify-V2-1 ccc9549ea4ea7c01d4f19e8f3c4ba0d9-63-12 (30m network)
2026-10-08T18:13:48Z full-fault triage: 3 harness FPs (seeds, IP churn, connect); G2 real (V1/V2 family); fixverify-V1 G1 suspect. Fix invocation 2 started. wait on fixverify-V2 hit 503, re-waiting with remaining 48m
2026-10-08T18:21:43Z USER-DECISION hunt runs use --param antithesis.performance_tier=turbo (boost_test)
2026-10-08T18:37:24Z fix invocation 2 done (workload 63f7cc96e480, static IPs 10.231.17.0/24, seeds on restart); launch iter-4 d59511b5246c23175adaf49eec9cfeae-63-12 (30m full faults)
2026-10-08T18:54:17Z fixverify-V2-1 completed: V1+V2 patched build still fails G1 (conservation 38, missing-row 3). V2 fix-verify failed; analysis agent started
2026-10-08T18:58:21Z fix-verify verdicts: V1 not verified, V2 failed (diagnostic never fired); P10 attempt cap reached for both (partial RCA)
2026-10-08T19:28:31Z iter-4 green(full) for harness purposes (only V1-family G1). P8→done. P9 running: launched hunts 1-4 (300/300/360/300m, turbo) run-hours now 24.583
2026-10-08T19:36:14Z summary draft written (IN PROGRESS); saved V2 first-failing log logs/iter2--3359217870427620869.log
2026-10-09T01:59:40Z hunts 1,2,4 completed (new G2/G3/G4/G5 failures, mostly in kill runs; G2 read-back also without kills); triage agent running. Added CONFIG_VARIANT build arg + sut/variants/*.sed. Launched hunt-5 (cfg-durable), hunt-6 (cfg-rebootstrap), hunt-7 (no kills+clock), 300m turbo. run-hours 39.583/40
2026-10-09T02:23:57Z hunts 1,2,4 triaged: kill-dependent G2/G3/G4 suspect (unsafe-startup confound); G5 every-node suspect (120s < 900s catch-up bound), hunt-2 catch-up after clean restart = liveness lead L1; hunt-4 G2 = V2 family
2026-10-09T02:28:57Z hunt-3 completed (360m): same families + node2 exit 3 x45 + G5 any-node 18; triage agent started
2026-10-09T02:35:09Z hunt-3 triaged: V3 candidate (killed node can never restart: Accord journal CRC failure on torn segment); adversarial started
2026-10-09T02:40:47Z V3 adversarial: (a) stands, (b) harness-caused. blinded RCA V3 started
2026-10-09T02:41:39Z USER-DECISION run-hours ceiling 40 -> 60
2026-10-09T02:50:50Z P10 V3 blinded RCA returned (blind_hash 6c301bc611abcf50): torn active segment (size marker, zero CRC) rebuilt as fsynced -> FAIL; patch treats CRC-0 tail of metadata-less segment as end
2026-10-09T02:55:25Z launch fixverify-V3-1 72728337f011528b627e81d1f2315090-63-12 (120m, hunt-3 params, turbo). run-hours 41.583/60
2026-10-09T02:58:00Z step B V2/V3 done: neither known upstream; V3 code unchanged on trunk; opt-in IGNORE_CRC_ZERO_RECORDS exists but default FAIL
2026-10-09T05:25:48Z STOP S8: fixverify-V3 72728337… no result at 150m timeout (in_progress). No new launches; waiting for hunts 5-7 to their timeouts (07:59Z), then summary
2026-10-09T07:56:11Z hunt-7 (no kills+clock) completed: G1 V1/V2 + G2 26; no G3/G4/G5 failures. fixverify-V3 reported late: exit3 x1 vs 45; analysis started
2026-10-09T08:08:10Z fixverify-V3 analysed: V3 fix verified (with caveat); new unreviewed lead L4 (LogTransaction inconsistent disk state after kill during compaction)
2026-10-09T08:40:55Z hunts 5/6 (reported late, live-checked): durable cfg still loses acked writes (G3) -> V4 candidate, adversarial started; REBOOTSTRAP cfg: no safety failures beyond G1, G5 fails
2026-10-09T08:46:20Z V4 adversarial: harness-caused (ALLOW_UNSAFE_STARTUP; G3 passes under REBOOTSTRAP). P9/P10 done. P11 summary started
2026-10-09T08:56:17Z P11 done: final summary written
