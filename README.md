
# Aplicação de Leilão

## Eventos e Notificações. Microsserviços. Chaves assimétricas.

**Microsserviços (MS)** são serviços menores e independentes. Cada
microsserviço é projetado para ter um conjunto de recursos e é dedicado à
solução de um problema específico. Vantagens do uso de Middlewares
Orientados a Mensagens em Microsserviços:
- **Desacoplamento**: os microsserviços podem operar de forma
independente, sem se conhecerem. Cada serviço escuta as filas que
interessa e reage de forma autônoma;
- **Escalabilidade**: se houver um aumento na demanda, podemos escalar
apenas os microsserviços que precisam de mais recursos (por exemplo,
aumentar a quantidade de instâncias de um MS);
- **Assincronismo**: os microsserviços podem processar suas tarefas em
paralelo, sem que um serviço precise esperar por outro para continuar.
Isso melhora o desempenho e a experiência do usuário;
- **Flexibilidade**: novos microsserviços podem ser facilmente adicionados
ao sistema.
Utilize qualquer linguagem de programação para desenvolver um sistema de
leilão composto por 3 microsserviços, cada um com uma responsabilidade
específica. Os microsserviços vão se comunicar exclusivamente via filas de
mensagens. O fluxo de dados é orquestrado por eventos através do serviço de
mensageria RabbitMQ e do protocolo AMQP que garantem a sincronização
entre as diferentes funcionalidades.