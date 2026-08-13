# Launch readiness

The app is engineering-complete, but the following are required before any
**public** launch:

1. **Privacy policy** — a real, reviewed policy. The app's technical stance
   (palm images used only to generate a reading, then discarded; readings stored
   per account; export & delete available) must be reflected in legally reviewed
   copy. The `/privacy` page currently states the intended model, not a policy.
2. **Terms of service** — entertainment-only positioning, acceptable use, and
   liability limits.
3. **Crisis-safety review** — because readings touch on people's lives, add a
   light safety layer: keep copy strictly entertainment, avoid deterministic or
   distressing claims (the interpretation engine already forbids lifespan/medical
   claims), and provide a clear path away from the product for anyone in distress.
4. **Age gating** — decide and enforce a minimum age; palm images are sensitive.
5. **Real-provider review** — if enabling Hugging Face / Pollinations, review
   their terms, add server-side timeouts/retries (Phase 11 fallback is in place),
   and monitor cost.
6. **Secrets & transport** — set `SECRET_KEY`, `SECURE_COOKIES=true` behind HTTPS,
   and a managed Postgres `DATABASE_URL`.

None of these are code-blocking; they are launch-blocking.
