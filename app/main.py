import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings, redis
from app.models import MessageIn, MessageOut
from app.utils import rate_limit_check, set_online, get_recent, add_recent
import json
from datetime import datetime

app = FastAPI()

# MongoDB
mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
messages_collection = mongo_client.chatdb.messages

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}  # room: set(WebSocket)

    async def connect(self, ws: WebSocket, room: str):
        await ws.accept()
        self.active_connections.setdefault(room, set()).add(ws)

    def disconnect(self, ws: WebSocket, room: str):
        self.active_connections.get(room, set()).discard(ws)

    async def broadcast(self, room: str, message: dict):
        for ws in self.active_connections.get(room, []):
            await ws.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{room}/{user_id}")
async def chat_ws(ws: WebSocket, room: str, user_id: str):
    await manager.connect(ws, room)
    await set_online(room, user_id)
    # Envia histórico recente ao conectar
    recent = await get_recent(room)
    await ws.send_json({"type": "recent", "messages": recent})

    pubsub = redis.pubsub()
    await pubsub.subscribe(f"chat:{room}")

    try:
        async def redis_listener():
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    await manager.broadcast(room, json.loads(msg["data"]))

        listener_task = asyncio.create_task(redis_listener())

        while True:
            data = await ws.receive_json()
            msg_in = MessageIn(**data)
            allowed = await rate_limit_check(room, user_id)
            if not allowed:
                await ws.send_json({"type": "error", "message": "Rate limit exceeded!"})
                continue
            msg_out = MessageOut(
                user_id=user_id,
                room=room,
                content=msg_in.content,
                timestamp=datetime.utcnow().isoformat()
            )
            await messages_collection.insert_one(msg_out.dict())
            await add_recent(room, msg_out.dict())
            await redis.publish(f"chat:{room}", json.dumps(msg_out.dict()))

        await listener_task
    except WebSocketDisconnect:
        manager.disconnect(ws, room)
        await ws.close()
    finally:
        await pubsub.unsubscribe(f"chat:{room}")
        await pubsub.close()