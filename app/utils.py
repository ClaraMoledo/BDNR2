import json
from app.config import redis

# Rate limit: 5 msg/sec por usuário/sala
async def rate_limit_check(room, user_id):
    key = f"rl:{room}:{user_id}"
    count = await redis.incr(key)
    await redis.expire(key, 1)
    return count <= 5

# Presença online
async def set_online(room, user_id):
    key = f"online:{room}"
    await redis.sadd(key, user_id)
    await redis.expire(key, 60)

# Histórico recente (máx. 50 mensagens)
async def add_recent(room, msg: dict):
    key = f"recent:{room}"
    await redis.lpush(key, json.dumps(msg))
    await redis.ltrim(key, 0, 49)

async def get_recent(room):
    key = f"recent:{room}"
    raw_msgs = await redis.lrange(key, 0, 49)
    return [json.loads(m) for m in raw_msgs]