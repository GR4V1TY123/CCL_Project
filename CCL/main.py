import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

load_dotenv()

from models import (
    Playbook,
    PlaybookBullet,
    LogEntry,
    Student,
    User,
    UserCreate,
    UserOut,
)
from database import db
from agents import Generator, Reflector, Curator

app = FastAPI(title="Student Information Backend")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://chatbot-bucket-ccl-project.s3-website.us-east-2.amazonaws.com",
]

extra_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
if extra_origins:
    ALLOWED_ORIGINS.extend(
        [origin.strip() for origin in extra_origins.split(",") if origin.strip()]
    )

ALLOWED_ORIGINS = list(dict.fromkeys(ALLOWED_ORIGINS))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth / JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRATION_SECONDS", "3600")) // 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[User]:
    user = db.get_user(username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.get_user(username)
    if user is None:
        raise credentials_exception
    return user


# In-memory storage for active sessions
# In a real app, this would be in Redis or a database
class SessionState:
    def __init__(self):
        self.playbook = Playbook(bullets=[
            PlaybookBullet(id=str(uuid.uuid4()), rule="Always be polite and professional.")
        ])
        self.messages = []

# Map session_id to SessionState
sessions: dict[str, SessionState] = {}

generator = Generator()
reflector = Reflector()
curator = Curator()

def get_session(session_id: str) -> SessionState:
    if session_id not in sessions:
        sessions[session_id] = SessionState()
    return sessions[session_id]

# --- Models ---
class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatFeedbackRequest(BaseModel):
    session_id: str
    message_index: int

class ConfirmMemoryRequest(BaseModel):
    session_id: str
    fact: str

class InfoRequest(BaseModel):
    topic: str
    info: str

class AdminRuleRequest(BaseModel):
    rule: str
    session_id: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Welcome to the Student API"}


@app.post("/auth/register", response_model=Token)
def register(user: UserCreate):
    existing = db.get_user(user.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed = get_password_hash(user.password)
    db.add_user(User(username=user.username, password_hash=hashed))
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/login", response_model=Token)
def login(user: UserCreate):
    auth_user = authenticate_user(user.username, user.password)
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": auth_user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    return UserOut(username=current_user.username)


@app.post("/chat/message")
def send_message(req: ChatRequest):
    session = get_session(req.session_id)
    
    # Check for memory confirmation
    if len(session.messages) >= 1:
        last_bot_msg = session.messages[-1]["content"]
        if "Are you sure? I will remember:" in last_bot_msg:
            user_confimation = req.message.lower().strip()
            if user_confimation in ["yes", "yeah", "yep", "sure", "of course", "yes i am sure"]:
                try:
                    fact_str = last_bot_msg.split("I will remember:")[1].strip()
                    db.add_learned_fact(fact_str)
                    session.messages.append({"role": "user", "content": req.message})
                    response = f"Got it! I have saved: '{fact_str}' to my knowledge base."
                    session.messages.append({"role": "assistant", "content": response})
                    return {"response": response, "sources": [], "messages": session.messages}
                except IndexError:
                    pass # Fallback to normal flow

    session.messages.append({"role": "user", "content": req.message})
    
    context = db.retrieve_context(session.messages)
    output = generator.generate(session.messages, session.playbook, context)
    
    session.messages.append({"role": "assistant", "content": output.response})
    
    return {"response": output.response, "sources": output.sources, "messages": session.messages}

@app.get("/chat/history/{session_id}")
def get_chat_history(session_id: str):
    session = get_session(session_id)
    return {"messages": session.messages}

@app.post("/chat/feedback")
def mark_invalid(req: ChatFeedbackRequest):
    session = get_session(req.session_id)
    i = req.message_index
    if i < 0 or i >= len(session.messages):
        raise HTTPException(status_code=400, detail="Invalid message index")
    
    msg = session.messages[i]
    if msg["role"] != "assistant":
        raise HTTPException(status_code=400, detail="Can only feedback on assistant messages")
    
    evaluation = reflector.evaluate("invalid")
    if evaluation == "harmful":
        user_query = session.messages[i-1]["content"] if i > 0 else ""
        bot_response = msg["content"]
        
        fix = curator.draft_fix(user_query, bot_response)
        
        log_entry = LogEntry(
            id=str(uuid.uuid4()),
            query=user_query,
            response=bot_response,
            suggested_fix=fix
        )
        db.save_invalid_log(log_entry)
        return {"status": "reported", "message": "Reported to Admin. A potential fix has been queued."}
    return {"status": "ignored", "message": "Not classified as harmful"}

@app.get("/admin/knowledge")
def get_knowledge(current_user: User = Depends(get_current_user)):
    return {"learned_facts": db.get_learned_facts()}

@app.post("/admin/knowledge")
def add_knowledge(req: InfoRequest, current_user: User = Depends(get_current_user)):
    db.add_general_info(req.topic, req.info)
    return {"status": "success", "message": f"Added info for: {req.topic}"}

@app.get("/admin/students")
def get_students(current_user: User = Depends(get_current_user)):
    return {"students_count": db.get_students_count()}

@app.post("/admin/students")
def add_student(student: Student, current_user: User = Depends(get_current_user)):
    db.add_student(student)
    return {"status": "success", "message": f"Added student {student.name}"}

@app.get("/admin/playbook/{session_id}")
def get_playbook(session_id: str, current_user: User = Depends(get_current_user)):
    session = get_session(session_id)
    return {"playbook": session.playbook}

@app.get("/admin/logs")
def get_logs(current_user: User = Depends(get_current_user)):
    logs = db.get_admin_logs()
    return {"logs": logs}

@app.post("/admin/logs/{log_id}/approve")
def approve_log(log_id: str, admin_rule: AdminRuleRequest, current_user: User = Depends(get_current_user)):
    session = get_session(admin_rule.session_id)
    rule_text = admin_rule.rule
    if rule_text:
        new_bullet = PlaybookBullet(id=str(uuid.uuid4()), rule=rule_text)
        session.playbook.bullets.append(new_bullet)
        db.delete_log(log_id)
        return {"status": "success", "message": "Rule added and log deleted."}
    return {"status": "error", "message": "Missing rule text."}

@app.delete("/admin/logs/{log_id}")
def delete_log(log_id: str, current_user: User = Depends(get_current_user)):
    db.delete_log(log_id)
    return {"status": "success", "message": "Log deleted."}
