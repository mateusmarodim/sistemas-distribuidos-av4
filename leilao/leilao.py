# MS Leilão (publisher)
# • (0,1) Mantém internamente uma lista pré-configurada (hardcoded)
# de leilões com: ID do leilão, descrição, data e hora de início e fim,
# status (ativo, encerrado).
# • (0,1) O leilão de um determinado produto deve ser iniciado quando
# o tempo definido para esse leilão for atingido. Quando um leilão
# começa, ele publica o evento na fila: leilao_iniciado.
# • (0,1) O leilão de um determinado produto deve ser finalizado
# quando o tempo definido para esse leilão expirar. Quando um leilão
# termina, ele publica o evento na fila: leilao_finalizado.

import pika
import json
import threading
import time
from datetime import datetime, timedelta
from pika.exchange_type import ExchangeType
import uvicorn
from model.leilao import Leilao, StatusLeilao
from fastapi import FastAPI
from uuid import uuid4
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

app = FastAPI()

leiloes = []
timers_finalizacao = {}

# Lock para sincronizar acesso ao RabbitMQ
rabbitmq_lock = threading.Lock()

# Conexão separada para publicação
pub_connection = None
pub_channel = None


def init_publisher():
    """Inicializa conexão e canal para publicação"""
    global pub_connection, pub_channel
    pub_connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    pub_channel = pub_connection.channel()
    
    pub_channel.exchange_declare(exchange='leilao_iniciado', exchange_type=ExchangeType.fanout, durable=False)
    pub_channel.exchange_declare(exchange='leilao_finalizado', exchange_type='direct', durable=True)


def publicar_evento(exchange, routing_key, evento):
    """Função thread-safe para publicar eventos no RabbitMQ"""
    global pub_connection, pub_channel
    with rabbitmq_lock:
        try:
            # Verifica se precisa reconectar
            if pub_connection is None or pub_connection.is_closed or pub_channel is None or pub_channel.is_closed:
                print(f"[LEILÃO] Reconectando ao RabbitMQ...")
                init_publisher()
            
            pub_channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(evento).encode('utf-8'),
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
            )
            return True
        except Exception as e:
            print(f"[LEILÃO] Erro ao publicar evento: {e}")
            # Tentar reconectar e publicar novamente
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
                print(f"[LEILÃO] Erro na segunda tentativa: {e2}")
                return False


@app.get("/leilao")
def get_leiloes():
    return leiloes


class LeilaoCreate(BaseModel):
    descricao: str
    inicio: datetime
    fim: datetime
    # status will be set internally, do not require on input

@app.post("/leilao")
def criar_leilao(leilao: LeilaoCreate):
    try:
        leiloes.append({
            "id": uuid4().hex,
            "descricao": leilao.descricao,
            "inicio": leilao.inicio,
            "fim": leilao.fim,
            "status": StatusLeilao.AGUARDANDO.value
        })
    except Exception as e:
        return {"error": str(e)}
    agendar_leiloes()
    return {"message": "Leilão criado com sucesso"}


def iniciar_leilao(leilao):
    """Inicia um leilão e publica evento leilao_iniciado"""
    leilao["status"] = StatusLeilao.ATIVO.value

    evento = {
        "id": leilao["id"],
        "descricao": leilao["descricao"],
        "inicio": leilao["inicio"].isoformat(),
        "fim": leilao["fim"].isoformat(),
        "status": leilao["status"]
    }
    
    if publicar_evento('leilao_iniciado', 'leilao_iniciado', evento):
        print(f"[LEILÃO] Iniciado leilão {leilao['id']}: {leilao['descricao']}")
    else:
        print(f"[LEILÃO] ERRO ao iniciar leilão {leilao['id']}")


def finalizar_leilao(leilao):
    """Finaliza um leilão e publica evento leilao_finalizado"""
    leilao["status"] = StatusLeilao.ENCERRADO.value
    
    evento = {
        "id": leilao["id"]
    }
    
    if publicar_evento('leilao_finalizado', 'leilao_finalizado', evento):
        print(f"[LEILÃO] Finalizado leilão {leilao['id']}: {leilao['descricao']}")
    else:
        print(f"[LEILÃO] ERRO ao finalizar leilão {leilao['id']}")


def agendar_leiloes():
    """Agenda o início de todos os leilões"""
    agora = datetime.now()
    
    for leilao in leiloes:
        # Verifica se já foi agendado
        if leilao["id"] in timers_finalizacao:
            continue
            
        tempo_para_inicio = (leilao["inicio"] - agora).total_seconds()
        tempo_para_fim = (leilao["fim"] - agora).total_seconds()
        
        if tempo_para_fim > 0:
            timer_fim = threading.Timer(tempo_para_fim, finalizar_leilao, args=[leilao])
            timer_fim.start()
            timers_finalizacao[leilao["id"]] = timer_fim
            print(f"[LEILÃO] Agendado fim do leilão {leilao['id']} em {tempo_para_fim:.1f}s")
        
        if tempo_para_inicio > 0:
            timer_inicio = threading.Timer(tempo_para_inicio, iniciar_leilao, args=[leilao])
            timer_inicio.start()
            print(f"[LEILÃO] Agendado início do leilão {leilao['id']} em {tempo_para_inicio:.1f}s")
        else:
            print(f"[LEILÃO] Iniciando leilão {leilao['id']} imediatamente")
            iniciar_leilao(leilao)


@app.on_event("startup")
async def startup_event():
    """Inicializa publisher quando a aplicação inicia"""
    print("[LEILÃO] Inicializando publisher...")
    init_publisher()
    print("[LEILÃO] Publisher inicializado")


@app.on_event("shutdown")
async def shutdown_event():
    """Fecha conexões quando a aplicação encerra"""
    print("\n[LEILÃO] Parando microsserviço...")
    for timer in timers_finalizacao.values():
        if timer.is_alive():
            timer.cancel()
    with rabbitmq_lock:
        if pub_connection and not pub_connection.is_closed:
            pub_connection.close()
    print("[LEILÃO] Microsserviço parado")


if __name__ == "__main__":
    print("[LEILÃO] Microsserviço de Leilão iniciado")
    uvicorn.run(app, host="0.0.0.0", port=8001)