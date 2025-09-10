try:
    from enum import StrEnum  # available from Python 3.11


    class Queue(StrEnum):
        leilao_iniciado="leilao_iniciado"
        leilao_finalizado="leilao_finalizado"
        leilao_vencedor="leilao_vencedor"
        leilao_prefix="leilao_"
        lance_realizado="lance_realizado"
        lance_validado="lance_validado"
except ImportError:
    from enum import Enum


    class Queue(str, Enum):
        leilao_iniciado="leilao_iniciado"
        leilao_finalizado="leilao_finalizado"
        leilao_vencedor="leilao_vencedor"
        leilao_prefix="leilao_"
        lance_realizado="lance_realizado"
        lance_validado="lance_validado"