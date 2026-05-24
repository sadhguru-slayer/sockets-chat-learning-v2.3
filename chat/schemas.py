from pydantic import BaseModel, Field
from typing import List


class CreateGroupSchema(BaseModel):
    name: str
    participants: List[int] = Field(default_factory=list)


class JoinGroupSchema(BaseModel):
    conversation_id: int