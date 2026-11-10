FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
ENV NWS_USER_AGENT="weather-alerts-mcp-server (your-email@example.com)"
EXPOSE 8000
# 0.0.0.0 is needed inside a container; publish the port only to localhost: docker run -p 127.0.0.1:8000:8000 ...
CMD ["uv", "run", "--no-dev", "weather-alerts-mcp-server", "--transport", "streamable-http", "--host", "0.0.0.0"]
