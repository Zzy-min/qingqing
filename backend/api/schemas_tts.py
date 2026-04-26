from pydantic import BaseModel, Field
from typing import Optional, List


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Text to synthesize (max 10k chars)")
    model: str = Field(
        default="speech-2.8-hd",
        description=(
            "TTS model. Token Plan recommended: speech-2.8-hd, speech-2.6-hd, speech-02-hd. "
            "Legacy aliases speech-2.6 / speech-02 are auto-mapped."
        ),
    )
    voice: str = Field(default="English_expressive_narrator", description="Voice ID")
    speed: Optional[float] = Field(default=None, description="Speech speed multiplier (normalized to [0.5, 2.0])")
    volume: Optional[float] = Field(default=None, description="Volume level (normalized to (0, 10])")
    pitch: Optional[int] = Field(default=None, description="Pitch adjustment (normalized to [-12, 12])")
    format: str = Field(default="mp3", description="Audio format: mp3, wav, pcm")
    sample_rate: int = Field(default=32000, description="Sample rate in Hz")
    bitrate: int = Field(default=128000, description="Bitrate in bps")
    channels: int = Field(default=1, ge=1, le=2, description="Audio channels: 1 (mono), 2 (stereo)")
    language_boost: Optional[str] = Field(
        default=None,
        description="Language boost code. Accepts short codes (zh/en/ja/ko/fr/de/es) and official enum values.",
    )
    subtitles: bool = Field(default=False, description="Include subtitle timing")
    pronunciation: Optional[List[str]] = Field(default=None, description="Custom pronunciation dict: 'text/replacement'")


class TTSResponse(BaseModel):
    success: bool
    audio_data: Optional[str] = None  # base64 data URL
    audio_url: Optional[str] = None   # direct URL fallback
    duration_ms: Optional[int] = None
    sample_rate: Optional[int] = None
    subtitles: Optional[str] = None
    message: str = ""


class VoiceItem(BaseModel):
    voice_id: str
    voice_name: Optional[str] = None
    source: Optional[str] = None
    description: Optional[List[str]] = None
    created_time: Optional[str] = None


class VoiceListResponse(BaseModel):
    voices: List[str]
    items: List[VoiceItem] = []
    source: str = "official"
