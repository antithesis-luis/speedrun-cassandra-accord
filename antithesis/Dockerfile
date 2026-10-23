# boost: pinned-ref SUT image for Apache Cassandra + Accord.
# One Dockerfile builds any ref; only build args change (SUT_REF, PATCH_SET).
# Build context: antithesis/ (so patches/ and sut/ are reachable).
# Source is cloned inside the build (never COPYed from the build context).
ARG TOOLCHAIN_IMAGE=eclipse-temurin:11-jdk
ARG RUNTIME_IMAGE=eclipse-temurin:11-jre

FROM ${TOOLCHAIN_IMAGE} AS build
ARG SUT_REPO=https://github.com/apache/cassandra.git
ARG SUT_REF
ARG PATCH_SET=common
ARG ANT_VERSION=1.10.14
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://archive.apache.org/dist/ant/binaries/apache-ant-${ANT_VERSION}-bin.tar.gz \
    | tar -xz -C /opt && ln -s /opt/apache-ant-${ANT_VERSION}/bin/ant /usr/local/bin/ant
RUN test -n "${SUT_REF}" \
 && git clone --filter=blob:none "${SUT_REPO}" /src \
 && git -C /src checkout --detach "${SUT_REF}" \
 && git -C /src submodule update --init modules/accord \
 && echo "cassandra=$(git -C /src rev-parse HEAD) accord=$(git -C /src/modules/accord rev-parse HEAD)"
COPY patches/ /patches/
RUN set -e; if ls /patches/${PATCH_SET}/*.patch >/dev/null 2>&1; then \
      for p in /patches/${PATCH_SET}/*.patch; do echo "applying $p"; git -C /src apply --whitespace=nowarn "$p"; done; \
    fi
WORKDIR /src
# _artifacts-init = jar + dist layout in build/dist (bin/, conf/, lib/ with all runtime deps).
RUN ant -Dno-checkstyle=true -Drat.skip=true _artifacts-init \
 && ls -la build/dist/lib/apache-cassandra-*.jar build/dist/lib/cassandra-accord-*.jar \
           build/dist/lib/sdk-*.jar build/dist/lib/ffi-*.jar
# Split the SUT's own jars (Cassandra + Accord) out of lib/ so only they are instrumented.
RUN mkdir -p /out/cassandra/sut \
 && cp -a build/dist/bin build/dist/conf build/dist/lib /out/cassandra/ \
 && rm -f /out/cassandra/lib/*-sources.jar /out/cassandra/lib/*-javadoc.jar \
 && mv /out/cassandra/lib/apache-cassandra-*.jar /out/cassandra/lib/cassandra-accord-*.jar /out/cassandra/sut/ \
 && ls -la /out/cassandra/sut

FROM ${RUNTIME_IMAGE}
ARG SUT_REF
ENV NO_COLOR=1 \
    BOOST_SUT_REF=${SUT_REF} \
    CASSANDRA_HOME=/opt/cassandra \
    CASSANDRA_CONF=/opt/cassandra/conf \
    PATH=/opt/cassandra-antithesis/bin:/opt/cassandra/bin:${PATH}
RUN apt-get update && apt-get install -y --no-install-recommends procps iproute2 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/cassandra/ /opt/cassandra/
# Config: the ref's stock cassandra.yaml with the harness overrides appended (later keys win;
# cassandra.allow_duplicate_config_keys defaults to true). __HOSTNAME__ is filled in at start.
COPY sut/cassandra-overrides.yaml /opt/cassandra-antithesis/cassandra-overrides.yaml
COPY sut/logback.xml /opt/cassandra/conf/logback.xml
COPY sut/entrypoint.sh sut/helper-cms-bootstrap.sh /opt/cassandra-antithesis/
COPY sut/nodetool /opt/cassandra-antithesis/bin/nodetool
# boost hunt variants: CONFIG_VARIANT=<name> applies sut/variants/<name>.sed to the rendered template
# (default: none, so the default build is unchanged). Only documented cassandra.yaml settings change.
ARG CONFIG_VARIANT=default
COPY sut/variants/ /opt/cassandra-antithesis/variants/
RUN cat /opt/cassandra/conf/cassandra.yaml /opt/cassandra-antithesis/cassandra-overrides.yaml \
      > /opt/cassandra-antithesis/cassandra.yaml.template \
 && if [ -f /opt/cassandra-antithesis/variants/${CONFIG_VARIANT}.sed ]; then sed -i -f /opt/cassandra-antithesis/variants/${CONFIG_VARIANT}.sed /opt/cassandra-antithesis/cassandra.yaml.template; fi \
 && chmod +x /opt/cassandra-antithesis/*.sh /opt/cassandra-antithesis/bin/nodetool /opt/cassandra/bin/* \
 && mkdir -p /var/lib/cassandra /var/log/cassandra /opt/antithesis/catalog \
 && ln -s /var/lib/cassandra /opt/cassandra/data \
 && ln -s /opt/cassandra/sut /opt/antithesis/catalog/cassandra
VOLUME ["/var/lib/cassandra"]
EXPOSE 7000 7199 9042
ENTRYPOINT ["/opt/cassandra-antithesis/entrypoint.sh"]
