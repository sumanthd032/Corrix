# Multi-stage build: the frontend is built first, then copied into the
# backend image so one container serves both the API/WebSocket and the
# static frontend from the same origin (see backend/app/main.py's static
# mount). This is the shape actually verified locally (a real browser
# session against port 8000 alone, no separate frontend server), not an
# assumed-to-work deployment shape.

FROM node:22-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci
COPY frontend/ ./frontend/
COPY .env.production ./.env.production
RUN cd frontend && npm run build

FROM python:3.13-slim
WORKDIR /app

# Playwright's Chromium needs these system libraries; installed once at
# build time, not left to fail silently at first Incident Report request.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt

# sentence-transformers and ultralytics both pull in torch with no
# constraint of their own, which defaults to the full CUDA build, several
# GB of NVIDIA libraries (confirmed: cublas, cudnn, cusolver, and a dozen
# more) that do nothing on Render's CPU-only free/starter tier. Installing
# the CPU-only wheel first satisfies pip's resolver before either package
# gets a chance to pull the CUDA one in.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r backend/requirements.txt \
    && python -m playwright install chromium

# ultralytics declares a hard dependency on plain opencv-python
# regardless of what's already installed, which silently overwrote
# opencv-python-headless's cv2 files with the GUI build's (confirmed:
# both were present in `pip list`), and the GUI build needs libGL.so.1,
# which this image deliberately doesn't have, crashing the container on
# every startup. Force-reinstalling headless last, without touching its
# already-satisfied dependencies, makes it win regardless of install order.
RUN pip install --no-cache-dir --force-reinstall --no-deps opencv-python-headless==5.0.0.93

COPY backend/ ./backend/
COPY data/ ./data/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
