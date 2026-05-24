from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models import (
    Conversation,
    ConversationParticipants,
    Message,
    User
)
from dependencies import db_session
from auth.service import get_current_user, oauth2_scheme
from .schemas import JoinGroupSchema, CreateGroupSchema
from manager import ConnectionManager

manager = ConnectionManager()

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post('/groups')
async def create_group(
    payload:CreateGroupSchema,
    db:db_session,
    token:str = Depends(oauth2_scheme)
    ):
    token_user = await get_current_user(db,token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    conversation = Conversation(
        is_group = True,
        name = payload.name
    )
    db.add(conversation)
    await db.flush()

    # User joining automatically
    creator = ConversationParticipants(
        conversation_id = conversation.id,
        user_id=token_user.id
    )
    db.add(creator)

    for user_id in payload.participants:
        if user_id == token_user.id:
            continue
        
        user_exists = await db.get(User,user_id)

        if not user_exists:
            continue

        db.add(
            ConversationParticipants(
                conversation_id = conversation.id,
                user_id=user_id
            )
        )

    await db.commit()

    return {
        "message": "Group created",
        "group_id": conversation.id
    }

@router.post('/groups/join')
async def join_group(
    payload:JoinGroupSchema,
    db:db_session,
    token:str = Depends(oauth2_scheme)
):
    token_user = await get_current_user(db,token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    conversation = await db.get(Conversation,payload.conversation_id)

    if not conversation:
        raise HTTPException(status_code=404,detail="Group not found")
    
    is_users_joined = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == payload.conversation_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(is_users_joined)

    already = result.scalar_one_or_none()

    if already:
        return {"message":"User already joined"}
    

    await db.commit()
    db.add(
        ConversationParticipants(
            conversation_id = conversation.id,
            user_id = token_user.id
        )
    )

    await manager.broadcast(str(conversation.id), {
        "type": "system",
        "event": "join",
        "user": token_user.username,
        "message": f"{token_user.username} joined group"
    })

    return {"message":"Joined group"}


@router.delete("/groups/{group_id}/leave")
async def leave_group(
    group_id: int,
    db: db_session,
    token: str = Depends(oauth2_scheme)
):

    token_user = await get_current_user(db, token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == group_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(stmt)

    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(404, "Not in group")

    await db.delete(participant)

    await db.commit()

    await manager.broadcast(str(group_id), {
        "type": "system",
        "event": "leave",
        "user": token_user.username,
        "message": f"{token_user.username} left group"
    })
    return {
        "message": "Left group"
    }

@router.get("/groups/{group_id}/messages")
async def get_messages(
    group_id: int,
    db: db_session,
    token: str = Depends(oauth2_scheme)
):

    token_user = await get_current_user(db, token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == group_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(stmt)

    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(403, "Not in group")

    query = (
        select(Message)
        .options(selectinload(Message.sender))
        .where(Message.conversation_id == group_id)
        .order_by(Message.timestamp.asc())
        .limit(100)
    )

    result = await db.execute(query)

    messages = result.scalars().all()

    return [
        {
            "id": m.id,
            "user": m.sender.username,
            "message": m.message,
            "time": m.timestamp.strftime("%H:%M:%S"),
            "type": "chat"
        }
        for m in messages
    ]


@router.get("/groups/{group_id}/users")
async def get_group_users(group_id: int, db: db_session, token: str = Depends(oauth2_scheme)):

    token_user = await get_current_user(db, token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == group_id
    )

    result = await db.execute(stmt)
    participants = result.scalars().all()

    all_users = []
    for p in participants:
        u = await db.get(User, p.user_id)
        all_users.append({"id": u.id, "username": u.username})

    online = manager.groups.get(str(group_id), {})

    return {
        "all": all_users,
        "online": [
            {"id": uid, "username": v["username"]}
            for uid, v in online.items()
        ]
    }


@router.get("/groups")
async def get_user_groups(
    db: db_session,
    token: str = Depends(oauth2_scheme)
):

    token_user = await get_current_user(db, token)

    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")

    print("Token User:-----",token_user)
    stmt = (
        select(Conversation)
        .join(ConversationParticipants)
        .where(
            ConversationParticipants.user_id == token_user.id
        )
    )

    result = await db.execute(stmt)

    groups = result.scalars().all()
    print("Groups:------",groups)
    return [
        {
            "id": g.id,
            "name": g.name
        }
        for g in groups
    ]