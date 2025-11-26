import { AfterViewInit, Component, OnInit, signal } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { RouterOutlet } from '@angular/router';
import { HttpService } from './services/http.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, ReactiveFormsModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App{
  protected readonly title = signal('leilao');
  public userId: string = '';
  public paymentURL: string = '';
  public createAuctionForm: FormGroup;
  public placeBidForm: FormGroup;
  public auctionList: any[] = [];
  public interestedAuctions: any[] = [];
  public notifications: any[] = [];
  public bids: any[] = [];


  constructor(private fb: FormBuilder, private httpService: HttpService) {
    this.createAuctionForm = this.fb.group({
      descricao: ['', [Validators.required, Validators.minLength(3)]],
      inicio: [Date.now().toLocaleString(), Validators.required],
      fim: [Date.now().toLocaleString(), Validators.required],
    });

    this.placeBidForm = this.fb.group({
      id_usuario: ['', [Validators.required, Validators.min(1)]],
      id_leilao: ['', [Validators.required, Validators.min(1)]],
      valor: ['', [Validators.required, Validators.min(0.01)]],
      ts: [new Date().toISOString().split('.')[0], Validators.required],
    });

    console.log('App component initialized');
  }

  criarLeilao() {
    const leilaoData = this.createAuctionForm.value;
    leilaoData.inicio = new Date(leilaoData.inicio).toISOString().split('.')[0];
    leilaoData.fim = new Date(leilaoData.fim).toISOString().split('.')[0];
    console.log('Criando leilão com os dados:', leilaoData);
    // Lógica para criar o leilão
    this.httpService.criarLeilaoEndpoint(leilaoData).subscribe({
      next: (response) => {
        console.log('Leilão criado com sucesso:', response);
        alert('Leilão criado com sucesso!');
        this.createAuctionForm.reset();
      },
      error: (error) => {
        console.error('Erro ao criar leilão:', error);
        alert('Erro ao criar leilão. Por favor, tente novamente.');
      }
    });
  }


  listarLeiloes() {
    this.httpService.consultarLeiloesEndpoint().subscribe({
      next: (response: any) => {
        this.auctionList = response;
        console.log('Leilões recuperados com sucesso:', this.auctionList);
      },
      error: (error) => {
        console.error('Erro ao recuperar leilões:', error);
        alert('Erro ao recuperar leilões. Por favor, tente novamente.');
      }
    });
  }

  subscribeLeilao(leilaoId: number ) {
    this.httpService.registrarInteresseEndpoint({
      cliente_id: this.userId,
      leilao_id: leilaoId
    }).subscribe({
      next: (response) => {
        this.interestedAuctions.push(leilaoId);
        console.log('Inscrição no leilão realizada com sucesso:', response);
        alert('Inscrição no leilão realizada com sucesso!');
        this.conectarEventos();
      },
      error: (error) => {
        console.error('Erro ao inscrever no leilão:', error);
        alert('Erro ao inscrever no leilão. Por favor, tente novamente.');
      }
    });
  }
  
  conectarEventos() {
    this.httpService.conectarEventosEndpoint(this.userId).subscribe({
      next: (data) => {
        console.log('Evento recebido:', data);
        alert(`Evento recebido: ${data}`);
        this.notifications.push(data);
      },
      error: (error) => {
        console.error('Erro na conexão de eventos:', error);
        alert('Erro na conexão de eventos. Por favor, tente novamente.');
      }
    });
  }

  publicarLance() {
    let lanceData = this.placeBidForm.value;
    lanceData.ts = new Date().toISOString().split('.')[0];
    lanceData.id_usuario = this.userId;
    console.log('Publicando lance com os dados:', lanceData);
    // Lógica para publicar o lance
    this.httpService.darLanceEndpoint(lanceData).subscribe({
      next: (response) => {
        if (!this.interestedAuctions.includes(lanceData.id_leilao)) {
          this.subscribeLeilao(lanceData.id_leilao);
        }
        console.log('Lance publicado com sucesso:', response);
        alert('Lance publicado com sucesso!');
        this.placeBidForm.reset();
      },
      error: (error) => {
        console.error('Erro ao publicar lance:', error);
        alert('Erro ao publicar lance. Por favor, tente novamente.');
      }
    });
  }

  realizarPagamento() {
    console.log('Realizando pagamento para a URL:', this.paymentURL);
    this.httpService.realizarPagamentoEndpoint(this.paymentURL).subscribe({
      next: (response) => {
        console.log('Pagamento realizado com sucesso:', response);
        alert(`Pagamento realizado com sucesso para a URL: ${this.paymentURL}`);
      },
      error: (error) => {
        console.error('Erro ao realizar pagamento:', error);
        alert('Erro ao realizar pagamento. Por favor, tente novamente.');
      }
    });     
    alert(`Pagamento realizado com sucesso para a URL: ${this.paymentURL}`);
  }

}
