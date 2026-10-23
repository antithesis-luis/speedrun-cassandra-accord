# Workload/client image (independent of the SUT ref). Build context: antithesis/test.
FROM python:3.11-slim-bookworm
ENV NO_COLOR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt /opt/antithesis/requirements.txt
RUN pip install --no-cache-dir -r /opt/antithesis/requirements.txt
COPY setup/ /opt/antithesis/setup/
COPY v1/ /opt/antithesis/test/v1/
# Python is catalog-only in Antithesis: expose the workload code for assertion cataloging.
RUN mkdir -p /opt/antithesis/catalog /ledger \
 && ln -s /opt/antithesis/test /opt/antithesis/catalog/workload
ENTRYPOINT ["/opt/antithesis/setup/entrypoint.sh"]
