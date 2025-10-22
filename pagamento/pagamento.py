# MS Pagamento (pub/sub)
# • (0,1) Consome os eventos leilao_vencedor (ID do leilão, ID do
# vencedor, valor).
# • (0,2) Para cada evento consumido, ele fará uma requisição REST ao
# sistema externo de pagamentos enviando os dados do pagamento
# (valor, moeda, informações do cliente) e, então, receberá um link de
# pagamento que será publicado em link_pagamento.
# • (0,2) Ele define um endpoint que recebe notificações assíncronas do
# sistema externo indicando o status da transação (aprovada ou
# recusada). Com base nos eventos externos recebidos, ele publica
# eventos status_pagamento, para que o API Gateway notifique o
# cliente via SSE.

import pika
import json
import threading
import requests
from pika.exchange_type import ExchangeType
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from uuid import uuid4

app = FastAPI()

# Armazenar informações de pagamentos
pagamentos = {}

# Conexão RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

# Declarar exchanges
channel.exchange_declare(exchange='leilao_vencedor', exchange_type=ExchangeType.direct, durable=True)
channel.exchange_declare(exchange='link_pagamento', exchange_type=ExchangeType.direct, durable=True)
channel.exchange_declare(exchange='status_pagamento', exchange_type=ExchangeType.direct, durable=True)

# Declarar e bind da fila leilao_vencedor
channel.queue_declare(queue='leilao_vencedor', durable=True)
channel.queue_bind(exchange='leilao_vencedor', queue='leilao_vencedor', routing_key='leilao_vencedor')

# Declarar filas para publicação
channel.queue_declare(queue='link_pagamento', durable=True)
channel.queue_bind(exchange='link_pagamento', queue='link_pagamento', routing_key='link_pagamento')
channel.queue_declare(queue='status_pagamento', durable=True)
channel.queue_bind(exchange='status_pagamento', queue='status_pagamento', routing_key='status_pagamento')


# Modelo para notificação externa
class NotificacaoPagamento(BaseModel):
    id_pagamento: str
    status: str  # "aprovada" ou "recusada"
    detalhes: str | None = None


def simular_sistema_externo_pagamento(id_leilao, id_vencedor, valor):
    """
    Simula uma requisição REST ao sistema externo de pagamentos.
    Em produção, isso seria uma chamada HTTP real para uma API externa.
    """
    try:
        # Em produção, faríamos algo como:
        # response = requests.post(
        #     "https://api-pagamento-externa.com/v1/pagamentos",
        #     json={
        #         "valor": valor,
        #         "moeda": "BRL",
        #         "cliente_id": id_vencedor,
        #         "descricao": f"Pagamento do leilão {id_leilao}"
        #     },
        #     headers={"Authorization": "Bearer TOKEN"}
        # )
        # link = response.json()["link_pagamento"]
        
        # Simulação de resposta do sistema externo
        id_pagamento = uuid4().hex
        link = f"https://pagamento-externo.com/pay/{id_pagamento}"
        
        print(f"[PAGAMENTO] Requisição ao sistema externo para leilão {id_leilao}")
        print(f"[PAGAMENTO] Link gerado: {link}")
        
        return {
            "id_pagamento": id_pagamento,
            "link_pagamento": link,
            "status": "pendente"
        }
    except Exception as e:
        print(f"[PAGAMENTO] Erro ao contactar sistema externo: {e}")
        return None


def callback_leilao_vencedor(ch, method, props, body):
    """
    Callback para processar eventos de leilao_vencedor.
    """
    try:
        msg = json.loads(body.decode("utf-8"))
        id_leilao = msg.get("id_leilao")
        id_vencedor = msg.get("id_vencedor")
        valor = msg.get("valor")
        
        if id_leilao is None or id_vencedor is None or valor is None:
            print("[PAGAMENTO] Evento leilao_vencedor inválido - dados incompletos")
            ch.basic_ack(method.delivery_tag)
            return
        
        # Se não há vencedor (leilão sem lances válidos), não processa pagamento
        if id_vencedor is None or valor is None:
            print(f"[PAGAMENTO] Leilão {id_leilao} não possui vencedor")
            ch.basic_ack(method.delivery_tag)
            return
        
        print(f"[PAGAMENTO] Processando leilão {id_leilao}, vencedor {id_vencedor}, valor {valor}")
        
        # Fazer requisição ao sistema externo de pagamentos
        resultado = simular_sistema_externo_pagamento(id_leilao, id_vencedor, valor)
        
        if resultado:
            # Armazenar informações do pagamento
            id_pagamento = resultado["id_pagamento"]
            pagamentos[id_pagamento] = {
                "id_leilao": id_leilao,
                "id_vencedor": id_vencedor,
                "valor": valor,
                "status": resultado["status"]
            }
            
            # Publicar evento link_pagamento
            evento_link = {
                "id_pagamento": id_pagamento,
                "id_leilao": id_leilao,
                "id_vencedor": id_vencedor,
                "link_pagamento": resultado["link_pagamento"],
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


@app.post("/notificacao-pagamento")
def receber_notificacao_pagamento(notificacao: NotificacaoPagamento):
    """
    Endpoint para receber notificações assíncronas do sistema externo
    sobre o status da transação (aprovada ou recusada).
    """
    try:
        id_pagamento = notificacao.id_pagamento
        status = notificacao.status.lower()
        
        if id_pagamento not in pagamentos:
            return {"error": "Pagamento não encontrado"}, 404
        
        # Atualizar status do pagamento
        pagamento = pagamentos[id_pagamento]
        pagamento["status"] = status
        
        print(f"[PAGAMENTO] Notificação recebida: {id_pagamento} - {status}")
        
        # Publicar evento status_pagamento
        evento_status = {
            "id_pagamento": id_pagamento,
            "id_leilao": pagamento["id_leilao"],
            "id_vencedor": pagamento["id_vencedor"],
            "valor": pagamento["valor"],
            "status": status,
            "detalhes": notificacao.detalhes
        }
        
        channel.basic_publish(
            exchange='status_pagamento',
            routing_key='status_pagamento',
            body=json.dumps(evento_status).encode('utf-8'),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
        )
        
        print(f"[PAGAMENTO] Status de pagamento publicado: {status}")
        
        return {
            "message": "Notificação recebida com sucesso",
            "id_pagamento": id_pagamento,
            "status": status
        }
        
    except Exception as e:
        print(f"[PAGAMENTO] Erro ao processar notificação: {e}")
        return {"error": str(e)}, 500


@app.get("/pagamentos")
def listar_pagamentos():
    """Endpoint para consultar todos os pagamentos."""
    return pagamentos


@app.get("/pagamentos/{id_pagamento}")
def consultar_pagamento(id_pagamento: str):
    """Endpoint para consultar um pagamento específico."""
    if id_pagamento not in pagamentos:
        return {"error": "Pagamento não encontrado"}, 404
    return pagamentos[id_pagamento]


def iniciar_consumidor():
    """Inicia o consumidor RabbitMQ em uma thread separada."""
    channel.basic_consume(
        queue='leilao_vencedor',
        on_message_callback=callback_leilao_vencedor,
        auto_ack=False
    )
    print("[PAGAMENTO] Aguardando eventos leilao_vencedor...")
    channel.start_consuming()


if __name__ == "__main__":
    print("[PAGAMENTO] Microsserviço de Pagamento iniciado")
    
    # Iniciar consumidor em thread separada
    consumidor_thread = threading.Thread(target=iniciar_consumidor, daemon=True)
    consumidor_thread.start()
    
    # Iniciar API FastAPI
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)