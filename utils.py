from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import models
from fastapi import HTTPException

async def get_or_create_wallet(db: AsyncSession, user_id: int) -> models.Wallet:
    result = await db.execute(
        select(models.Wallet).where(models.Wallet.user_id == user_id)
    )
    wallet = result.scalar_one_or_none()
    
    if not wallet:
        wallet = models.Wallet(user_id=user_id)
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
    
    return wallet

async def get_wallet(db: AsyncSession, user_id: int) -> models.Wallet:
    result = await db.execute(
        select(models.Wallet).where(models.Wallet.user_id == user_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet

async def get_course(db: AsyncSession, course_id: int) -> models.Course:
    result = await db.execute(
        select(models.Course).where(models.Course.id == course_id)
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(
            status_code=404,
            detail=f"Course with id {course_id} not found"
        )
    return course