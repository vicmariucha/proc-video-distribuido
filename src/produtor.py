"""Produtor: lê um vídeo, divide em frames e publica cada frame como uma tarefa na fila AMQP."""
import argparse
import json
import sys
import time
import uuid

import cv2
import pika

from comum import (FILA_CONTROLE, FILA_TAREFAS, PERSISTENTE, conectar,
                   configurar_log, declarar_filas)
from filtros import FILTROS

log = configurar_log("produtor")

def publicar_controle(canal, msg: dict) -> None:
    canal.basic_publish(
        exchange="",
        routing_key=FILA_CONTROLE,
        body=json.dumps(msg).encode(),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=PERSISTENTE),
    )

def main() -> int:
    ap = argparse.ArgumentParser(description="Divide um vídeo em frames e distribui para os workers.")
    ap.add_argument("--entrada", required=True, help="Caminho do vídeo de entrada")
    ap.add_argument("--filtro", default="estilizar", choices=sorted(FILTROS))
    ap.add_argument("--qualidade", type=int, default=90, help="Qualidade JPEG dos frames (1-100)")
    ap.add_argument("--max-frames", type=int, default=0, help="Limita a quantidade de frames (0 = todos)")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.entrada)
    if not cap.isOpened():
        log.error("Não foi possível abrir %s", args.entrada)
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    conexao = conectar()
    canal = conexao.channel()
    declarar_filas(canal)

    job_id = uuid.uuid4().hex[:8]
    t0 = time.time()
    publicar_controle(canal, {"tipo": "inicio", "job_id": job_id, "filtro": args.filtro,
                              "fps": fps, "entrada": args.entrada, "t0": t0})
    log.info("Job %s iniciado | filtro=%s | fps=%.2f", job_id, args.filtro, fps)

    indice = 0
    while True:
        ok, frame = cap.read()
        if not ok or (args.max_frames and indice >= args.max_frames):
            break
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, args.qualidade])
        if not ok:
            log.warning("Falha ao codificar frame %d, ignorado", indice)
            continue
        canal.basic_publish(
            exchange="",
            routing_key=FILA_TAREFAS,
            body=buf.tobytes(),
            properties=pika.BasicProperties(
                content_type="image/jpeg",
                delivery_mode=PERSISTENTE,
                headers={"job_id": job_id, "indice": indice, "filtro": args.filtro, "fps": str(fps)},
            ),
        )
        indice += 1
        if indice % 100 == 0:
            log.info("%d frames publicados", indice)

    cap.release()
    publicar_controle(canal, {"tipo": "fim", "job_id": job_id, "total": indice, "t0": t0})
    conexao.close()
    log.info("Job %s: %d frames publicados em %.2fs", job_id, indice, time.time() - t0)
    print(f"JOB_ID={job_id}", flush=True) 
    return 0

if __name__ == "__main__":
    sys.exit(main())