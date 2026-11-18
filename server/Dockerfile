# Mapa domácí sítě: server (docs/nas.md). Hotový image staví GitHub Actions (.github/workflows/image.yml).
# Ručně, kontext sestavení je kořen repozitáře: docker build -f server/Dockerfile .
FROM python:3.12-slim
# nmap dostane jen schopnost posílat surové pakety (ARP sken), server pak nemusí běžet jako root
RUN apt-get update && apt-get install -y --no-install-recommends tzdata nmap libcap2-bin \
 && setcap cap_net_raw+eip /usr/bin/nmap \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app/server
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# start: najde uživatele se zápisem do data/ a config/ a server spustí pod ním (ne jako root)
COPY server/entrypoint.sh /usr/local/bin/netmap-start
RUN sed -i 's/\r$//' /usr/local/bin/netmap-start && chmod 755 /usr/local/bin/netmap-start
COPY ukazka/ /app/ukazka/
COPY ukazka-en/ /app/ukazka-en/
COPY server/netmap/ ./netmap/
# editor je součástí image; vlastní verze jde podstrčit volume ./www (www/mapa.html má přednost)
COPY mapa.html /app/mapa.html
# verze z git describe (workflow image.yml), editor ji ukáže a server podle ní hlásí nové vydání
ARG NETMAP_VERSION=dev
ENV NETMAP_VERSION=$NETMAP_VERSION
ENV PORT=8780 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ['PORT'])"
ENTRYPOINT ["netmap-start"]
CMD ["sh", "-c", "exec uvicorn netmap.api:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips=127.0.0.1"]
