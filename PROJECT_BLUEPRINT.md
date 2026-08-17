# Megor Project Blueprint

## 1. Product Goal

Metor is an AI workspace for overseas users, starting as a multi-model AI chat app and gradually evolving into a productivity SaaS.

Primary goal:
- Get real overseas users
- Convert free users to paid users
- Build recurring subscription revenue

## 2. Current Core Features

- Email/password login
- Persistent login
- Multi-model chat
- Auto model selection
- Image recognition
- Chat history
- Sidebar sessions
- New chat
- Delete chat
- Clear current chat
- LemonSqueezy payment link

## 3. Tech Stack

- Frontend: Streamlit
- Backend: Python
- Auth: Supabase Auth
- Database: Supabase Postgres
- Deployment: Render
- Payments: LemonSqueezy
- AI Providers:
  - DeepSeek
  - GLM
  - Kimi
  - Doubao
  - Qwen

## 4. Database Tables

### device_sessions

Purpose:
- Track device login status
- Limit number of devices
- Store plan and last seen time

Fields:
- id
- device_id
- user_id
- email
- plan
- last_seen
- created_at
- updated_at

Note:
- Do not rely on device_sessions as the long-term refresh token source in V2.

### chat_sessions

Purpose:
- Store chat sessions

Fields:
- id
- user_id
- title
- created_at
- updated_at

### messages

Purpose:
- Store chat messages

Fields:
- id
- session_id
- role
- content
- created_at

## 5. V2 Target Architecture

Project structure:

```text
app.py
config.py
database.py
models.py
utils.py

auth.py
sidebar.py
chat.py

services/
    __init__.py
    auth_service.py
    chat_service.py
    device_service.py
    session_service.py

components/
    __init__.py
    history.py
    message.py
    uploader.py
