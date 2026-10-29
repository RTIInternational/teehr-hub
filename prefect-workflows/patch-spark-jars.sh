#!/bin/sh
# Copy of teehr-cloud-core/spark/docker/patch-spark-jars.sh (the Spark executor
# image's) so driver and executors get the same jars. Keep the two in sync.
#
# Patch the jars bundled with Spark, which carry most of the image's fixable CVEs.
#
# Usage: patch-spark-jars.sh <spark jars dir>
#
# Spark runs against an Iceberg REST catalog, so the Hive/metastore stack (Hive,
# Derby, Thrift, ZooKeeper, legacy Jackson ASL), jline and the Scala Spark Connect
# REPL (connect-repl/) are unused and are removed. hive-storage-api stays because
# ORC depends on it. Netty, Jackson, Jersey, Bouncy Castle, aircompressor and
# snappy-java are swapped for later patch releases on the lines Spark ships;
# log4j has no fix on 2.24 so it moves to 2.25.
#
# Not fixable here: CVEs shaded inside hadoop-client-runtime, spark-core and
# parquet-jackson, which need Hadoop/Spark/Parquet upgrades.
# Re-check these versions whenever Spark is bumped.
set -eu

NETTY_VERSION=4.1.139.Final
JACKSON_VERSION=2.18.12
JERSEY_VERSION=3.0.18
LOG4J_VERSION=2.25.5
BCPROV_VERSION=1.86
AIRCOMPRESSOR_VERSION=2.0.3
SNAPPY_VERSION=1.1.10.12

MVN=https://repo1.maven.org/maven2

fetch() {
    curl -fsSL -o "$(basename "$1")" "$MVN/$1"
}

cd "$1"

rm -rf connect-repl
find . -name '*.jar' \( -name 'hive-*' ! -name 'hive-storage-api-*' -o -name 'spark-hive*' \
    -o -name 'derby*' -o -name 'libthrift-*' -o -name 'zookeeper*' -o -name 'jackson-*-asl-*' \
    -o -name 'jline-*' \) -print -delete

old_netty=$(ls netty-common-*.jar | sed 's/^netty-common-\(.*\)\.jar$/\1/')
for f in netty-*-"$old_netty"*.jar; do
    artifact=${f%%-"$old_netty"*}
    suffix=${f#"$artifact"-"$old_netty"}
    fetch "io/netty/$artifact/$NETTY_VERSION/$artifact-$NETTY_VERSION$suffix"
    rm "$f"
done

for f in jackson-*-2.*.jar; do
    artifact=${f%-2.*.jar}
    case "$artifact" in
        jackson-core|jackson-databind|jackson-annotations) group=core ;;
        jackson-dataformat-*) group=dataformat ;;
        jackson-datatype-*) group=datatype ;;
        jackson-module-*) group=module ;;
        *) continue ;;
    esac
    fetch "com/fasterxml/jackson/$group/$artifact/$JACKSON_VERSION/$artifact-$JACKSON_VERSION.jar"
    rm "$f"
done

for f in jersey-*.jar; do
    artifact=${f%-[0-9]*.jar}
    case "$artifact" in
        jersey-container-*) group=containers ;;
        jersey-hk2) group=inject ;;
        *) group=core ;;
    esac
    fetch "org/glassfish/jersey/$group/$artifact/$JERSEY_VERSION/$artifact-$JERSEY_VERSION.jar"
    rm "$f"
done

for f in log4j-*.jar; do
    artifact=${f%-[0-9]*.jar}
    fetch "org/apache/logging/log4j/$artifact/$LOG4J_VERSION/$artifact-$LOG4J_VERSION.jar"
    rm "$f"
done

rm bcprov-jdk18on-*.jar aircompressor-*.jar snappy-java-*.jar
fetch "org/bouncycastle/bcprov-jdk18on/$BCPROV_VERSION/bcprov-jdk18on-$BCPROV_VERSION.jar"
fetch "io/airlift/aircompressor/$AIRCOMPRESSOR_VERSION/aircompressor-$AIRCOMPRESSOR_VERSION.jar"
fetch "org/xerial/snappy/snappy-java/$SNAPPY_VERSION/snappy-java-$SNAPPY_VERSION.jar"
