from pydantic import BaseModel
from datetime import datetime


class ParticipantOut(BaseModel):
    user_id: int
    conversation_id: int

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    sender_id: int
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: int
    is_group: bool
    name: str | None
    created_at: datetime

    participants: list[ParticipantOut]
    messages: list[MessageOut]

    class Config:
        from_attributes = True