# v2.3 📡 FastAPI Real-Time Group Chat

A real-time group chat application built with **FastAPI**, **WebSockets**, **Redis Pub/Sub**, **SQLAlchemy (async)**, and a simple HTML/CSS/JS frontend.

It supports:

* User authentication (JWT)
* Create / Join chat groups
* Real-time messaging via WebSockets
* Typing indicators
* Online users tracking
* Message persistence in SQLite
* Redis-powered scaling (Pub/Sub)

---

# 🚀 Features

* 🔐 JWT Authentication (Login/Register)
* 💬 Real-time group chat using WebSockets
* 👥 Create or join chat groups
* 🟢 Online users list
* ⌨️ Typing indicators
* 💾 Message storage (SQLite async)
* ⚡ Redis Pub/Sub for message broadcasting
* 🐳 Docker support

---

# 🧱 Tech Stack

* **Backend:** FastAPI
* **WebSockets:** FastAPI WebSocket
* **Database:** SQLite (async with SQLAlchemy)
* **Cache / PubSub:** Redis
* **Frontend:** HTML, CSS, Vanilla JavaScript
* **Containerization:** Docker, Docker Compose

---

# 📁 Project Structure

```
.
├── admin/
├── auth/
├── websocket/
├── models.py
├── db.py
├── manager.py
├── redis_client.py
├── dependencies.py
├── main.py
├── index.html
├── style.css
├── chat.db
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# ⚙️ Setup & Installation

## 1️⃣ Clone the project

```bash
git clone <your-repo-url>
cd <your-project-folder>
```

---

## 2️⃣ Run with Docker (Recommended)

```bash
docker-compose up --build
```

Then open:

```
http://localhost:8000
```

---

## 3️⃣ Run manually (without Docker)

### Install dependencies

```bash
pip install -r requirements.txt
```

### Start Redis

Make sure Redis is running locally:

```bash
redis-server
```

### Run FastAPI app

```bash
uvicorn main:app --reload
```

---

# 🔌 API & WebSocket Usage

## Authentication

### Register

```
POST /auth/register
```

### Login

```
POST /auth/login
```

Returns:

```json
{
  "access_token": "...",
  "refresh_token": "..."
}
```

---

## WebSocket Connection

### Join existing group

```
ws://localhost:8000/ws/{group_id}?token=JWT_TOKEN
```

### Create new group

```
ws://localhost:8000/ws/{group_id}?token=JWT_TOKEN&is_new_group=true
```

---

## Message Format

### Send message

```json
{
  "type": "chat",
  "message": "Hello world"
}
```

### Typing indicator

```json
{
  "type": "typing"
}
```

---

## Server Broadcasts

### Chat message

```json
{
  "type": "chat",
  "user": "john",
  "message": "hello",
  "time": "12:30:45"
}
```

### Typing

```json
{
  "type": "typing",
  "user": "john"
}
```

### Error

```json
{
  "type": "error",
  "message": "Conversation not found"
}
```

---

# 🐳 Docker Services

### FastAPI App

* Runs on `http://localhost:8000`
* Auto-reload enabled in development

### Redis

* Runs on `localhost:6379`
* Handles Pub/Sub messaging

---

# 💾 Database

SQLite database file:

```
chat.db
```

Stores:

* Users
* Conversations
* Messages
* Participants

---

# ⚠️ Important Notes

* Do NOT commit `chat.db` (already in `.gitignore`)
* Redis is required for real-time messaging
* WebSocket requires valid JWT token
* Group ID must exist unless `is_new_group=true`

---

# 🧠 Architecture Overview

```
Frontend (HTML/JS)
        ↓
FastAPI WebSocket
        ↓
Redis Pub/Sub
        ↓
Other connected clients

+ SQLite for persistence
```

---

# 🚀 Future Improvements

* Message pagination (load history)
* Read receipts
* Private chats (1-to-1)
* Group admin roles
* File/image sharing
* React frontend upgrade
* Kubernetes deployment

---

# 👨‍💻 Author

Built as a learning project for:

* FastAPI WebSockets
* Real-time systems
* Redis Pub/Sub architecture
