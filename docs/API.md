# API reference

All routes require a logged-in session unless noted. Errors return JSON
`{ "detail": "..." }` for `/api/*` paths and a friendly HTML page otherwise.

## Auth (form-based, HTML)
| Method | Path | Notes |
|---|---|---|
| GET/POST | `/register` | Create account (CSRF token required on POST) |
| GET/POST | `/login` | Log in (CSRF) |
| POST | `/logout` | Log out (CSRF) |

## Readings (JSON API)
### `POST /api/v1/readings`
Create a reading. Body: multipart `file` + `hand`, or JSON `{ "image": "<data URL>", "hand": "left|right" }`.

- Runs the quality gate synchronously.
- **Bad image** → `200 { "status": "rejected", "job_id": null, "quality": {...} }` (no AI spent).
- **Good image** → `202 { "status": "queued", "job_id": "...", "quality": {...}, "detection": {...} }`.
- Rate limited per user (`429` past the hourly cap).

### `GET /api/v1/readings/{job_id}`
Poll a job (owner-only; `404` otherwise).
```
{ "job_id", "status": "queued|processing|complete|failed",
  "stage", "progress", "error", "reading_id", "result": { ... } | null }
```
`result` (when complete) contains `quality`, `detection`, `observation`,
`interpretation`, `reading`, `storyboard`, `comic`, `providers`.

### `POST /api/v1/image-quality-check`
Cheap, no-AI quality + detection check. Body as above (image only). Returns a
`VisionResult`.

## Reading pages (HTML)
| Method | Path | Notes |
|---|---|---|
| GET | `/history` | Your readings |
| GET | `/reading/{id}` | Reading detail (owner-only) |
| POST | `/reading/{id}/delete` | Delete one (CSRF) |

## Settings & account (HTML)
| Method | Path | Notes |
|---|---|---|
| GET | `/settings` | Account & data controls |
| GET | `/settings/export` | Download all readings as JSON |
| POST | `/settings/delete-all` | Delete all readings (CSRF) |
| POST | `/account/delete` | Delete account + all data (CSRF) |

## Ops
| Method | Path | Notes |
|---|---|---|
| GET | `/healthz` | `{ status, version, providers }` (public) |
