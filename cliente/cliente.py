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
from pika.exchange_type import ExchangeType
import threading
from queues import Queue
from model.lance import Lance
from model.leilao import Leilao

class Cliente:
    def __init__(self):
        self.leilao_iniciado_thread = None
        self.leiloes_interesse_threads: list[threading.Thread] = []
        self.interface_thread = None
        self.leiloes_disponiveis = set()

    
    def run(self):
        pass


    def iniciar_leilao_iniciado(self):
        self.connection_consumidor = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel_consumidor = self.connection_consumidor.channel()
        self.channel_consumidor.exchange_declare(exchange=Queue.leilao_iniciado, exchange_type=ExchangeType.fanout)
        self.leilao_iniciado = self.channel.queue_declare(queue='', exclusive=True)
        queue_name = self.leilao_iniciado.method.queue
        self.channel_consumidor.queue_bind(exchange=Queue.leilao_iniciado, queue=queue_name)
        self.channel_consumidor.basic_consume(queue=queue_name, on_message_callback=self.leilao_iniciado_callback, auto_ack=True)
        self.channel_consumidor.start_consuming()


    def leilao_iniciado_callback(self, ch, method, properties, body:Leilao):
        self.leiloes_disponiveis.add(body.id)
        print(f"[I] Leilao iniciado!\nID: {body.id}\nDescricao: {body.descricao}\nHorario de início: {body.inicio}\nHorario de fim: {body.fim}\n")
    
    
    def iniciar_leilao_interesse(self, id:int):
        _connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        _channel = _connection.channel()
        binding_key = f"{Queue.leilao_prefix}{id}"
        _channel.exchange_declare(exchange=binding_key, exchange_type=ExchangeType.direct)
        leilao_queue = _channel.queue_declare(queue=binding_key, exclusive=True)
        _channel.queue_bind(exchange=binding_key, queue=binding_key)
        _channel.basic_consume(queue=binding_key, on_message_callback=self.leilao_interesse_callback, auto_ack=True)
        _channel.start_consuming()
        
    
    def leilao_interesse_callback(self, ch, method, properties, body):
        pass