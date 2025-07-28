from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import POSTGRES_DB_URL

pg_engine = create_async_engine(POSTGRES_DB_URL, echo=True)
AsyncPostgresSessionLocal= sessionmaker( bind=pg_engine, class_=AsyncSession, expire_on_commit=False,)
PostgresBase = declarative_base()
