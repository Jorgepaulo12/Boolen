from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body, Form
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import os
import shutil
import uuid

import models
import schemas
from auth import get_current_admin, get_current_user, authenticate_user, create_user
from database import get_db
from main import COURSE_DIR
from payment import paychangu
from utils import get_or_create_wallet, get_wallet, get_course
from dependencies import ACCESS_TOKEN_EXPIRE_MINUTES

# Configurar diretórios de mídia
MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "media")
PROFILE_PICTURES_DIR = os.path.join(MEDIA_DIR, "profile_pictures")
COURSE_COVERS_DIR = os.path.join(MEDIA_DIR, "course_covers")
COURSE_FILES_DIR = os.path.join(MEDIA_DIR, "course_files")

# Criar diretórios se não existirem
os.makedirs(PROFILE_PICTURES_DIR, exist_ok=True)
os.makedirs(COURSE_COVERS_DIR, exist_ok=True)
os.makedirs(COURSE_FILES_DIR, exist_ok=True)

# Router de Autenticação
auth_router = APIRouter()

@auth_router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/register", response_model=schemas.User)
async def register_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    is_first_user = len(users) == 0
    
    return await create_user(db=db, user=user, is_admin=is_first_user)

# Router de Cursos
course_router = APIRouter()

@course_router.get("/cover/{course_id}")
async def get_course_cover(course_id: int, db: AsyncSession = Depends(get_db)):
    """Endpoint para servir a imagem de capa do curso"""
    course = await get_course(db, course_id)
    if not course or not course.cover_image:
        raise HTTPException(status_code=404, detail="Course cover not found")
    
    return FileResponse(course.cover_image)

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

    # Gerar nomes únicos para os arquivos
    cover_filename = f"{uuid.uuid4()}_{cover_image.filename}"
    course_filename = f"{uuid.uuid4()}_{course_file.filename}"
    
    # Definir caminhos completos
    cover_path = os.path.join(COURSE_COVERS_DIR, cover_filename)
    course_path = os.path.join(COURSE_FILES_DIR, course_filename)

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

# Router de Wallet
wallet_router = APIRouter()

@wallet_router.post("/deposit/initialize")
async def initialize_deposit(
    deposit: schemas.DepositInitialize,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Gerar charge_id único
    charge_id = str(uuid.uuid4())

    # Preparar pagamento
    payment = schemas.PaymentInitialize(
        mobile=deposit.mobile,
        amount=deposit.amount,
        charge_id=charge_id,
        email=deposit.email,
        first_name=deposit.first_name,
        last_name=deposit.last_name
    )

    # Inicializar pagamento
    payment_response = await paychangu.initialize_payment(payment)
    
    if payment_response["status"] != "success":
        raise HTTPException(
            status_code=400,
            detail=payment_response.get("message", "Payment initialization failed")
        )

    # Registrar transação pendente
    wallet = await get_or_create_wallet(db, current_user.id)
    transaction = models.WalletTransaction(
        wallet_id=wallet.id,
        amount=float(deposit.amount),
        transaction_type="deposit",
        payment_ref=payment_response["data"]["ref_id"],
        status="pending"
    )
    db.add(transaction)
    await db.commit()

    return payment_response

@wallet_router.post("/verify-deposit/{payment_ref}")
async def verify_deposit(
    payment_ref: str,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verificar status do pagamento
    payment_status = await paychangu.verify_payment_status(payment_ref)
    
    if payment_status["status"] == "success":
        # Atualizar transação e saldo da wallet
        result = await db.execute(
            select(models.WalletTransaction)
            .where(models.WalletTransaction.payment_ref == payment_ref)
        )
        transaction = result.scalar_one_or_none()
        
        if transaction and transaction.status == "pending":
            transaction.status = "completed"
            
            # Atualizar saldo da wallet
            wallet = await get_wallet(db, current_user.id)
            wallet.balance += transaction.amount
            
            await db.commit()
            
            return {"message": "Deposit completed successfully", "new_balance": wallet.balance}
    
    raise HTTPException(status_code=400, detail="Payment not completed")

# Router de Admin
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
    
    await get_current_admin(db, user_id)
    return {"message": f"User {user.username} promoted to admin"}

# Router de Usuário
user_router = APIRouter()

@user_router.post("/profile/picture")
async def update_profile_picture(
    profile_picture: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not profile_picture.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Profile picture must be PNG or JPEG")

    # Gerar nome único para o arquivo
    filename = f"{uuid.uuid4()}_{profile_picture.filename}"
    file_path = os.path.join(PROFILE_PICTURES_DIR, filename)
    
    # Remover foto antiga se existir
    if current_user.profile_picture and os.path.exists(current_user.profile_picture):
        try:
            os.remove(current_user.profile_picture)
        except:
            pass  # Ignora erros ao tentar remover arquivo antigo
    
    # Salvar nova foto
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_picture.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Atualizar caminho no banco de dados
    current_user.profile_picture = file_path
    await db.commit()
    
    return {"message": "Profile picture updated successfully"}

@user_router.get("/profile/picture/{user_id}")
async def get_profile_picture(user_id: int, db: AsyncSession = Depends(get_db)):
    """Endpoint para servir a foto de perfil do usuário"""
    stmt = select(models.User).where(models.User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.profile_picture:
        raise HTTPException(status_code=404, detail="Profile picture not found")
    
    return FileResponse(user.profile_picture)