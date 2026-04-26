import asyncio
import base64
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Header

from api.schemas import (
    ErrorResponse,
    GenerateRequest,
    ImageResponse,
    ProcessRequest,
    TokenPlanRemainsResponse,
)
from api.key_override import normalize_override_key
from services.image_processor import ImageProcessor
from services.minimax import MiniMaxService
from services.token_plan import TokenPlanService
from version import APP_VERSION

logger = logging.getLogger(__name__)

router = APIRouter(tags=['image'])

_minimax_service: Optional[MiniMaxService] = None
_image_processor: Optional[ImageProcessor] = None
_token_plan_service: Optional[TokenPlanService] = None
_service_lock = asyncio.Lock()
_token_plan_lock = asyncio.Lock()


async def get_minimax_service() -> MiniMaxService:
    global _minimax_service
    if _minimax_service is None:
        async with _service_lock:
            if _minimax_service is None:  # double-check
                _minimax_service = MiniMaxService()
    return _minimax_service


def get_image_processor() -> ImageProcessor:
    global _image_processor
    if _image_processor is None:
        _image_processor = ImageProcessor()
    return _image_processor


async def get_token_plan_service() -> TokenPlanService:
    global _token_plan_service
    if _token_plan_service is None:
        async with _token_plan_lock:
            if _token_plan_service is None:
                _token_plan_service = TokenPlanService()
    return _token_plan_service


async def _resolve_minimax_service(
    x_minimax_api_key: Optional[str],
) -> tuple[MiniMaxService, bool]:
    override_key = normalize_override_key(x_minimax_api_key)
    if override_key:
        return MiniMaxService(api_key=override_key), True
    return await get_minimax_service(), False


async def _resolve_token_plan_service(
    x_minimax_api_key: Optional[str],
) -> tuple[TokenPlanService, bool]:
    override_key = normalize_override_key(x_minimax_api_key)
    if override_key:
        return TokenPlanService(api_key=override_key), True
    return await get_token_plan_service(), False


@router.get('/health', response_model=dict)
async def health_check():
    return {'status': 'ok', 'version': APP_VERSION}


