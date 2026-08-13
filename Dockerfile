# PalmStory AI — container image.
# Runs the FastAPI app with mock providers by default (no external AI). The
# committed static/js/app.js is the built front-end, so no Node build is needed;
# to rebuild the TypeScript, run `npm install && npm run build` before building.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEV_MOCK_AI=true \
    PORT=8000

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY backend/ ./backend/
COPY vision/ ./vision/
COPY palmistry/ ./palmistry/
COPY frontend/ ./frontend/
COPY static/ ./static/
COPY docs/ ./docs/

# Run as a non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
