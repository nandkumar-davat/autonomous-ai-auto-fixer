FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies required for building some packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging files
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

# Install the application and its production dependencies
RUN pip wheel --no-deps --wheel-dir /app/wheels . && \
    pip wheel --no-deps --wheel-dir /app/wheels -r <(pipdeptree -p autofixer -f | grep '^[a-zA-Z]') || true
# Simplified installation for standard wheels
RUN pip install --no-cache-dir .

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv

# Run as non-root user
RUN groupadd -r autofixer && useradd -d /home/autofixer -r -g autofixer autofixer
USER autofixer

WORKDIR /home/autofixer/app

# Copy installed site-packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /app/src/ ./src/

# Configuration directory mapping
VOLUME ["/home/autofixer/app/config"]

# Run the CLI as the default entrypoint
ENTRYPOINT ["autofixer"]
CMD ["--mode", "dry-run"]
