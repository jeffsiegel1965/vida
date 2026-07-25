# Vida Wallet — Docker image for agent runners
#
# Build:
#   docker build -t vida-wallet:0.2.0 .
#
# Run (interactive):
#   docker run -it --rm \
#     -v $(pwd)/wallet:/wallet \
#     -e VIDA_OWNER_ADDRESS=kaspa:... \
#     vida-wallet:0.2.0
#
# Run (agent session):
#   docker run -d --name vida-agent \
#     -v $(pwd)/session.json:/session.json \
#     -e VIDA_SESSION=/session.json \
#     vida-wallet:0.2.0 \
#     python -m vida.agents.orchestrator "Check covenant status"

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="Vida Wallet"
LABEL org.opencontainers.image.description="Session-gated agent wallet for Kaspa and Bittensor"
LABEL org.opencontainers.image.url="https://github.com/jeffsiegel1965/vida"
LABEL org.opencontainers.image.version="0.2.0"

# ── System dependencies ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ──
WORKDIR /app

# Copy dependency files first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install optional pqcrypto (may fail on some platforms — graceful fallback)
RUN pip install --no-cache-dir pqcrypto 2>/dev/null || true
RUN pip install --no-cache-dir pytest uvicorn fastapi jinja2 2>/dev/null || true

# Copy application code
COPY vida/ vida/
COPY scripts/ scripts/
COPY tests/ tests/
COPY pyproject.toml README.md LICENSE ./

# Install Vida package
RUN pip install --no-cache-dir -e .

# ── Runtime ──
# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash vida && \
    chown -R vida:vida /app
USER vida

# Create directories for persistent data
RUN mkdir -p /home/vida/.vida/sessions /home/vida/.vida/logs /home/vida/.vida/memory

# Expose admin dashboard port
EXPOSE 8082

# Default: admin dashboard
CMD ["python", "scripts/vida_admin.py"]

# Alternative entrypoints:
# 1. Agent loop:
#    CMD ["python", "-m", "vida.agents.orchestrator", "Your goal here"]
#
# 2. MCP server:
#    CMD ["python", "scripts/vida_mcp_server.py"]
#
# 3. Shell for debugging:
#    CMD ["/bin/bash"]
