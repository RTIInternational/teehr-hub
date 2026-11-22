# The v1 flows' image (ADR-0019 in teehr-cloud-core): Prefect and teehr-core's warehouse
# writer and builders (PyIceberg, DuckDB). No legacy teehr, Spark or JVM.
FROM prefecthq/prefect:3.9.0-python3.12

# A teehr-core commit (an archive URL: the image has no git); project.garden.yml's
# teehrCoreVersion.
ARG TEEHR_CORE_VERSION

RUN pip install --no-cache-dir \
    "teehr-core[engine,iceberg] @ https://github.com/RTIInternational/teehr-core/archive/${TEEHR_CORE_VERSION}.zip"

RUN groupadd -g 1000 prefect && useradd -u 1000 -g 1000 -m -d /home/prefect prefect \
    && mkdir -p /teehr-v1 && chown -R prefect:prefect /teehr-v1
COPY --chown=prefect:prefect prefect-local.yaml prefect-remote.yaml /teehr-v1/
COPY --chown=prefect:prefect flows/ /teehr-v1/flows/

WORKDIR /teehr-v1
ENV PYTHONPATH=/teehr-v1
USER prefect
