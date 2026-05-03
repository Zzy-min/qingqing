# backend/gateway/registry/models.py
from dataclasses import dataclass
from gateway.adapters.base import Capability


@dataclass
class ModelEntry:
    provider: str
    display_name: str
    capabilities: set[Capability]
    context_window: int = 0
    supports_vision: bool = False
    supports_streaming: bool = True


MODEL_REGISTRY: dict[str, ModelEntry] = {
    # OpenAI
    "openai:gpt-4o": ModelEntry(provider="openai", display_name="GPT-4o", capabilities={Capability.CHAT}, context_window=128000, supports_vision=True),
    "openai:gpt-4o-mini": ModelEntry(provider="openai", display_name="GPT-4o Mini", capabilities={Capability.CHAT}, context_window=128000, supports_vision=True),
    "openai:dall-e-3": ModelEntry(provider="openai", display_name="DALL·E 3", capabilities={Capability.IMAGE}),
    "openai:tts-1": ModelEntry(provider="openai", display_name="TTS-1", capabilities={Capability.TTS}),
    # Gemini
    "google:gemini-2.5-pro": ModelEntry(provider="google", display_name="Gemini 2.5 Pro", capabilities={Capability.CHAT}, context_window=1000000, supports_vision=True),
    "google:gemini-2.5-flash": ModelEntry(provider="google", display_name="Gemini 2.5 Flash", capabilities={Capability.CHAT}, context_window=1000000, supports_vision=True),
    "google:imagen-3": ModelEntry(provider="google", display_name="Imagen 3", capabilities={Capability.IMAGE}),
    # Qwen
    "qwen:qwen-vl-max": ModelEntry(provider="qwen", display_name="通义千问 VL Max", capabilities={Capability.CHAT}, supports_vision=True),
    "qwen:qwen-turbo": ModelEntry(provider="qwen", display_name="通义千问 Turbo", capabilities={Capability.CHAT}),
    "qwen:wanx-v1": ModelEntry(provider="qwen", display_name="通义万相", capabilities={Capability.IMAGE}),
    # ERNIE
    "ernie:ernie-4.0": ModelEntry(provider="ernie", display_name="文心一言 4.0", capabilities={Capability.CHAT}),
    # Zhipu
    "zhipu:glm-4": ModelEntry(provider="zhipu", display_name="GLM-4", capabilities={Capability.CHAT}, supports_vision=True),
    "zhipu:cogview-3": ModelEntry(provider="zhipu", display_name="CogView-3", capabilities={Capability.IMAGE}),
    # MiniMax
    "minimax:abab6.5s-chat": ModelEntry(provider="minimax", display_name="MiniMax ABAB 6.5s", capabilities={Capability.CHAT}),
    "minimax:image-01": ModelEntry(provider="minimax", display_name="MiniMax Image-01", capabilities={Capability.IMAGE}),
    "minimax:video-01": ModelEntry(provider="minimax", display_name="MiniMax Video-01", capabilities={Capability.VIDEO}),
    "minimax:music-01": ModelEntry(provider="minimax", display_name="MiniMax Music-01", capabilities={Capability.MUSIC}),
    "minimax:tts-01": ModelEntry(provider="minimax", display_name="MiniMax TTS-01", capabilities={Capability.TTS}),
}


def get_model(model_id: str) -> ModelEntry | None:
    return MODEL_REGISTRY.get(model_id)


def list_models(enabled_only: bool = False, available_providers: set[str] | None = None) -> dict[str, dict]:
    result = {}
    for model_id, entry in MODEL_REGISTRY.items():
        enabled = available_providers is None or entry.provider in available_providers
        if enabled_only and not enabled:
            continue
        result[model_id] = {
            "id": model_id,
            "provider": entry.provider,
            "display_name": entry.display_name,
            "capabilities": [c.value for c in entry.capabilities],
            "supports_vision": entry.supports_vision,
            "supports_streaming": entry.supports_streaming,
            "enabled": enabled,
            "disabled_reason": None if enabled else f"Provider '{entry.provider}' API key not configured",
        }
    return result
