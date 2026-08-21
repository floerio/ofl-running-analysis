# Deployment

The AI Data Assistant is deployed as a Streamlit web app, containerized with Docker,
and served over HTTPS via a dedicated Traefik reverse proxy on a shared Hetzner VPS. The Traefik
instance is standalone and shared only in the sense that other projects can also connect to it —
it is not tied to any single app.

**Live URL:** https://ofl-running.duckdns.org
**Protected by password** (see `APP_PASSWORD` below).

---

## Infrastructure Overview

| Item | Value |
|---|---|
| Server | Hetzner VPS, SSH alias `ht2-cmd` (`46.224.167.17`) |
| SSH user | `peter` |
| App directory on server | `~/apps/ofl-running-analysis` |
| Domain | `ofl-running.duckdns.org` (free DuckDNS subdomain → server IP) |
| Container image | `ghcr.io/floerio/ofl-running-analysis:latest` |
| Reverse proxy | Traefik `latest`, container `traefik`, standalone stack at `~/traefik/` on `ht2-cmd` (owned by `peter`, dedicated to routing — no app bundled in) |
| TLS | Automatic via Let's Encrypt (HTTP-01 challenge, handled by Traefik) |
| Container runtime | Docker, orchestrated with `docker compose` (v2 plugin, v5.5.0, installed per-user at `~/.docker/cli-plugins/docker-compose` — no root needed) |
| Restart policy | `unless-stopped` (auto-restarts on crash/reboot) for both the app and Traefik |

### Why Traefik instead of a fresh nginx setup?

Traefik auto-discovers containers via the Docker socket and requests/renews Let's Encrypt certs
automatically based on container labels — no manual nginx/certbot config needed. Any container that
joins the shared `proxy` Docker network and carries the right `traefik.*` labels gets routed and
TLS-terminated automatically.

Our app's container joins the `proxy` network and exposes itself to Traefik via Docker labels
(see `docker-compose.yml` below). This required no `sudo`/root access — only Docker group
membership (`peter` is in the `docker` group), since controlling the Docker daemon is equivalent
to root-level control of containers.

### The dedicated Traefik instance (`~/traefik/`)

```yaml
# ~/traefik/docker-compose.yml (on ht2-cmd, owned by peter)
services:
  traefik:
    image: traefik:latest
    container_name: traefik
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=ofl@posteo.de"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./letsencrypt:/letsencrypt"
    networks:
      - proxy
    restart: unless-stopped

networks:
  proxy:
    external: true
```

This instance is intentionally minimal and app-agnostic — **any project** on the box can use it,
simply by:
1. Joining the external `proxy` Docker network.
2. Adding `traefik.enable=true` plus routing labels (see example below).

No changes to this Traefik config are needed to add new apps.

---

## Files Added for Deployment

| File | Purpose |
|---|---|
| `Dockerfile` | Builds the app image (Python 3.12-slim + dependencies + app code) |
| `docker-compose.yml` | Defines the `app` service, pulls image from GHCR, Traefik routing labels, and the external `proxy` network |
| `.dockerignore` | Excludes local dev artifacts (`.venv`, `.git`, logs, cached parquet, etc.) from the build context |
| `deploy.sh` | One-command deploy: build image on Mac → push to GHCR → pull & restart on VPS |
| `.env` (server-only, **not in git**) | Production secrets: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `APP_PASSWORD`, `DOMAIN` |
| `prompt_manager.py` | **NEW** - Prompt loading, saving, and rendering |
| `pages/config.py` | **NEW** - Configuration page (model selector + data upload/download + prompt editor) |
| `prompts/` | **NEW** - AI prompt files (Markdown format, user overrides in `prompts/user/`) |

### `docker-compose.yml` Traefik labels

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.docker.network=proxy"
  - "traefik.http.routers.ofl-running-analysis.rule=Host(`${DOMAIN}`)"
  - "traefik.http.routers.ofl-running-analysis.entrypoints=websecure"
  - "traefik.http.routers.ofl-running-analysis.tls.certresolver=letsencrypt"
  - "traefik.http.services.ofl-running-analysis.loadbalancer.server.port=8501"
```

`${DOMAIN}` is read from the server's `.env` file.

---

## Security

- **Password gate**: the app requires a password (`APP_PASSWORD` env var, checked in `app.py`)
  before granting access. This is essential because the app calls the LLM API with a real
  API key on every question — an unprotected public instance would allow anyone to rack up
  API costs.
- **Secrets never committed to git**: `.env` lives only on the server (`~/apps/ofl-running-analysis/.env`,
  file mode `600`), separate from the local dev `.env`.
- **HTTPS everywhere**: Traefik terminates TLS and redirects HTTP → HTTPS.

### `.env` on the VPS
```
OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://api.mistral.ai/v1
OPENAI_MODEL=mistral-medium-latest
APP_PASSWORD=<your-password>
DOMAIN=ofl-running.duckdns.org
```

To edit:
```bash
ssh ht2-cmd "nano ~/apps/ofl-running-analysis/.env"
```

> ⚠️ Make sure each variable is on its own line with no trailing spaces — malformed `.env` files
> (e.g. values accidentally merged across lines) will cause authentication errors at runtime.

---

## Initial Setup (already done — for reference)

1. Confirmed SSH access as `peter@ht2-cmd` (Docker group member, no root needed).
2. Registered `ofl-running.duckdns.org` on [duckdns.org](https://www.duckdns.org), pointed at `46.224.167.17`.
3. Set up the dedicated Traefik instance at `~/traefik/` (see above) on the `proxy` network.
4. Created `~/apps/ofl-running-analysis/` and the production `.env` directly on the server, `chmod 600`.
5. Authenticated Docker to GHCR on both Mac and VPS (see below).
6. Ran `./deploy.sh` for the first time to build, push, and start the container.
7. Verified: `curl -I https://ofl-running.duckdns.org/` → `HTTP/2 200`, valid Let's Encrypt cert.

