from dataclasses import dataclass

@dataclass
class Lance:
    id_leilao: int
    id_usuario: int
    valor: float

    @classmethod
    def from_dict(cls, data: dict):
        """Create a Lance instance from a dictionary"""
        return cls(
            id_leilao=data['id_leilao'],
            id_usuario=data['id_usuario'],
            valor=float(data['valor'])
        )

    def to_dict(self):
        """Convert the Lance instance to a dictionary"""
        return {
            'id_leilao': self.id_leilao,
            'id_usuario': self.id_usuario,
            'valor': self.valor
        }
