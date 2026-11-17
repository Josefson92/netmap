# Mapa domácí sítě: server (docs/nas.md). Kontext sestavení je kořen repozitáře:
# docker build -f server/Dockerfile .
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tzdata nmap && rm -rf /var/lib/apt/lists/*
WORKDIR /app/server
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/app.py .
COPY ukazka/ /app/ukazka/
COPY ukazka-en/ /app/ukazka-en/
ENV PORT=8780 PYTHONUNBUFFERED=1
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ['PORT'])"
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips=127.0.0.1"]
