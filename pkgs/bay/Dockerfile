# ============================================
# Stage 1: Build frontend (Vue.js Dashboard)
# ============================================
FROM node:22-alpine AS frontend-builder

WORKDIR /app/dashboard

# Copy package files first for better caching
COPY dashboard/package.json dashboard/package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY dashboard/ ./

# Build for production
RUN npm run build

# ============================================
# Stage 2: Build Python dependencies
# ============================================
FROM python:3.11-slim AS python-builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ============================================
# Stage 3: Final image with Nginx + Python
# ============================================
FROM python:3.11-slim

# Install Nginx and curl (for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python wheels and install
COPY --from=python-builder /app/wheels /app/wheels
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/app/wheels -r requirements.txt \
    && rm -rf /app/wheels

# Copy Python application files
COPY pyproject.toml alembic.ini run.py ./
COPY app/ ./app/
COPY alembic/ ./alembic/

# Create data directory
RUN mkdir -p /app/data

# Copy built frontend to Nginx html directory
COPY --from=frontend-builder /app/dashboard/dist /usr/share/nginx/html

# Copy Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy and prepare entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose ports:
# - 8156: API (Python backend, can be exposed publicly)
# - 8157: Dashboard (Nginx, can be hidden behind NAT)
EXPOSE 8156 8157

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8157/nginx-health && curl -f http://localhost:8156/health || exit 1

# Start both services
ENTRYPOINT ["/docker-entrypoint.sh"]
