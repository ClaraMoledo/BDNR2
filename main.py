import time
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração Redis e MongoDB
REDIS_URL = "redis://localhost:6379/0"
MONGO_URL = "mongodb://localhost:27017"

redis_client = redis.from_url(REDIS_URL, decode_responses=True)
mongo_client = AsyncIOMotorClient(MONGO_URL)
mongo_db = mongo_client["chatdb"]
messages_collection = mongo_db["messages"]

# Rate limiting config
RATE_LIMIT = 5        # mensagens por minuto
RATE_LIMIT_WINDOW = 60  # segundos

async def check_rate_limit(user_id: str):
    key = f"rate:{user_id}"
    ts = int(time.time())
    async with redis_client.pipeline(transaction=True) as pipe:
        await pipe.zadd(key, {str(ts): ts})
        await pipe.zremrangebyscore(key, 0, ts - RATE_LIMIT_WINDOW)
        await pipe.zcard(key)
        await pipe.expire(key, RATE_LIMIT_WINDOW)
        res = await pipe.execute()
        count = res[2]
        if count > RATE_LIMIT:
            return False
        return True

async def set_user_online(room: str, user: str, ttl: int=30):
    key = f"online:{room}"
    await redis_client.hset(key, user, int(time.time()))
    await redis_client.expire(key, ttl)

async def get_online_users(room: str):
    key = f"online:{room}"
    users = await redis_client.hkeys(key)
    return users

async def save_message(room: str, user: str, msg: str):
    doc = {"room": room, "user": user, "msg": msg, "timestamp": int(time.time())}
    await messages_collection.insert_one(doc)
    # LPUSH (adiciona mensagem recente) + LTRIM (mantém só as últimas 100)
    redis_key = f"messages:{room}"
    await redis_client.lpush(redis_key, json.dumps(doc))
    await redis_client.ltrim(redis_key, 0, 99)

async def get_last_messages(room: str, limit: int=20):
    redis_key = f"messages:{room}"
    msgs = await redis_client.lrange(redis_key, 0, limit-1)
    return [json.loads(m) for m in msgs]

@app.websocket("/ws/{room}/{user}")
async def websocket_endpoint(websocket: WebSocket, room: str, user: str):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    redis_channel = f"room:{room}"

    await pubsub.subscribe(redis_channel)
    await set_user_online(room, user)

    try:
        # Enviar últimas mensagens ao conectar
        last_msgs = await get_last_messages(room)
        for msg in last_msgs:
            await websocket.send_json(msg)

        while True:
            # Receber mensagens do WebSocket
            data = await websocket.receive_text()
            if not await check_rate_limit(user):
                await websocket.send_text("Rate limit exceeded. Please wait.")
                continue

            msg_doc = {"room": room, "user": user, "msg": data, "timestamp": int(time.time())}
            await save_message(room, user, data)
            await redis_client.publish(redis_channel, json.dumps(msg_doc))
            await set_user_online(room, user)

            # Ler novas mensagens do canal Redis e enviar ao cliente
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.01)
                if message is None:
                    break
                payload = json.loads(message["data"])
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_json(payload)

    except WebSocketDisconnect:
        await redis_client.hdel(f"online:{room}", user)
        await pubsub.unsubscribe(redis_channel)
    finally:
        await pubsub.close()

@app.get("/online/{room}")
async def online_users(room: str):
    users = await get_online_users(room)
    return {"online_users": users}

