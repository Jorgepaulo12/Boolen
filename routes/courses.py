from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import os
import shutil
import uuid
from datetime import datetime

import models
import schemas
from auth import get_current_admin, get_current_user
from database import get_db
from config import COURSE_DIR
from utils import get_course, get_wallet

course_router = APIRouter()

@course_router.get("/code/{course_code}", response_model=schemas.Course)
async def get_course_by_code(
    course_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Buscar curso pelo código único"""
    stmt = select(models.Course).where(models.Course.course_code == course_code)
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return course

@course_router.get("/enrollment/{enrollment_code}", response_model=schemas.CourseDownload)
async def get_enrollment_by_code(
    enrollment_code: str,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Buscar matrícula pelo código único"""
    stmt = select(models.CourseDownload).where(
        models.CourseDownload.enrollment_code == enrollment_code
    )
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    # Verificar se o usuário é o dono da matrícula ou um admin
    if enrollment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to access this enrollment")
    
    return enrollment

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
    # Validar arquivos
    if not course_file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Course file must be a ZIP archive")
    
    if not cover_image.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Cover image must be PNG or JPEG")

    # Gerar nomes únicos para os arquivos
    cover_filename = f"{uuid.uuid4()}_{cover_image.filename}"
    course_filename = f"{uuid.uuid4()}_{course_file.filename}"
    
    # Criar diretórios se não existirem
    os.makedirs(os.path.join(COURSE_DIR, "covers"), exist_ok=True)
    os.makedirs(os.path.join(COURSE_DIR, "files"), exist_ok=True)
    
    # Definir caminhos completos
    cover_path = os.path.join(COURSE_DIR, f"covers/{cover_filename}")
    course_path = os.path.join(COURSE_DIR, f"files/{course_filename}")

    # Salvar arquivos
    try:
        with open(cover_path, "wb") as buffer:
            shutil.copyfileobj(cover_image.file, buffer)
        with open(course_path, "wb") as buffer:
            shutil.copyfileobj(course_file.file, buffer)
    except Exception as e:
        # Limpar arquivos em caso de erro
        if os.path.exists(cover_path):
            os.remove(cover_path)
        if os.path.exists(course_path):
            os.remove(course_path)
        raise HTTPException(status_code=500, detail=str(e))

    # Criar o curso
    course = models.Course(
        title=title,
        description=description,
        price=price,
        duration_minutes=duration_minutes,
        cover_image=cover_path,
        file_path=course_path,
        uploaded_by=current_user.id,
        status="draft"  # Inicialmente como rascunho
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)

    return course

@course_router.put("/{course_id}/status", response_model=schemas.Course)
async def update_course_status(
    course_id: int,
    status: str,
    current_user: models.User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar o status do curso (draft, published, archived)"""
    if status not in ["draft", "published", "archived"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be draft, published, or archived")
    
    course = await get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    course.status = status
    await db.commit()
    await db.refresh(course)
    
    return course

@course_router.get("/public", response_model=List[schemas.Course])
async def list_public_courses(db: AsyncSession = Depends(get_db)):
    # Buscar todos os cursos disponíveis publicamente
    courses = await db.execute(select(models.Course))
    courses = courses.scalars().all()
    
    # Inicializar campos que requerem autenticação com valores padrão
    for course in courses:
        course.liked = False
        course.likes_count = 0
    
    return courses

@course_router.get("/", response_model=List[schemas.Course])
async def list_courses(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Buscar todos os cursos
    courses = await db.execute(select(models.Course))
    courses = courses.scalars().all()
    
    # Para cada curso, verificar se o usuário atual deu like
    for course in courses:
        reaction = await db.execute(
            select(models.CourseLike)
            .where(
                models.CourseLike.user_id == current_user.id,
                models.CourseLike.course_id == course.id
            )
        )
        course.liked = reaction.scalar_one_or_none() is not None
        
        # Contar total de likes
        likes = await db.execute(
            select(models.CourseLike)
            .where(models.CourseLike.course_id == course.id)
        )
        course.likes_count = len(likes.scalars().all())
    
    return courses

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

@course_router.post("/{course_id}/like")
async def toggle_course_like(
    course_id: int,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verificar se o curso existe
    course = await get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Verificar se já existe um like do usuário
    result = await db.execute(
        select(models.CourseLike)
        .where(
            models.CourseLike.user_id == current_user.id,
            models.CourseLike.course_id == course_id
        )
    )
    existing_like = result.scalar_one_or_none()

    if existing_like:
        # Se já existe um like, remover
        await db.delete(existing_like)
        await db.commit()
        message = "Like removed"
        liked = False
    else:
        # Criar novo like
        new_like = models.CourseLike(
            user_id=current_user.id,
            course_id=course_id
        )
        db.add(new_like)
        await db.commit()
        message = "Like added"
        liked = True

    # Contar total de likes
    likes_count = await db.execute(
        select(models.CourseLike)
        .where(models.CourseLike.course_id == course_id)
    )

    return {
        "message": message,
        "likes_count": len(likes_count.scalars().all()),
        "liked": liked
    }

@course_router.get("/enrollments", response_model=List[schemas.CourseDownload])
async def get_user_enrollments(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Obter todas as matrículas do usuário atual"""
    stmt = select(models.CourseDownload).where(
        models.CourseDownload.user_id == current_user.id
    )
    result = await db.execute(stmt)
    enrollments = result.scalars().all()
    
    return enrollments

@course_router.put("/enrollment/{enrollment_code}/progress")
async def update_enrollment_progress(
    enrollment_code: str,
    progress: float = Body(..., embed=True),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Atualizar o progresso de uma matrícula"""
    stmt = select(models.CourseDownload).where(
        models.CourseDownload.enrollment_code == enrollment_code
    )
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    # Verificar se o usuário é o dono da matrícula
    if enrollment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this enrollment")
    
    # Atualizar progresso
    enrollment.progress = min(100, max(0, progress))  # Limitar entre 0 e 100
    enrollment.last_accessed = datetime.utcnow()
    
    # Se o progresso atingiu 100%, marcar como concluído
    if enrollment.progress >= 100:
        enrollment.status = "completed"
    
    await db.commit()
    await db.refresh(enrollment)
    
    return {"message": "Progress updated successfully", "progress": enrollment.progress}