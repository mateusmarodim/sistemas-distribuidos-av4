import axios from 'axios';

const http = axios.create({baseURL: 'http://localhost:8003/' });

const criarLeilaoEndpoint = async (leilao) => {
    const response = await http.post('/leilao', leilao);
    return response.data;
}
    
const consultarLeiloesEndpoint = async () => {
    const response = await http.get('/leilao');
    console.log(response);
    return response.data;
}

const darLanceEndpoint = async (lance) => {
    const response = await http.post('/lance', lance);
    console.log(response);
    return response.data;
}

const registrarInteresseEndpoint = async (interesse) => {
    const response = await http.post('/interesse', interesse);
    console.log(response);
    return response.data;
}

const removerInteresseEndpoint = async (clienteId, leilaoId) => {
    const response = await http.delete(`/interesse/${clienteId}/${leilaoId}`);
    console.log(response);
    return response.data;
}

const conectarEventosEndpoint = (clienteId, onMessage, onError) => {
    const eventSource = new EventSource(`http://localhost:8003/eventos/${clienteId}`);
    
    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onMessage(data);
        } catch (error) {
            console.error('Erro ao parsear evento:', error);
        }
    };
    
    eventSource.onerror = (error) => {
        console.error('Erro no SSE:', error);
        if (onError) onError(error);
    };
    
    eventSource.onopen = () => {
        console.log('Conexão SSE estabelecida');
    };
    
    return () => {
        eventSource.close();
        console.log('Conexão SSE fechada');
    };
}

export {
    criarLeilaoEndpoint,
    consultarLeiloesEndpoint,
    darLanceEndpoint,
    registrarInteresseEndpoint,
    removerInteresseEndpoint,
    conectarEventosEndpoint
};