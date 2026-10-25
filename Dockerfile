# The public site (docs/DEPLOY.md): scripts/serve_dashboard.py over the Astro
# build. data/, portraits/ and dashboard/ (the person index) are mounted, not
# baked in; compose.sample.yml has the mounts, the network and the health
# check.

FROM node:22-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# Only for building the index inside the container
# (`docker compose run --rm vrk-app python scripts/build_person_index.py`);
# serving needs nothing beyond the standard library. brotli writes the .br
# copies of the index.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt brotli==1.1.0
COPY scraper/ scraper/
COPY scripts/ scripts/
COPY docs/ docs/
COPY --from=frontend /src/frontend/dist frontend/dist
RUN useradd --uid 1000 --user-group --no-create-home --shell /usr/sbin/nologin vrk
USER vrk

ENV VRK_BIND=0.0.0.0 VRK_PORT=8080
EXPOSE 8080
CMD ["python", "scripts/serve_dashboard.py"]
