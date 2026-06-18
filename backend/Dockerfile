# ── Hugging Face Spaces – FastAPI Backend ────────────────────────────────────
# Build: automatically handled by HF Spaces Docker runtime.
# Port:  HF Spaces requires the app to listen on 7860.
# Env:   Set GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY as HF Space Secrets.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Prevents .pyc files and buffers stdout so logs appear in real-time
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Use headless matplotlib backend (no display available in container)
ENV MPLBACKEND=Agg

# HF Spaces requires the app to listen on port 7860
ENV PORT=7860

WORKDIR /code

# Install system dependencies needed by psycopg2 and general builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Pre-create runtime directories the app expects at startup
RUN mkdir -p /code/temp_datasets /code/local_storage/datasets /code/local_storage/charts

# Expose the HF Spaces port
EXPOSE 7860

# Start the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
