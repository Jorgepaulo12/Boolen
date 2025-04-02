from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Criar tabelas no banco de dados
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield

# Configuração do FastAPI
app = FastAPI(
    title="Course Management Boolen",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Importar e incluir routers
from routes.auth import auth_router
from routes.courses import course_router
from routes.wallet import wallet_router
from routes.admin import admin_router
from routes.users import user_router

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(course_router, prefix="/courses", tags=["Courses"])
app.include_router(wallet_router, prefix="/wallet", tags=["Wallet"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(user_router, prefix="/users", tags=["Users"])

@app.get("/")
async def root():
    return {"message": "Welcome to Course Management System"}

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", 8080))  # Usa 8080 como padrão
    uvicorn.run(app, host="0.0.0.0", port=port)
