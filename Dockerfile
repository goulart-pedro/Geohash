FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Baixa a malha viária de BH durante o build (cache em /app/cache).
# Se falhar, o app tenta novamente na primeira execução.
RUN python scripts/baixar_malha.py || echo "malha será baixada na primeira execução"

ENV PORT=8050
EXPOSE 8050

# 1 worker: a frota (Trie) vive em memória do processo.
CMD gunicorn main:server --workers 1 --threads 4 --timeout 300 --bind 0.0.0.0:${PORT}
