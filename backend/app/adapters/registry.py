"""Adapter registry — resolves a system name to a concrete adapter instance."""
from app.adapters.base import AdapterInterface
from app.adapters.openmrs import OpenMRSAdapter
from app.adapters.openemr import OpenEMRAdapter
from app.adapters.satusehat import SatusehatAdapter

_ADAPTERS: dict[str, type[AdapterInterface]] = {
    "openmrs": OpenMRSAdapter,
    "openemr": OpenEMRAdapter,
    "satusehat": SatusehatAdapter,
}


def get_adapter(name: str) -> AdapterInterface:
    try:
        return _ADAPTERS[name]()
    except KeyError as exc:
        raise ValueError(f"Adapter tidak dikenal: {name}") from exc


def available_adapters() -> list[str]:
    return list(_ADAPTERS.keys())
