import asyncio
import logging
from typing import Optional, Set

logger = logging.getLogger("clipforge.workers.cancellation")

class CancellationToken:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self._cancelled = False
        self._pids: Set[int] = set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def register_pid(self, pid: int):
        self._pids.add(pid)

    def cancel(self):
        self._cancelled = True
        logger.info(f"Cancellation requested for job {self.job_id}")

class CancellationManager:
    _tokens: dict[str, CancellationToken] = {}

    @classmethod
    def create_token(cls, job_id: str) -> CancellationToken:
        token = CancellationToken(job_id)
        cls._tokens[job_id] = token
        return token

    @classmethod
    def get_token(cls, job_id: str) -> Optional[CancellationToken]:
        return cls._tokens.get(job_id)

    @classmethod
    def cancel_job(cls, job_id: str) -> bool:
        token = cls._tokens.get(job_id)
        if token:
            token.cancel()
            return True
        return False

    @classmethod
    def remove_token(cls, job_id: str):
        cls._tokens.pop(job_id, None)
