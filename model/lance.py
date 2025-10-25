from pydantic import BaseModel
from datetime import datetime

class Lance(BaseModel):
    id_leilao: str
    id_usuario: str
    valor: float
    ts: datetime
    
    def to_dict(self):
        return {
            "id_leilao": self.id_leilao,
            "id_usuario": self.id_usuario,
            "valor": self.valor,
            "ts": self.ts.isoformat() if isinstance(self.ts, datetime) else self.ts
        }
