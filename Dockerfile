# Toolchain for the skills in .agents/skills: Python, uv, DuckDB with its spatial extension,
# and the libraries the scripts and tests import.
# Build:  docker build -t geoai-skills .
# Run:    docker run --rm -it -v "$PWD":/work geoai-skills
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /usr/local/bin/

# Lighter than a conda stack: wheels bundle GDAL and PROJ. rasterio's wheel still needs libexpat.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# TabPFN, XGBoost, LightGBM and CatBoost are left out; add them per run with `uvx --with ...`.
RUN uv venv /opt/venv && VIRTUAL_ENV=/opt/venv uv pip install --no-cache \
    'duckdb>=1.5.5' numpy scipy scikit-learn pandas pyarrow statsmodels networkx \
    shapely rasterio esda libpysal pytest

ENV PATH=/opt/venv/bin:$PATH \
    UV_CACHE_DIR=/opt/uv-cache \
    HOME=/home/geo

# Warm the uvx cache so `uvx --from 'duckdb>=1.5.5' ...` in the docs also works offline,
# and install the DuckDB extensions the docs load.
RUN useradd --uid 1000 --create-home --home-dir /home/geo geo \
 && mkdir -p /opt/uv-cache /work && chown -R geo /opt/uv-cache /work
USER geo
RUN python -c "import duckdb; c = duckdb.connect(); c.sql('install spatial; install httpfs')" \
 && uvx --from 'duckdb>=1.5.5' python -c "import duckdb" \
 && chmod -R a+rwX /opt/uv-cache

WORKDIR /work
CMD ["bash"]
