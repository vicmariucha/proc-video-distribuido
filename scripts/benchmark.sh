#!/usr/bin/env bash
# Processa o mesmo vídeo com 1, 2 e 4 workers e mostra o tempo de cada execução.
# Uso: ./scripts/benchmark.sh data/input/teste.mp4 estilizar
set -euo pipefail

VIDEO="${1:-data/input/teste.mp4}"
FILTRO="${2:-estilizar}"
NOME=$(basename "$VIDEO")

for N in 1 2 4; do
  docker compose up -d --scale worker="$N" > /dev/null
  sleep 3
  JOB=$(docker compose run --rm -T produtor --entrada "/data/input/$NOME" --filtro "$FILTRO" | grep JOB_ID | cut -d= -f2 | tr -d '\r')
  echo -n "workers=$N job=$JOB ... "
  until [ -f "data/output/${JOB}_stats.json" ]; do sleep 1; done
  python3 -c "import json;d=json.load(open('data/output/${JOB}_stats.json'));print(f\"{d['tempo_total_s']} s | {d['frames_por_segundo']} frames/s\")"
done
