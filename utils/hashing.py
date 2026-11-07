import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

from fastapi import HTTPException
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


class PasswordWorkerPool:
    """Bound CPU work and queued requests independently of the default executor.

    Capacity is per API process. Cancellation must not free a slot while the
    underlying bcrypt operation is still running in its worker thread.
    """

    def __init__(self, workers=4, capacity=16):
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='password')
        self.slots = BoundedSemaphore(capacity)

    async def run(self, operation, *args):
        if not self.slots.acquire(blocking=False):
            raise HTTPException(503, 'Password service is busy; retry shortly',
                                headers={'Retry-After': '1'})
        try:
            future = self.executor.submit(operation, *args)
        except BaseException:
            self.slots.release()
            raise
        future.add_done_callback(lambda _: self.slots.release())
        return await asyncio.wrap_future(future)


password_workers = PasswordWorkerPool()


class Hasher:
    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    async def hash_async(password: str) -> str:
        return await password_workers.run(Hasher.get_password_hash, password)

    @staticmethod
    async def verify_async(plain_password: str, hashed_password: str) -> bool:
        return await password_workers.run(Hasher.verify_password, plain_password, hashed_password)
