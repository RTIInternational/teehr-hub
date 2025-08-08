# Install TEEHR in the Pangeo Image
 # 2025.05.22
FROM pangeo/base-notebook:2025.05.22 

ARG IMAGE_TAG

USER root
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=${NB_PYTHON_PREFIX}/bin:$PATH

# Needed for apt-key to work -- Is this part needed?
RUN apt-get update -qq --yes > /dev/null && \
    apt-get install --yes -qq gnupg2 > /dev/null && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update \
    && apt-get install -y wget curl bzip2 libxtst6 libgtk-3-0 libx11-xcb-dev libdbus-glib-1-2 libxt6 libpci-dev libasound2 firefox openjdk-17-jdk git vim

# RUN conda install -y -c conda-forge nodejs
RUN mamba install -n ${CONDA_ENV} -y -c conda-forge nodejs selenium geckodriver awscli htop

RUN if [ "$IMAGE_TAG" = "dev" ]; then \
        echo "Building TEEHR dev version from main..."; \
        # Install latest from main.
        pip install git+https://github.com/RTIInternational/teehr.git@475-update-python-dependencies; \
    else \
        echo "Building TEEHR from specific tag..."; \
        # Install specific tag from pypi.
        pip install teehr==${IMAGE_TAG}; \
    fi
# RUN pip install duckdb spatialpandas easydev colormap colorcet hydrotools datashader
RUN pip install dask[distributed]


USER ${NB_USER}

WORKDIR /home/jovyan
