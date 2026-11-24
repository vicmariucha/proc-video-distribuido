"""Worker: consome frames da fila de tarefas, aplica o filtro e publica o resultado.
"""
import os
import socket
import time

import cv2
import numpy as np
import pika

from comum import (FILA_RESULTADOS, FILA_TAREFAS, PERSISTENTE, conectar,
                   configurar_log, declarar_filas)
from filtros import aplicar

WORKER_ID = os.getenv("WORKER_ID") or socket.gethostname()
log = configurar_log(f"worker {WORKER_ID}")

def processar(canal, metodo, props, corpo):
    h = dict(props.headers or {})
    try:
        img = cv2.imdecode(np.frombuffer(corpo, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("frame inválido")
        t = time.perf_counter()
        saida = aplicar(h["filtro"], img)
        tempo_ms = (time.perf_counter() - t) * 1000
        ok, buf = cv2.imencode(".jpg", saida, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise ValueError("falha ao codificar resultado")
    except Exception as e:  # mensagem venenosa: descarta sem reenfileirar
        log.error("Job %s frame %s descartado: %s", h.get("job_id"), h.get("indice"), e)
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=False)
        return

    h.update({"worker": WORKER_ID, "tempo_ms": f"{tempo_ms:.2f}"})
    canal.basic_publish(
        exchange="",
        routing_key=FILA_RESULTADOS,
        body=buf.tobytes(),
        properties=pika.BasicProperties(content_type="image/jpeg", delivery_mode=PERSISTENTE, headers=h),
    )
    canal.basic_ack(delivery_tag=metodo.delivery_tag)
    if h["indice"] % 50 == 0:
        log.info("job %s frame %d (%s) em %.1f ms", h["job_id"], h["indice"], h["filtro"], tempo_ms)

def main():
    conexao = conectar()
    canal = conexao.channel()
    declarar_filas(canal)
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(queue=FILA_TAREFAS, on_message_callback=processar)
    log.info("Aguardando frames em '%s'...", FILA_TAREFAS)
    try:
        canal.start_consuming()
    except KeyboardInterrupt:
        canal.stop_consuming()
    conexao.close()

if __name__ == "__main__":
    main()