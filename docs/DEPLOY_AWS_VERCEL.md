# Deploying Corrix: AWS EC2 backend + Vercel frontend (free, stable, HTTPS/WSS)

This deploys Corrix as two pieces, entirely on free tiers:

- **Backend** on an AWS EC2 free-tier instance, running the Docker image.
- **Frontend** on Vercel.
- **A free, stable HTTPS URL** for the backend using **DuckDNS** (a free
  subdomain) plus **Caddy** (which fetches a free Let's Encrypt certificate
  automatically). This is required: the Vercel frontend is served over HTTPS,
  so the browser will refuse a plain `ws://` WebSocket to the backend. Caddy
  gives you `https` and `wss` at zero cost.

```
Browser  ──https──▶  Vercel (frontend)
   │
   └──https / wss──▶  corrix.duckdns.org  ──▶  Caddy (TLS)  ──▶  localhost:8000 (backend)
```

> Why not Cloudflare Tunnel with `api.yourdomain.com`? That is also fine, but a
> stable custom hostname there needs a domain you own, which is not free. DuckDNS
> plus Caddy is the fully free path with a stable URL. (Cloudflare's zero-setup
> "quick tunnel" is free too, but its URL changes on every restart.)

## What you need first

- An **AWS** account (free tier).
- A **Vercel** account.
- A **DuckDNS** account (free; sign in with GitHub/Google at duckdns.org).
- Your real secrets: `GROQ_API_KEY`, `GEMINI_API_KEY`, the three `NEO4J_*`
  values, and optionally the `ERO_SMTP_*` email settings.

---

## Part 1 - Launch the EC2 instance and give it a stable IP

