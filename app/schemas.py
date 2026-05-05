from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModelStatus(BaseModel):
    name: str
    path: str
    available: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    device: Literal["cpu"]
    models: list[ModelStatus]


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    speaker: str | None = None


class DiarizationSegment(BaseModel):
    start: float
    end: float
    speaker: str


class TranscriptionResponse(BaseModel):
    language: str | None = None
    language_probability: float | None = None
    segments: list[TranscriptSegment]
    text: str


class DiarizationResponse(BaseModel):
    segments: list[DiarizationSegment]


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    direction: Literal["vi-en", "en-vi"] = "vi-en"
    max_new_tokens: int = Field(default=256, ge=1, le=1024)


class TranslateResponse(BaseModel):
    direction: Literal["vi-en", "en-vi"]
    text: str
    translated_text: str


class SummaryRequest(BaseModel):
    text: str = Field(min_length=1)
    max_new_tokens: int = Field(default=160, ge=1, le=512)
    min_new_tokens: int = Field(default=24, ge=1, le=256)


class SummaryResponse(BaseModel):
    text: str
    summary: str


class ActionItem(BaseModel):
    task: str
    assignee: str | None = None
    deadline: str | None = None


class LLMRefinement(BaseModel):
    summary: str | None = None
    action_items: list[ActionItem] = Field(default_factory=list)
    meeting_minutes: str | None = None
    risks_or_blockers: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    raw_text: str | None = None
    parsed_json: bool = False
    error: str | None = None


class LLMTranscriptCorrection(BaseModel):
    corrected_transcript: TranscriptionResponse | None = None
    raw_text: str | None = None
    parsed_json: bool = False
    error: str | None = None


class LLMTestRequest(BaseModel):
    transcript: str | None = None


class LLMHealthResponse(BaseModel):
    ok: bool
    model: str
    base_url: str
    result: LLMRefinement | None = None
    error: str | None = None


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: Literal["processing"]


class JobProcessingResponse(BaseModel):
    status: Literal["processing"]


class ProcessResponse(BaseModel):
    transcript: TranscriptionResponse
    original_transcript: TranscriptionResponse | None = None
    transcript_correction: LLMTranscriptCorrection | None = None
    diarization: DiarizationResponse | None = None
    merged_transcript: str
    translated_transcript: str | None = None
    translated_text: str | None = None
    summary: str | None = None
    translated_summary: str | None = None
    llm: LLMRefinement | None = None
    llm_summary: str | None = None
    action_items: list[ActionItem] = Field(default_factory=list)
    meeting_minutes: str | None = None
    risks_or_blockers: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    normalized_audio_path: str
    warnings: list[str] = Field(default_factory=list)
