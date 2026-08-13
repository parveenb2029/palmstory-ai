# PalmStory AI

> **Your palm. Your story. Reimagined by AI.**
>
> **Entertainment only.** Palmistry is a cultural tradition, not a scientifically
> validated method of prediction. Readings are AI-generated, fictionalized
> storytelling based on visible image features — never medical, financial, legal,
> or psychological advice.

Capture your palm and get a traditional-palmistry-inspired reading and a
four-panel comic, made for you. A full-stack portfolio project built in 19
reviewed phases.

**Status:** v1.0.0 — engineering-complete. See `docs/LAUNCH_READINESS.md` for
pre-launch items.

---

## Quickstart

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
# open http://localhost:8000   (localhost is a secure origin → camera works)
```

Runs out of the box with **zero setup**: SQLite database, **mock AI** (no keys,
no network), and an in-process job runner. Register an account, go to *Read my
palm*, and capture.

### Real AI (optional)
```bash
DEV_MOCK_AI=false VISION_PROVIDER=huggingface TEXT_PROVIDER=huggingface \
IMAGE_PROVIDER=pollinations HF_TOKEN=... uvicorn backend.app.main:app
```
Pollinations needs no key (images render in the browser). Hugging Face needs
`HF_TOKEN`. A bounded fallback drops back to mocks on any provider error.

### Deploy / get a shareable link
The fastest public **https** link is Render (free): push to GitHub, then
**New → Blueprint** using the included `render.yaml`. Full steps for Render /
Railway / Fly / Docker / tunnels are in **[`docs/DEPLOY.md`](docs/DEPLOY.md)**.

### Docker
```bash
docker compose up            # app on http://localhost:8000 (SQLite + mock AI)
docker compose --profile postgres up   # with Postgres
```

---

## What it does

1. **Capture** — camera or upload, with an on-device quality gate (lighting,
   focus, framing) so a bad photo never reaches the AI.
2. **See** — server-side computer vision preprocesses the image and detects the
   palm (MediaPipe when installed; a NumPy heuristic otherwise).
3. **Interpret** — a structured palmistry **knowledge base** + a deterministic
   rules engine turn observations into a grounded, auditable interpretation.
4. **Narrate** — an LLM writes the reading *from that interpretation* (not from
   the raw photo), then a four-beat comic **storyboard**.
5. **Illustrate** — each panel is rendered to an image, with a guaranteed SVG
   fallback so a comic always appears.

All the heavy work runs as a **background job** with live progress; the palm
image is used in memory and **never stored** — only the reading is saved.

---

## Architecture

```
Browser (Jinja + TypeScript)
   │  POST /api/v1/readings (image)         ┌───────────── background job ─────────────┐
   ▼                                        │ observe → interpret → reading → storyboard│
FastAPI  ──quality gate (sync)──▶ create job│                                    → comic│
   │  GET /api/v1/readings/{id} (poll)      └───────────────────────────────────────────┘
   ▼
Reading persisted (SQLite/Postgres)         Providers: mock ⇆ Hugging Face / Pollinations
```

- **Provider abstraction** — `VisionProvider` / `TextProvider` /
  `ImageGenerationProvider`, swappable by config, deterministic mocks by default.
- **Grounded interpretation** — `palmistry/knowledge/lines.json` +
  `palmistry/interpretation/engine.py`; no free-form fortune-telling, no
  lifespan/medical claims.
- Full design in [`docs/architecture.md`](docs/architecture.md); API in
  [`docs/API.md`](docs/API.md).

### Structure
```
backend/app/    FastAPI app: api/, auth/, jobs/, models/, providers/, services/, schemas/
vision/         preprocessing, quality, palm detection, pipeline
palmistry/      knowledge base, interpretation engine, schemas
frontend/       Jinja templates + TypeScript source
static/         design system (css) + built client (js)
docs/           architecture, API, launch readiness
```

---

## Tech stack
FastAPI · SQLAlchemy · Argon2 · Pillow + NumPy (OpenCV/MediaPipe optional) ·
Jinja · TypeScript + Vite · Docker · GitHub Actions.

## Testing & CI
```bash
make test        # 68 tests, all on mock providers (no external AI, no network)
make lint        # ruff (pyflakes)
make typecheck   # tsc --noEmit
```
CI (`.github/workflows/ci.yml`) runs the suite on Python 3.11 & 3.12 plus the TS
typecheck.

## Configuration
Environment variable names are documented in [`.env.example`](.env.example)
(providers, `DEV_MOCK_AI`, `JOBS_SYNC`, `DATABASE_URL`, `SECURE_COOKIES`,
`RATE_LIMIT_READINGS_PER_HOUR`, …).

## Roadmap
All 19 phases complete: UI foundation, auth, camera, computer vision, provider
abstraction, observation, interpretation, reading, storyboard, comic, async jobs,
persistence, security, tests/CI, performance, Docker, UX polish, docs, release.

## License
MIT — see [`LICENSE`](LICENSE).
