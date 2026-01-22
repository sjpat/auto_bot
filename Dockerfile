# ============================================
# Stage 1: Builder - Install dependencies
# ============================================
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libssl-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ============================================
# Stage 2: Runtime - Final image
# ============================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash botuser

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=botuser:botuser . .

# Create directories
RUN mkdir -p logs && \
    chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Health check (checks if bot is running)
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import os; from datetime import datetime, timedelta; \
        log_file='logs/bot.log'; \
        exit(0 if os.path.exists(log_file) and \
        (datetime.now() - datetime.fromtimestamp(os.path.getmtime(log_file))) < timedelta(minutes=5) \
        else 1)"

# Default command (can be overridden)
CMD ["python", "main.py", "kalshi"]
