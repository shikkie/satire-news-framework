# Multi-stage: build SPA into api/static, then run Flask/gunicorn
FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
COPY package.json package-lock.json ./
# prepare installs git hooks — skip in the image
RUN npm ci --ignore-scripts
COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
COPY scripts ./scripts
COPY articles ./articles
COPY ads ./ads
# Build SPA into a temporary outDir (not docs/) so Docker image is self-contained
ENV VITE_OUT_DIR=/frontend/dist
RUN npm run articles:build && npm run ads:build \
    && npx vite build --outDir /frontend/dist --emptyOutDir \
    && node scripts/inject-og-html.mjs || true

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY api/app /app/app
COPY api/scripts /app/scripts
COPY api/wsgi.py /app/wsgi.py
COPY --from=frontend /frontend/dist /app/static

# Seed paths used by onboard (compose also mounts live folders)
RUN mkdir -p /app/seed/articles /app/seed/ads

EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "--timeout", "120", "wsgi:app"]