@app.get("/")
async def get():
    return HTMLResponse("""
    <!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Chat Escolar - Roxo & Vermelho</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {
            --cor-roxo: #7c3aed;
            --cor-roxo-escuro: #4c1d95;
            --cor-vermelho: #ef4444;
            --cor-vermelho-escuro: #991b1b;
            --branco: #fff;
            --cinza: #f3f4f6;
        }
        body {
            background: linear-gradient(135deg, var(--cor-roxo), var(--cor-vermelho));
            font-family: 'Roboto', Arial, sans-serif;
            color: var(--branco);
            min-height: 100vh;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .chat-container {
            background: var(--cinza);
            box-shadow: 0 8px 32px 0 rgba(124,58,237,0.25), 0 1px 2px rgba(239,68,68,0.12);
            border-radius: 1.5rem;
            padding: 2rem;
            width: 100%;
            max-width: 420px;
            min-height: 480px;
            display: flex;
            flex-direction: column;
        }
        .chat-header {
            font-size: 2rem;
            font-weight: bold;
            background: linear-gradient(90deg, var(--cor-roxo-escuro), var(--cor-vermelho-escuro));
            color: transparent;
            background-clip: text;
            -webkit-background-clip: text;
            margin-bottom: 1.2rem;
            text-align: center;
            letter-spacing: 1px;
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            background: var(--branco);
            border-radius: 1rem;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 4px rgba(124,58,237,0.08);
        }
        .message {
            margin-bottom: 0.7rem;
            padding: 0.4rem 0.8rem;
            border-radius: 0.7rem;
            max-width: 80%;
            word-wrap: break-word;
        }
        .message.user {
            background: linear-gradient(90deg, var(--cor-roxo), var(--cor-vermelho));
            color: var(--branco);
            align-self: flex-end;
            text-align: right;
        }
        .message.other {
            background: linear-gradient(90deg, var(--cor-vermelho), var(--cor-roxo));
            color: var(--branco);
            align-self: flex-start;
            text-align: left;
        }
        .input-area {
            display: flex;
            gap: 0.6rem;
        }
        .input-area input, .input-area button {
            font-size: 1rem;
            border: none;
            outline: none;
            border-radius: 0.7rem;
            padding: 0.7rem 1rem;
        }
        .input-area input {
            flex: 1;
            background: var(--cinza);
            color: var(--cor-roxo-escuro);
        }
        .input-area button {
            background: linear-gradient(90deg, var(--cor-roxo), var(--cor-vermelho));
            color: var(--branco);
            font-weight: bold;
            cursor: pointer;
            transition: box-shadow 0.2s;
            box-shadow: 0 2px 8px rgba(239,68,68,0.15);
        }
        .input-area button:hover {
            box-shadow: 0 4px 16px rgba(124,58,237,0.25), 0 2px 4px rgba(239,68,68,0.22);
        }
        .user-form {
            margin-bottom: 1rem;
            display: flex;
            gap: 0.6rem;
        }
        .user-form input {
            flex: 1;
            padding: 0.7rem 1rem;
            border-radius: 0.7rem;
            border: 1px solid var(--cor-roxo-escuro);
            background: var(--cinza);
            color: var(--cor-vermelho-escuro);
        }
        .user-form button {
            background: linear-gradient(90deg, var(--cor-roxo), var(--cor-vermelho));
            color: var(--branco);
            font-weight: bold;
            border: none;
            padding: 0.7rem 1.2rem;
            border-radius: 0.7rem;
            cursor: pointer;
        }
        .online-users {
            margin-bottom: 1rem;
            font-size: 0.96rem;
            color: var(--cor-roxo-escuro);
        }
        .online-users span {
            background: var(--cor-roxo);
            color: var(--branco);
            border-radius: 0.5rem;
            padding: 0.2rem 0.6rem;
            margin-right: 0.25rem;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">Chat Escolar <span style="font-size:1.2rem;">💬</span></div>
        <form class="user-form" id="userForm">
            <input type="text" id="roomInput" placeholder="Sala (ex: turma1)" required>
            <input type="text" id="userInput" placeholder="Seu nome" required>
            <button type="submit">Entrar</button>
        </form>
        <div class="online-users" id="onlineUsers"></div>
        <div class="chat-messages" id="messages"></div>
        <form class="input-area" id="messageForm" style="display:none;">
            <input type="text" id="messageInput" placeholder="Digite sua mensagem..." autocomplete="off" required>
            <button type="submit">Enviar</button>
        </form>
    </div>
    <script>
        let ws = null;
        let user = "";
        let room = "";

        const messagesDiv = document.getElementById('messages');
        const onlineUsersDiv = document.getElementById('onlineUsers');
        const userForm = document.getElementById('userForm');
        const roomInput = document.getElementById('roomInput');
        const userInput = document.getElementById('userInput');
        const messageForm = document.getElementById('messageForm');
        const messageInput = document.getElementById('messageInput');

        function addMessage(msg, isUser) {
            const div = document.createElement('div');
            div.className = 'message ' + (isUser ? 'user' : 'other');
            div.innerHTML = `<b>${msg.user}:</b> ${msg.msg}`;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function renderOnline(users) {
            if (users.length === 0) {
                onlineUsersDiv.innerHTML = `Ninguém online`;
                return;
            }
            onlineUsersDiv.innerHTML = `<b>Online:</b> ` + users.map(u => `<span>${u}</span>`).join('');
        }

        async function fetchOnlineUsers() {
            if (!room) return;
            let resp = await fetch(`/online/${room}`);
            let data = await resp.json();
            renderOnline(data.online_users || []);
        }

        userForm.onsubmit = function(e) {
            e.preventDefault();
            user = userInput.value.trim();
            room = roomInput.value.trim();
            if (!user || !room) return;
            userForm.style.display = 'none';
            messageForm.style.display = '';
            connectWS();
            fetchOnlineUsers();
        };

        messageForm.onsubmit = function(e) {
            e.preventDefault();
            let msg = messageInput.value.trim();
            if (msg && ws && ws.readyState === 1) {
                ws.send(msg);
                messageInput.value = '';
            }
        };

        function connectWS() {
            ws = new WebSocket(`ws://${window.location.host}/ws/${room}/${user}`);
            ws.onopen = () => {
                addMessage({user: 'Sistema', msg: 'Você entrou na sala.'}, false);
            };
            ws.onmessage = (event) => {
                let data;
                try {
                    data = JSON.parse(event.data);
                } catch {
                    data = {user: 'Sistema', msg: event.data};
                }
                addMessage(data, data.user === user);
                fetchOnlineUsers();
            };
            ws.onclose = () => {
                addMessage({user: 'Sistema', msg: 'Você saiu da sala.'}, false);
                messageForm.style.display = 'none';
                userForm.style.display = '';
            };
        }
    </script>
</body>
</html>
    """)