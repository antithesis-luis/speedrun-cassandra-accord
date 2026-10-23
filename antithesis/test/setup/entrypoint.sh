#!/usr/bin/env bash
# Client container entrypoint: cluster bootstrap (schema, probe, setup_complete), then idle so
# Antithesis can run test commands from /opt/antithesis/test/v1/.
set -euo pipefail
python3 /opt/antithesis/setup/client_setup.py
exec sleep infinity
