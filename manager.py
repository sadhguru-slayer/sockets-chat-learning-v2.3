from collections import defaultdict
from datetime import datetime
from fastapi import WebSocket
import json
from redis_client import r


class ConnectionManager:
    def __init__(self):
        # 🔥 CHANGED: using username as key for readability in frontend
        # group_id -> { user_id -> {username, ws} }
        self.groups: dict[str, dict[int, dict]] = defaultdict(dict)

    def _now(self):
        return datetime.now().strftime("%H:%M:%S")

    async def connect(self, group_id: str, user_id:int,username: str, ws: WebSocket):

        await ws.accept()

        # 🔥 WHY: prevent duplicate username connections in same group
        if user_id in self.groups[group_id]:
            await ws.send_json({
                "type": "error",
                "message": "Username already taken in this group"
            })
            await ws.close(code=4000)
            return False

        # 🔥 STORE connection using username for frontend readability
        self.groups[group_id][user_id] ={
            "ws": ws,
            "username": username
        }

        # OPTIONAL: history logic can stay (if you use Redis history list)
        history = await r.lrange(f"group:{group_id}:history", -50, -1)

        for msg in history:
            await ws.send_json(json.loads(msg))

        # system join message
        join_msg = {
            "type": "system",
            "event": "join",
            "user": username,
            "time": self._now(),
            "message": f"{username} joined {group_id}"
        }

        await self.broadcast(group_id, join_msg)
        await self.send_online_users(group_id)

    async def disconnect(self, group_id: str, user_id: int, ws: WebSocket):

        if group_id not in self.groups:
            return
        

        if user_id in self.groups[group_id]:
            del self.groups[group_id][user_id]
        
        # cleanup empty group
        if not self.groups[group_id]:
            del self.groups[group_id]

        await self.send_online_users(group_id)

    async def send_personal_message(self, ws: WebSocket, data: dict):
        await ws.send_json(data)

    async def broadcast(self, group_id: str, data: dict):

        # 🔥 WHY: track dead sockets to avoid memory leaks
        dead_users = []

        # store history in Redis (last 50 messages)
        await r.rpush(
            f"group:{group_id}:history",
            json.dumps(data)
        )
        
        await r.ltrim(
            f"group:{group_id}:history",
            -50,
            -1
        )

        # send to all connected users
        for user_id, data_ws in list(self.groups[group_id].items()):
            try:
                await data_ws["ws"].send_json(data)
            except Exception:
                dead_users.append(user_id)

        # cleanup dead connections
        for user_id in dead_users:
            del self.groups[group_id][user_id]

    async def send_online_users(self, group_id: str):

        if group_id not in self.groups:
            return

        users = [
            {
                "id": user_id,
                "username": data["username"]
            }
            for user_id, data in self.groups[group_id].items()
        ]

        payload = {
            "type": "online_users",
            "users": users
        }
        

        for id, data_ws in self.groups[group_id].items():
            try:
                await data_ws["ws"].send_json(payload)
            except:
                pass