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

leiloes = [
    {
        "id": 1,
        "descricao": "Smartphone Samsung Galaxy S23",
        "inicio": datetime.now() + timedelta(seconds=10),
        "fim": datetime.now() + timedelta(seconds=60),
        "status": "aguardando"
    },
    {
        "id": 2,
        "descricao": "Notebook Dell Inspiron 15", 
        "inicio": datetime.now() + timedelta(seconds=30),
        "fim": datetime.now() + timedelta(seconds=90),
        "status": "aguardando"
    },

]

timers_finalizacao = {}

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='leilao_iniciado', exchange_type=ExchangeType.fanout, durable=False)
channel.exchange_declare(exchange='leilao_finalizado', exchange_type='direct', durable=True)

def iniciar_leilao(leilao):
    """Inicia um leilão e publica evento leilao_iniciado"""
    leilao["status"] = "ativo"
    
    evento = {
        "id": leilao["id"],
        "descricao": leilao["descricao"],
        "inicio": leilao["inicio"].isoformat(),
        "fim": leilao["fim"].isoformat(),
        "status": leilao["status"]
    }
    
    channel.basic_publish(
        exchange='leilao_iniciado',
        routing_key='leilao_iniciado',
        body=json.dumps(evento).encode('utf-8'),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
    )
    
    print(f"[LEILÃO] Iniciado leilão {leilao['id']}: {leilao['descricao']}")

def finalizar_leilao(leilao):
    """Finaliza um leilão e publica evento leilao_finalizado"""
    leilao["status"] = "encerrado"
    
    evento = {
        "id": leilao["id"]
    }
    
    channel.basic_publish(
        exchange='leilao_finalizado',
        routing_key='leilao_finalizado',
        body=json.dumps(evento).encode('utf-8'),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
    )
    
    print(f"[LEILÃO] Finalizado leilão {leilao['id']}: {leilao['descricao']}")

def agendar_leiloes():
    """Agenda o início de todos os leilões"""
    agora = datetime.now()
    
    for leilao in leiloes:
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

if __name__ == "__main__":
    print("[LEILÃO] Microsserviço de Leilão iniciado")
    print(f"[LEILÃO] {len(leiloes)} leilões configurados")
    
    try:
        agendar_leiloes()
        
        print("[LEILÃO] Pressione Ctrl+C para parar")
        while True:
            time.sleep(30)
            print(f"[LEILÃO] Status: {[(l['id'], l['status']) for l in leiloes]}")
            
    except KeyboardInterrupt:
        print("\n[LEILÃO] Parando microsserviço...")
        for timer in timers_finalizacao.values():
            if timer.is_alive():
                timer.cancel()
        connection.close()
        print("[LEILÃO] Microsserviço parado")