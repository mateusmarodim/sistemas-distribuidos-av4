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
from model.lance import Lance
from model.leilao import Leilao, EventoLeilaoFinalizado
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15
import json
import base64
from datetime import datetime

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
        self.iniciar_leilao_iniciado_thread()
        self.iniciar_interface()

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
        id_leilao = int(comando[1])

        if id_leilao not in self.leiloes_disponiveis:
            print(f"[E] Leilão {id_leilao} não disponível!")
            return
        
        valor_lance = comando[2]
        lance = Lance(id_leilao=id_leilao, id_usuario=self.id, valor=valor_lance)
        mensagem = self.construir_mensagem(lance)
        self.channel_lance_realizado.basic_publish(exchange="lance_realizado", routing_key=f"lance_realizado", body=mensagem, properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"))
        
        if id_leilao not in self.leiloes_interesse_threads.keys():
            self.iniciar_leilao_interesse_thread(id_leilao)


    def construir_mensagem(self, lance: Lance):
        payload = {
            "id_leilao": lance.id_leilao,
            "id_usuario": lance.id_usuario,
            "valor": float(lance.valor),
            "ts": datetime.utcnow().isoformat() + "Z"
        }
        msg_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        h = SHA256.new(msg_bytes)
        assinatura = pkcs1_15.new(self.private_key).sign(h)
        return json.dumps({
            "lance": payload,
            "signature_headers": {"sig": base64.b64encode(assinatura).decode("utf-8")}
        })


    @staticmethod
    def get_id():
        filenames = os.listdir(f"{os.getcwd()}/chaves_privadas/")
        for i in range(1, 15):
            filename = f"usuario_{i}_private.pem"
            if filename not in filenames:
                return i

        raise Exception("Número máximo de clientes excedido!")


    def gerar_chaves_rsa(self, id: int):
        try:
            key = RSA.generate(2048)
            self.private_key = key
            
            private_key_bytes = key.export_key()
            with open(f"{os.getcwd()}/chaves_privadas/usuario_{id}_private.pem", "wb") as f:
                f.write(private_key_bytes)

            public_key = key.publickey().export_key()
            with open(f"{os.getcwd()}/chaves_publicas/usuario_{id}_public.pem", "wb") as f:
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
        self.channel_leilao_iniciado.exchange_declare(exchange="leilao_iniciado", exchange_type=ExchangeType.fanout)
        self.leilao_iniciado = self.channel_leilao_iniciado.queue_declare(queue='', exclusive=True)
        queue_name = self.leilao_iniciado.method.queue
        self.channel_leilao_iniciado.queue_bind(exchange="leilao_iniciado", queue=queue_name)
        self.channel_leilao_iniciado.basic_consume(queue=queue_name, on_message_callback=self.leilao_iniciado_callback, auto_ack=True)
        self.channel_leilao_iniciado.start_consuming()


    def leilao_iniciado_callback(self, ch, method, properties, body):
        leilao_data = json.loads(body.decode('utf-8'))
        leilao = Leilao.from_dict(leilao_data)
        
        with self.lock:
            self.leiloes_disponiveis.add(leilao.id)
        
        print(f"[I] Leilão iniciado!\nID: {leilao.id}\nDescrição: {leilao.descricao}\nHorário de início: {leilao.inicio}\nHorário de fim: {leilao.fim}\n")
    


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
        routing_key = f"leilao_{id}"
        _channel.exchange_declare(exchange="leilao", exchange_type=ExchangeType.direct, durable=True)
        leilao_queue = _channel.queue_declare(queue="", exclusive=True)
        _channel.queue_bind(exchange="leilao", queue=leilao_queue.method.queue, routing_key=routing_key)
        _channel.basic_consume(queue=leilao_queue.method.queue, on_message_callback=self.leilao_interesse_callback, auto_ack=True)
        _channel.start_consuming()
        
    
    def leilao_interesse_callback(self, ch, method, properties, body):
        try:
            msg = json.loads(body.decode("utf-8"))
            
            payload = msg.get("data", msg)

            if "id_leilao" in payload and "id_usuario" in payload and "valor" in payload:
            
                lance = Lance.from_dict(payload)
                print(f"[I] Lance publicado no leilão {lance.id_leilao}\nUsuário: {lance.id_usuario}\nValor: {lance.valor}")

            elif "id_vencedor" in payload:
                
                evento = EventoLeilaoFinalizado.from_dict(payload)
                print(f"[I] Leilão finalizado!\nID: {evento.id_leilao}\nVencedor: Usuário {evento.id_vencedor}\nValor: {evento.valor}")
                
                with self.lock:
                    self.leiloes_disponiveis.discard(evento.id_leilao)

        except Exception as e:
            print(f"Erro ao processar mensagem de interesse: {e}")

    def setup_lance_realizado(self):
        self.connection_lance_realizado = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel_lance_realizado = self.connection_lance_realizado.channel()
        self.channel_lance_realizado.exchange_declare(exchange="lance_realizado", exchange_type=ExchangeType.direct)
    

if __name__ == "__main__":
    try:
        cliente = Cliente()
        cliente.iniciar_cliente()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

