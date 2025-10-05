# Chat Escolar - FastAPI, WebSocket, Redis & MongoDB

Um projeto de chat em tempo real, feito com FastAPI, WebSocket, Redis e MongoDB, com interface web estilizada em roxo e vermelho, pensado para trabalhos escolares ou universitários.

## Recursos

- **FastAPI**: Backend rápido e moderno
- **WebSocket**: Comunicação em tempo real entre navegador e servidor
- **Redis**: Armazenamento rápido para mensagens, presença online, rate limiting
- **MongoDB**: Persistência das mensagens do chat
- **Rate Limiting**: Limita o envio de mensagens por usuário
- **Presença Online**: Mostra quem está online na sala
- **UI colorida**: Front-end em HTML/CSS/JS com visual bonito, cores roxa e vermelha, responsivo, fácil de usar

---

## Como rodar

1. **Instale as dependências**

```bash
pip install -r requirements.txt
```

2. **Inicie o Redis e o MongoDB**
   - Redis: `redis-server`
   - MongoDB: `mongod`

3. **Execute o servidor FastAPI**

```bash
uvicorn main:app --reload
```

4. **Abra o arquivo `index.html` no navegador**  
   (ou acesse a rota `/` se o FastAPI estiver servindo o arquivo)

---

## Estrutura dos arquivos

- `main.py` - Backend FastAPI com WebSocket, Redis e MongoDB
- `requirements.txt` - Lista de dependências Python
- `index.html` - Interface colorida do chat
- `README.md` - Este guia

---

## Personalização

- **Cores**: Roxo e vermelho para destaque visual
- **Experiência do usuário**: Interface responsiva, fácil de usar, mensagens separadas por usuário, indicação de online

---

## Observações

- O chat usa WebSocket, então o navegador precisa suportar.
- Rate limiting protege contra spam.
- Presença online é automática e expira após alguns segundos sem atividade.
- As mensagens são armazenadas tanto no Redis (para velocidade) quanto no MongoDB (persistência).

---

## Créditos

Feito para fins educacionais e projetos de alunos!
