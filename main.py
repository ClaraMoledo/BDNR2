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



from fastapi.responses import HTMLResponse

@app.get("/")
async def home():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Conversa Local - Chat Luxuoso</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Roboto:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
    --roxo: #5B21B6;
    --roxo-claro: #BFA3F4;
    --vermelho: #F43F5E;
    --vermelho-claro: #FCA5A5;
    --gradiente: linear-gradient(120deg, #5B21B6 0%, #F43F5E 100%);
    --cinza-bg: #f6f6f9;
    --branco: #fff;
    --cinza-card: #f9fafc;
    --cinza-borda: #ececec;
    --cinza-texto: #222;
    --cinza-claro: #e0e7ef;
    --cinza-medio: #bdbdbd;
    --fonte: 'Montserrat', 'Roboto', Arial, sans-serif;
    --azul: #312E81;
}
body {
    background: var(--cinza-bg);
    font-family: var(--fonte);
    min-height: 100vh;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}
@media (max-width: 600px) {
    .chat-card { padding: 1rem; min-width: 98vw;}
    .chat-header {font-size: 1.35rem;}
}
.chat-card {
    background: var(--branco);
    border-radius: 2.2rem;
    box-shadow: 0 16px 40px rgba(91,33,182,0.14), 0 2px 10px rgba(244,63,94,0.07);
    padding: 2.6rem 2.6rem 1.3rem 2.6rem;
    width: 100%;
    max-width: 440px;
    min-height: 540px;
    display: flex;
    flex-direction: column;
    gap: 1.2rem;
    animation: fadeIn 1.2s cubic-bezier(.62,.2,.24,.94);
    border: 1.5px solid var(--cinza-borda);
    position: relative;
}
@keyframes fadeIn {
    from { opacity: 0; transform: scale(.96);}
    to { opacity: 1; transform: scale(1);}
}
.chat-header {
    font-size: 2.5rem;
    font-weight: 700;
    background: var(--gradiente);
    color: transparent;
    background-clip: text;
    -webkit-background-clip: text;
    letter-spacing: 1.5px;
    text-align: center;
    margin-bottom: 0.7rem;
    user-select: none;
    text-shadow: 0 2px 12px #dfd7f9;
}
.user-form {
    display: flex; gap: 0.8rem; margin-bottom: 0.5rem;
}
.user-form input {
    flex: 1;
    font-size: 1.1rem;
    border-radius: 1.1rem;
    padding: 1rem 1.3rem;
    border: 1.5px solid var(--cinza-medio);
    background: var(--cinza-claro);
    color: var(--cinza-texto);
    font-family: inherit;
    outline: none;
    transition: border-color .3s, box-shadow .2s;
    box-shadow: 0 1px 6px rgba(91,33,182,0.04);
}
.user-form input:focus { border-color: var(--vermelho); }
.user-form button {
    background: var(--gradiente);
    color: var(--branco);
    font-weight: 700;
    border: none;
    padding: 1rem 1.5rem;
    border-radius: 1.1rem;
    cursor: pointer;
    font-family: inherit;
    font-size: 1.1rem;
    letter-spacing: .5px;
    box-shadow: 0 2px 12px rgba(91,33,182,0.10);
    transition: box-shadow .2s, transform .2s;
}
.user-form button:hover {
    box-shadow: 0 8px 22px rgba(244,63,94,0.14);
    transform: scale(1.04);
}
.online-users {
    margin-bottom: 0.8rem;
    font-size: 1.09rem;
    color: var(--azul);
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    align-items: center;
    min-height: 1.3rem;
}
.online-users span {
    background: var(--gradiente);
    color: var(--branco);
    border-radius: 0.8rem;
    padding: 0.2rem 1rem;
    margin-right: 0.2rem;
    font-weight: 700;
    font-size: 1.02rem;
    display: inline-block;
    box-shadow: 0 1px 4px rgba(91,33,182,0.10);
    letter-spacing: .3px;
    animation: popIn .7s cubic-bezier(.62,.2,.24,.94);
}
@keyframes popIn { from {transform: scale(0.85);} to {transform: scale(1);} }
.chat-messages {
    flex: 1;
    overflow-y: auto;
    background: var(--cinza-card);
    border-radius: 1.7rem;
    padding: 1.1rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 8px rgba(91,33,182,0.06);
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    border: 1px solid var(--cinza-borda);
}
.message {
    margin-bottom: 0.4rem;
    padding: 1rem 1.4rem;
    border-radius: 1.4rem;
    max-width: 85%;
    word-wrap: break-word;
    box-shadow: 0 2px 18px rgba(244,63,94,0.08);
    position: relative;
    animation: fadeMsg .7s cubic-bezier(.62,.2,.24,.94);
    font-size: 1.13rem;
    color: #2d2940;
    font-family: 'Montserrat', Arial, sans-serif;
    border: 1px solid #f3e8ff;
}
@keyframes fadeMsg { from { opacity: 0; transform: translateY(16px);} to { opacity: 1; transform: none;} }
.message.user {
    background: linear-gradient(90deg, #f1eafe 60%, #ffe4ec 100%);
    color: var(--roxo);
    align-self: flex-end;
    text-align: right;
    border-bottom-right-radius: 0.3rem;
    border-top-left-radius: 1.7rem;
    border: 1.5px solid #bfa3f4;
}
.message.other {
    background: linear-gradient(90deg, #ffe4ec 30%, #f1eafe 100%);
    color: var(--vermelho);
    align-self: flex-start;
    text-align: left;
    border-bottom-left-radius: 0.3rem;
    border-top-right-radius: 1.7rem;
    border: 1.5px solid #fca5a5;
}
.message .tag {
    font-size: 1.01rem;
    font-weight: bold;
    background: var(--gradiente);
    color: var(--branco);
    border-radius: 0.7rem;
    padding: 0.13rem 0.9rem;
    margin-right: 0.65rem;
    box-shadow: 0 1px 3px rgba(91,33,182,0.13);
}
.input-area {
    display: flex;
    gap: 0.8rem;
}
.input-area input, .input-area button {
    font-size: 1.1rem;
    border: none;
    outline: none;
    border-radius: 1.1rem;
    padding: 1rem 1.2rem;
    font-family: inherit;
}
.input-area input {
    flex: 1;
    background: var(--cinza-claro);
    color: #3c355c;
    border: 1.5px solid var(--cinza-borda);
}
.input-area input:focus { border-color: var(--roxo); }
.input-area button {
    background: var(--gradiente);
    color: var(--branco);
    font-weight: 700;
    cursor: pointer;
    font-size: 1.1rem;
    letter-spacing: .3px;
    box-shadow: 0 2px 12px rgba(244,63,94,0.13);
    transition: box-shadow .2s, transform .2s;
}
.input-area button:hover {
    box-shadow: 0 8px 22px rgba(91,33,182,0.20), 0 2px 8px rgba(244,63,94,0.22);
    transform: scale(1.04);
}
.sistema-msg {
    color: var(--vermelho);
    background: var(--cinza-claro);
    border-radius: 1.1rem;
    padding: 0.6rem 1.2rem;
    text-align: center;
    font-size: 1.15rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 10px rgba(91,33,182,0.11);
    letter-spacing: .3px;
}
::-webkit-scrollbar {
    width: 7px;
    background: var(--cinza-claro);
}
::-webkit-scrollbar-thumb {
    background: var(--roxo);
    border-radius: 5px;
}
</style>
</head>
<body>
<div class="chat-card">
    <div class="chat-header">Conversa Local <span style="font-size:1.5rem;">💬</span></div>
    <form class="user-form" id="userForm">
        <input type="text" id="roomInput" placeholder="Sala (ex: gourmet)" required>
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
    div.innerHTML = `<span class="tag">${msg.user}</span> ${msg.msg}`;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
function addSystemMessage(txt) {
    const div = document.createElement('div');
    div.className = 'sistema-msg';
    div.textContent = txt;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
function renderOnline(users) {
    if (!users || users.length === 0) {
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
        addSystemMessage('Bem-vindo(a)! Você entrou na sala.');
    };
    ws.onmessage = (event) => {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch {
            data = {user: 'Sistema', msg: event.data};
        }
        if(data.user && data.user === user){
            addMessage(data, true);
        } else {
            addMessage(data, false);
        }
        fetchOnlineUsers();
    };
    ws.onclose = () => {
        addSystemMessage('Você saiu da sala.');
        messageForm.style.display = 'none';
        userForm.style.display = '';
    };
}
</script>
</body>
</html>
""")