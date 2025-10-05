from pydantic_settings import BaseSettings
import redis.asyncio as redis_async

class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://mongo:27017"
    REDIS_URI: str = "redis://redis:6379/0"

settings = Settings()
redis = redis_async.from_url(settings.REDIS_URI, decode_responses=True)