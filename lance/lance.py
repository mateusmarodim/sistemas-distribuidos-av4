import pika
import os
import sys
import json, base64
from pika.exchange_type import ExchangeType
from fastapi import FastAPI
from model.lance import Lance
from model.leilao import StatusLeilao
import uvicorn
from threading import Thread, Lock
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

app = FastAPI()

leilao_status = {}
leilao_vencedor = {}

# Lock para sincronizar acesso ao RabbitMQ de publicação
rabbitmq_lock = Lock()

# Conexão separada para publicação (usada pela API FastAPI)
pub_connection = None
pub_channel = None

# Conexão separada para consumo (usada pela thread consumidora)
consumer_connection = None
consumer_channel = None

class LanceIn(BaseModel):
    id_leilao: str
    id_usuario: int | str
    valor: float
    ts: Optional[datetime] = None


def init_publisher():
    """Inicializa conexão e canal para publicação"""
    global pub_connection, pub_channel
    pub_connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    pub_channel = pub_connection.channel()
    
    # Declarar exchanges para publicação
    pub_channel.exchange_declare(exchange='lance_validado', exchange_type=ExchangeType.direct, durable=True)
    pub_channel.exchange_declare(exchange='lance_invalidado', exchange_type=ExchangeType.direct, durable=True)
    pub_channel.exchange_declare(exchange='leilao_vencedor', exchange_type=ExchangeType.direct, durable=True)


def init_consumer():
    """Inicializa conexão e canal para consumo"""
    global consumer_connection, consumer_channel
    consumer_connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    consumer_channel = consumer_connection.channel()
    
    # Declarar exchanges
    consumer_channel.exchange_declare(exchange='leilao_iniciado', exchange_type=ExchangeType.fanout)
    consumer_channel.exchange_declare(exchange='leilao_finalizado', exchange_type=ExchangeType.direct, durable=True)
    consumer_channel.exchange_declare(exchange='lance_validado', exchange_type=ExchangeType.direct, durable=True)
    consumer_channel.exchange_declare(exchange='lance_invalidado', exchange_type=ExchangeType.direct, durable=True)
    consumer_channel.exchange_declare(exchange='leilao_vencedor', exchange_type=ExchangeType.direct, durable=True)
    
    # Declarar e fazer bind das filas
    consumer_channel.queue_declare(queue='leilao_iniciado', durable=True)
    consumer_channel.queue_bind(exchange="leilao_iniciado", queue='leilao_iniciado')
    
    consumer_channel.queue_declare(queue='leilao_finalizado', durable=True)
    consumer_channel.queue_bind(exchange="leilao_finalizado", queue='leilao_finalizado', routing_key='leilao_finalizado')
    
    consumer_channel.queue_declare(queue='lance_validado', durable=True)
    consumer_channel.queue_bind(exchange='lance_validado', queue='lance_validado', routing_key='lance_validado')
    
    consumer_channel.queue_declare(queue='lance_invalidado', durable=True)
    consumer_channel.queue_bind(exchange='lance_invalidado', queue='lance_invalidado', routing_key='lance_invalidado')
    
    consumer_channel.queue_declare(queue='leilao_vencedor', durable=True)
    consumer_channel.queue_bind(exchange='leilao_vencedor', queue='leilao_vencedor', routing_key='leilao_vencedor')


def publicar_evento(exchange, routing_key, evento):
    """Função thread-safe para publicar eventos no RabbitMQ"""
    global pub_connection, pub_channel
    with rabbitmq_lock:
        try:
            # Verifica se precisa reconectar
            if pub_connection is None or pub_connection.is_closed or pub_channel is None or pub_channel.is_closed:
                print("[LANCE] Reconectando publisher ao RabbitMQ...")
                init_publisher()
            
            pub_channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(evento).encode('utf-8'),
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
            )
            return True
        except Exception as e:
            print(f"[LANCE] Erro ao publicar evento: {e}")
            # Tentar reconectar
            try:
                init_publisher()
                pub_channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=json.dumps(evento).encode('utf-8'),
                    properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
                )
                return True
            except Exception as e2:
                print(f"[LANCE] Erro na segunda tentativa: {e2}")
                return False


@app.post("/lance")
def receber_lance(lance: LanceIn):  # <- typed as Pydantic model
    print(lance)
    sucesso, codigo, mensagem = callback_lance_realizado(lance)
    if not sucesso:
        return {"status": "error", "message": mensagem}, codigo
    return {"status": "success", "message": mensagem}


