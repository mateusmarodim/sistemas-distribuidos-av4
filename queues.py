from enum import Enum

class Queue(Enum):
    leilao_iniciado="leilao_iniciado"
    leilao_finalizado="leilao_finalizado"
    leilao_vencedor="leilao_vencedor"
    leilao_prefix="leilao_"
    lance_realizado="lance_realizado"
    lance_validado="lance_validado"
    