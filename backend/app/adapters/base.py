"""Uniform adapter contract.

Adapters ONLY handle connectivity, auth and I/O. They must NOT make business
decisions (routing, policy). All results are returned in a uniform AdapterResult.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AdapterResult:
    ok: bool
    http_status: Optional[int] = None
    resource: Optional[dict] = None          # single FHIR resource
    bundle: Optional[dict] = None            # FHIR Bundle (search result)
    error: Optional[dict] = None             # {category, message, retryable, detail}
    meta: dict = field(default_factory=dict)  # e.g. {"created": True}


def make_error(category: str, message: str, retryable: bool = False, detail: str = "") -> dict:
    return {
        "category": category,       # connectivity|auth|not_found|validation|server|unknown
        "message": message,
        "retryable": retryable,
        "detail": detail,
    }


class AdapterInterface(ABC):
    name: str

    @abstractmethod
    async def check_connectivity(self) -> AdapterResult: ...

    @abstractmethod
    async def get_capability(self) -> AdapterResult: ...

    @abstractmethod
    async def read(self, resource_type: str, resource_id: str) -> AdapterResult: ...

    @abstractmethod
    async def search(self, resource_type: str, params: dict) -> AdapterResult: ...

    @abstractmethod
    async def create(self, resource_type: str, resource: dict) -> AdapterResult: ...

    @abstractmethod
    async def update(self, resource_type: str, resource_id: str, resource: dict) -> AdapterResult: ...

    async def transaction(self, bundle: dict) -> AdapterResult:
        """POST a FHIR transaction Bundle to the server base URL."""
        raise NotImplementedError
