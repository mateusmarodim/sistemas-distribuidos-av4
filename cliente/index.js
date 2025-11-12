import { criarLeilaoEndpoint, darLanceEndpoint, consultarLeiloesEndpoint, registrarInteresseEndpoint, removerInteresseEndpoint, conectarEventosEndpoint } from './http.js';

const API_GATEWAY_URL = 'http://localhost:8003';

let userId = localStorage.getItem('userId');
let lance = null;
let novoLeilao = null;

const userForm = document.getElementById('userForm');
const createAuctionForm = document.getElementById('createAuctionForm');
const placeBidForm = document.getElementById('placeBidForm');

const criarLeilao = async () => {
    const descricao = document.getElementById('descricao').value;
    const inicio = document.getElementById('inicio').value;
    const fim = document.getElementById('fim').value;

    if (!descricao || !inicio || !fim) {
        alert('Por favor, preencha todos os campos.');
        return;
    }
    novoLeilao = { "descricao": descricao, "inicio": inicio, "fim": fim };

    const leilaoCriado = await criarLeilaoEndpoint(novoLeilao);
    console.log('Leilão criado:', leilaoCriado);
    alert('Leilão criado com sucesso!');
    listarLeiloes();
}

const listarLeiloes = async () => {
    const leiloes = await consultarLeiloesEndpoint();
    const tableBody = document.querySelector('#activeAuctionsTable tbody');
    tableBody.innerHTML = '';

    leiloes.forEach((leilao) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${leilao.id}</td>
            <td>${leilao.descricao}</td>
            <td>${leilao.inicio}</td>
            <td>${leilao.fim}</td>
            <td>${leilao.status || 'ativo'}</td>
            <td>${leilao.vencedor || '-'}</td>
        `;
        tableBody.appendChild(row);
    });
}

const publicarLance = async () => {
    const idLeilao = document.getElementById('idLeilao').value;
    const valor = parseFloat(document.getElementById('valor').value);

    if (!idLeilao || isNaN(valor)) {
        alert('Por favor, preencha todos os campos corretamente.');
        return;
    }
    const ts = new Date().toISOString();
    console.log(ts);
    lance = { "id_usuario": userId, "id_leilao": idLeilao, "valor": valor, "ts": ts};
    const lancePublicado = await darLanceEndpoint(lance);
    console.log('Lance publicado:', lancePublicado);
    alert('Lance publicado com sucesso!');
}



userForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const userIdInput = document.getElementById('userId');
    userId = userIdInput.value;
    localStorage.setItem('userId', userId);
    console.log(`User ID saved: ${userId}`);
});

createAuctionForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    await criarLeilao();
});

placeBidForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    await publicarLance();
});

setInterval(listarLeiloes, 5000);
listarLeiloes();
