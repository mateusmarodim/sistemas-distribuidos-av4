from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class StatusLeilao(Enum):
    ATIVO = "ativo"
    ENCERRADO = "encerrado"

@dataclass
class Leilao:
    id: int
    descricao: str
    inicio: datetime
    fim: datetime
    status: StatusLeilao | None