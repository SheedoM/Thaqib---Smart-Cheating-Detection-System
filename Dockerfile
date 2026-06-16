FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-ai.txt ./
ARG INSTALL_AI=false
RUN python -m pip install --upgrade pip==26.1.2 setuptools==82.0.1 wheel==0.45.1 \
    && python -m pip install -r requirements.txt \
    && if [ "$INSTALL_AI" = "true" ]; then python -m pip install -r requirements-ai.txt; fi

COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN adduser --disabled-password --gecos "" thaqib \
    && mkdir -p /app/data /app/archive /app/alerts /app/uploads /app/logs /app/models \
    && chown -R thaqib:thaqib /app

USER thaqib
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5).read()" || exit 1

CMD ["uvicorn", "src.thaqib.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]
