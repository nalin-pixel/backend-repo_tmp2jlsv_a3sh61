import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from database import db, create_document, get_documents

# App setup
app = FastAPI(title="School App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security setup
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[Literal["student", "teacher"]] = None

# Utility functions

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        role: str = payload.get("role")
        if user_id is None or email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    # fetch user from DB
    users = get_documents("user", {"_id": {"$in": []}})  # dummy to ensure DB ready
    # Actually fetch by email
    user_list = get_documents("user", {"email": email})
    if not user_list:
        raise credentials_exception
    user = user_list[0]
    return user


# Public endpoints
@app.get("/")
def read_root():
    return {"message": "School App Backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# Auth routes
@app.post("/auth/register")
def register_user(name: str, email: str, password: str, role: Literal["student", "teacher"], grade: Optional[str] = None):
    if role == "student" and not grade:
        raise HTTPException(status_code=400, detail="grade is required for students")
    # check existing
    existing = get_documents("user", {"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    hashed = get_password_hash(password)
    user_doc = {
        "name": name,
        "email": email,
        "role": role,
        "hashed_password": hashed,
        "grade": grade,
    }
    user_id = create_document("user", user_doc)
    # issue token
    token = create_access_token({"sub": user_id, "email": email, "role": role})
    return {"user_id": user_id, "access_token": token, "token_type": "bearer"}


@app.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    email = form_data.username  # OAuth2 form uses username field
    password = form_data.password
    users = get_documents("user", {"email": email})
    if not users:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    user = users[0]
    if not verify_password(password, user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(
        data={"sub": str(user.get("_id")), "email": user["email"], "role": user["role"]}
    )
    return {"access_token": access_token, "token_type": "bearer"}


# Example protected routes for roles
@app.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    # remove sensitive fields
    user = {k: v for k, v in current_user.items() if k != "hashed_password"}
    user["_id"] = str(user.get("_id"))
    return user


@app.get("/dashboard")
async def dashboard(current_user: dict = Depends(get_current_user)):
    role = current_user.get("role")
    if role == "teacher":
        return {"welcome": f"Welcome, {current_user.get('name')}!", "view": "teacher"}
    else:
        return {"welcome": f"Welcome, {current_user.get('name')}!", "view": "student"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
