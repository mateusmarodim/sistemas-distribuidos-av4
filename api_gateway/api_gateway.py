from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Set
import httpx
import asyncio
import json
from datetime import datetime
import pika
from pika.exchange_type import ExchangeType
import threading
import uvicorn
from model.leilao import Leilao
from model.lance import Lance

app = FastAPI(title="API Gateway")

# Configurações dos microsserviços
LEILAO_SERVICE_URL = "http://localhost:8001"
LANCE_SERVICE_URL = "http://localhost:8000"

# Gerenciamento de clientes SSE
sse_clients: Dict[str, asyncio.Queue] = {}
client_interests: Dict[str, Set[str]] = {}  # client_id -> set of auction_ids

# Conexão RabbitMQ
consumer_connection = None
consumer_channel = None

# Models
class LeilaoCreate(BaseModel):
    descricao: str
    inicio: datetime
    fim: datetime

class LanceCreate(BaseModel):
    id_leilao: str
    id_usuario: str
    valor: float
    ts: datetime

class InterestRegister(BaseModel):
    cliente_id: str
    leilao_id: str

# Endpoints REST
@app.post("/leilao")
async def criar_leilao(leilao: Leilao):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LEILAO_SERVICE_URL}/leilao", 
                data=json.dumps(leilao.to_dict()).encode('utf-8')
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Erro ao criar leilão: {str(e)}")

@app.get("/leilao")
async def consultar_leiloes_ativos():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{LEILAO_SERVICE_URL}/leilao")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Erro ao consultar leilões: {str(e)}")

@app.post("/lance")
async def efetuar_lance(lance: Lance):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LANCE_SERVICE_URL}/lance", 
                json=json.dumps(lance.to_dict())
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(e)
            raise HTTPException(status_code=500, detail=f"Erro ao efetuar lance: {str(e)}")

@app.post("/interesses")
async def registrar_interesse(interest: InterestRegister):
    if interest.cliente_id not in client_interests:
        client_interests[interest.cliente_id] = set()
    client_interests[interest.cliente_id].add(interest.leilao_id)
    return {"message": "Interesse registrado com sucesso"}

@app.delete("/interesses/{cliente_id}/{leilao_id}")
async def cancelar_interesse(cliente_id: str, leilao_id: str):
    if cliente_id in client_interests:
        client_interests[cliente_id].discard(leilao_id)
    return {"message": "Interesse cancelado com sucesso"}

# SSE Endpoint
@app.get("/eventos/{cliente_id}")
async def sse_stream(cliente_id: str):
    queue = asyncio.Queue()
    sse_clients[cliente_id] = queue
    
    async def event_generator():
        try:
            # Enviar evento de conexão estabelecida
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Conectado ao stream de eventos'})}\n\n"
            
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            if cliente_id in sse_clients:
                del sse_clients[cliente_id]
            if cliente_id in client_interests:
                del client_interests[cliente_id]
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# RabbitMQ Consumer
def init_consumer():
    """Inicializa conexão e canal para consumo"""
    global consumer_connection, consumer_channel
    consumer_connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    consumer_channel = consumer_connection.channel()
    
    # Declarar exchanges (devem existir)
    consumer_channel.exchange_declare(exchange='lance_validado', exchange_type=ExchangeType.direct, durable=True)
    consumer_channel.exchange_declare(exchange='lance_invalidado', exchange_type=ExchangeType.direct, durable=True)
    consumer_channel.exchange_declare(exchange='leilao_vencedor', exchange_type=ExchangeType.direct, durable=True)
    consumer_channel.exchange_declare(exchange='link_pagamento', exchange_type=ExchangeType.direct, durable=True)
    consumer_channel.exchange_declare(exchange='status_pagamento', exchange_type=ExchangeType.direct, durable=True)
    
    # Declarar filas com os mesmos parâmetros dos outros microsserviços
    events = {
        'lance_validado': 'lance_validado',
        'lance_invalidado': 'lance_invalidado',
        'leilao_vencedor': 'leilao_vencedor',
        'link_pagamento': 'link_pagamento',
        'status_pagamento': 'status_pagamento'
    }
    
    for queue_name, routing_key in events.items():
        consumer_channel.queue_declare(queue=queue_name, durable=True)
        consumer_channel.queue_bind(
            exchange=queue_name,
            queue=queue_name,
            routing_key=routing_key
        )

def consume_rabbitmq_events():
    """Consome eventos do RabbitMQ e notifica clientes SSE"""
    global consumer_channel
    
    def callback(ch, method, properties, body):
        try:
            event_data = json.loads(body.decode('utf-8'))
            event_type = method.routing_key
            
            print(f"[API GATEWAY] Evento recebido: {event_type} - {event_data}")
            
            # Processar evento de forma assíncrona
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_event(event_type, event_data))
            loop.close()
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"[API GATEWAY] Erro ao processar evento: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    # Configurar consumidores para todas as filas
    events = ['lance_validado', 'lance_invalidado', 'leilao_vencedor', 
              'link_pagamento', 'status_pagamento']
    
    for event in events:
        consumer_channel.basic_consume(
            queue=event, 
            on_message_callback=callback, 
            auto_ack=False
        )
    
    print("[API GATEWAY] Consumidores RabbitMQ iniciados")
    consumer_channel.start_consuming()

async def process_event(event_type: str, event_data: dict):
    """Processa eventos e notifica clientes SSE interessados"""
    for client_id, queue in list(sse_clients.items()):
        try:
            # Verificar se o cliente tem interesse no leilão
            leilao_id = event_data.get('id_leilao')
            usuario_id = event_data.get('id_usuario') or event_data.get('id_vencedor')
            
            should_notify = False
            
            if event_type in ['lance_invalidado', 'link_pagamento', 'status_pagamento']:
                # Notificar apenas o usuário específico
                should_notify = (str(client_id) == str(usuario_id))
            elif event_type in ['lance_validado', 'leilao_vencedor']:
                # Notificar todos os interessados no leilão
                should_notify = (client_id in client_interests and 
                               leilao_id in client_interests[client_id])
            
            if should_notify:
                await queue.put({
                    "type": event_type,
                    "data": event_data,
                    "timestamp": datetime.now().isoformat()
                })
                print(f"[API GATEWAY] Evento {event_type} notificado para cliente {client_id}")
        except Exception as e:
            print(f"[API GATEWAY] Erro ao notificar cliente {client_id}: {e}")

@app.on_event("startup")
async def startup_event():
    """Inicializa consumidor RabbitMQ ao iniciar a aplicação"""
    print("[API GATEWAY] Inicializando consumidor RabbitMQ...")
    init_consumer()
    
    # Iniciar consumidor RabbitMQ em thread separada
    rabbitmq_thread = threading.Thread(target=consume_rabbitmq_events, daemon=True)
    rabbitmq_thread.start()
    print("[API GATEWAY] Consumidor RabbitMQ iniciado")

@app.on_event("shutdown")
async def shutdown_event():
    """Fecha conexões ao encerrar a aplicação"""
    print("[API GATEWAY] Encerrando...")
    if consumer_connection and not consumer_connection.is_closed:
        consumer_connection.close()
    print("[API GATEWAY] Conexões fechadas")

if __name__ == "__main__":
    print("[API GATEWAY] API Gateway iniciado")
    uvicorn.run(app, host="0.0.0.0", port=8003)