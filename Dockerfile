# Stage 1: Build Next.js frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend runtime
FROM python:3.12-slim AS final
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install backend dependencies (no dev extras, use lockfile exactly)
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --no-dev --frozen

# Copy backend source
COPY backend/ ./backend/

# Copy frontend static export produced by Stage 1
COPY --from=frontend-builder /app/frontend/out/ ./static/

# Create db directory for SQLite volume mount
RUN mkdir -p /app/db

EXPOSE 8000

ENV PYTHONPATH=/app/backend
ENV STATIC_DIR=/app/static
ENV DATABASE_URL=/app/db/finally.db

CMD ["/app/backend/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
