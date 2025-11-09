# MS Pagamento (pub/sub)
# • (0,1) Consome os eventos leilao_vencedor (ID do leilão, ID do vencedor, valor).
# • (0,2) Para cada evento consumido, ele chama o sistema externo e publica link_pagamento.
# • (0,2) Expõe endpoint que recebe notificações do provedor e publica status_pagamento.

import json
import threading
from typing import Optional

import pika
import requests
from pika.exchange_type import ExchangeType
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

URL_EXTERNAL_PAYMENT_SYSTEM = "http://localhost:8004"
RABBIT_HOST = "localhost"

app = FastAPI()

# Armazenar informações de pagamentos (memória)
pagamentos = {}

# ---- Modelo para notificação externa ----
class NotificacaoPagamento(BaseModel):
    id_pagamento: str
    status: str  # "aprovada" ou "recusada"
    detalhes: Optional[dict] = None

# ---- Funções auxiliares RabbitMQ ----
EVENTS = ['leilao_vencedor', 'link_pagamento', 'status_pagamento']

def declare_all(channel: pika.adapters.blocking_connection.BlockingChannel):
    for event_name in EVENTS:
        channel.exchange_declare(exchange=event_name, exchange_type=ExchangeType.direct, durable=True)
        channel.queue_declare(queue=event_name, durable=True)
        channel.queue_bind(exchange=event_name, queue=event_name, routing_key=event_name)

def publish_event(exchange: str, routing_key: str, payload: dict):
    """
    Abre uma conexão curta para publicar (seguro entre threads).
    """
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    try:
        ch = conn.channel()
        declare_all(ch)  # idempotente
        ch.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(payload).encode('utf-8'),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
        )
    finally:
        conn.close()

# ---- Sistema externo (mock/real) ----
def gerar_link_pagamento(id_leilao: str, id_vencedor: str, valor: float):
    try:
        response = requests.get(
            URL_EXTERNAL_PAYMENT_SYSTEM + '/gerar-link-pagamento',
            params={
                'callback_url': "http://localhost:8002/notificacao-pagamento",
                'id_vencedor': id_vencedor,
                'valor': valor
            },
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[PAGAMENTO] Erro ao gerar link de pagamento: {e}")
        return None

# ---- Callback do consumidor ----
def callback_leilao_vencedor(ch, method, props, body):
    """
    Callback para processar eventos de leilao_vencedor.
    """
    try:
        print("[PAGAMENTO] >> ENTROU no callback_leilao_vencedor")
        msg = json.loads(body.decode("utf-8"))
        id_leilao = msg.get("id_leilao")
        id_vencedor = msg.get("id_vencedor")
        valor = msg.get("valor")

        if id_leilao is None or id_vencedor is None or valor is None:
            print("[PAGAMENTO] Evento leilao_vencedor inválido - dados incompletos")
            ch.basic_ack(method.delivery_tag)
            return

        print(f"[PAGAMENTO] Processando leilão {id_leilao}, vencedor {id_vencedor}, valor {valor}")

        # Chama sistema externo
        resultado = gerar_link_pagamento(id_leilao, id_vencedor, valor)

        if resultado:
            id_pagamento = resultado["id_pagamento"]
            pagamentos[id_pagamento] = {
                "id_leilao": id_leilao,
                "id_vencedor": id_vencedor,
                "valor": valor,
                "status": resultado.get("status", "pendente")
            }

            # Publica link_pagamento (usa o MESMO canal — estamos na thread do consumidor)
            evento_link = {
                "id_pagamento": id_pagamento,
                "id_leilao": id_leilao,
                "id_vencedor": id_vencedor,
                "link_pagamento": resultado.get("link_pagamento"),
                "valor": valor
            }

            ch.basic_publish(
                exchange='link_pagamento',
                routing_key='link_pagamento',
                body=json.dumps(evento_link).encode('utf-8'),
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
            )

            print(f"[PAGAMENTO] Link de pagamento publicado para leilão {id_leilao}")

        ch.basic_ack(method.delivery_tag)

    except Exception as e:
        print(f"[PAGAMENTO] Erro ao processar leilao_vencedor: {e}")
        ch.basic_ack(method.delivery_tag)

# ---- Thread de consumo (conexão/canal criados NA MESMA THREAD) ----
def consume_rabbitmq_events():
    """
    Cria conexão e canal nesta thread e consome SOMENTE 'leilao_vencedor'.
    """
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    channel = connection.channel()
    declare_all(channel)

    def _dispatch(ch, method, props, body):
        if method.routing_key == 'leilao_vencedor':
            callback_leilao_vencedor(ch, method, props, body)
        else:
            ch.basic_ack(method.delivery_tag)

    channel.basic_consume(
        queue='leilao_vencedor',
        on_message_callback=_dispatch,
        auto_ack=False
    )

    print("[PAGAMENTO] Consumindo fila 'leilao_vencedor'…")
    try:
        channel.start_consuming()
    finally:
        try:
            channel.close()
        except:
            pass
        connection.close()

# ---- Endpoints FastAPI ----
@app.post("/notificacao-pagamento")
def receber_notificacao_pagamento(notificacao: NotificacaoPagamento):
    """
    Recebe notificações assíncronas do provedor externo (aprovada/recusada)
    e publica 'status_pagamento'.
    """
    try:
        id_pagamento = notificacao.id_pagamento
        status = notificacao.status.lower()

        if id_pagamento not in pagamentos:
            raise HTTPException(status_code=404, detail="Pagamento não encontrado")

        pagamento = pagamentos[id_pagamento]
        pagamento["status"] = status

        print(f"[PAGAMENTO] Notificação recebida: {id_pagamento} - {status}")

        evento_status = {
            "id_pagamento": id_pagamento,
            "id_leilao": pagamento["id_leilao"],
            "id_vencedor": pagamento["id_vencedor"],
            "valor": pagamento["valor"],
            "status": status,
            "detalhes": notificacao.detalhes
        }

        # Publica usando conexão curta (seguro fora da thread do consumer)
        publish_event('status_pagamento', 'status_pagamento', evento_status)
        print(f"[PAGAMENTO] Status de pagamento publicado: {status}")

        return {
            "message": "Notificação recebida com sucesso",
            "id_pagamento": id_pagamento,
            "status": status
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PAGAMENTO] Erro ao processar notificação: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pagamentos")
def listar_pagamentos():
    return pagamentos

@app.get("/pagamentos/{id_pagamento}")
def consultar_pagamento(id_pagamento: str):
    if id_pagamento not in pagamentos:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    return pagamentos[id_pagamento]

# ---- Lifecycle ----
@app.on_event("startup")
def startup_event():
    print("[PAGAMENTO] Inicializando consumidor RabbitMQ…")
    rabbitmq_thread = threading.Thread(target=consume_rabbitmq_events, daemon=True)
    rabbitmq_thread.start()
    print("[PAGAMENTO] Consumidor RabbitMQ iniciado")

if __name__ == "__main__":
    print("[PAGAMENTO] Microsserviço de Pagamento iniciado")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
