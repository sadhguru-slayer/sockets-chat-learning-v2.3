from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from models import (
    Conversation,
    ConversationParticipants,
    Message,
    User
)
from dependencies import db_session
from auth.service import get_current_user, oauth2_scheme
from .schemas import JoinGroupSchema, CreateGroupSchema,DMRequest
from manager import ConnectionManager
from redis_client import r
import json

manager = ConnectionManager()

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/dm")
async def initiate_direct_message(
    db:db_session,
    payload: DMRequest,
    token:str=Depends(oauth2_scheme),
):
    token_user = await get_current_user(db, token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_ids = payload.user_ids
    
    if len(user_ids) != 1:
        raise HTTPException(
            status_code=400,
            detail="You must provide exactly 1 other user"
        )
    other_user_id = user_ids[0]

    if other_user_id == token_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot DM yourself"
        )
    
    all_users = sorted([token_user.id, user_ids[0]])
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.participants))
        .join(ConversationParticipants)
        .where(Conversation.is_group == False)
        .group_by(Conversation.id)
        .having(
            func.count(ConversationParticipants.user_id) == 2
        )
        )
    result = await db.execute(stmt)
    conversations = result.scalars().unique().all()
    
    for c in conversations:
        participant_ids = sorted([p.user_id for p in c.participants])
    
        if participant_ids == all_users:
            return {
                "message": "DM already exists",
                "conversation_id": c.id
            }
    conversation = Conversation(
        is_group=False,
        name="DM"
    )
    db.add(conversation)
    await db.flush()
    db.add_all([
        ConversationParticipants(
            conversation_id=conversation.id,
            user_id=token_user.id
        ),
        ConversationParticipants(
            conversation_id=conversation.id,
            user_id=other_user_id
        )
    ])
    await db.commit()
    return {
            "message":"Private chat created",
            "conversation_id": conversation.id
            }


@router.get("/dms")
async def get_user_dms(
    db: db_session,
    token: str = Depends(oauth2_scheme)
):
    token_user = await get_current_user(db, token)

    if not token_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.participants)
            .selectinload(ConversationParticipants.user)
        )
        .join(ConversationParticipants)
        .where(
            ConversationParticipants.user_id == token_user.id,
            Conversation.is_group.is_(False)
        )
    )

    result = await db.execute(stmt)

    conversations = result.scalars().unique().all()

    dms = []

    for convo in conversations:

        other_user = next(
            (
                p.user
                for p in convo.participants
                if p.user_id != token_user.id
            ),
            None
        )

        if other_user:
            dms.append({
                "conversation_id": convo.id,
                "user_id": other_user.id,
                "username": other_user.username
            })

    return dms


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

    db.add(Message(
                    conversation_id=int(conversation.id),
                    sender_id=token_user.id,
                    type="system",
                    message=f"{token_user.username} joined group"
    ))
    
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

        if conversation.is_group:
            db.add(Message(
                    conversation_id=int(conversation.id),
                    sender_id=token_user.id,
                    type="system",
                    message=f"{token_user.username} joined group"
            ))

    await db.commit()

    return {
        "message": "Group created",
        "conversation_id": conversation.id
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
    
    print(conversation,"Coversation----")
    is_users_joined = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == payload.conversation_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(is_users_joined)

    already = result.scalar_one_or_none()
    print(already)
    if already:
        return {"message":"User already joined"}
    

    db.add(
        ConversationParticipants(
            conversation_id = conversation.id,
            user_id = token_user.id
        )
    )
    if conversation.is_group:
        msg = {
            "type": "system",
            "event": "join",
            "user": token_user.username,
            "message": f"{token_user.username} joined group"
        }

        db.add(Message(
                        conversation_id=int(conversation.id),
                        sender_id=token_user.id,
                        type="system",
                        message=f"{token_user.username} joined group"
                    ))
        await r.publish(
            f"group:{conversation.id}",
            json.dumps(msg)
        )
    await db.commit()
    

    

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
    
    stmt_conv = select(Conversation).where(
        Conversation.id == group_id
    )

    conv_result = await db.execute(stmt_conv)
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_group = conversation.is_group
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == group_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(stmt)

    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(404, "Not in group")

    await db.delete(participant)

    msg = {
        "type": "system",
        "event": "leave",
        "user": token_user.username,
        "message": f"{token_user.username} left group"
    }
    if is_group:
        db.add(Message(
                    conversation_id=int(group_id),
                    sender_id=token_user.id,
                    type="system",
                    message=f"{token_user.username} left group"
                ))
        await r.publish(
        f"group:{group_id}",
        json.dumps(msg)
        )
    await db.commit()
    

    
    return {
        "message": "Left group"
    }



@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    db: db_session,
    token: str = Depends(oauth2_scheme)
):

    token_user = await get_current_user(db, token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    stmt_conv = select(Conversation).where(
        Conversation.id == conversation_id
    )

    conv_result = await db.execute(stmt_conv)
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_group = conversation.is_group

    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(stmt)

    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(403, "Not in group")

    query = (
        select(Message)
        .options(selectinload(Message.sender))
        .where(Message.conversation_id == conversation_id)
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
            "type": m.type
        }
        for m in messages
    ]


@router.get("/conversations/{conversation_id}/users")
async def get_group_users(conversation_id: int, db: db_session, token: str = Depends(oauth2_scheme)):

    token_user = await get_current_user(db, token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation_id
    )

    result = await db.execute(stmt)
    participants = result.scalars().all()

    all_users = []
    for p in participants:
        u = await db.get(User, p.user_id)
        all_users.append({"id": u.id, "username": u.username})

    online = manager.groups.get(str(conversation_id), {})

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

    stmt = (
        select(Conversation)
        .join(ConversationParticipants)
        .where(
            ConversationParticipants.user_id == token_user.id,
            Conversation.is_group.is_(True)
        )
    )

    result = await db.execute(stmt)

    groups = result.scalars().all()
    return [
        {
            "id": g.id,
            "name": g.name
        }
        for g in groups
    ]