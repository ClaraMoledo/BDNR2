from pydantic import BaseModel

class MessageIn(BaseModel):
    content: str

class MessageOut(BaseModel):
    user_id: str
    room: str
    content: str
    timestamp: str