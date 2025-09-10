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
import sys
import threading
import pika
from pika.exchange_type import ExchangeType
from queues import Queue
from config import Config
from model.lance import Lance
from model.leilao import Leilao, EventoLeilaoFinalizado
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15

class Cliente:
    def __init__(self):
        self.leilao_iniciado_thread = None
        self.leiloes_interesse_threads: dict[int,threading.Thread] = {}
        self.leiloes_disponiveis = set()
        self.lock: threading.Lock = threading.Lock()


    def iniciar_cliente(self):
        print("Leilão APP\nIniciando cliente...")
        try:
            self.id = self.get_id()
            print(f"Cliente {self.id} iniciado.")
        except Exception as e:
            print(e)
            try:
                sys.exit(0)
            except SystemExit:
                os._exit(0)

        self.gerar_chaves_rsa(self.id)
        self.setup_lance_realizado()

        

    def iniciar_interface(self):
        self.print_menu()
        while True:
            comando = input()
            self.handle_comando(comando)


    @staticmethod
    def print_menu():
        print("Para dar um lance, digite:\nLANCE ID_DO_LEILAO VALOR_DO_LANCE\n\nPara sair, digite: SAIR\n\nPara exibir o menu novamente, digite MENU\n")


    def handle_comando(self, comando: str):
        comando = comando.strip()
        comando_prefix = comando.split(" ")[0].strip()
        match comando_prefix:
            case "LANCE":
                self.realizar_lance(comando)
            case "SAIR":
                try:
                    sys.exit(0)
                except SystemExit:
                    os._exit(0)
            case "MENU":
                self.print_menu()


    def realizar_lance(self, comando: str):
        comando = comando.split(" ")
        id_leilao = comando[1]
        valor_lance = comando[2]
        lance = Lance(id_leilao=id_leilao, id_usuario=self.id, valor=valor_lance)
        mensagem = self.construir_mensagem(lance)
        self.channel_lance_realizado.basic_publish(exchange=Queue.lance_realizado, routing_key=f"{Queue.lance_prefix}{str(id_leilao)}", body=mensagem)


    def construir_mensagem(self, lance: Lance):
        mensagem = bytes(str(lance))
        hash = SHA256.new(mensagem)
        assinatura = pkcs1_15.new(self.private_key).sign(hash)

        return {"mensagem": mensagem, "assinatura": assinatura}


    @staticmethod
    def get_id():
        filenames = os.listdir(f"{Config.PRIVATE_KEYS_DIR}")
        for i in range(1, Config.MAX_CLIENTS):
            filename = f"{i}_priv.pem"
            if filename not in filenames:
                return i

        raise Exception("Número máximo de clientes excedido!")


    def gerar_chaves_rsa(self, id: int):
        try:
            key = RSA.generate(2048)
            self.private_key = key.export_key()
            
            with open(f"{Config.PRIVATE_KEYS_DIR}{id}_priv.pem", "wb") as f:
                f.write(self.private_key)

            public_key = key.publickey().export_key()
            with open(f"{Config.PUBLIC_KEYS_DIR}{id}_pub.pem", "wb") as f:
                f.write(public_key)

        except Exception as e:
            print(f"Erro ao gerar chaves RSA! {e}")


    def iniciar_leilao_iniciado_thread(self):
        self.leilao_iniciado_thread = threading.Thread(target=self.setup_leilao_iniciado)
        self.leilao_iniciado_thread.daemon = True
        self.leilao_iniciado_thread.start()

    def setup_leilao_iniciado(self):
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


    def iniciar_leilao_interesse_thread(self, id:int):
        if id in self.leiloes_interesse_threads:
            return
        
        thread = threading.Thread(target=self.setup_leilao_interesse, args=(id,))
        thread.daemon = True
        thread.start()
        self.leiloes_interesse_threads[id] = thread
        

    def setup_leilao_interesse(self, id:int):
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


    def setup_lance_realizado(self):
        self.connection_lance_realizado = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel_lance_realizado = self.connection_lance_realizado.channel()
        self.channel_lance_realizado.exchange_declare(exchange=Queue.lance_realizado, exchange_type=ExchangeType.direct)

    
if __name__ == "__main__":
    try:
        cliente = Cliente()
        cliente.run()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
            
