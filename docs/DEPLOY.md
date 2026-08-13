# Deploy & share PalmStory AI

Goal: get a public **https link** you can send to anyone, on any device. The app
needs no API keys to run (mock AI by default), so a free host is enough.

> The camera only works over **https** (or localhost). Every option below gives
> you https, so the camera works for your visitors. Where it can't, the app shows
> a clear message and an **upload a photo** fallback.

---

## Option A — Render (recommended, free, ~3 minutes)

1. Push this project to a **GitHub** repo.
2. Go to <https://render.com> → sign in with GitHub.
3. **New → Blueprint** → pick your repo → **Apply**. Render reads `render.yaml`
   and provisions everything (Python, build, start command, a generated
   `SECRET_KEY`, secure cookies, health checks).
4. When it finishes you get a URL like `https://palmstory-ai.onrender.com` —
   **that's your shareable link.**

Notes:
- Free instances sleep after inactivity; the first visit after a nap takes ~30s
  to wake. Normal for free tier.
- Free-tier disk is ephemeral, so the SQLite database resets on redeploy/restart
  (accounts/readings clear). Fine for a demo. For durable data, see **Postgres**
  below.

## Option B — Railway (free trial credit)
1. <https://railway.app> → **New Project → Deploy from GitHub repo**.
2. Railway auto-detects the `Procfile`. Add env vars: `DEV_MOCK_AI=true`,
   `SECURE_COOKIES=true`, `SECRET_KEY=<a long random string>`.
3. Under Settings → Networking → **Generate Domain** → that's your link.

## Option C — Fly.io
1. Install `flyctl`, run `fly launch` (it detects the `Dockerfile`).
2. Set secrets: `fly secrets set SECRET_KEY=<random> SECURE_COOKIES=true DEV_MOCK_AI=true`.
3. `fly deploy` → your app is at `https://<app>.fly.dev`.

## Option D — Docker anywhere
```bash
docker build -t palmstory .
docker run -p 8000:8000 -e SECRET_KEY=$(openssl rand -hex 32) palmstory
# http://localhost:8000   (put behind a TLS proxy for a public https link)
```
Or `docker compose up`.

---

## Durable data (Postgres)
Free SQLite resets on restart. To keep data:
1. Create a Postgres database (Render/Railway/Neon all offer one).
2. Build with `pip install -r requirements-postgres.txt`.
3. Set `DATABASE_URL=postgresql://user:pass@host:5432/dbname`.
No code changes — the app uses whatever `DATABASE_URL` points at.

## Turning on real, image-based readings (Google Gemini — free)
This makes the reading respond to the ACTUAL palm in the photo (instead of the
built-in demo reading). Gemini has a free tier and only needs a free key.

1. Go to <https://aistudio.google.com/apikey> and create a free API key.
2. On your host (Render → your service → **Environment**), add:
   ```
   DEV_MOCK_AI=false
   VISION_PROVIDER=gemini
   TEXT_PROVIDER=gemini
   GEMINI_API_KEY=<your key>
   GEMINI_MODEL=gemini-2.0-flash
   PROVIDER_FALLBACK_MOCK=true
   ```
3. Save — Render redeploys automatically. `/healthz` will then show
   `"vision":"gemini"`.

The comic stays the built-in illustrated style (no image key needed). If Gemini
ever errors or hits its free limit, the app falls back to the built-in reading
rather than failing — so it never breaks.

### Alternative: Hugging Face
```
DEV_MOCK_AI=false
VISION_PROVIDER=huggingface  TEXT_PROVIDER=huggingface  HF_TOKEN=<token>
```
(Free HF vision inference is slower/less reliable than Gemini.)

---

## Run locally & share on your network (no host needed)
```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
- On your machine: <http://localhost:8000> (camera works — localhost is secure).
- Same Wi-Fi: others can open `http://<your-computer-ip>:8000` (camera may be
  blocked on plain http; upload still works). For a quick public https link,
  use a tunnel: `npx localtunnel --port 8000` or `cloudflared tunnel --url http://localhost:8000`.

## Production checklist
- [ ] `SECRET_KEY` set to a long random value (never the default)
- [ ] `SECURE_COOKIES=true` (you're on https)
- [ ] `DATABASE_URL` → Postgres if you want data to persist
- [ ] Review `docs/LAUNCH_READINESS.md` before a real public launch
