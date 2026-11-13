# The site as one image (PLAN step 11, S8): the built frontend, the app and the release it
# serves. Build from a checkout that has cache/ filled (gamedata pictures, the saved card
# art, a release from `wfb build-all`); none of it is in git (T2), so the image is built
# where the release is and pushed only to a private registry:
#   podman build --format docker --build-arg RELEASE="$(cat cache/releases/current)" -t warframebuild .
# Run read-only, as in README "Run the container" (--format docker keeps the HEALTHCHECK).
# Base images are pinned by digest (same as .gitlab-ci.yml; Renovate keeps them current).

FROM node:24.21.0-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS python
ARG UV_VERSION=0.13.7
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
RUN uv sync --locked --no-dev --no-install-project
COPY app/ app/
RUN uv sync --locked --no-dev && .venv/bin/python -m compileall -q app

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ARG RELEASE
RUN test -n "${RELEASE}" || (echo "--build-arg RELEASE=<id> is required" >&2; exit 1)
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin wfb
WORKDIR /app
# Everything stays root-owned: the server only reads.
COPY --from=python /app /app
COPY --from=web /web/dist web/dist
COPY gamedata/ gamedata/
COPY cache/img/ cache/img/
COPY cache/raw/wiki/img/ cache/raw/wiki/img/
COPY cache/releases/${RELEASE}/ cache/releases/${RELEASE}/
RUN test "$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' \
        "cache/releases/${RELEASE}/manifest.json")" = "${RELEASE}" \
    && printf '%s\n' "${RELEASE}" > cache/releases/current
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"]
ENTRYPOINT ["wfb", "serve", "--host", "0.0.0.0", "--port", "8000"]
