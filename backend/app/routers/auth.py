"""FORGE-VISION — Auth router with JWT + RBAC"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

import aiosqlite
from ..database import get_db, seed_demo_users_and_data

SECRET_KEY = "FORGE-VISION-SIH150-SECRET-CHANGE-IN-PRODUCTION"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours for demo

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str
    full_name: str
    role: str


class UserCreate(BaseModel):
    username: str
    full_name: str
    password: str
    role: str = "investigator"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: aiosqlite.Connection = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
        user = await cur.fetchone()
    if not user:
        raise credentials_exception
    return dict(user)


def require_role(*roles: str):
    async def checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"Role '{current_user['role']}' not permitted. Required: {roles}")
        return current_user
    return checker


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: aiosqlite.Connection = Depends(get_db)
):
    await seed_demo_users_and_data(db)
    async with db.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1", (form_data.username,)
    ) as cur:
        user = await cur.fetchone()

    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    token = create_access_token({"sub": user["id"], "role": user["role"]},
                                 timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return Token(
        access_token=token, token_type="bearer",
        user_id=user["id"], username=user["username"],
        full_name=user["full_name"], role=user["role"],
    )


@router.post("/register")
async def register(user_in: UserCreate, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM users WHERE username = ?", (user_in.username,)) as cur:
        existing = await cur.fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user_id = str(uuid.uuid4())
    hashed = pwd_context.hash(user_in.password)
    await db.execute(
        "INSERT INTO users (id, username, full_name, role, hashed_password, is_active, created_at) VALUES (?,?,?,?,?,1,?)",
        (user_id, user_in.username, user_in.full_name, user_in.role, hashed, datetime.now(timezone.utc).isoformat())
    )
    await db.commit()
    return {"id": user_id, "username": user_in.username, "role": user_in.role, "message": "User created"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {k: v for k, v in current_user.items() if k != "hashed_password"}
