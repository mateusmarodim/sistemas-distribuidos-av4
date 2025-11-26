import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { SseService } from './sse.service';

@Injectable({
  providedIn: 'root',
})
export class HttpService {
   private baseUrl = 'http://localhost:8003';

  constructor(private http: HttpClient, private sseService: SseService) {}

  criarLeilaoEndpoint(data: any) {
    return this.http.post(`${this.baseUrl}/leilao`, data);
  }

  consultarLeiloesEndpoint() {
    return this.http.get(`${this.baseUrl}/leilao`);
  }

  darLanceEndpoint(data: any) {
    return this.http.post(`${this.baseUrl}/lance`, data);
  }

  registrarInteresseEndpoint(data: any) {
    return this.http.post(`${this.baseUrl}/interesses`, data);
  }

  removerInteresseEndpoint(data: any) {
    return this.http.delete(`${this.baseUrl}/interesses/${data.userId}/${data.leilaoId}`, data);
  }

  conectarEventosEndpoint(userId: string): Observable<any> {
    const url = `${this.baseUrl}/eventos/${userId}`;
    return new Observable(observer => {
      const eventSource = this.sseService.getEventSource(url);

      eventSource.onmessage = event => {
        observer.next(event.data);
      }

      eventSource.onerror = error => {
        observer.error(error);
      }
    })
  }

  realizarPagamentoEndpoint(url: string) {
    return this.http.post(url, {});
  }
}