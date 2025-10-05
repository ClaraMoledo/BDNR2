# Chat FastAPI + MongoDB + Redis

## Instalação

1. **Requisitos:** Docker e Docker Compose

2. **Clone o projeto:**
   ```bash
   git clone https://github.com/ClaraMoledo/BDNR2.git
   cd BDNR2
   ```

3. **Suba os containers:**
   ```bash
   docker-compose up --build
   ```

4. **Acesse:** [http://localhost:8000](http://localhost:8000)

## WebSocket

- Endpoint: `/ws/{room}/{user_id}`
- Recebe as últimas 50 mensagens da sala ao conectar
- Envia mensagem: retorna para todos na sala em tempo real
- Rate limit: 5 msgs/segundo por usuário/sala

## Estruturas Redis

- `recent:{room}` - LIST das 50 últimas mensagens
- `online:{room}` - SET de usuários online (TTL 60s)
- `rl:{room}:{user_id}` - STRING de rate limit

## MongoDB

- Todas as mensagens são persistidas na coleção `messages`
