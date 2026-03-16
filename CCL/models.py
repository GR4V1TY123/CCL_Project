from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class DeltaOperationAction(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    REMOVE = "REMOVE"

class PlaybookBullet(BaseModel):
    id: str
    rule: str

class Playbook(BaseModel):
    bullets: List[PlaybookBullet]

class GeneratorOutput(BaseModel):
    response: str
    sources: List[str]

class DeltaOperation(BaseModel):
    action: DeltaOperationAction
    target_id: Optional[str]
    new_rule: Optional[str]

class LogEntry(BaseModel):
    id: str
    query: str
    response: str
    suggested_fix: Optional[DeltaOperation]

class Student(BaseModel):
    name: str
    secret_key: str
    gpa: float
    major: str
    enrollment_year: int

class User(BaseModel):
    username: str
    password_hash: str

class UserCreate(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    username: str
