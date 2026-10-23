# P6b throwaway build check (not the P5 harness Dockerfile).
FROM eclipse-temurin:11-jdk
ARG SUT_REF=c9ffe116457384200851939e3687f81c00015e02
ARG ANT_VERSION=1.10.14
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://archive.apache.org/dist/ant/binaries/apache-ant-${ANT_VERSION}-bin.tar.gz \
    | tar -xz -C /opt && ln -s /opt/apache-ant-${ANT_VERSION}/bin/ant /usr/local/bin/ant
WORKDIR /src
RUN git clone --filter=blob:none https://github.com/apache/cassandra.git cassandra \
 && cd cassandra && git checkout ${SUT_REF} \
 && git submodule update --init modules/accord \
 && git -C modules/accord rev-parse HEAD
WORKDIR /src/cassandra
RUN ant -Dno-checkstyle=true -Drat.skip=true jar \
 && ls -la build/*.jar build/lib/jars/cassandra-accord-*.jar
