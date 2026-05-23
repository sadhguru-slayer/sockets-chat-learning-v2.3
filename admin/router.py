from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from dependencies import db_session
from models import (
    User,
    Conversation,
    ConversationParticipants,
    Message
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)

# =========================================
# USERS
# =========================================

@router.get("/users")
async def get_users(db: db_session):

    result = await db.execute(
        select(User)
    )

    return result.scalars().all()


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: db_session):

    user = await db.get(User, user_id)

    if not user:
        raise HTTPException(404, "User not found")

    await db.delete(user)
    await db.commit()

    return {"message": "User deleted"}


# =========================================
# CONVERSATIONS
# =========================================

from .schemas import ConversationOut

@router.get("/conversations")
async def get_conversations(db: db_session):

    result = await db.execute(
        select(Conversation.id)
    )

    return result.scalars().all()

@router.post("/conversations")
async def create_conversation(
    name: str,
    is_group: bool,
    db: db_session
):

    convo = Conversation(
        name=name,
        is_group=is_group
    )

    db.add(convo)

    await db.commit()
    await db.refresh(convo)

    return convo


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: db_session
):

    convo = await db.get(
        Conversation,
        conversation_id
    )

    if not convo:
        raise HTTPException(404, "Conversation not found")

    await db.delete(convo)
    await db.commit()

    return {"message": "Conversation deleted"}


# =========================================
# MESSAGES
# =========================================

@router.get("/messages")
async def get_messages(db: db_session):

    result = await db.execute(
        select(Message)
    )

    return result.scalars().all()


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    db: db_session
):

    msg = await db.get(Message, message_id)

    if not msg:
        raise HTTPException(404, "Message not found")

    await db.delete(msg)

    await db.commit()

    return {"message": "Message deleted"}


@router.put("/messages/{message_id}")
async def edit_message(
    message_id: int,
    new_message: str,
    db: db_session
):

    msg = await db.get(Message, message_id)

    if not msg:
        raise HTTPException(404, "Message not found")

    msg.message = new_message

    await db.commit()

    return {
        "message": "Updated successfully"
    }


# =========================================
# PARTICIPANTS
# =========================================

@router.post("/conversations/{conversation_id}/participants/{user_id}")
async def add_participant(
    conversation_id: int,
    user_id: int,
    db: db_session
):

    participant = ConversationParticipants(
        conversation_id=conversation_id,
        user_id=user_id
    )

    db.add(participant)

    await db.commit()

    return {
        "message": "Participant added"
    }


@router.delete("/conversations/{conversation_id}/participants/{user_id}")
async def remove_participant(
    conversation_id: int,
    user_id: int,
    db: db_session
):

    participant = await db.get(
        ConversationParticipants,
        {
            "conversation_id": conversation_id,
            "user_id": user_id
        }
    )

    if not participant:
        raise HTTPException(404, "Participant not found")

    await db.delete(participant)

    await db.commit()

    return {
        "message": "Participant removed"
    }