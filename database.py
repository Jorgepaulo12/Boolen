from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Configuração do MySQL
MYSQL_USER = "avnadmin"
MYSQL_PASSWORD = "AVNS_ykNZYlJpoMZgLzg37yx"
MYSQL_HOST = "mysql-3cab6e4e-jorgesebastiao900-366f.k.aivencloud.com"
MYSQL_PORT = "15277"
MYSQL_DB = "defaultdb"

# String de conexão para MySQL
DATABASE_URL = f"mysql+aiomysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?ssl-mode=REQUIRED"

# Criar engine assíncrona
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Criar fábrica de sessões assíncrona
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncSession:
    """Dependency para obter uma sessão do banco de dados."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() 
