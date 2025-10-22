# MS Lance (publisher e subscriber)
# • Possui as chaves públicas de todos os clientes.
# • (0,2) Escuta os eventos das filas lance_realizado, leilao_iniciado
# e leilao_finalizado.
# • (0,3) Recebe lances de usuários (ID do leilão; ID do usuário, valor
# do lance) e checa a assinatura digital da mensagem utilizando a
# chave pública correspondente. Somente aceitará o lance se:
# o A assinatura for válida;
# o ID do leilão existir e se o leilão estiver ativo;
# o Se o lance for maior que o último lance registrado;
# • (0,1) Se o lance for válido, o MS Lance publica o evento na fila
# lance_validado.
# • (0,2) Ao finalizar um leilão, deve publicar na fila leilao_vencedor,
# informando o ID do leilão, o ID do vencedor do leilão e o valor
# negociado. O vencedor é o que efetuou o maior lance válido até o
# encerramento.

import pika
import os
import sys
import json, base64
from pika.exchange_type import ExchangeType
from fastapi import FastAPI
from model.lance import Lance
from model.leilao import StatusLeilao

app = FastAPI()

leilao_status = {}
leilao_vencedor = {}

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='leilao_iniciado', exchange_type=ExchangeType.fanout)
channel.exchange_declare(exchange='leilao_finalizado', exchange_type=ExchangeType.direct, durable=True)
channel.exchange_declare(exchange='lance_validado', exchange_type=ExchangeType.direct, durable=True)
channel.exchange_declare(exchange='lance_invalidado', exchange_type=ExchangeType.direct, durable=True)
channel.exchange_declare(exchange='leilao_vencedor', exchange_type=ExchangeType.direct, durable=True)



channel.queue_declare(queue='leilao_iniciado', durable=True)
channel.queue_bind(exchange="leilao_iniciado", queue='leilao_iniciado', routing_key='leilao_iniciado')
channel.queue_declare(queue='leilao_finalizado', durable=True)
channel.queue_bind(exchange="leilao_finalizado", queue='leilao_finalizado', routing_key='leilao_finalizado')

channel.queue_declare(queue='lance_validado', durable=True)
channel.queue_bind(exchange='lance_validado', queue='lance_validado', routing_key='lance_validado')
channel.queue_declare(queue='lance_invalidado', durable=True)
channel.queue_bind(exchange='lance_invalidado', queue='lance_invalidado', routing_key='lance_invalidado')
channel.queue_declare(queue='leilao_vencedor', durable=True)
channel.queue_bind(exchange='leilao_vencedor', queue='leilao_vencedor', routing_key='leilao_vencedor')

@app.post("/lance")
def receber_lance(lance: Lance):
    status, message = callback_lance_realizado(channel, lance)
    return {"status": status, "message": message}


def callback_lance_realizado(ch, lance: Lance):

    id_leilao = lance.id_leilao
    id_usuario = lance.id_usuario
    valor = lance.valor

    if id_leilao is None or id_usuario is None or valor is None:
        print(" [x] Lance inválido - dados incompletos")
        ch.basic_publish(exchange="lance_invalidado",
        routing_key="lance_invalidado",
        body=lance.to_dict().encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"))
        return False, 400, "Lance inválido - dados incompletos"

    try:
        id_leilao  = int(id_leilao)
        id_usuario = int(id_usuario)
        valor      = float(valor)
    except Exception as e:
        print(" [x] Lance inválido - tipagem incorreta")
        ch.basic_publish(exchange="lance_invalidado",
        routing_key="lance_invalidado",
        body=lance.to_dict().encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"))
        return False, 400, "Lance inválido - tipagem incorreta"
   
    status = leilao_status.get(id_leilao)
    if status != StatusLeilao.ATIVO.value:
        print(" [x] Lance inválido - leilão não ativo")
        ch.basic_publish(exchange="lance_invalidado",
        routing_key="lance_invalidado",
        body=lance.to_dict().encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"))
        return False, 400, "Lance inválido - leilão não está ativo"

    ultimo_lance = leilao_vencedor.get(id_leilao) or (None, None)
    if ultimo_lance[1] is not None and valor <= ultimo_lance[1]:
        print(" [x] Lance inválido - valor muito baixo")
        ch.basic_publish(exchange="lance_invalidado",
        routing_key="lance_invalidado",
        body=lance.to_dict().encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"))
        return False, 400, "Lance inválido - valor muito baixo"

    leilao_vencedor[id_leilao] = (id_usuario, valor)

    evento = {
        "id_leilao": id_leilao,
        "id_usuario": id_usuario,
        "valor": valor,
        "ts": lance.get("ts"),
    }
    ch.basic_publish(
        exchange="lance_validado",
        routing_key="lance_validado",
        body=json.dumps(evento).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
    )


def callback_leilao_iniciado(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
        id_leilao = msg.get("id")
        if id_leilao is None:
            print(" [x] Leilão inexistente")
            ch.basic_ack(method.delivery_tag); 
            return
        id_leilao = int(id_leilao)
        leilao_status[id_leilao] = StatusLeilao.ATIVO.value
        leilao_vencedor[id_leilao] = (None, None)
        ch.basic_ack(method.delivery_tag)
    except Exception as e:
        print(" [x] Erro leilao_iniciado:", e)
        ch.basic_ack(method.delivery_tag)


def callback_leilao_finalizado(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
        id_leilao = msg.get("id")

        if id_leilao is None:
            print(" [x] Invalid leilao_finalizado message")
            ch.basic_ack(method.delivery_tag); 
            return
        
        id_leilao = int(id_leilao)
        leilao_status[id_leilao] = "encerrado"

        vencedor = leilao_vencedor.get(id_leilao) or (None, None)
        evento = {
            "id_leilao": id_leilao,
            "id_vencedor": vencedor[0],
            "valor": vencedor[1],
        }
        ch.basic_publish(
            exchange="leilao_vencedor",
            routing_key="leilao_vencedor",
            body=json.dumps(evento).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json")
        )
        ch.basic_ack(method.delivery_tag)

    except Exception as e:
        print(" [x] Erro leilao_finalizado:", e)
        ch.basic_ack(method.delivery_tag)

channel.basic_consume(queue='leilao_iniciado', on_message_callback=callback_leilao_iniciado, auto_ack=False)
channel.basic_consume(queue='leilao_finalizado', on_message_callback=callback_leilao_finalizado, auto_ack=False)

channel.start_consuming()