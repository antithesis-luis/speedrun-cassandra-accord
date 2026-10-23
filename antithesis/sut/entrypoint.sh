#!/usr/bin/env bash
# Cassandra node entrypoint (Antithesis harness).
# - Renders cassandra.yaml for this host and boot kind (seeds; config only; never touches /var/lib/cassandra contents,
#   so a killed/restarted node rejoins with its existing data).
# - Points Cassandra's log dir at $ANTITHESIS_OUTPUT_DIR/<hostname> (fallback /var/log/cassandra).
# - Puts the SUT jars (and any jars Antithesis injects beside them) on the classpath.
# - On the node with CMS_BOOTSTRAP_HELPER=1 (node1), starts the one-shot CMS reconfigure helper
#   in the background until /bootstrap/cms-ready exists.
# - execs `cassandra -f` so the JVM's stdout/stderr are the container's main output.
set -euo pipefail

HOST="$(hostname)"
LOG_BASE="${ANTITHESIS_OUTPUT_DIR:-/var/log/cassandra}"
export CASSANDRA_LOG_DIR="${LOG_BASE}/${HOST}"
mkdir -p "${CASSANDRA_LOG_DIR}" /var/lib/cassandra/accord_journal

# Seeds: on first boot (no system keyspace on disk yet) only node1 is a seed, which keeps the
# bootstrap order node1 -> node2 -> node3. On a restart (after an Antithesis kill) every node is
# listed: SimpleSeedProvider skips entries it cannot resolve (e.g. node1 while node1 is down) and
# only fails when none resolve; a node's own name always resolves.
if [[ -d /var/lib/cassandra/data/system ]]; then
  SEEDS="cassandra-accord-node1,cassandra-accord-node2,cassandra-accord-node3"
  BOOT="restart"
else
  SEEDS="cassandra-accord-node1"
  BOOT="first-boot"
fi

sed -e "s/__HOSTNAME__/${HOST}/g" -e "s/__SEEDS__/${SEEDS}/g" \
  /opt/cassandra-antithesis/cassandra.yaml.template > "${CASSANDRA_CONF}/cassandra.yaml"

# Explicit jar list (no wildcard: bin/nodetool word-splits its command line).
EXTRA_CLASSPATH="$(ls -1 /opt/cassandra/sut/*.jar | paste -sd: -)"
export EXTRA_CLASSPATH

echo "boost: host=${HOST} sut_ref=${BOOST_SUT_REF:-unknown} logdir=${CASSANDRA_LOG_DIR} heap=${MAX_HEAP_SIZE:-auto} boot=${BOOT} seeds=${SEEDS}"

if [[ "${CMS_BOOTSTRAP_HELPER:-0}" == "1" && ! -e /bootstrap/cms-ready ]]; then
  /opt/cassandra-antithesis/helper-cms-bootstrap.sh &
fi

exec /opt/cassandra/bin/cassandra -f -R
