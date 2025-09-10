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

    @classmethod
    def from_dict(cls, data: dict):
        """Create a Leilao instance from a dictionary"""
        return cls(
            id=data['id'],
            descricao=data['descricao'],
            inicio=datetime.fromisoformat(data['inicio']) if isinstance(data['inicio'], str) else data['inicio'],
            fim=datetime.fromisoformat(data['fim']) if isinstance(data['fim'], str) else data['fim'],
            status=StatusLeilao(data['status']) if data.get('status') else None
        )
    
    def to_dict(self):
        """Convert Leilao instance to dictionary"""
        return {
            'id': self.id,
            'descricao': self.descricao,
            'inicio': self.inicio.isoformat(),
            'fim': self.fim.isoformat(),
            'status': self.status.value if self.status else None
        }

@dataclass
class EventoLeilaoFinalizado:
    id_leilao: int
    id_vencedor: int
    valor: float

    @classmethod
    def from_dict(cls, data: dict):
        """Create an EventoLeilaoFinalizado instance from a dictionary"""
        return cls(
            id_leilao=data['id_leilao'],
            id_vencedor=data['id_vencedor'],
            valor=float(data['valor'])
        )
    
    def to_dict(self):
        """Convert EventoLeilaoFinalizado instance to dictionary"""
        return {
            'id_leilao': self.id_leilao,
            'id_vencedor': self.id_vencedor,
            'valor': self.valor
        }