from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

import models
from auth import get_current_admin, promote_to_admin
from database import get_db

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

# ... código das rotas de admin ... 