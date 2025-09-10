# MS Notificação (publisher e subscriber)
# • (0,2) Escuta os eventos das filas lance_validado e
# leilao_vencedor.
# • (0,2) Publica esses eventos nas filas específicas para cada leilão,
# de acordo com o seu ID (leilao_1, leilao_2, ...), de modo que
# somente os consumidores interessados nesses leilões recebam as
# notificações correspondentes.

import pika
import json

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

channel.exchange_declare(exchange='lance_validado', exchange_type='direct', durable=True)
channel.exchange_declare(exchange='leilao_vencedor', exchange_type='direct', durable=True)

channel.exchange_declare(exchange='leilao', exchange_type='direct', durable=True)

channel.queue_declare(queue='lance_validado', durable=True)
channel.queue_bind(exchange='lance_validado', queue='lance_validado', routing_key='lance_validado')
channel.queue_declare(queue='leilao_vencedor', durable=True)
channel.queue_bind(exchange='leilao_vencedor', queue='leilao_vencedor', routing_key='leilao_vencedor')

def callback_lance_validado(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
        aid = msg.get("id_leilao")
        if aid is None:
            print("[lance_validado] sem id_leilao; ignorando.")
            return

        qname = f"leilao_{int(aid)}"
        ch.queue_declare(queue=qname, durable=True) 
        ch.queue_bind(exchange='leilao', queue=qname, routing_key=qname)

        envelope = {"event": "lance_validado", "data": msg}
        ch.basic_publish(
            exchange='leilao',
            routing_key=qname,
            body=json.dumps(envelope).encode("utf-8"),
        )
        ch.basic_ack(method.delivery_tag)

    except Exception as e:
        print("[lance_validado] erro:", e)
        ch.basic_ack(method.delivery_tag)

def callback_leilao_vencedor(ch, method, props, body):
    try:
        msg = json.loads(body.decode("utf-8"))
        aid = msg.get("id_leilao")
        if aid is None:
            print("[leilao_vencedor] sem id_leilao; ignorando.")
            return

        qname = f"leilao_{int(aid)}"
        ch.queue_declare(queue=qname, durable=True)
        ch.queue_bind(exchange='leilao', queue=qname, routing_key=qname)

        envelope = {"event": "leilao_vencedor", "data": msg}
        ch.basic_publish(
            exchange='leilao',
            routing_key=qname,
            body=json.dumps(envelope).encode("utf-8"),
        )
        ch.basic_ack(method.delivery_tag)

    except Exception as e:
        print("[leilao_vencedor] erro:", e)
        ch.basic_ack(method.delivery_tag)


channel.basic_consume(queue='lance_validado',  on_message_callback=callback_lance_validado,  auto_ack=False)
channel.basic_consume(queue='leilao_vencedor', on_message_callback=callback_leilao_vencedor, auto_ack=False)

channel.start_consuming()