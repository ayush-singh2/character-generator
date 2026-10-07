# syntax=docker/dockerfile:1
#
# Single-service deploy for Render (bb-illustrator): build the Vite React SPA in
# a Node stage, then serve it alongside the FastAPI API from a Python stage.
# The backend (server/app.py) mounts the built dist/ and falls back to
# index.html for client-side routes — so one web service serves UI + API.

# ----- Stage 1: build the Vite React SPA ------------------------------------ #
FROM node:24-slim AS web
WORKDIR /web
# Copy manifests first so `npm ci` is cached until deps actually change.
COPY frontend/frontend/blue-balloon/package.json frontend/frontend/blue-balloon/package-lock.json ./
RUN npm ci
COPY frontend/frontend/blue-balloon/ ./
RUN npm run build          # -> /web/dist

# ----- Stage 2: Python runtime (API + static SPA) --------------------------- #
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000
WORKDIR /app

# Native libs Pillow / pdfplumber load at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Python deps first (cached layer): root pipeline deps + backend deps.
COPY requirements.txt ./requirements.txt
COPY server/requirements.txt ./server/requirements.txt
RUN pip install -r requirements.txt -r server/requirements.txt

# Application code (server + the generation pipeline it shells out to).
COPY pipeline/ ./pipeline/
COPY server/ ./server/
COPY serve_app.sh ./serve_app.sh

# The built SPA, placed exactly where server/app.py's SPA_DIR expects it
# (REPO = /app  ->  /app/frontend/frontend/blue-balloon/dist).
COPY --from=web /web/dist/ ./frontend/frontend/blue-balloon/dist/

# Render injects $PORT; bind 0.0.0.0 so the platform can reach us.
CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
