from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from backend.app.core.security import decode_token
from backend.app.db.session import get_db
from backend.app.models import AuditLog, User

bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    payload = decode_token(cred.credentials) if cred else None
    user = db.get(User, payload["sub"]) if payload else None
    if not user or not user.is_active:
        raise HTTPException(401, "Not authenticated")
    return user


def require_roles(*roles):
    """Server-side permission check. admin is always allowed."""
    def dep(user: User = Depends(current_user)) -> User:
        if user.role != "admin" and user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return dep


def audit(db: Session, user, action: str, detail: str = ""):
    db.add(AuditLog(user_id=user.id if user else None, action=action, detail=detail[:500]))
