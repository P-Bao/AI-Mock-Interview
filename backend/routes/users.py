from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_database
from auth import get_current_user
from models.user import UserInDB, UserResponse
from datetime import datetime
from bson import ObjectId

router = APIRouter(prefix="/users", tags=["users"])

class UserUpdate(BaseModel):
    email: str = None
    full_name: str = None

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name
    )

@router.put("/me", response_model=UserResponse)
async def update_current_user_info(
    user_update: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db = Depends(get_database)
):
    update_data = {"updated_at": datetime.utcnow()}
    
    if user_update.email:
        # Check if email is already taken by another user
        existing_user = await db.users.find_one({"email": user_update.email, "_id": {"$ne": current_user.id}})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already in use")
        update_data["email"] = user_update.email
    
    if user_update.full_name is not None:
        update_data["full_name"] = user_update.full_name
    
    await db.users.update_one({"_id": ObjectId(current_user.id)}, {"$set": update_data})
    
    # Fetch updated user
    updated_user_doc = await db.users.find_one({"_id": ObjectId(current_user.id)})
    updated_user_doc["id"] = str(updated_user_doc["_id"])
    updated_user = UserInDB(**updated_user_doc)
    
    return UserResponse(
        id=updated_user.id,
        username=updated_user.username,
        email=updated_user.email,
        full_name=updated_user.full_name
    )