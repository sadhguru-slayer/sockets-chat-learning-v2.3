from fastapi import (
                FastAPI, 
                WebSocket, 
                WebSocketDisconnect,
                Query,
                Depends,
                HTTPException,
                )
from datetime import datetime
from dependencies import db_session
from auth.router import router as auth_router
from admin.router import router as admin_router
from auth.jwt_auth import verify_access_token
from auth.service import get_current_user
import json
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from redis_client import r
from db import init_db
from models import Message


app = FastAPI()

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get('/')
async def get():
    with open("index.html","r",encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(html)

from manager import ConnectionManager

manager = ConnectionManager()

def channel(group_id: str):
    return f"group:{group_id}"

@app.on_event("startup")
async def startup():
    await init_db()
    asyncio.create_task(redis_listener())

app.include_router(auth_router)
app.include_router(admin_router)

@app.websocket('/ws/{group_id}')
async def groupChat(
    ws: WebSocket,
    group_id: str,
    db: db_session,
    token: str = Query(...)
):
    user = await get_current_user(db, token)

    user_id = user.id
    username = user.username

    await manager.connect(group_id, user_id,username, ws)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "chat":
                message = data.get("message", "")

                chat_message = {
                    "type": "chat",
                    "user": username,
                    "group": group_id,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "message": message
                }

                db.add(Message(
                    conversation_id=int(group_id),
                    sender_id=user_id,
                    message=message   # ✅ store raw text, not dict
                ))

                await db.commit()

                await r.publish(
                    f"group:{group_id}",
                    json.dumps(chat_message)
                )

            elif msg_type == "typing":
                typing_message = {
                    "type": "typing",
                    "user": username,
                    "group": group_id
                }

                await r.publish(
                    f"group:{group_id}",
                    json.dumps(typing_message)
                )

    except WebSocketDisconnect:
        await manager.disconnect(group_id, user_id, ws)
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

        group_id = channel.split(":")[1]

        if manager.groups.get(group_id):
            for data_ws in list(manager.groups[group_id].values()):
                try:
                    await data_ws["ws"].send_json(data)
                except Exception as e:
                    print("Redis listener error:", e)