FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

# CPU-only torch keeps the image to a manageable size — there is no GPU in
# the target cluster and the models are small enough not to need one.
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY src/ ./src/

RUN mkdir -p /app/output

ENV PYTHONUNBUFFERED=1 \
    REDIS_HOST=redis \
    REDIS_PORT=6379

# Overridden per-workload: the Job/CronJob run the pipeline, the Deployment
# runs the report server.
CMD ["python", "-m", "src.agents.graph"]
