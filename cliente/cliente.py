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
import pika
import threading
from model.lance import Lance
from model.leilao import Leilao

class Cliente:
    def __init__(self):
        self.consumer_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.consumer_channel = self.consumer_connection.channel()
        self.producer_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.producer_channel = self.producer_connection.channel()
        self.consuming_thread = None
        self.interface_thread = None
        self.leiloes_interesse = set()


    def start_consuming(self):
        if self.consuming_thread is None:
            self.consuming_thread = threading.Thread(target=self.channel.start_consuming)
            self.consuming_thread.daemon = True
            self.consuming_thread.start()
            print("Ouvindo 'leilao_iniciado'...")


    def leilao_iniciado_setup(self):
        def leilao_iniciado_callback(ch, method, properties, body: Leilao):
            print("Leilão iniciado:", body)

        self.channel.exchange_declare(exchange='leilao_iniciado', exchange_type='fanout')
        self.leilao_iniciado = self.channel.queue_declare(queue='', exclusive=True)
        queue_name = self.leilao_iniciado.method.queue
        self.channel.queue_bind(exchange='leilao_iniciado', queue=queue_name)
        self.channel.basic_consume(queue=queue_name, on_message_callback=leilao_iniciado_callback, auto_ack=True)

    
    def lance_setup(self):
        self.producer_channel.exchange_declare(exchange='lance_realizado', exchange_type='direct')
        

    def publish_lance(self, lance: Lance):
        self.producer_channel.basic_publish(
            exchange='lance_realizado',
            routing_key='lance_realizado',
            body=lance
        )
        
        print("Lance publicado:", lance)
