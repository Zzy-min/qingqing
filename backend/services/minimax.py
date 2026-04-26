import logging
from contextlib import asynccontextmanager
from ipaddress import ip_address
from typing import Any, Dict, List, Optional

import httpx

from services.minimax_config import auth_headers, load_minimax_config

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0
MAX_RETRIES = 2

# SSRF whitelist: only MiniMax API domains and specific OSS buckets
ALLOWED_DOMAINS = {
    'api.minimaxi.com',
    'filecdn.minimaxi.com',
    'minimaxi.com',
    # Specific OSS buckets only — no broad oss-cn-*.aliyuncs.com wildcard
    'hailuo-image-algeng-data.oss-cn-wulanchabu.aliyuncs.com',
    'hailuo-image-algeng-data.oss-cn-beijing.aliyuncs.com',
}


def _is_url_safe(url: str) -> bool:
    """Validate URL against SSRF: scheme, private IPs, and domain whitelist."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            return False
        hostname = (parsed.hostname or '').strip().lower()
        if not hostname:
            return False

        # Explicitly reject private/reserved/loopback IP targets.
        try:
            resolved_ip = ip_address(hostname)
            if (
                resolved_ip.is_private
                or resolved_ip.is_loopback
                or resolved_ip.is_link_local
                or resolved_ip.is_multicast
                or resolved_ip.is_reserved
                or resolved_ip.is_unspecified
            ):
                return False
            # Public IP literals are not in allowlist flow.
            return False
        except ValueError:
            # Non-IP hostname: validate against allowlist.
            pass

        # Domain whitelist — exact match or subdomain
        for allowed in ALLOWED_DOMAINS:
            if hostname == allowed or hostname.endswith('.' + allowed):
                return True
        return False
    except Exception:
        return False


class MiniMaxService:

    def __init__(self, api_key: Optional[str] = None):
        self.config = load_minimax_config(api_key=api_key)
        self.api_key = self.config.api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.rest_base_url,
                headers=auth_headers(self.api_key),
                timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    @asynccontextmanager
    async def _request_with_retry(self, method: str, url: str, **kwargs):
        last_error = None
        for attempt in range(MAX_RETRIES):
            client = await self._get_client()
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                yield response
                return
            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500:
                    raise
                last_error = e
                logger.warning('API %s error (attempt %d/%d): %s', method, attempt + 1, MAX_RETRIES, e.response.status_code)
            except httpx.RequestError as e:
                last_error = e
                logger.warning('Network error (attempt %d/%d): %s', attempt + 1, MAX_RETRIES, e)

            if attempt < MAX_RETRIES - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)

        raise last_error or RuntimeError('Max retries exceeded')

    async def generate_image(
        self,
        prompt: str,
        model: str = 'image-01',
        negative_prompt: Optional[str] = None,
        aspect_ratio: str = '1:1',
        n: int = 1,
        seed: Optional[int] = None,
        aigc_watermark: bool = True,
        prompt_optimizer: bool = False,
        response_format: str = 'url',
        width: Optional[int] = None,
        height: Optional[int] = None,
        image_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate image from text prompt, optionally with reference image (img2img).

        When image_data is provided, MiniMax treats this as img2img:
        the generated image is based on the reference image + prompt.
        """
        payload: Dict[str, Any] = {
            'model': model or 'image-01',
            'prompt': prompt,
            'n': n,
            'response_format': response_format or 'url',
            'prompt_optimizer': bool(prompt_optimizer),
            'aigc_watermark': bool(aigc_watermark),
        }
        if width is not None or height is not None:
            if width is None or height is None:
                raise ValueError('width and height must be set together')
            if width % 8 != 0 or height % 8 != 0:
                raise ValueError('width and height must be divisible by 8')
            payload['width'] = width
            payload['height'] = height
        else:
            payload['aspect_ratio'] = aspect_ratio
        if negative_prompt:
            payload['negative_prompt'] = negative_prompt
        if seed is not None:
            payload['seed'] = seed
        if image_data:
            # Strip data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',', 1)[1]
            payload['image'] = image_data

        mode = 'img2img' if image_data else 'text2img'
        logger.info('Calling MiniMax %s: model=%s, prompt=%s, ratio=%s, n=%d', mode, model, prompt[:80], aspect_ratio, n)

        async with self._request_with_retry('POST', '/image_generation', json=payload) as resp:
            data = resp.json()
            logger.info('MiniMax response: %s', str(data)[:500])
            return self._parse_response(data)

    async def process_image(
        self,
        image_data: str,
        prompt: str,
        negative_prompt: Optional[str] = None,
        style: str = 'general',
    ) -> Dict[str, Any]:
        """Process image with prompt — thin wrapper around generate_image for /process endpoint."""
        return await self.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image_data=image_data,
        )

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        base_resp = data.get('base_resp', {})
        status_code = base_resp.get('status_code', 0)
        if status_code != 0:
            status_msg = base_resp.get('status_msg', 'Unknown error')
            raise ValueError(f'MiniMax API error (code={status_code}): {status_msg}')

        result = data.get('data', {})
        image_urls = result.get('image_urls', [])
        image_base64 = result.get('image_base64', [])

        safe_urls: List[str] = []
        for url in image_urls:
            if url and _is_url_safe(url):
                safe_urls.append(url)
            elif url:
                logger.warning('Unsafe URL blocked: %s', url[:100])

        return {
            'image_url': safe_urls[0] if safe_urls else '',
            'image_urls': safe_urls,
            'image_base64': image_base64 if isinstance(image_base64, list) else [],
            '_raw': data,
        }

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
