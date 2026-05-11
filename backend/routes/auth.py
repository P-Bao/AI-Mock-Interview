from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from database import get_database
from auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from models.user import UserCreate, UserInDB
from datetime import timedelta, datetime
from bson import ObjectId

router = APIRouter(prefix="/auth", tags=["authentication"])

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register", response_model=Token)
async def register(user: UserCreate, db = Depends(get_database)):
    # Check if user exists
    existing_user = await db.users.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = get_password_hash(user.password)
    user_doc = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_password,
        "full_name": user.full_name,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = await db.users.insert_one(user_doc)
    user_doc["id"] = str(result.inserted_id)
    
    # Create token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db = Depends(get_database)):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout():
    # For JWT, logout is handled client-side by discarding token
    return {"message": "Logged out successfully"}