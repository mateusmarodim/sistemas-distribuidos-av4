# Cliente (publisher e subscriber)
# • Não se comunica diretamente com nenhum serviço, toda a
# comunicação é indireta através de filas de mensagens.
# • (0,1) Logo ao inicializar, atuará como consumidor recebendo
# eventos da fila leilao_iniciado. Os eventos recebidos contêm ID do
# leilão, descrição, data e hora de início e fim.

# • (0,2) Possui um par de chaves pública/privada. Publica lances na
# fila de mensagens lance_realizado. Cada lance contém: ID do
# leilão, ID do usuário, valor do lance. O cliente assina digitalmente
# cada lance com sua chave privada.
# • (0,2) Ao dar um lance em um leilão, o cliente atuará como
# consumidor desse leilão, registrando interesse em receber
# notificações quando um novo lance for efetuado no leilão de seu
# interesse ou quando o leilão for encerrado. Por exemplo, se o
# cliente der um lance no leilão de ID 1, ele escutará a fila leilao_1.
import os
import threading
import pika
from pika.exchange_type import ExchangeType
from queues import Queue
from model.lance import Lance
from model.leilao import Leilao, EventoLeilaoFinalizado
from Crypto.PublicKey import RSA

class Cliente:
    def __init__(self):
        self.leilao_iniciado_thread = None
        self.leiloes_interesse_threads: dict[int,threading.Thread] = {}
        self.interface_thread = None
        self.leiloes_disponiveis = set()
        self.lock: threading.Lock = threading.Lock()

    
    def run(self):
        print(os.getcwd())
        pass


    def gerar_chaves_rsa(self, id: int):
        try:
            key = RSA.generate(2048)
            private_key = key.export_key()
            with open("private.pem", "wb") as f:
                f.write(private_key)

            public_key = key.publickey().export_key()
            with open("receiver.pem", "wb") as f:
                f.write(public_key)

        except Exception as e:
            pass


    def iniciar_leilao_iniciado(self):
        self.connection_leilao_iniciado = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel_leilao_iniciado = self.connection_leilao_iniciado.channel()
        self.channel_leilao_iniciado.exchange_declare(exchange=Queue.leilao_iniciado, exchange_type=ExchangeType.fanout)
        self.leilao_iniciado = self.channel.queue_declare(queue='', exclusive=True)
        queue_name = self.leilao_iniciado.method.queue
        self.channel_leilao_iniciado.queue_bind(exchange=Queue.leilao_iniciado, queue=queue_name)
        self.channel_leilao_iniciado.basic_consume(queue=queue_name, on_message_callback=self.leilao_iniciado_callback, auto_ack=True)
        self.channel_leilao_iniciado.start_consuming()


    def leilao_iniciado_callback(self, ch, method, properties, body:Leilao):
        self.lock.acquire()
        self.leiloes_disponiveis.add(body.id)
        self.lock.release()
        print(f"[I] Leilão iniciado!\nID: {body.id}\nDescrição: {body.descricao}\nHorário de início: {body.inicio}\nHorário de fim: {body.fim}\n")


    def iniciar_leilao_interesse(self, id:int):
        _connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        _channel = _connection.channel()
        routing_key = f"{Queue.leilao_prefix}{id}"
        _channel.exchange_declare(exchange=routing_key, exchange_type=ExchangeType.direct)
        leilao_queue = _channel.queue_declare(queue="", exclusive=True)
        _channel.queue_bind(exchange=routing_key, queue=leilao_queue.method.queue, routing_key=routing_key)
        _channel.basic_consume(queue=leilao_queue.method.queue, on_message_callback=self.leilao_interesse_callback, auto_ack=True)
        _channel.start_consuming()
        
    
    def leilao_interesse_callback(self, ch, method, properties, body):
        if isinstance(body, Lance):
            print(f"[I] Lance publicado no leilão {body.id_leilao}\nUsuário: {body.id_usuario}\nValor: {body.valor}")

        elif isinstance(body, EventoLeilaoFinalizado):
            print(f"[I] Leilão finalizado!\nID: {body.id_leilao}\nVencedor: Usuário {body.id_vencedor}\nValor: {body.valor}")
            self.lock.acquire()
            self.leiloes_disponiveis.discard(body.id_leilao)
            self.lock.release()


    def iniciar_lance_realizado(self):
        self.connection_lance_realizado = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel_lance_realizado = self.connection_lance_realizado.channel()
        self.channel_lance_realizado.exchange_declare(exchange=Queue.lance_realizado, exchange_type=ExchangeType.direct)

    
if __name__ == "__main__":
    try:
        cliente = Cliente()
        cliente.run()

    except KeyboardInterrupt:
        print("Interrupted")

