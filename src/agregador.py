"""Agregador: recebe os frames processados (fora de ordem), reordena e remonta o vídeo final.

Ao terminar um job grava:
  /data/output/<job_id>_<filtro>.mp4   vídeo processado
  /data/output/<job_id>_stats.json     tempo total, throughput e distribuição de frames por worker
"""
import json
import os
import time
from collections import Counter, defaultdict

import cv2
import numpy as np

from comum import (FILA_CONTROLE, FILA_RESULTADOS, conectar, configurar_log,
                   declarar_filas)

PASTA_SAIDA = os.getenv("PASTA_SAIDA", "/data/output")
log = configurar_log("agregador")

class Job:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.filtro = "?"
        self.fps = 30.0
        self.t0 = None              
        self.total = None           
        self.proximo = 0            
        self.pendentes = {}         
        self.writer = None
        self.caminho = None
        self.frames_por_worker = Counter()
        self.tempo_por_worker = defaultdict(float)
        self.max_pendentes = 0

jobs: dict[str, Job] = {}

def obter_job(job_id: str) -> Job:
    if job_id not in jobs:
        jobs[job_id] = Job(job_id)
    return jobs[job_id]

def drenar(job: Job) -> None:
    """Escreve no vídeo todos os frames consecutivos disponíveis a partir de job.proximo."""
    while job.proximo in job.pendentes:
        img = cv2.imdecode(np.frombuffer(job.pendentes.pop(job.proximo), np.uint8), cv2.IMREAD_COLOR)
        if job.writer is None:
            os.makedirs(PASTA_SAIDA, exist_ok=True)
            altura, largura = img.shape[:2]
            job.caminho = os.path.join(PASTA_SAIDA, f"{job.job_id}_{job.filtro}.mp4")
            job.writer = cv2.VideoWriter(job.caminho, cv2.VideoWriter_fourcc(*"mp4v"), job.fps, (largura, altura))
        job.writer.write(img)
        job.proximo += 1
        if job.proximo % 100 == 0:
            total = job.total if job.total is not None else "?"
            log.info("job %s: %d/%s frames montados", job.job_id, job.proximo, total)

    if job.total is not None and job.proximo >= job.total:
        finalizar(job)

def finalizar(job: Job) -> None:
    if job.writer is not None:
        job.writer.release()
    duracao = time.time() - job.t0 if job.t0 else None
    stats = {
        "job_id": job.job_id,
        "filtro": job.filtro,
        "frames": job.total,
        "workers": len(job.frames_por_worker),
        "tempo_total_s": round(duracao, 2) if duracao else None,
        "frames_por_segundo": round(job.total / duracao, 2) if duracao and job.total else None,
        "max_frames_fora_de_ordem": job.max_pendentes,
        "por_worker": {
            w: {"frames": n, "tempo_medio_ms": round(job.tempo_por_worker[w] / n, 2)}
            for w, n in job.frames_por_worker.most_common()
        },
        "video": job.caminho,
    }
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    with open(os.path.join(PASTA_SAIDA, f"{job.job_id}_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    log.info("=" * 60)
    log.info("JOB %s CONCLUÍDO | filtro=%s | %s frames | %s workers", job.job_id, job.filtro, job.total, stats["workers"])
    log.info("tempo total: %ss | %s frames/s", stats["tempo_total_s"], stats["frames_por_segundo"])
    for w, d in stats["por_worker"].items():
        log.info("  %-20s %5d frames | %.1f ms/frame", w, d["frames"], d["tempo_medio_ms"])
    log.info("vídeo: %s", job.caminho)
    log.info("=" * 60)
    del jobs[job.job_id]

def ao_receber_resultado(canal, metodo, props, corpo):
    h = props.headers
    job = obter_job(h["job_id"])
    job.filtro, job.fps = h["filtro"], float(h["fps"])
    if h["indice"] >= job.proximo:  
        job.pendentes[h["indice"]] = corpo
        job.frames_por_worker[h["worker"]] += 1
        job.tempo_por_worker[h["worker"]] += float(h["tempo_ms"])
        job.max_pendentes = max(job.max_pendentes, len(job.pendentes))
    canal.basic_ack(delivery_tag=metodo.delivery_tag)
    drenar(job)

def ao_receber_controle(canal, metodo, props, corpo):
    msg = json.loads(corpo)
    job = obter_job(msg["job_id"])
    job.t0 = msg["t0"]
    if msg["tipo"] == "inicio":
        job.filtro, job.fps = msg["filtro"], float(msg["fps"])
        log.info("job %s iniciado (filtro=%s, entrada=%s)", job.job_id, job.filtro, msg.get("entrada"))
    elif msg["tipo"] == "fim":
        job.total = int(msg["total"])
        log.info("job %s: produtor terminou de enviar %d frames", job.job_id, job.total)
    canal.basic_ack(delivery_tag=metodo.delivery_tag)
    drenar(job)

def main():
    conexao = conectar()
    canal = conexao.channel()
    declarar_filas(canal)
    canal.basic_qos(prefetch_count=200)
    canal.basic_consume(queue=FILA_RESULTADOS, on_message_callback=ao_receber_resultado)
    canal.basic_consume(queue=FILA_CONTROLE, on_message_callback=ao_receber_controle)
    log.info("Aguardando resultados em '%s' e controle em '%s'...", FILA_RESULTADOS, FILA_CONTROLE)
    try:
        canal.start_consuming()
    except KeyboardInterrupt:
        canal.stop_consuming()
    conexao.close()

if __name__ == "__main__":
    main()