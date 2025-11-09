from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import threading
import uuid
import time
import random
import uvicorn

app = FastAPI()

pagamentos_pendentes = {}

class CallbackData(BaseModel):
    id_pagamento: str
    aprovado: bool
    status: str


@app.get('/gerar-link-pagamento')
async def gerar_link_pagamento(callback_url: str = None, id_vencedor: str = '', valor: str = "100.00"):
    """
    Gera um link de pagamento e retorna o endpoint para realizar o pagamento
    """
    id_pagamento = str(uuid.uuid4())
    
    pagamentos_pendentes[id_pagamento] = {
        'status': 'pendente',
        'callback_url': callback_url,
        'id_vencedor': id_vencedor,
        'valor': valor
    }

    endpoint_pagamento = f"http://localhost:8004/realizar-pagamento/{id_pagamento}"

    return {
        'id_pagamento': id_pagamento,
        'link_pagamento': endpoint_pagamento,
        'status': pagamentos_pendentes[id_pagamento]['status'],
        'mensagem': f'Use o comando: curl -X POST {endpoint_pagamento}'
    }


@app.post('/realizar-pagamento/{id_pagamento}')
async def realizar_pagamento(id_pagamento: str):
    """
    Simula o pagamento via terminal
    """
    if id_pagamento not in pagamentos_pendentes:
        raise HTTPException(status_code=404, detail='Pagamento não encontrado')
    
    if pagamentos_pendentes[id_pagamento]['status'] != 'pendente':
        raise HTTPException(status_code=400, detail='Pagamento já processado')
    
    aprovado = random.choice([True, False])
    
    pagamentos_pendentes[id_pagamento]['status'] = 'aprovado' if aprovado else 'reprovado'
    
    callback_url = pagamentos_pendentes[id_pagamento]['callback_url']
    if callback_url:
        threading.Thread(target=enviar_callback, args=(callback_url, id_pagamento, aprovado)).start()
    
    return {
        'id_pagamento': id_pagamento,
        'status': 'aprovado' if aprovado else 'reprovado',
        'mensagem': 'Pagamento processado com sucesso'
    }


def enviar_callback(callback_url, id_pagamento, aprovado):
    """
    Envia POST ao microsserviço de pagamento informando o resultado
    """
    time.sleep(1)  # Pequeno delay para simular processamento
    
    try:
        response = requests.post(callback_url, json={
            'id_pagamento': id_pagamento,
            'aprovado': aprovado,
            'status': 'aprovado' if aprovado else 'reprovado'
        })
        print(f"Callback enviado: {response.status_code}")
    except Exception as e:
        print(f"Erro ao enviar callback: {e}")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8004)