# The Examiner runs in its own container so the sealed exam never touches the
# builders' disk. Build from the repo root:
#   docker compose -f docker/compose.yaml up --build examiner
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
COPY src ./src
COPY specs ./specs
RUN uv pip install --system --no-cache . \
 && python -m playwright install --with-deps chromium

ENV ONSEN_HOME=/data/onsen \
    ONSEN_SPECS_DIR=/app/specs \
    ONSEN_AGENT_CONFIG=/run/secrets/agent_config.yaml \
    ONSEN_REVEAL_DIR=/data/revealed

VOLUME ["/data/onsen"]
ENTRYPOINT ["onsen-examiner"]
