FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends nftables \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY portalctl ./portalctl
RUN uv pip install --system --no-cache .

ENTRYPOINT ["portalctl"]
CMD ["watch"]
