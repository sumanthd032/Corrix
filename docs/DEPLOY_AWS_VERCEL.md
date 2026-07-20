# Deploying Corrix: AWS EC2 backend + Vercel frontend + Cloudflare Tunnel

This deploys Corrix as two pieces:

- **Backend** on an AWS EC2 free-tier instance, running the Docker image.
- **Frontend** on Vercel.
- **Cloudflare Tunnel** gives the backend a public `https` / `wss` URL with a
  valid TLS certificate. This is required: the Vercel frontend is served over
  HTTPS, so the browser will refuse a plain `ws://` WebSocket to the backend.
  The tunnel is also outbound-only, so the EC2 security group only needs SSH
  open, nothing else.

```
Browser  ──https──▶  Vercel (frontend)
   │
   └──https / wss──▶  Cloudflare Tunnel  ──▶  EC2 : localhost:8000 (backend)
```

## What you need first

- An **AWS** account (free tier).
- A **Vercel** account.
- A **Cloudflare** account (free).
- Your real secrets: `GROQ_API_KEY`, `GEMINI_API_KEY`, the three `NEO4J_*`
  values, and optionally the `ERO_SMTP_*` email settings.
- For a **stable** backend URL, a domain managed by Cloudflare. If you do not
  have one, use the Quick Tunnel option in Part 5, which needs no domain but
  gives a URL that changes each restart.

---

## Part 1, Launch the EC2 instance

1. AWS Console → EC2 → **Launch instance**.
2. Settings:
   - **Name**: `corrix-backend`
   - **AMI**: Ubuntu Server 24.04 LTS (free tier eligible)
   - **Instance type**: `t3.micro` (or `t2.micro`), free tier
   - **Key pair**: create one and download the `.pem` (for SSH)
   - **Network / security group**: allow **SSH (port 22) from My IP** only. Do
     not open 80 or 443; the Cloudflare Tunnel connects outbound.
   - **Storage**: **30 GiB** gp3 (the free-tier maximum; the image and its
     dependencies are large).
3. Launch, then note the instance's **public IPv4** (used only for SSH).

## Part 2, Connect and prepare the box

```bash
chmod 400 corrix-key.pem
ssh -i corrix-key.pem ubuntu@<EC2_PUBLIC_IP>
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

## Part 3, Get the code and set secrets

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

## Part 4, Build and run the backend

```bash
sudo docker build -t corrix .
```

The build downloads torch, sentence-transformers, Ultralytics, and Playwright's
Chromium, and builds the frontend stage. On a micro instance with swap this can
take 20 to 40 minutes. It only runs when you deploy or update.

Run it, bound to localhost only (the tunnel reaches it locally; nothing is
exposed to the internet directly):

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

## Part 5, Cloudflare Tunnel (HTTPS + WSS)

Install `cloudflared`:

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
sudo mv cloudflared /usr/local/bin/ && sudo chmod +x /usr/local/bin/cloudflared
```

### Option A, Named tunnel (stable URL, needs a Cloudflare-managed domain)

Add your domain to Cloudflare first (free plan, "Add a site"), then:

```bash
cloudflared tunnel login                     # authorize your domain in the browser
cloudflared tunnel create corrix             # creates a tunnel + a credentials .json
cloudflared tunnel route dns corrix api.YOURDOMAIN.com
```

Create `~/.cloudflared/config.yml` (replace the tunnel id and hostname):

```yaml
tunnel: corrix
credentials-file: /home/ubuntu/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: api.YOURDOMAIN.com
    service: http://localhost:8000
  - service: http_status:404
```

Run it as a service so it survives reboots:

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared
```

Your backend is now at `https://api.YOURDOMAIN.com` (and `wss://api.YOURDOMAIN.com`).

### Option B, Quick tunnel (no domain, instant, URL changes on restart)

```bash
cloudflared tunnel --url http://localhost:8000
```

It prints a URL like `https://<random-words>.trycloudflare.com`. Use that as the
backend URL. Note it is ephemeral: it changes every time you restart it and is
meant for quick testing, not a stable deployment. To keep it running in the
background, use `nohup cloudflared tunnel --url http://localhost:8000 &` and
copy the printed URL.

## Part 6, Frontend on Vercel

1. Make sure the repo is pushed to GitHub.
2. vercel.com → **Add New → Project** → import the `Corrix` repo.
3. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - Build command and output directory: leave the Vite defaults (`npm run build`, `dist`).
4. **Environment Variables** (add these before the first deploy, for the
   Production environment), using your backend URL from Part 5:
   - `VITE_API_BASE_URL` = `https://api.YOURDOMAIN.com`
   - `VITE_WS_BASE_URL` = `wss://api.YOURDOMAIN.com`
5. **Deploy**. Vercel gives you a URL like `https://corrix-xxxx.vercel.app`.

## Part 7, Point CORS at the Vercel domain

Back on the EC2 box, edit `.env` and set the frontend origin so the backend
accepts its API calls:

```bash
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

## Part 8, Verify

Open your Vercel URL, select **Launch live demo**, and the top-bar indicator
should read **LIVE** within a few seconds (a real `wss` connection). Run a
scenario to confirm the Council convenes end to end.

If it shows **Backend offline**:

- `sudo systemctl status cloudflared` (or the quick-tunnel process) is running.
- `curl http://localhost:8000/health` on the box returns ok.
- `VITE_WS_BASE_URL` is `wss://...` and matches the tunnel hostname exactly.
- `CORRIX_EXTRA_CORS_ORIGIN` matches your Vercel origin, and the container was
  restarted after setting it.

## Updating after code changes

```bash
cd Corrix
git pull
sudo docker build -t corrix .
sudo docker restart corrix        # or: docker rm -f corrix && docker run ... again
```

Vercel redeploys the frontend automatically on every push to the connected
branch.

## Notes and constraints

- **Memory**: with 1 GiB of RAM plus 4 GiB of swap the full stack runs, but
  the memory-spiking features (PDF incident report via Chromium, CV inference)
  are slow. For a smoother demo, a paid `t3.small` (2 GiB) is the obvious next
  step, but it is not free tier.
- **Neo4j**: the deployed backend uses the same AuraDB Free instance as local.
  Run `setup_neo4j.py` once against it (Part 4).
- **Image size**: about 5 GB; the 30 GiB free-tier volume holds it comfortably.
- **CV weights**: the fine-tuned PPE checkpoint is gitignored and not in the
  image, so computer vision falls back to base person-detection unless you
  retrain and bake the weights in.
