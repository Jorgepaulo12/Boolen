from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
from jose import jwt, JWTError
from dependencies import SECRET_KEY, ALGORITHM

import models
import schemas
from auth import get_current_user, get_user
from database import get_db
from utils import get_or_create_wallet, get_wallet
from payment import paychangu

# Configurar templates
templates = Jinja2Templates(directory="templates")

wallet_router = APIRouter()

@wallet_router.post("/deposit/initialize")
async def initialize_deposit(
    deposit: schemas.DepositInitialize,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Gerar charge_id único
    charge_id = str(uuid.uuid4())
    
    # Criar objeto de pagamento com dados do usuário logado
    payment = schemas.PaymentInitialize(
        mobile=deposit.mobile,
        amount=deposit.amount,
        charge_id=charge_id
    )

    # Inicializar pagamento
    payment_response = await paychangu.initialize_payment(payment)
    
    if payment_response["status"] == "success":
        # Registrar transação e atualizar saldo imediatamente
        wallet = await get_or_create_wallet(db, current_user.id)
        
        # Criar a transação como completed
        transaction = models.WalletTransaction(
            wallet_id=wallet.id,
            amount=float(deposit.amount),
            transaction_type="deposit",
            payment_ref=payment_response["data"]["ref_id"],
            status="completed"  # Alterado de 'pending' para 'completed'
        )
        db.add(transaction)

        # Atualizar o saldo da wallet imediatamente
        wallet.balance += float(deposit.amount)
        
        await db.commit()

        # Retornar resposta com o novo saldo
        return {
            **payment_response,
            "wallet_balance": wallet.balance
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=payment_response.get("message", "Payment initialization failed")
        )

@wallet_router.post("/verify-deposit/{payment_ref}")
async def verify_deposit(
    payment_ref: str,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    payment_status = await paychangu.verify_payment_status(payment_ref)
    
    if payment_status["status"] == "success":
        result = await db.execute(
            select(models.WalletTransaction)
            .where(models.WalletTransaction.payment_ref == payment_ref)
        )
        transaction = result.scalar_one_or_none()
        
        if transaction and transaction.status == "pending":
            transaction.status = "completed"
            wallet = await get_wallet(db, current_user.id)
            wallet.balance += transaction.amount
            await db.commit()
            return {"message": "Deposit completed successfully", "new_balance": wallet.balance}
    
    raise HTTPException(status_code=400, detail="Payment not completed")

@wallet_router.get("/deposit", response_class=HTMLResponse)
async def show_deposit_page(
    request: Request,
    amount: str,
    email: str,
    first_name: str,
    last_name: str,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = await get_user(db, username=username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
            
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    charge_id = str(uuid.uuid4())
    return templates.TemplateResponse(
        "payment.html",
        {
            "request": request,
            "amount": amount,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "charge_id": charge_id,
            "token": token
        }
    )

@wallet_router.get("/deposit/result")
async def deposit_result(
    tx_ref: str,
    status: str,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if status == "successful":
        result = await db.execute(
            select(models.WalletTransaction)
            .where(models.WalletTransaction.payment_ref == tx_ref)
        )
        transaction = result.scalar_one_or_none()
        
        if transaction and transaction.status == "pending":
            transaction.status = "completed"
            wallet = await get_wallet(db, current_user.id)
            wallet.balance += transaction.amount
            await db.commit()
            return {"message": "Deposit completed successfully", "new_balance": wallet.balance}
    
    return {"message": "Payment failed or already processed"}

# ... código das rotas de wallet ... 