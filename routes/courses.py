from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import os
import shutil

import models
import schemas
from auth import get_current_admin, get_current_user
from database import get_db
from config import COURSE_DIR
from utils import get_course, get_wallet

course_router = APIRouter()

@course_router.post("/", response_model=schemas.Course)
async def create_course(
    title: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    duration_minutes: int = Form(...),
    cover_image: UploadFile = File(...),
    course_file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    if not course_file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Course file must be a ZIP archive")
    
    if not cover_image.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Cover image must be PNG or JPEG")

    # Salvar imagem de capa
    cover_path = os.path.join(COURSE_DIR, f"covers/{title}_{cover_image.filename}")
    os.makedirs(os.path.dirname(cover_path), exist_ok=True)
    with open(cover_path, "wb") as buffer:
        shutil.copyfileobj(cover_image.file, buffer)

    # Salvar arquivo do curso
    course_path = os.path.join(COURSE_DIR, f"files/{title}_{course_file.filename}")
    os.makedirs(os.path.dirname(course_path), exist_ok=True)
    with open(course_path, "wb") as buffer:
        shutil.copyfileobj(course_file.file, buffer)

    course = models.Course(
        title=title,
        description=description,
        price=price,
        duration_minutes=duration_minutes,
        cover_image=cover_path,
        file_path=course_path,
        uploaded_by=current_user.id
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)

    return course

@course_router.get("/", response_model=List[schemas.Course])
async def list_courses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Course))
    return result.scalars().all()

@course_router.post("/{course_id}/purchase")
async def purchase_course(
    course_id: int,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verificar se o curso existe
    course = await get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Verificar se o usuário já comprou o curso
    result = await db.execute(
        select(models.CourseDownload)
        .where(
            models.CourseDownload.user_id == current_user.id,
            models.CourseDownload.course_id == course_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Course already purchased")

    # Verificar saldo da wallet
    wallet = await get_wallet(db, current_user.id)
    if wallet.balance < course.price:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Criar transação de compra
    transaction = models.WalletTransaction(
        wallet_id=wallet.id,
        amount=-course.price,
        transaction_type="purchase",
        status="completed"
    )
    db.add(transaction)

    # Atualizar saldo
    wallet.balance -= course.price

    # Registrar download
    download = models.CourseDownload(
        user_id=current_user.id,
        course_id=course_id,
        transaction_id=transaction.id
    )
    db.add(download)
    
    await db.commit()

    return {"message": "Course purchased successfully"}

@course_router.get("/{course_id}/download")
async def download_course(
    course_id: int,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verificar se o curso existe
    course = await get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Verificar se o usuário já comprou o curso
    result = await db.execute(
        select(models.CourseDownload)
        .where(
            models.CourseDownload.user_id == current_user.id,
            models.CourseDownload.course_id == course_id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Course not purchased")

    # Retornar o arquivo
    return FileResponse(
        path=course.file_path,
        filename=os.path.basename(course.file_path),
        media_type='application/zip'
    )

@course_router.post("/{course_id}/reaction")
async def toggle_course_reaction(
    course_id: int,
    is_like: bool,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verificar se o curso existe
    course = await get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Verificar se já existe uma reação do usuário
    result = await db.execute(
        select(models.CourseLike)
        .where(
            models.CourseLike.user_id == current_user.id,
            models.CourseLike.course_id == course_id
        )
    )
    existing_reaction = result.scalar_one_or_none()

    if existing_reaction:
        if existing_reaction.is_like == is_like:
            # Se a reação é a mesma, remover a reação
            await db.delete(existing_reaction)
            await db.commit()
            message = "Reaction removed"
        else:
            # Se a reação é diferente, atualizar
            existing_reaction.is_like = is_like
            await db.commit()
            message = "Reaction updated"
    else:
        # Criar nova reação
        new_reaction = models.CourseLike(
            user_id=current_user.id,
            course_id=course_id,
            is_like=is_like
        )
        db.add(new_reaction)
        await db.commit()
        message = "Reaction added"

    # Contar likes e dislikes atualizados
    likes_count = await db.execute(
        select(models.CourseLike)
        .where(
            models.CourseLike.course_id == course_id,
            models.CourseLike.is_like == True
        )
    )
    dislikes_count = await db.execute(
        select(models.CourseLike)
        .where(
            models.CourseLike.course_id == course_id,
            models.CourseLike.is_like == False
        )
    )

    return {
        "message": message,
        "likes_count": len(likes_count.scalars().all()),
        "dislikes_count": len(dislikes_count.scalars().all()),
        "current_user_reaction": is_like if existing_reaction or message == "Reaction added" else None
    } 