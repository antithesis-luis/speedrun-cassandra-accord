# Apache Cassandra Accord under Antithesis

This repository holds an Antithesis test of Accord transactions in Apache Cassandra
cassandra-6.0-alpha2 (Cassandra `e874e3a9`, Accord `fff32de2`): the test harness and workload in
[antithesis/](antithesis/), the evidence gathered during the runs in
[antithesis/scratchbook/](antithesis/scratchbook/), and the proposed patches in
[antithesis/fixes/](antithesis/fixes/). The results are in three documents: the
[report](speedrun-report.md) (what was tested and found, shareable with the Accord developers),
[how the tests work](speedrun-tests.md) (every test command and the checks it makes), and the
[internal briefing](speedrun-briefing.md) (confidence, caveats, unconfirmed findings and method
notes, for Antithesis only). [boost-summary.md](boost-summary.md) is the earlier single summary
these were reformatted from.
