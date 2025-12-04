# syntax=docker/dockerfile:1

FROM python:3.11-slim AS python-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ------------------------
# Contract extractor image
# ------------------------
FROM python-base AS contract_extractor
WORKDIR /opt/app

COPY services/contract_extractor/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /tmp/requirements.txt

COPY services/contract_extractor/app /opt/app/app

EXPOSE 8085
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8085"]

# --------------
# AI economizer
# --------------
FROM python-base AS ai_econom
WORKDIR /app

COPY services/ai_econom/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY services/ai_econom /app

EXPOSE 10000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]

# ---------
# AI legal
# ---------
FROM python-base AS ai_legal
WORKDIR /app

COPY services/ai_legal/app/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY services/ai_legal/app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# -----------------
# Document slicer
# -----------------
FROM python-base AS document_slicer
WORKDIR /app

COPY services/document_slicer/app/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY services/document_slicer/static /app/static
COPY services/document_slicer/app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------
# Admin panel (frontend)
# ---------------------
FROM node:20-alpine AS admin_panel_build
WORKDIR /app

ARG VITE_SLICER_API_BASE_URL
ARG VITE_AI_LEGAL_API_BASE_URL
ENV VITE_SLICER_API_BASE_URL=${VITE_SLICER_API_BASE_URL}
ENV VITE_AI_LEGAL_API_BASE_URL=${VITE_AI_LEGAL_API_BASE_URL}

COPY services/admin-panel/package.json services/admin-panel/package-lock.json* services/admin-panel/pnpm-lock.yaml* services/admin-panel/yarn.lock* ./
RUN npm ci || yarn install --frozen-lockfile || (npm install -g pnpm && pnpm install)

COPY services/admin-panel/ ./
RUN npm run build

FROM nginx:1.27-alpine AS admin-panel
COPY --from=admin_panel_build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
