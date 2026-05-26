from fastapi import (
                FastAPI, 
                WebSocket, 
                WebSocketDisconnect,
                Query
                )
from datetime import datetime
from dependencies import db_session
import json
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio

# Routers
from auth.router import router as auth_router
from admin.router import router as admin_router
from chat.router import router as chat_router

# Services
from auth.service import get_current_user_ws

# Redis client
from redis_client import r

# DB and models
from db import init_db
from sqlalchemy import select
from models import Message, ConversationParticipants


app = FastAPI()

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get('/')
async def get():
    with open("index.html","r",encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(html)


# Connection manager for actual ws logic connection
from manager import ConnectionManager

manager = ConnectionManager()

# Channelsa used in redis to listen and publish msgs
def channel(conversation_id: str):
    return f"group:{conversation_id}"

# Startup function
@app.on_event("startup")
async def startup():
    await init_db()
    asyncio.create_task(redis_listener())


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(chat_router)

# WS route
@app.websocket('/ws/{conversation_id}')
async def conversation_socket(
    ws: WebSocket,
    conversation_id: str | None,
    db: db_session,
    token: str = Query(...)
):
    user = await get_current_user_ws(db, token)
    if not user:
        await ws.close(code=1008)
        return
    user_id = user.id
    username = user.username
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == int(conversation_id),
        ConversationParticipants.user_id == user_id
    )

    result = await db.execute(stmt)

    participant = result.scalar_one_or_none()

    if not participant:
        await ws.close(code=1008)
        return

    await manager.connect(conversation_id, user_id,username, ws)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "chat":
                message = data.get("message", "")

                chat_message = {
                    "type": "chat",
                    "user": username,
                    "group": conversation_id,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "message": message
                }

                db.add(Message(
                    conversation_id=int(conversation_id),
                    sender_id=user_id,
                    type="chat",
                    message=message
                ))

                await db.commit()

                await r.publish(
                    f"group:{conversation_id}",
                    json.dumps(chat_message)
                )

            elif msg_type == "typing":
                typing_message = {
                    "type": "typing",
                    "user": username,
                    "group": conversation_id
                }

                await r.publish(
                    f"group:{conversation_id}",
                    json.dumps(typing_message)
                )

    except WebSocketDisconnect:
        await manager.disconnect(conversation_id, user_id, ws)
    
async def redis_listener():
    pubsub = r.pubsub()
    await pubsub.psubscribe("group:*")

    async for message in pubsub.listen():
        # print(message["type"],"-------------")
        if message["type"] != "pmessage":
            continue

        raw = message["data"]

        # print(raw,"RAW______")

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        data = json.loads(raw)

        channel = message["channel"]

        if isinstance(channel, bytes):
            channel = channel.decode()

        conversation_id = channel.split(":")[1]

        if manager.groups.get(conversation_id):
            for data_ws in list(manager.groups[conversation_id].values()):
                try:
                    await data_ws["ws"].send_json(data)
                except Exception as e:
                    print("Redis listener error:", e)