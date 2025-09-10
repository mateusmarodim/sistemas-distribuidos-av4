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
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

leilao_status = {}
leilao_vencedor = {}

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='lance_realizado', exchange_type=ExchangeType.direct, durable=True)
channel.exchange_declare(exchange='leilao_iniciado', exchange_type=ExchangeType.direct, durable=True)
channel.exchange_declare(exchange='leilao_finalizado', exchange_type=ExchangeType.direct, durable=True)
channel.exchange_declare(exchange='lance_validado', exchange_type='direct', durable=True)
channel.exchange_declare(exchange='leilao_vencedor', exchange_type='direct', durable=True)

channel.queue_declare(queue='lance_realizado', durable=True)
channel.queue_bind(exchange="lance_realizado", queue='lance_realizado', routing_key='lance_realizado')
channel.queue_declare(queue='leilao_iniciado', durable=True)
channel.queue_bind(exchange="leilao_iniciado", queue='leilao_iniciado', routing_key='leilao_iniciado')
channel.queue_declare(queue='leilao_finalizado', durable=True)
channel.queue_bind(exchange="leilao_finalizado", queue='leilao_finalizado', routing_key='leilao_finalizado')

channel.queue_declare(queue='lance_validado', durable=True)
channel.queue_bind(exchange='lance_validado', queue='lance_validado', routing_key='lance_validado')
channel.queue_declare(queue='leilao_vencedor', durable=True)
channel.queue_bind(exchange='leilao_vencedor', queue='leilao_vencedor', routing_key='leilao_vencedor')


def callback_lance_realizado(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
    except Exception as e:
        print(" [x] Invalid JSON")
        ch.basic_ack(method.delivery_tag)
        return
    
    lance     = msg.get("lance") or {}
    signature_headers = msg.get("signature_headers") or {}

    id_leilao = lance.get("id_leilao")
    id_usuario = lance.get("id_usuario")
    valor = lance.get("valor")
    sig_b64    = signature_headers.get("sig")

    if id_leilao is None or id_usuario is None or valor is None or not sig_b64:
        print(" [x] Invalid lance_realizado message")
        ch.basic_ack(method.delivery_tag)
        return

    try:
        id_leilao  = int(id_leilao)
        id_usuario = int(id_usuario)
        valor      = float(valor)
    except Exception as e:
        print(" [x] Tipagem inválida em lance_realizado")
        ch.basic_ack(method.delivery_tag)
        return
    
    local_chave = f"{os.getcwd()}/chaves_publicas/usuario_{id_usuario}_public.pem"
    try:
        key = RSA.import_key(open(local_chave, "rb").read())
    except Exception as e:
        print(f" [x] Falha ao carregar chave pública: {e}")
        ch.basic_ack(method.delivery_tag)
        return
    
    message_bytes = json.dumps({
        "id_leilao": id_leilao,
        "id_usuario": id_usuario,
        "valor": valor,
        "ts": lance.get("ts"),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = SHA256.new(message_bytes)

    try:
        signature = base64.b64decode(sig_b64)
        pkcs1_15.new(key).verify(h, signature)
    except (ValueError, TypeError):
        print(" [x]  Assinatura inválida")
        ch.basic_ack(method.delivery_tag)
        return       

    status = leilao_status.get(id_leilao)
    if status != "ativo":
        print(" [x] Lance inválido")
        ch.basic_ack(method.delivery_tag)
        return        
    ultimo_lance = leilao_vencedor.get(id_leilao) or (None, None)
    if ultimo_lance[1] is not None and valor <= ultimo_lance[1]:
        print(" [x] Lance inválido")
        ch.basic_ack(method.delivery_tag)
        return
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
    )

    ch.basic_ack(method.delivery_tag)

def callback_leilao_iniciado(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
        id_leilao = msg.get("id_leilao")
        if id_leilao is None:
            print(" [x] Invalid leilao_iniciado message")
            ch.basic_ack(method.delivery_tag); 
            return
        id_leilao = int(id_leilao)
        leilao_status[id_leilao] = "ativo"
        leilao_vencedor[id_leilao] = (None, None)
        ch.basic_ack(method.delivery_tag)
    except Exception as e:
        print(" [x] Erro leilao_iniciado:", e)
        ch.basic_ack(method.delivery_tag)

def callback_leilao_finalizado(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
        id_leilao = msg.get("id_leilao")

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
        )
        ch.basic_ack(method.delivery_tag)

    except Exception as e:
        print(" [x] Erro leilao_finalizado:", e)
        ch.basic_ack(method.delivery_tag)

channel.basic_consume(queue='lance_realizado', on_message_callback=callback_lance_realizado, auto_ack=False)
channel.basic_consume(queue='leilao_iniciado', on_message_callback=callback_leilao_iniciado, auto_ack=False)
channel.basic_consume(queue='leilao_finalizado', on_message_callback=callback_leilao_finalizado, auto_ack=False)

channel.start_consuming()