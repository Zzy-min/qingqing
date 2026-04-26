from pydantic import BaseModel, Field
from typing import Optional, List


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Video description/storyboard")
    model: str = Field(default="MiniMax-Hailuo-2.3", description="Model: MiniMax-Hailuo-2.3, MiniMax-Hailuo-2.3-Fast, MiniMax-Hailuo-02, S2V-01")
    first_frame: Optional[str] = Field(default=None, description="First frame image as data URL or URL")
    last_frame: Optional[str] = Field(default=None, description="Last frame image for SEF mode (requires first_frame)")
    subject_image: Optional[str] = Field(default=None, description="Subject reference image for character consistency")
    duration: Optional[int] = Field(default=None, description="Video duration in seconds, usually 6 or 10")
    resolution: Optional[str] = Field(default=None, description="Video resolution: 512P, 720P, 768P, 1080P")
    prompt_optimizer: Optional[bool] = Field(default=None, description="Whether to auto-optimize prompt")
    fast_pretreatment: Optional[bool] = Field(default=None, description="Reduce prompt optimization latency when supported")
    aigc_watermark: Optional[bool] = Field(default=None, description="Whether to add AIGC watermark")
    callback_url: Optional[str] = Field(default=None, description="Webhook URL for completion notification")
    no_wait: bool = Field(default=False, description="Return task ID immediately without polling")


class VideoTaskRequest(BaseModel):
    task_id: str = Field(..., description="Video generation task ID")


class VideoResponse(BaseModel):
    success: bool
    task_id: Optional[str] = None
    status: Optional[str] = None  # Pending, Processing, Success, Failed
    video_url: Optional[str] = None
    video_data: Optional[str] = None  # base64 data URL
    video_width: Optional[int] = None
    video_height: Optional[int] = None
    message: str = ""
