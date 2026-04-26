from pydantic import BaseModel, Field
from typing import Optional, List


class MusicGenerateRequest(BaseModel):
    prompt: str = Field(..., max_length=2000, description="Music style description")
    lyrics: Optional[str] = Field(default=None, max_length=3500, description="Song lyrics with structure tags")
    instrumental: bool = Field(default=False, description="Generate instrumental (no vocals)")
    lyrics_optimizer: bool = Field(default=False, description="Auto-generate lyrics from prompt")
    model: str = Field(default="music-2.6", description="Model: music-2.6, music-2.6-free, music-2.5+, music-2.5")
    vocals: Optional[str] = Field(default=None, description="Vocal style description")
    genre: Optional[str] = Field(default=None, description="Music genre")
    mood: Optional[str] = Field(default=None, description="Mood/emotion")
    instruments: Optional[str] = Field(default=None, description="Instruments to feature")
    tempo: Optional[str] = Field(default=None, description="Tempo description")
    bpm: Optional[int] = Field(default=None, ge=20, le=300)
    key: Optional[str] = Field(default=None, description="Musical key")
    avoid: Optional[str] = Field(default=None, description="Elements to avoid")
    use_case: Optional[str] = Field(default=None, description="Use case context")
    structure: Optional[str] = Field(default=None, description="Song structure")
    references: Optional[str] = Field(default=None, description="Reference tracks/artists")
    extra: Optional[str] = Field(default=None, description="Extra fine-grained requirements")
    format: str = Field(default="mp3", description="Audio format: mp3, wav, pcm")
    sample_rate: int = Field(default=44100, description="Sample rate in Hz")
    bitrate: int = Field(default=256000, description="Bitrate in bps")
    aigc_watermark: bool = Field(default=False, description="Embed AIGC watermark")


class MusicCoverRequest(BaseModel):
    prompt: str = Field(..., description="Target cover style description")
    audio_url: Optional[str] = Field(default=None, description="Reference audio URL (6s-6min, max 50MB)")
    audio_data: Optional[str] = Field(default=None, description="Reference audio as base64 data URL")
    lyrics: Optional[str] = Field(default=None, description="Cover lyrics (if omitted, extracted via ASR)")
    model: str = Field(default="music-cover", description="Model: music-cover, music-cover-free")
    seed: Optional[int] = Field(default=None, ge=0, le=1000000, description="Random seed for reproducibility")
    format: str = Field(default="mp3", description="Audio format: mp3, wav, pcm")
    sample_rate: int = Field(default=44100, description="Sample rate in Hz")
    bitrate: int = Field(default=256000, description="Bitrate in bps")
    channels: int = Field(default=2, ge=1, le=2, description="Channels: 1 (mono), 2 (stereo)")


class MusicResponse(BaseModel):
    success: bool
    audio_data: Optional[str] = None   # base64 data URL
    audio_url: Optional[str] = None     # direct URL
    task_id: Optional[str] = None       # for async tracking
    message: str = ""
