# TripWeaver backend + MCP servers, packaged as a single container.
# The FastAPI process (main.py) spawns the two MCP child processes on
# startup and terminates them on shutdown, so one container runs the whole
# Python side of TripWeaver.

FROM python:3.12-slim

# Small, deterministic layer for pip
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: curl for healthcheck, build-essential for occasional wheels.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first — faster rebuilds when only source changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the rest of the app.
COPY main.py entity.py ./
COPY agents/ ./agents/
COPY mcp_servers/ ./mcp_servers/

# Backend listens on 8000. MCP subprocesses use 8001/8002 internally.
EXPOSE 8000

# `main.py` handles MCP subprocess spawn/shutdown internally.
CMD ["python", "main.py"]
