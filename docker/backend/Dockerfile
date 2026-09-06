FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libmagic1 \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 docvault \
    && useradd --system --uid 10001 --gid docvault --create-home --home-dir /home/docvault docvault \
    && mkdir -p /var/lib/docvault \
    && chown -R docvault:docvault /var/lib/docvault

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app
RUN chown -R docvault:docvault /app

ENV PYTHONPATH=/app
EXPOSE 8000
USER docvault
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
