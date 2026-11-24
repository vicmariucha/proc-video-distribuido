"""Configuração e utilitários compartilhados entre os módulos (conexão AMQP e nomes das filas)."""
import logging
import os
import time

import pika

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

FILA_TAREFAS = "video.tarefas"        
FILA_RESULTADOS = "video.resultados"  
FILA_CONTROLE = "video.controle"     

PERSISTENTE = 2 

def configurar_log(nome: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{nome}] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("pika").setLevel(logging.WARNING)
    return logging.getLogger(nome)

def conectar(tentativas: int = 30, intervalo: float = 2.0) -> pika.BlockingConnection:
    """Conecta ao RabbitMQ, tentando novamente enquanto o broker sobe."""
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
        heartbeat=600,
        blocked_connection_timeout=300,
    )
    ultimo_erro = None
    for _ in range(tentativas):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError as e:
            ultimo_erro = e
            time.sleep(intervalo)
    raise RuntimeError(f"Não foi possível conectar ao RabbitMQ em {RABBITMQ_HOST}:{RABBITMQ_PORT}") from ultimo_erro

def declarar_filas(canal) -> None:
    for fila in (FILA_TAREFAS, FILA_RESULTADOS, FILA_CONTROLE):
        canal.queue_declare(queue=fila, durable=True)