1. AWS Console, EC2, **Launch instance**.
   - **Name**: `corrix-backend`
   - **AMI**: Ubuntu Server 24.04 LTS (free tier eligible)
   - **Instance type**: `t3.micro` (or `t2.micro`), free tier
   - **Key pair**: create one and download the `.pem` (for SSH)
   - **Security group**, allow:
     - **SSH (22)** from **My IP**
     - **HTTP (80)** from **Anywhere** (Let's Encrypt validation + redirect)
     - **HTTPS (443)** from **Anywhere** (the app, over `https`/`wss`)
   - **Storage**: **30 GiB** gp3 (the free-tier maximum; the image is large).
2. **Allocate an Elastic IP** and associate it with the instance (EC2, Elastic
   IPs, Allocate, then Associate). This keeps the public address stable across
   restarts. It is free while attached to a running instance.
3. Note the **Elastic IP**.

## Part 2 - Point a free DuckDNS subdomain at the instance

1. Go to duckdns.org, sign in, and create a subdomain, for example `corrix`,
   giving you `corrix.duckdns.org`.
2. Set its **current ip** to your **Elastic IP** and save.
3. (Optional) Note your DuckDNS token if you want to script IP updates later.

## Part 3 - Connect and prepare the box

```bash
chmod 400 corrix-key.pem
ssh -i corrix-key.pem ubuntu@<ELASTIC_IP>
```

Add swap. This is essential: 1 GiB of RAM is not enough for the full stack
(torch, sentence-transformers, Playwright/Chromium) on its own.

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h            # confirm 4.0Gi of swap
```

Install Docker and git:

```bash
sudo apt-get update
sudo apt-get install -y docker.io git
sudo systemctl enable --now docker
```

## Part 4 - Get the code and set secrets

```bash
git clone https://github.com/sumanthd032/Corrix.git
cd Corrix
cp .env.example .env
nano .env
```

Fill in at least `GROQ_API_KEY`, `GEMINI_API_KEY`, and the three `NEO4J_*`
values (and the `ERO_SMTP_*` block if you want email alerts). Leave the two
`CORRIX_*CORS*` values for now; you will set them in Part 7 once you know the
Vercel URL.

## Part 5 - Build and run the backend

```bash
sudo docker build -t corrix .
```

The build downloads torch, sentence-transformers, Ultralytics, and Playwright's
Chromium, and builds the frontend stage. On a micro instance with swap this can
take 20 to 40 minutes. It only runs when you deploy or update.

Run it, bound to localhost only (Caddy reaches it locally; the backend is never
exposed to the internet directly, only through Caddy):

```bash
sudo docker run -d --name corrix --restart unless-stopped \
  -p 127.0.0.1:8000:8000 --env-file .env corrix
```

Confirm it is healthy:

```bash
curl http://localhost:8000/health      # {"status":"ok","service":"corrix-backend"}
```

Populate the Neo4j instance once (idempotent):

```bash
sudo docker exec corrix python scripts/setup_neo4j.py
```

## Part 6 - Caddy for free HTTPS/WSS

Install Caddy:

```bash
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update
sudo apt-get install -y caddy
```

Replace the Caddyfile with a reverse proxy to the backend (use your own
DuckDNS hostname):

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
corrix.duckdns.org {
    reverse_proxy localhost:8000
}
EOF
sudo systemctl reload caddy
```

That is all Caddy needs: it automatically obtains and renews a Let's Encrypt
certificate for `corrix.duckdns.org`, serves it on 443, and proxies everything,
including WebSocket upgrades, to the backend. Give it a few seconds, then from
your laptop:

```bash
curl https://corrix.duckdns.org/health   # {"status":"ok",...}
```

Your backend is now at `https://corrix.duckdns.org` and `wss://corrix.duckdns.org`.

## Part 7 - Frontend on Vercel

1. Make sure the repo is pushed to GitHub.
2. vercel.com, **Add New, Project**, import the `Corrix` repo.
3. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - Build command and output directory: leave the Vite defaults (`npm run build`, `dist`).
4. **Environment Variables** (add before the first deploy, for Production),
   using your DuckDNS hostname:
   - `VITE_API_BASE_URL` = `https://corrix.duckdns.org`
   - `VITE_WS_BASE_URL` = `wss://corrix.duckdns.org`
5. **Deploy**. Vercel gives you a URL like `https://corrix-xxxx.vercel.app`.

## Part 8 - Point CORS at the Vercel domain

Back on the EC2 box, edit `.env` and set the frontend origin so the backend
accepts its API calls:

```bash
cd Corrix
nano .env
```

```
CORRIX_EXTRA_CORS_ORIGIN=https://corrix-xxxx.vercel.app
CORRIX_CORS_ORIGIN_REGEX=https://.*\.vercel\.app
```

The regex line also allows Vercel preview deployments. Restart the backend so
it picks up the change:

```bash
sudo docker restart corrix
```

## Part 9 - Verify

Open your Vercel URL, select **Launch live demo**, and the top-bar indicator
should read **LIVE** within a few seconds (a real `wss` connection). Run a
scenario to confirm the Council convenes end to end.

If it shows **Backend offline**:

- `curl https://corrix.duckdns.org/health` returns ok (Caddy + backend up).
- `sudo systemctl status caddy` is running and the Caddyfile hostname is exact.
- Ports 80 and 443 are open in the security group, and DuckDNS points at the
  Elastic IP.
- `VITE_WS_BASE_URL` is `wss://corrix.duckdns.org` (not `ws://`).
- `CORRIX_EXTRA_CORS_ORIGIN` matches your Vercel origin, and the container was
  restarted after setting it.

## Updating after code changes

```bash
cd Corrix
git pull
sudo docker build -t corrix .
sudo docker rm -f corrix
sudo docker run -d --name corrix --restart unless-stopped \
  -p 127.0.0.1:8000:8000 --env-file .env corrix
```

`docker restart` alone is NOT enough: it re-runs the existing container with
its old image and old environment. To pick up new code or a changed `.env`
you must `rm -f` and `run` again, as above. The rebuild is fast when only
backend code changed (Docker caches the torch/pip/frontend layers); it is only
slow again if `requirements.txt` or the frontend dependencies changed.

Vercel redeploys the frontend automatically on every push to the connected
branch. Caddy, DNS, and the Elastic IP never need touching.

## Notes and constraints

- **Cost**: everything here is free, AWS EC2 free tier, the 30 GiB volume,
  the Elastic IP (while attached to a running instance), DuckDNS, Let's Encrypt,
  and Vercel's hobby tier. The only thing that would cost money is a custom
  paid domain, which this setup avoids.
- **Memory**: with 1 GiB of RAM plus 4 GiB of swap the full stack runs, but the
  memory-spiking features (PDF incident report via Chromium) are slow. A paid
  `t3.small` (2 GiB) is the obvious upgrade, but not free tier.
- **Neo4j**: the deployed backend uses the same AuraDB Free instance as local.
  Run `setup_neo4j.py` once against it (Part 5).
- **Elastic IP**: keep the instance running, or you will be billed a small
  hourly rate for an unattached/idle Elastic IP. Release it if you tear the
  instance down.
- **CV weights**: the fine-tuned PPE checkpoint is gitignored and not in the
  image, so computer vision falls back to base person-detection.
