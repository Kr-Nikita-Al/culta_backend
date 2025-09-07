from typing import Generator

from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

import settings

###############################
# БЛОК ПО ВЗАИМОДЕЙСТВИЯ С БД #
###############################

# create async engine for interaction with database
engine = create_async_engine(settings.REAL_DATABASE_URL,
                             future=True,
                             echo=True,
                             pool_size=20,
                             max_overflow=10,
                             pool_timeout=30,  # 30 секунд таймаут для получения соединения
                             pool_recycle=1800,  # Пересоздавать соединения каждые 30 минут
                             pool_pre_ping=True,  # Проверять соединение перед использованием
                             )

# create session for the interaction with database
async_session = sessionmaker(engine,
                             autoflush=False,
                             expire_on_commit=False,
                             class_=AsyncSession)


async def get_db() -> AsyncSession:
    """
    Улучшенная асинхронная фабрика сессий с обработкой ошибок соединения
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


