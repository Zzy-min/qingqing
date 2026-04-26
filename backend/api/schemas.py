from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal


ASPECT_RATIOS = Literal['1:1', '3:4', '4:3', '3:2', '2:3', '9:16', '16:9', '21:9']

class GenerateRequest(BaseModel):
    model: str = Field(
        default='image-01',
        description='Image model: image-01 or image-01-live',
    )
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=1500,
        description='Image generation prompt (MiniMax limit: 1500 chars)',
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        max_length=1500,
        description='Things to avoid in the generated image',
    )
    image_data: Optional[str] = Field(
        default=None,
        description='Optional base64 image for img2img generation',
    )
    aspect_ratio: str = Field(
        default='1:1',
        description='Image aspect ratio: 1:1, 3:4, 4:3, 9:16, 16:9, 21:9',
    )
    n: int = Field(
        default=1,
        ge=1,
        le=9,
        description='Number of images to generate (1-9)',
    )
    seed: Optional[int] = Field(
        default=None,
        description='Random seed for reproducible results',
    )
    prompt_optimizer: bool = Field(
        default=False,
        description='Whether to auto-optimize prompt',
    )
    response_format: Literal['url', 'base64'] = Field(
        default='url',
        description='MiniMax response format: url or base64',
    )
    width: Optional[int] = Field(
        default=None,
        ge=512,
        le=2048,
        description='Custom width, must be paired with height and divisible by 8',
    )
    height: Optional[int] = Field(
        default=None,
        ge=512,
        le=2048,
        description='Custom height, must be paired with width and divisible by 8',
    )
    logo_watermark: bool = Field(
        default=True,
        description='Backward-compatible watermark flag',
    )
    aigc_watermark: Optional[bool] = Field(
        default=None,
        description='Whether to add MiniMax AIGC watermark',
    )


class ProcessRequest(BaseModel):
    image_data: str = Field(
        ...,
        min_length=1,
        max_length=10000000,
        description='Base64-encoded image data',
    )
    prompt: Optional[str] = Field(
        default=None,
        max_length=1500,
        description='Processing instruction (for AI mode)',
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        max_length=1500,
        description='Things to avoid (for AI mode)',
    )
    style: Optional[str] = Field(
        default=None,
        description='Processing style (for AI mode)',
    )
    brightness: Optional[float] = Field(default=None, ge=0, le=3)
    contrast: Optional[float] = Field(default=None, ge=0, le=3)
    saturation: Optional[float] = Field(default=None, ge=0, le=3)
    sharpness: Optional[float] = Field(default=None, ge=0, le=3)
    blur: Optional[float] = Field(default=None, ge=0, le=20)
    rotate: Optional[int] = Field(default=None, ge=-180, le=180)
    flip_h: Optional[bool] = None
    flip_v: Optional[bool] = None
    filter_type: Optional[str] = Field(
        default=None,
        description='Preset filter: vintage, bw, sepia, edge, sharpen',
    )


class ImageResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    image_data: Optional[str] = None
    images: Optional[List[str]] = None
    message: str = ''
    style: Optional[str] = None
    dimensions: Optional[dict] = None


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class TokenPlanNonTextItem(BaseModel):
    model_name: str
    display_name: str
    category: str = 'other'
    usage: Optional[float] = None
    limit: Optional[float] = None
    remaining: Optional[float] = None
    scope: str = 'daily'


class TokenPlanRemainsResponse(BaseModel):
    success: bool
    text_window_usage: Optional[float] = None
    text_window_limit: Optional[float] = None
    non_text_daily_usage: Optional[float] = None
    non_text_daily_limit: Optional[float] = None
    non_text_daily_items: Optional[List[TokenPlanNonTextItem]] = None
    message: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
