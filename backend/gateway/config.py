# backend/gateway/config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ProviderKeys:
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    google_api_key: str = ""
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    ernie_api_key: str = ""
    ernie_secret_key: str = ""
    zhipu_api_key: str = ""
    minimax_api_key: str = ""
    minimax_group_id: str = ""

    @classmethod
    def from_env(cls) -> "ProviderKeys":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            qwen_api_key=os.getenv("QWEN_API_KEY", ""),
            qwen_base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/api/v1"),
            ernie_api_key=os.getenv("ERNIE_API_KEY", ""),
            ernie_secret_key=os.getenv("ERNIE_SECRET_KEY", ""),
            zhipu_api_key=os.getenv("ZHIPU_API_KEY", ""),
            minimax_api_key=os.getenv("MINIMAX_API_KEY", ""),
            minimax_group_id=os.getenv("MINIMAX_GROUP_ID", ""),
        )

    def available_providers(self) -> set[str]:
        providers = set()
        if self.openai_api_key: providers.add("openai")
        if self.google_api_key: providers.add("google")
        if self.qwen_api_key: providers.add("qwen")
        if self.ernie_api_key and self.ernie_secret_key: providers.add("ernie")
        if self.zhipu_api_key: providers.add("zhipu")
        if self.minimax_api_key: providers.add("minimax")
        return providers


_keys = None


def get_keys() -> ProviderKeys:
    global _keys
    if _keys is None:
        _keys = ProviderKeys.from_env()
    return _keys


def get_api_key(provider_id: str, header_key: str | None = None) -> str:
    if header_key:
        return header_key
    return getattr(get_keys(), f"{provider_id}_api_key", "") or ""


def get_base_url(provider_id: str, header_url: str | None = None) -> str | None:
    if header_url:
        return header_url
    return getattr(get_keys(), f"{provider_id}_base_url", None) or None
