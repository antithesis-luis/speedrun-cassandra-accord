#!/usr/bin/env bash
# One-shot bootstrap helper, run in the background by node1's entrypoint until it has succeeded once.
# Waits for all 3 nodes to be UN, then reconfigures the Cluster Metadata Service to 3 members
# (`nodetool cms reconfigure 3`), waits until 3 members are listed, and writes /bootstrap/cms-ready
# (shared volume) so the client can continue with schema creation and setup_complete.
set -uo pipefail
EXPECTED_NODES="${EXPECTED_NODES:-3}"
log() { echo "boost-cms-helper: $*"; }

until [[ "$(nodetool status 2>/dev/null | grep -c '^UN')" -ge "${EXPECTED_NODES}" ]]; do
  sleep 5
done
log "all ${EXPECTED_NODES} nodes UN"

members() { nodetool cms describe 2>/dev/null | sed -n 's/^Members: //p' | tr ',' '\n' | grep -c .; }

while [[ "$(members)" -lt "${EXPECTED_NODES}" ]]; do
  log "running nodetool cms reconfigure ${EXPECTED_NODES}"
  nodetool cms reconfigure "${EXPECTED_NODES}" || log "reconfigure returned $?"
  for _ in $(seq 1 12); do
    [[ "$(members)" -ge "${EXPECTED_NODES}" ]] && break
    sleep 5
  done
  nodetool cms reconfigure --status 2>/dev/null || true
done
nodetool cms describe 2>/dev/null || true
mkdir -p /bootstrap && touch /bootstrap/cms-ready
log "CMS has ${EXPECTED_NODES} members; wrote /bootstrap/cms-ready"
