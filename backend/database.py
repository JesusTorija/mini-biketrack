import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Leer URL de la base de datos desde variables de entorno
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://hc_user:hc_password_secret@localhost:5432/hors_categorie_db"
)

# Motor de base de datos asíncrono
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Cambiar a True para ver las consultas SQL en consola durante desarrollo
    future=True
)

# Fabrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Clase base para los futuros modelos/tablas
Base = declarative_base()

# Dependencia de FastAPI para inyectar la sesión DB en los endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()