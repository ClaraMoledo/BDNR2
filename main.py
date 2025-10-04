from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
# ... (demais imports e configurações)

app = FastAPI()

# ... (demais configurações e rotas)

@app.get("/")
def home():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Chat Escolar - FastAPI</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700&family=Roboto:wght@400&display=swap" rel="stylesheet">
    <style>
        :root {
            --roxo: #7b2ff2;
            --vermelho: #f11a2a;
            --branco: #fff;
            --cinza: #222;
            --cinza-claro: #eee;
        }
        body {
            background: linear-gradient(135deg, var(--roxo) 60%, var(--vermelho) 100%);
            height: 100vh;
            margin: 0;
            font-family: 'Roboto', Arial, sans-serif;
            color: var(--branco);
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: rgba(34, 34, 34, 0.96);
            border-radius: 18px;
            box-shadow: 0 8px 24px 0 rgba(123,47,242,0.15), 0 4px 8px 0 rgba(241,26,42,0.08);
            padding: 2.5rem 2rem 2rem 2rem;
            max-width: 420px;
            width: 100%;
        }
        h1 {
            font-family: 'Montserrat', sans-serif;
            font-size: 2.1rem;
            margin-bottom: 0.7rem;
            letter-spacing: 1.5px;
            color: var(--roxo);
            text-shadow: 1px 1px 4px var(--vermelho);
        }
        label {
            font-size: 1.1rem;
            margin-bottom: 0.2rem;
            color: var(--branco);
        }
        input[type="text"] {
            width: 100%;
            padding: 0.6rem;
            border-radius: 8px;
            border: none;
            background: var(--cinza-claro);
            margin-bottom: 1rem;
            font-size: 1rem;
            color: var(--cinza);
            outline: none;
            transition: box-shadow 0.2s;
        }
        input[type="text"]:focus {
            box-shadow: 0 0 0 2px var(--roxo);
        }
        button {
            width: 100%;
            padding: 0.7rem;
            border-radius: 12px;
            border: none;
            background: linear-gradient(90deg, var(--roxo), var(--vermelho));
            font-family: 'Montserrat', sans-serif;
            font-size: 1.15rem;
            color: var(--branco);
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 2px 8px 0 rgba(123,47,242,0.15), 0 1px 4px 0 rgba(241,26,42,0.08);
            transition: transform 0.15s;
        }
        button:hover {
            transform: scale(1.05);
            background: linear-gradient(90deg, var(--vermelho), var(--roxo));
        }
        #chat {
            background: var(--cinza);
            border-radius: 14px;
            height: 230px;
            overflow-y: auto;
            margin: 1.2rem 0 0.7rem 0;
            padding: 1rem;
            box-shadow: 0 1px 8px 0 rgba(123,47,242,0.10), 0 1px 4px 0 rgba(241,26,42,0.07);
        }
        .msg {
            margin-bottom: 0.7rem;
            padding: 0.5rem 0.9rem;
            border-radius: 9px;
            background: linear-gradient(90deg, var(--roxo) 75%, var(--vermelho) 100%);
            color: var(--branco);
            font-size: 1.07rem;
            box-shadow: 0 1px 4px 0 rgba(123,47,242,0.10), 0 1px 4px 0 rgba(241,26,42,0.08);
            animation: fadeIn 0.9s;
        }
        .msg.me {
            background: linear-gradient(90deg, var(--vermelho) 75%, var(--roxo) 100%);
            text-align: right;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(30px);}
            to { opacity: 1; transform: translateY(0);}
        }
        #msg, #sendBtn {
            display: inline-block;
            vertical-align: middle;
        }
        #msg {
            width: 74%;
            margin-right: 2%;
        }
        #sendBtn {
            width: 24%;
        }
        .footer {
            text-align: center;
            margin-top: 1.3rem;
            font-size: 0.97rem;
            color: #bdbdbd;
        }
        .userTag {
            color: var(--vermelho);
            font-weight: bold;
        }
        .roomTag {
            color: var(--roxo);
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>💬 Chat Escolar</h1>
        <form id="form">
            <label for="user">Usuário:</label>
            <input id="user" type="text" value="aluno123" autocomplete="off"/>
            <label for="room">Sala:</label>
            <input id="room" type="text" value="geral" autocomplete="off"/>
            <button type="submit">Entrar na Sala</button>
        </form>
        <div id="chat"></div>
        <input id="msg" type="text" placeholder="Digite sua mensagem..." autocomplete="off"/>
        <button id="sendBtn" onclick="sendMsg()">Enviar</button>
        <div class="footer">
            <span>@claramoledo</span>
        </div>
    </div>
    <script>
        let ws;
        let meuUsuario = "";
        let salaAtual = "";

        document.getElementById('form').onsubmit = (e) => {
            e.preventDefault();
            meuUsuario = document.getElementById('user').value;
            salaAtual = document.getElementById('room').value;
            ws = new WebSocket(`ws://${location.host}/ws/${salaAtual}/${meuUsuario}`);
            document.getElementById('chat').innerHTML = "";
            ws.onmessage = (msg) => {
                try {
                    let obj = eval("(" + msg.data + ")");
                    let tag = "<span class='userTag'>" + obj.user + "</span>";
                    let sala = "<span class='roomTag'>#" + obj.room + "</span>";
                    let hora = new Date(obj.timestamp*1000).toLocaleTimeString('pt-BR',{hour: '2-digit', minute:'2-digit'});
                    let cls = obj.user == meuUsuario ? "msg me" : "msg";
                    document.getElementById('chat').innerHTML += `<div class="${cls}">${tag} ${sala} <span style="font-size:0.93em;color:#eee;">[${hora}]</span>:<br>${obj.text}</div>`;
                } catch {
                    // Mensagem de texto normal ou erro de rate limit
                    document.getElementById('chat').innerHTML += `<div class="msg">${msg.data}</div>`;
                }
                document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
            };
        };
        function sendMsg() {
            if (ws && ws.readyState === 1) {
                let txt = document.getElementById('msg').value;
                if (txt.trim().length > 0) {
                    ws.send(txt);
                    document.getElementById('msg').value = "";
                }
            }
        }
        document.getElementById('msg').addEventListener('keyup', function(e) {
            if (e.key === 'Enter') sendMsg();
        });
    </script>
</body>
</html>
    """)