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
| Server | Hetzner VPS, SSH alias `ht2` (`46.224.167.17`) |
| SSH user | `peter` |
| App directory on server | `~/apps/kn-query-assistant` |
| Domain | `ofl-running.duckdns.org` (free DuckDNS subdomain → server IP) |
| Reverse proxy | Traefik `latest`, container `traefik`, standalone stack at `~/traefik/` on `ht2` (owned by `peter`, dedicated to routing — no app bundled in) |
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
# ~/traefik/docker-compose.yml (on ht2, owned by peter)
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

#### History: replaced the `format-validator` bundled Traefik

The box previously ran a different Traefik instance bundled inside another project's compose file
(`/opt/docker/ai-based-mapping/format-validator/docker-compose.yml`, container
`format-validator_traefik_1`). That setup was replaced with the dedicated instance above because:
- It mixed an unrelated app's lifecycle with shared routing infrastructure.
- The intent going forward is to have **one** neutral Traefik instance that any project can attach
  to.

The old Traefik container and the `format-validator` app container were both stopped and set to
`restart: no` (so they won't come back on their own):
```bash
ssh ht2 "docker update --restart no format-validator_traefik_1 && docker stop format-validator_traefik_1"
```
They were left in place (not removed) in case that project still needs them later — they simply
no longer occupy ports 80/443.

There's also a separate, unrelated, unused root-owned compose file at `/opt/docker/docker-compose.yml`
with a similar Traefik definition — that one was **not** used (it's root-owned, `peter` can't edit
it without sudo, and it had a bug where the service never actually joined the `proxy` network).
The `~/traefik/` stack above is a corrected, peter-owned equivalent.

---

## Files Added for Deployment

| File | Purpose |
|---|---|
| `Dockerfile` | Builds the app image (Python 3.12-slim + dependencies + app code) |
| `docker-compose.yml` | Defines the `app` service, pulls image from GHCR, Traefik routing labels, and the external `proxy` network |
| `.dockerignore` | Excludes local dev artifacts (`.venv`, `.git`, logs, cached parquet, etc.) from the build context |
| `deploy.sh` | One-command deploy: build image on Mac → push to GHCR → pull & restart on VPS |
| `.env` (server-only, **not in git**) | Production secrets: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `APP_PASSWORD`, `DOMAIN` |

### `docker-compose.yml` Traefik labels

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.docker.network=proxy"
  - "traefik.http.routers.kn-query-assistant.rule=Host(`${DOMAIN}`)"
  - "traefik.http.routers.kn-query-assistant.entrypoints=websecure"
  - "traefik.http.routers.kn-query-assistant.tls.certresolver=letsencrypt"
  - "traefik.http.services.kn-query-assistant.loadbalancer.server.port=8501"
```

`${DOMAIN}` is read from the server's `.env` file.

---

## Security

- **Password gate**: the app requires a password (`APP_PASSWORD` env var, checked in `app.py`)
  before granting access. This is essential because the app calls the OpenAI API with a real
  API key on every question — an unprotected public instance would allow anyone to rack up
  API costs.
- **Secrets never committed to git**: `.env` lives only on the server (`~/apps/kn-query-assistant/.env`,
  file mode `600`), separate from the local dev `.env`. `.env_example` in the repo documents the
  required variables without real values.
- **HTTPS everywhere**: Traefik terminates TLS and (per its global config) redirects HTTP → HTTPS.

---

## Initial Setup (already done — for reference)

1. Confirmed SSH access as `peter@ht2` (Docker group member, no root needed).
2. Registered `ofl-running.duckdns.org` on [duckdns.org](https://www.duckdns.org), pointed at `46.224.167.17`.
3. Set up the dedicated Traefik instance at `~/traefik/` (see above) on the `proxy` network.
4. Copied the project to the server (excluding local dev artifacts):
   ```bash
   rsync -avz --exclude='.venv' --exclude='.git' --exclude='__pycache__' \
     --exclude='app.log' --exclude='test_chart_0.png' --exclude='data.parquet' \
     --exclude='scratchpad.txt' --exclude='.env' \
     ./ ht2:~/apps/kn-query-assistant/
   ```
5. Created the production `.env` directly on the server (real API key, `APP_PASSWORD`, `DOMAIN`),
   `chmod 600`.
6. Built and started the container:
   ```bash
   ssh ht2
   cd ~/apps/kn-query-assistant
   docker-compose up -d --build
   ```
7. Verified: `curl -I https://ofl-running.duckdns.org/` → `HTTP/2 200`, valid Let's Encrypt cert.

---

## Day-to-Day Operations

All commands run on the server (`ssh ht2`, then `cd ~/apps/kn-query-assistant`):

```bash
docker compose logs -f          # tail live logs
docker compose restart          # restart the app (e.g. after config change)
docker compose ps               # check status
docker compose down             # stop and remove the container
```

### Deploying code changes

From your local machine, in the project directory:

```bash
./deploy.sh
```

This single script:
1. Builds the image locally on your Mac (`--platform linux/amd64` for VPS compatibility)
2. Pushes it to GitHub Container Registry (`ghcr.io/floerio/kn-query-assistant:latest`)
3. SSHes into the VPS, pulls the new image, and restarts the container

The VPS no longer needs the source code or build tools — it only runs the pre-built image.

> **First-time setup:** you need to authenticate Docker to GHCR once on your Mac:
> ```bash
> echo YOUR_GITHUB_PAT | docker login ghcr.io -u floerio --password-stdin
> ```
> Create a PAT at https://github.com/settings/tokens with `write:packages` scope.
>
> On the VPS, authenticate once too (read-only is enough):
> ```bash
> ssh ht2
> echo YOUR_GITHUB_PAT | docker login ghcr.io -u floerio --password-stdin
> ```
>
> The `docker-compose.yml` on the VPS now uses `image: ghcr.io/floerio/kn-query-assistant:latest`
> instead of `build: .` — so no source code needs to be on the server.

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
dataset is updated, it will be picked up automatically on the next `docker compose up -d --build`
(no separate upload step needed beyond the rsync above). `data.parquet` is regenerated inside the
container on first run.

### Updating secrets (API key, password, etc.)

```bash
ssh ht2
nano ~/apps/kn-query-assistant/.env
cd ~/apps/kn-query-assistant && docker compose up -d   # recreates container with new env
```

### Certificate renewal

Handled automatically by Traefik — no action needed. Certs are stored in
`~/traefik/letsencrypt/acme.json` on the host (`peter`-owned, mode `600`, shared across all
projects routed through this Traefik instance).

---

## Troubleshooting

### Site unreachable (connection refused on 443), but the app container is running

This happened once (before the Traefik migration described above): the VPS rebooted, and the
then-shared **Traefik** container (`format-validator_traefik_1`, bundled inside another project)
did not come back up automatically, because it had restart policy `no`. Since Traefik is what
terminates TLS and routes traffic to our app, nothing was listening on ports 80/443 even though
`kn-query-assistant` itself was healthy (it has `restart: unless-stopped` and came back up fine on
its own).

**Check:**
```bash
ssh ht2 "docker ps -a"          # look for the `traefik` container as Exited
ssh ht2 "uptime"                # low uptime = recent reboot
```

**Fix:**
```bash
ssh ht2 "cd ~/traefik && docker compose up -d"
```

The dedicated `~/traefik/` instance now has `restart: unless-stopped`, so this class of issue
should no longer happen — but if Traefik is ever manually stopped and the box reboots before it's
started again, `docker start traefik` (or `docker compose up -d` as above) brings it back.

---

## Adding Another Project to This Traefik Instance

Any new project on `ht2` can be routed through the same `~/traefik/` instance without touching
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
- No per-user rate limiting on OpenAI calls — the password gate prevents unauthenticated access,
  but a single authenticated user could still run up API costs with many questions.
- No log rotation configured for `app.log` inside the container.
- The old `format-validator` Traefik/app containers were stopped, not removed — they still exist
  on the host (`docker ps -a`) and could be cleaned up (`docker rm`) once confirmed unneeded.
