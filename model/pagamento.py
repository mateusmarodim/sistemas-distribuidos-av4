from dataclasses import dataclass
from enum import Enum

class StatusPagamento(Enum):
    PENDENTE = "pendente"
    APROVADA = "aprovada"
    RECUSADA = "recusada"

@dataclass
class Pagamento:
    id_pagamento: str
    id_leilao: int
    id_vencedor: int
    valor: float
    status: StatusPagamento
    link_pagamento: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create a Pagamento instance from a dictionary"""
        return cls(
            id_pagamento=data['id_pagamento'],
            id_leilao=data['id_leilao'],
            id_vencedor=data['id_vencedor'],
            valor=float(data['valor']),
            status=StatusPagamento(data['status']) if isinstance(data['status'], str) else data['status'],
            link_pagamento=data.get('link_pagamento')
        )
    
    def to_dict(self):
        """Convert Pagamento instance to dictionary"""
        return {
            'id_pagamento': self.id_pagamento,
            'id_leilao': self.id_leilao,
            'id_vencedor': self.id_vencedor,
            'valor': self.valor,
            'status': self.status.value if isinstance(self.status, StatusPagamento) else self.status,
            'link_pagamento': self.link_pagamento
        }

@dataclass
class EventoLinkPagamento:
    id_pagamento: str
    id_leilao: int
    id_vencedor: int
    link_pagamento: str
    valor: float
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create an EventoLinkPagamento instance from a dictionary"""
        return cls(
            id_pagamento=data['id_pagamento'],
            id_leilao=data['id_leilao'],
            id_vencedor=data['id_vencedor'],
            link_pagamento=data['link_pagamento'],
            valor=float(data['valor'])
        )
    
    def to_dict(self):
        """Convert EventoLinkPagamento instance to dictionary"""
        return {
            'id_pagamento': self.id_pagamento,
            'id_leilao': self.id_leilao,
            'id_vencedor': self.id_vencedor,
            'link_pagamento': self.link_pagamento,
            'valor': self.valor
        }

@dataclass
class EventoStatusPagamento:
    id_pagamento: str
    id_leilao: int
    id_vencedor: int
    valor: float
    status: str
    detalhes: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create an EventoStatusPagamento instance from a dictionary"""
        return cls(
            id_pagamento=data['id_pagamento'],
            id_leilao=data['id_leilao'],
            id_vencedor=data['id_vencedor'],
            valor=float(data['valor']),
            status=data['status'],
            detalhes=data.get('detalhes')
        )
    
    def to_dict(self):
        """Convert EventoStatusPagamento instance to dictionary"""
        return {
            'id_pagamento': self.id_pagamento,
            'id_leilao': self.id_leilao,
            'id_vencedor': self.id_vencedor,
            'valor': self.valor,
            'status': self.status,
            'detalhes': self.detalhes
        }
