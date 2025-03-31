from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os

# Criar diretório data se não existir
os.makedirs("data", exist_ok=True)

# Configurações do banco de dados
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./data/database.db"

# Configuração do banco de dados
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False}  # Necessário para SQLite
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Database dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() 