# Multi-stage Dockerfile for LLM Council
# Production-ready with security best practices

# ============================================
# Stage 1: Build frontend
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --silent

# Copy frontend source
COPY frontend/ ./

# Build frontend for production
RUN npm run build

# ============================================
# Stage 2: Python backend
# ============================================
FROM python:3.12-slim AS backend

# Build arguments
ARG VERSION=1.0.0
ARG BUILD_DATE
ARG GIT_COMMIT

# Labels for image metadata
LABEL org.opencontainers.image.title="LLM Council" \
      org.opencontainers.image.description="Multi-LLM deliberation system" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.source="https://github.com/your-org/llm-council"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Application defaults
    PORT=8001 \
    HOST=0.0.0.0 \
    LOG_LEVEL=INFO \
    LOG_FORMAT=json

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 council \
    && useradd --uid 1000 --gid council --shell /bin/bash --create-home council

# Copy Python requirements
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install ".[production]"

# Copy backend code
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create data directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/backups \
    && chown -R council:council /app

# Switch to non-root user
USER council

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the application
CMD ["python", "-m", "backend.main"]
