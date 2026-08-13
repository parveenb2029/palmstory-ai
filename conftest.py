"""Shared test setup: force deterministic, offline defaults so the whole suite
runs on mock providers with inline jobs — no external AI, no network."""
import os

os.environ.setdefault("DEV_MOCK_AI", "true")
os.environ.setdefault("JOBS_SYNC", "true")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("PROVIDER_FALLBACK_MOCK", "true")
