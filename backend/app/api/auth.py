import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.security import create_token, hash_password, verify_password
from backend.app.db.session import get_db
from backend.app.deps import audit, current_user
from backend.app.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_fails: dict = {}          # email -> [count, window_start]  (in-memory; use Redis if you scale out)
_DUMMY = hash_password("not-a-real-password")


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    key = body.email.lower()
    cnt, start = _fails.get(key, [0, time.time()])
    if time.time() - start > 900:
        cnt, start = 0, time.time()
    if cnt >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == key))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY)
    if not (user and ok and user.is_active):
        _fails[key] = [cnt + 1, start]
        raise HTTPException(401, "Invalid email or password")
    _fails.pop(key, None)
    audit(db, user, "login"); db.commit()
    return {"access_token": create_token(user.id, user.role), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}
