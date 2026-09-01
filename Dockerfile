# ---- Builder stage: compile wheels (needs build tools) ----
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build tools are only needed to compile packages (e.g. pyswisseph); they stay in
# this stage and never reach the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies into an isolated virtualenv we can copy wholesale.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage: slim image, no compilers ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Bring over just the built packages, not the toolchain that built them.
COPY --from=builder /opt/venv /opt/venv

# Copy the application code (see .dockerignore for what's excluded).
COPY . .

# Precompile bytecode at build time so cold starts don't recompile on first
# import. PYTHONDONTWRITEBYTECODE is intentionally left unset so these .pyc are used.
RUN python -m compileall -q /app /opt/venv

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
