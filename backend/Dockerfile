# Pin Debian bookworm: o `slim` mudou para trixie, onde libgdk-pixbuf2.0-0 deixou
# de existir (renomeado) e quebra o apt-get. bookworm é o que o Dockerfile espera.
FROM python:3.11-slim-bookworm

# WeasyPrint system dependencies (Pango, Cairo, GDK-PixBuf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libglib2.0-0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Carimbo do commit DENTRO da imagem. Sem ele nao existe forma honesta de responder "o que roda
# no container e o que eu acabo de commitar?" -- o codigo e baked, e `git pull` no host nao muda
# container nenhum. Ja declarei um conserto verificado tendo rodado o teste no lugar errado
# (regra 4 do CLAUDE.md). `desconhecido` e o padrao para build manual, e o deploy.sh reprova.
ARG GIT_SHA=desconhecido
RUN echo "$GIT_SHA" > /app/.git_sha

RUN mkdir -p /data

ENV GAPHUNTER_DB=/data/leaklab.db
ENV PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD gunicorn api.app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
