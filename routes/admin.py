from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

import models
from auth import get_current_admin, promote_to_admin
from database import get_db
from schemas import UserProfile

admin_router = APIRouter()

@admin_router.post("/promote/{user_id}")
async def promote_user_to_admin(
    user_id: int,
    current_user: models.User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await promote_to_admin(db, user_id)
    return {"message": f"User {user.username} promoted to admin"}

@admin_router.get("/users", response_model=List[UserProfile])
async def list_users(
    current_user: models.User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    return users

@admin_router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: models.User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Você não pode deletar sua própria conta"
        )
    
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    await db.delete(user)
    await db.commit()
    
    return {"message": f"Usuário {user.username} foi deletado com sucesso"}