# backend/gateway/adapters/ernie_adapter.py
import httpx
from typing import AsyncIterator
from .base import ProviderAdapter, Capability
from gateway.schemas.chat import ChatRequest, ChatChunk
from gateway.schemas.image import ImageRequest, ImageResponse, ImageData
from gateway.config import get_keys
from gateway.errors import AuthError


class ERNIEAdapter(ProviderAdapter):
    provider_id = "ernie"
    capabilities = {Capability.CHAT, Capability.IMAGE}
    request_timeout = 60

    async def _get_access_token(self) -> str:
        keys = get_keys()
        if not keys.ernie_api_key or not keys.ernie_secret_key:
            raise AuthError("ernie", "ERNIE requires both API_KEY and SECRET_KEY", "auth_missing")
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://aip.baidubce.com/oauth/2.0/token",
                                    params={"grant_type": "client_credentials", "client_id": keys.ernie_api_key, "client_secret": keys.ernie_secret_key})
            if resp.status_code != 200:
                raise AuthError("ernie", "ERNIE token exchange failed", "auth_failed")
            return resp.json()["access_token"]

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        token = await self._get_access_token()
        model_name = request.model.split(":", 1)[1]
        messages = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)} for m in request.messages]
        payload = {"messages": messages, "temperature": request.temperature, "max_output_tokens": request.max_tokens}
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model_name}?access_token={token}"

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        yield ChatChunk(model=request.model, delta=data.get("result", ""), finish_reason="stop")

    async def image(self, request: ImageRequest) -> ImageResponse:
        token = await self._get_access_token()
        model_name = request.model.split(":", 1)[1]
        payload = {"prompt": request.prompt, "size": request.size.replace("x", "×")}
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/text2image/{model_name}?access_token={token}"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        images = [ImageData(b64_json=img.get("image")) for img in data.get("data", [])]
        return ImageResponse(model=request.model, images=images)
