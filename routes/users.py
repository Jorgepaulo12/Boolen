from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
import os
import shutil
from sqlalchemy import select

import models
import schemas
from auth import get_current_user
from database import get_db
from utils import get_wallet

user_router = APIRouter()

@user_router.get("/profile", response_model=schemas.UserProfile)
async def get_profile(current_user: models.User = Depends(get_current_user)):
    return current_user

@user_router.post("/profile/picture")
async def update_profile_picture(
    profile_picture: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not profile_picture.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Profile picture must be PNG or JPEG")

    # Create profiles directory if it doesn't exist
    os.makedirs("profiles", exist_ok=True)
    
    # Save profile picture
    file_path = f"profiles/{current_user.username}_{profile_picture.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(profile_picture.file, buffer)
    
    # Update user profile picture path
    current_user.profile_picture = file_path
    await db.commit()
    
    return {"message": "Profile picture updated successfully"}

@user_router.get("/wallet/balance")
async def get_wallet_balance(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    wallet = await get_wallet(db, current_user.id)
    if not wallet:
        return {"balance": 0.0}
    return {"balance": wallet.balance}

@user_router.get("/wallet/transactions")
async def get_wallet_transactions(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    wallet = await get_wallet(db, current_user.id)
    if not wallet:
        return {"transactions": []}
    
    result = await db.execute(
        select(models.WalletTransaction)
        .where(models.WalletTransaction.wallet_id == wallet.id)
        .order_by(models.WalletTransaction.created_at.desc())
    )
    transactions = result.scalars().all()
    
    return {
        "balance": wallet.balance,
        "transactions": [
            {
                "amount": t.amount,
                "type": t.transaction_type,
                "status": t.status,
                "created_at": t.created_at,
                "payment_ref": t.payment_ref
            } for t in transactions
        ]
    } 