---

## Day-to-Day Operations

All commands run on the server (`ssh ht2-cmd`, then `cd ~/apps/ofl-running-analysis`):

```bash
docker compose logs -f          # tail live logs
docker compose restart          # restart the app (e.g. after config change)
docker compose ps               # check status
docker compose down             # stop and remove the container
```

### Deploying code changes

From your local machine, in the project directory:

```bash
cd /Users/iteratec/Projects/ofl-running-analysis
./deploy.sh
```

This single script:
1. Builds the image locally on your Mac (`--platform linux/amd64` for VPS compatibility), using Docker's local layer cache for speed
2. Pushes it to GitHub Container Registry (`ghcr.io/floerio/ofl-running-analysis:latest`)
3. SSHes into the VPS, pulls the new image, and restarts the container

The VPS does not need the source code or build tools — it only runs the pre-built image.

> **GHCR authentication:** you need to authenticate Docker to GHCR once on your Mac:
> ```bash
> echo YOUR_GITHUB_PAT | docker login ghcr.io -u floerio --password-stdin
> ```
> Create a PAT at https://github.com/settings/tokens with `write:packages` scope.
>
> On the VPS, authenticate once too (read-only is enough):
> ```bash
> ssh ht2-cmd
> echo YOUR_GITHUB_PAT | docker login ghcr.io -u floerio --password-stdin
> ```

> **Note:** `docker buildx` is not available in this environment. The script uses the legacy
> `docker build` with local layer cache. Unchanged layers (base image, pip installs) are reused
> automatically between builds on the same machine.

> **Resolved issue (historical):** early deployments used the old standalone `docker-compose`
> v1.29.2 binary, which failed to *recreate* an existing container against newer Docker Engine
> image formats (`KeyError: 'ContainerConfig'`). Fixed by installing the `docker compose` v2 plugin
> per-user (no root required):
> ```bash
> mkdir -p ~/.docker/cli-plugins
> curl -sSL https://github.com/docker/compose/releases/download/v5.5.0/docker-compose-linux-x86_64 \
>   -o ~/.docker/cli-plugins/docker-compose
> chmod +x ~/.docker/cli-plugins/docker-compose
> ```
> Use `docker compose` (no hyphen) going forward — it doesn't have this bug.

Note: `data.csv` is baked into the Docker image (`COPY data.csv ./` in the `Dockerfile`). If the
dataset is updated, it will be picked up automatically on the next `./deploy.sh`.
`data.parquet` is regenerated inside the container on first run.

### Updating secrets (API key, password, etc.)

```bash
ssh ht2-cmd
nano ~/apps/ofl-running-analysis/.env
cd ~/apps/ofl-running-analysis && docker compose up -d   # recreates container with new env
```

### Certificate renewal

Handled automatically by Traefik — no action needed. Certs are stored in
`~/traefik/letsencrypt/acme.json` on the host (`peter`-owned, mode `600`, shared across all
projects routed through this Traefik instance).

---

## Troubleshooting

### Site unreachable (connection refused on 443), but the app container is running

The VPS rebooted and the Traefik container didn't come back up.

**Check:**
```bash
ssh ht2-cmd "docker ps -a"          # look for the `traefik` container as Exited
ssh ht2-cmd "uptime"                # low uptime = recent reboot
```

**Fix:**
```bash
ssh ht2-cmd "cd ~/traefik && docker compose up -d"
```

The dedicated `~/traefik/` instance has `restart: unless-stopped`, so this should rarely happen.

### Model list shows only one model / wrong models

The `OPENAI_BASE_URL` in the VPS `.env` is missing or incorrect. The app fetches available models
live from the configured provider — if `OPENAI_BASE_URL` is not set, it falls back to
`api.openai.com` which won't have the expected models.

**Check:**
```bash
ssh ht2-cmd "cat ~/apps/ofl-running-analysis/.env"
```

**Fix:** ensure `OPENAI_BASE_URL` is set correctly and each line has no trailing spaces or merged values.

---

## Adding Another Project to This Traefik Instance

Any new project on `ht2-cmd` can be routed through the same `~/traefik/` instance without touching
its config. In that project's `docker-compose.yml`:

```yaml
services:
  app:
    # ... build/image/etc ...
    networks:
      - proxy
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=proxy"
      - "traefik.http.routers.<unique-name>.rule=Host(`<your-domain>`)"
      - "traefik.http.routers.<unique-name>.entrypoints=websecure"
      - "traefik.http.routers.<unique-name>.tls.certresolver=letsencrypt"
      - "traefik.http.services.<unique-name>.loadbalancer.server.port=<container-port>"

networks:
  proxy:
    external: true
```

Make sure `<your-domain>` has a DNS A record pointing at `46.224.167.17` before starting the
container, otherwise the Let's Encrypt HTTP-01 challenge will fail.

---

## Known Limitations / Future Improvements

- No automated CI/CD — deployment is manual (`./deploy.sh`). Could be automated with GitHub Actions (build & push on every push to `main`, then trigger a VPS pull via SSH).
- No per-user rate limiting on API calls — the password gate prevents unauthenticated access, but a single authenticated user could still run up API costs with many questions.
- No log rotation configured for `app.log` inside the container.
