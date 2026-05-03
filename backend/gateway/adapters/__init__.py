# backend/gateway/adapters/__init__.py
import importlib
import pkgutil
from .base import ProviderAdapter, Capability, CapabilityNotSupported

_registry: dict[str, ProviderAdapter] = {}


def discover_adapters():
    _registry.clear()
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name.startswith("_") or module_name == "base":
            continue
        module = importlib.import_module(f".{module_name}", __package__)
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, ProviderAdapter) and obj is not ProviderAdapter:
                instance = obj()
                _registry[instance.provider_id] = instance


def get_adapter(provider_id: str) -> ProviderAdapter:
    if provider_id not in _registry:
        raise KeyError(f"No adapter for provider: {provider_id}")
    return _registry[provider_id]


def list_adapters() -> dict[str, ProviderAdapter]:
    return dict(_registry)