@router.get('/token-plan/remains', response_model=TokenPlanRemainsResponse)
async def token_plan_remains(
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    service, close_after = await _resolve_token_plan_service(x_minimax_api_key)
    try:
        return await service.fetch_remains()
    except httpx.HTTPStatusError as e:
        logger.error('Token Plan API error: %s %s', e.response.status_code, e.response.text[:200])
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
    except httpx.RequestError as e:
        logger.error('Token Plan network error: %s', e)
        raise HTTPException(status_code=502, detail=f'Network error: {e}')
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception('Unexpected error in token_plan_remains')
        raise HTTPException(status_code=500, detail=f'Internal error: {e}')
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning('Failed to close request-scoped token service')


def _extract_base64(data: str) -> bytes:
    if not data:
        raise HTTPException(status_code=400, detail='Empty image data')
    if ',' in data:
        data = data.split(',', 1)[1]
    try:
        return base64.b64decode(data)
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid base64 image data')


def _make_data_url(b64_str: str, mime: str = 'image/jpeg') -> str:
    if b64_str.startswith('data:'):
        return b64_str
    return f'data:{mime};base64,{b64_str}'


async def _download_image_as_data_url(image_url: str) -> str:
    from services.minimax import _is_url_safe
    if not _is_url_safe(image_url):
        raise ValueError(f'Unsafe image URL: {image_url[:80]}')

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()

    content_type = resp.headers.get('content-type', 'image/jpeg')
    b64 = base64.b64encode(resp.content).decode('ascii')
    return f'data:{content_type};base64,{b64}'


async def _download_multiple_images(image_urls: list) -> list:
    tasks = [_download_image_as_data_url(url) for url in image_urls]
    results = []
    for coro in asyncio.as_completed(tasks):
        try:
            results.append(await coro)
        except Exception as e:
            logger.warning('Failed to download image: %s', e)
            results.append(None)
    return results


@router.post('/generate', response_model=ImageResponse, responses={500: {'model': ErrorResponse}})
async def generate_image(
    request: GenerateRequest,
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    """Unified text2img and img2img endpoint.

    - Without image_data: text-to-image generation
    - With image_data: img2img (reference image + prompt)
    """
    service, close_after = await _resolve_minimax_service(x_minimax_api_key)
    try:
        result = await service.generate_image(
            prompt=request.prompt,
            model=request.model,
            negative_prompt=request.negative_prompt,
            aspect_ratio=request.aspect_ratio,
            n=request.n,
            seed=request.seed,
            aigc_watermark=request.aigc_watermark if request.aigc_watermark is not None else request.logo_watermark,
            prompt_optimizer=request.prompt_optimizer,
            response_format=request.response_format,
            width=request.width,
            height=request.height,
            image_data=request.image_data,
        )

        image_urls = result.get('image_urls', [])
        image_base64 = result.get('image_base64', [])
        if image_base64:
            data_urls = [_make_data_url(value) for value in image_base64 if value]
            if len(data_urls) == 1:
                return ImageResponse(
                    success=True,
                    image_data=data_urls[0],
                    message='Image generated successfully',
                    dimensions=None,
                )
            if len(data_urls) > 1:
                return ImageResponse(
                    success=True,
                    image_data=data_urls[0],
                    images=data_urls,
                    message=f'{len(data_urls)} images generated',
                )

        if not image_urls:
            raw = result.get('_raw', {})
            detail = f'MiniMax returned no image. Response: {str(raw)[:300]}'
            logger.error(detail)
            raise HTTPException(status_code=502, detail=detail)

        logger.info('Downloading %d generated images', len(image_urls))
        try:
            data_urls = await _download_multiple_images(image_urls)
            # Filter out None (failed downloads)
            valid_urls = [u for u in data_urls if u is not None]

            if len(valid_urls) == 1:
                return ImageResponse(
                    success=True,
                    image_data=valid_urls[0],
                    message='Image generated successfully',
                    dimensions=None,
                )
            elif len(valid_urls) > 1:
                return ImageResponse(
                    success=True,
                    image_data=valid_urls[0],
                    images=valid_urls,
                    message=f'{len(valid_urls)} images generated',
                )
            else:
                # All downloads failed, return URL fallback
                return ImageResponse(
                    success=True,
                    image_url=image_urls[0],
                    message='Image generated (direct URL)',
                )
        except Exception as e:
            logger.warning('Failed to download images, returning URL fallback: %s', e)
            return ImageResponse(
                success=True,
                image_url=image_urls[0],
                message='Image generated (direct URL)',
            )
    except httpx.HTTPStatusError as e:
        logger.error('MiniMax API error: %s %s', e.response.status_code, e.response.text[:200])
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
    except httpx.RequestError as e:
        logger.error('Network error: %s', e)
        raise HTTPException(status_code=502, detail=f'Network error: {e}')
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception('Unexpected error in generate_image')
        raise HTTPException(status_code=500, detail=f'Internal error: {e}')
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning('Failed to close request-scoped image service')


@router.post('/process', response_model=ImageResponse, responses={500: {'model': ErrorResponse}})
async def process_image(
    request: ProcessRequest,
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    image_bytes = _extract_base64(request.image_data)

    if request.prompt:
        processor = get_image_processor()
        try:
            validation_result = await asyncio.to_thread(
                processor.validate_and_prepare, image_bytes
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        service, close_after = await _resolve_minimax_service(x_minimax_api_key)
        try:
            result = await service.process_image(
                image_data=validation_result['base64'],
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                style=request.style or 'general',
            )
            image_urls = result.get('image_urls', [])
            if not image_urls:
                raw = result.get('_raw', {})
                detail = f'MiniMax returned no image. Response: {str(raw)[:300]}'
                raise HTTPException(status_code=502, detail=detail)

            # Try to download first image
            image_url = image_urls[0]
            try:
                data_url = await _download_image_as_data_url(image_url)
            except Exception as e:
                logger.warning('Failed to download image: %s', e)
                return ImageResponse(
                    success=True,
                    image_url=image_url,
                    message='Image processed (direct URL)',
                    style=request.style,
                    dimensions=validation_result.get('dimensions'),
                )

            return ImageResponse(
                success=True,
                image_data=data_url,
                message='Image processed successfully',
                style=request.style,
                dimensions=validation_result.get('dimensions'),
            )
        except httpx.HTTPStatusError as e:
            logger.error('MiniMax API error: %s %s', e.response.status_code, e.response.text[:200])
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f'Network error: {e}')
        finally:
            if close_after:
                try:
                    await service.close()
                except Exception:
                    logger.warning('Failed to close request-scoped process service')
    else:
        processor = get_image_processor()
        try:
            result_b64 = await asyncio.to_thread(
                processor.apply_filters,
                image_bytes,
                brightness=request.brightness,
                contrast=request.contrast,
                saturation=request.saturation,
                sharpness=request.sharpness,
                blur=request.blur,
                rotate=request.rotate,
                flip_h=request.flip_h,
                flip_v=request.flip_v,
                filter_type=request.filter_type,
            )
            data_url = _make_data_url(result_b64)
            return ImageResponse(success=True, image_data=data_url, message='Filter applied')
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception('Unexpected error in process_image (filters)')
            raise HTTPException(status_code=500, detail=f'Internal error: {e}')