def callback_lance_realizado(lance: LanceIn):
    id_leilao = lance.id_leilao
    id_usuario = lance.id_usuario
    valor = lance.valor

    if id_leilao is None or id_usuario is None or valor is None:
        print("[LANCE] Lance inválido - dados incompletos")
        publicar_evento("lance_invalidado", "lance_invalidado", lance.model_dump())
        return False, 400, "Lance inválido - dados incompletos"

    try:
        id_usuario = int(id_usuario)
        valor = float(valor)
    except Exception:
        print("[LANCE] Lance inválido - tipagem incorreta")
        publicar_evento("lance_invalidado", "lance_invalidado", lance.model_dump())
        return False, 400, "Lance inválido - tipagem incorreta"

    status = leilao_status.get(id_leilao)
    if status != StatusLeilao.ATIVO.value:
        print("[LANCE] Lance inválido - leilão não ativo")
        publicar_evento("lance_invalidado", "lance_invalidado", lance.model_dump())
        return False, 400, "Lance inválido - leilão não está ativo"

    ultimo_lance = leilao_vencedor.get(id_leilao) or (None, None)
    if ultimo_lance[1] is not None and valor <= ultimo_lance[1]:
        print("[LANCE] Lance inválido - valor muito baixo")
        publicar_evento("lance_invalidado", "lance_invalidado", lance.model_dump())
        return False, 400, "Lance inválido - valor muito baixo"

    leilao_vencedor[id_leilao] = (id_usuario, valor)

    evento = {
        "id_leilao": id_leilao,
        "id_usuario": id_usuario,
        "valor": valor,
        "ts": (lance.ts.isoformat() if lance.ts else None),
    }

    if publicar_evento("lance_validado", "lance_validado", evento):
        print(f"[LANCE] Lance validado: Leilão {id_leilao}, Usuário {id_usuario}, Valor {valor}")
        return True, 200, "Lance validado com sucesso"
    else:
        return False, 500, "Erro ao publicar lance validado"


def callback_leilao_iniciado(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
        id_leilao = msg.get("id")
        if id_leilao is None:
            print("[LANCE] Leilão inexistente")
            ch.basic_ack(method.delivery_tag); 
            return
        leilao_status[id_leilao] = StatusLeilao.ATIVO.value
        leilao_vencedor[id_leilao] = (None, None)
        print(f"[LANCE] Leilão {id_leilao} iniciado")
        ch.basic_ack(method.delivery_tag)
    except Exception as e:
        print(f"[LANCE] Erro leilao_iniciado: {e}")
        ch.basic_ack(method.delivery_tag)


def callback_leilao_finalizado(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
        id_leilao = msg.get("id")

        if id_leilao is None:
            print("[LANCE] Leilão inválido em leilao_finalizado")
            ch.basic_ack(method.delivery_tag); 
            return
        
        leilao_status[id_leilao] = StatusLeilao.ENCERRADO.value

        vencedor = leilao_vencedor.get(id_leilao) or (None, None)
        evento = {
            "id_leilao": id_leilao,
            "id_vencedor": vencedor[0],
            "valor": vencedor[1],
        }
        
        publicar_evento("leilao_vencedor", "leilao_vencedor", evento)
        print(f"[LANCE] Leilão {id_leilao} finalizado - Vencedor: {vencedor[0]}, Valor: {vencedor[1]}")
        ch.basic_ack(method.delivery_tag)

    except Exception as e:
        print(f"[LANCE] Erro leilao_finalizado: {e}")
        ch.basic_ack(method.delivery_tag)


def iniciar_consumidores():
    """Inicia o consumidor RabbitMQ em uma thread separada"""
    global consumer_channel
    consumer_channel.basic_consume(queue='leilao_iniciado', on_message_callback=callback_leilao_iniciado, auto_ack=False)
    consumer_channel.basic_consume(queue='leilao_finalizado', on_message_callback=callback_leilao_finalizado, auto_ack=False)
    print("[LANCE] Consumidores iniciados")
    consumer_channel.start_consuming()


if __name__ == "__main__":
    print("[LANCE] Microsserviço de Lance iniciado")
    
    # Inicializar conexão do publisher
    init_publisher()
    print("[LANCE] Publisher inicializado")
    
    # Inicializar conexão do consumer
    init_consumer()
    print("[LANCE] Consumer inicializado")
    
    # Iniciar consumidor em thread separada
    consumidor_thread = Thread(target=iniciar_consumidores, daemon=True)
    consumidor_thread.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)