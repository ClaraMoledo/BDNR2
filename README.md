# FastAPI Chat com Redis e MongoDB

## Descrição

Chat em tempo real usando FastAPI, WebSockets, Redis (Pub/Sub, presença, rate limit, histórico) e MongoDB (persistência das mensagens).

## Instalação

1. Clone o repositório:
   ```
   git clone https://github.com/ClaraMoledo/BDNR2.git
   cd BDNR2
   ```

2. Crie o arquivo `requirements.txt` e adicione as dependências abaixo:
   ```
   fastapi
   uvicorn[standard]
   pymongo
   redis
   python-dotenv
   ```

3. Crie o arquivo `docker-compose.yml`:

   ```yaml
   # Use o conteúdo fornecido acima
   ```

4. Crie o arquivo `main.py`:

   ```python
   # Use o conteúdo fornecido acima
   ```

5. Execute:
   ```
   docker-compose up --build
   ```

6. Acesse `http://localhost:8000` para testar o chat.

## Funcionalidades

- Mensagens em tempo real via WebSocket.
- Rate limit: 1 mensagem por segundo por usuário.
- Presença online via Redis SET.
- Histórico das últimas 50 mensagens por sala (Redis LIST).
- Persistência das mensagens no MongoDB.
- Pub/Sub do Redis para distribuição eficiente.

## Observações

- O rate limit pode ser ajustado conforme necessidade.
- Toda a lógica principal está no `main.py`.
- O histórico é recuperado automaticamente ao conectar.