from __future__ import annotations

from pathlib import Path
from typing import Annotated
import re
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_ROOT, settings
from app.schemas import (
    DiarizationResponse,
    HealthResponse,
    JobAcceptedResponse,
    JobProcessingResponse,
    LLMHealthResponse,
    LLMTestRequest,
    SummaryRequest,
    SummaryResponse,
    TranslateRequest,
    TranslateResponse,
    TranscriptionResponse,
)
from app.services.audio import normalize_audio, save_upload_bytes
from app.services.ai_pipeline import STTQuality, is_ai_job_running, process_local_ai_job, release_ai_job_reservation, reserve_ai_job
from app.services.diarization import diarization_service
from app.services.job_store import progress_path_for_job, read_progress_json, read_result_json, result_path_for_job, upload_path_for_job
from app.services.llm_service import llm_service
from app.services.model_status import get_model_statuses
from app.services.stt import stt_service
from app.services.summarization import summarization_service
from app.services.translation import Direction
from app.services.translation import translation_service


app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "app" / "static"), name="static")

JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


@app.middleware("http")
async def no_cache_for_local_ui(request: Request, call_next) -> Response:
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


async def save_uploaded_audio(file: UploadFile) -> str:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return str(save_upload_bytes(data, file.filename or "audio"))


async def save_job_upload(file: UploadFile, job_id: str) -> Path:
    output_path = upload_path_for_job(job_id, file.filename or "audio")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    with output_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            total_bytes += len(chunk)
            output.write(chunk)
    if total_bytes == 0:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return output_path


def to_http_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=500, detail=str(exc))


@app.get("/", include_in_schema=False)
def web_app() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "static" / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "static" / "favicon.svg")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", device="cpu", models=get_model_statuses())


@app.get("/health/llm", response_model=LLMHealthResponse)
async def llm_health() -> LLMHealthResponse:
    result = await run_in_threadpool(llm_service.smoke_test)
    return LLMHealthResponse(
        ok=result.error is None,
        model=llm_service.config.model,
        base_url=llm_service.config.base_url,
        result=result,
        error=result.error,
    )


@app.post("/debug/llm-test", response_model=LLMHealthResponse)
async def debug_llm_test(payload: LLMTestRequest) -> LLMHealthResponse:
    result = await run_in_threadpool(llm_service.smoke_test, payload.transcript)
    return LLMHealthResponse(
        ok=result.error is None,
        model=llm_service.config.model,
        base_url=llm_service.config.base_url,
        result=result,
        error=result.error,
    )


@app.get("/models/status")
def models_status():
    return {"models": get_model_statuses()}


@app.post("/api/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: Annotated[UploadFile, File(...)],
    language: Annotated[str, Query(description="Language hint for faster-whisper.")] = "vi",
) -> TranscriptionResponse:
    try:
        uploaded_path = await save_uploaded_audio(file)
        normalized_path = await run_in_threadpool(normalize_audio, Path(uploaded_path))
        return await run_in_threadpool(stt_service.transcribe, normalized_path, language)
    except HTTPException:
        raise
    except Exception as exc:
        raise to_http_error(exc) from exc


@app.post("/api/diarize", response_model=DiarizationResponse)
async def diarize_audio(
    file: Annotated[UploadFile, File(...)],
    num_speakers: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> DiarizationResponse:
    try:
        uploaded_path = await save_uploaded_audio(file)
        normalized_path = await run_in_threadpool(normalize_audio, Path(uploaded_path))
        return await run_in_threadpool(diarization_service.diarize, normalized_path, num_speakers)
    except HTTPException:
        raise
    except Exception as exc:
        raise to_http_error(exc) from exc


@app.post("/api/process", response_model=JobAcceptedResponse)
async def process_audio(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(...)],
    language: str = "vi",
    include_diarization: bool = True,
    translate_to: Direction | None = None,
    include_summary: bool = True,
    include_llm: bool = True,
    num_speakers: Annotated[int | None, Query(ge=1, le=12)] = None,
    meeting_context: str | None = None,
    stt_quality: STTQuality = "balanced",
) -> JobAcceptedResponse:
    reserved = False
    try:
        reserved = reserve_ai_job()
        if not reserved:
            raise HTTPException(
                status_code=429,
                detail="Another AI job is still running. Please wait for it to finish before starting a new one.",
            )
        job_id = uuid.uuid4().hex
        uploaded_path = await save_job_upload(file, job_id)
        background_tasks.add_task(
            process_local_ai_job,
            job_id,
            uploaded_path,
            language,
            include_diarization,
            translate_to,
            include_summary,
            include_llm,
            num_speakers,
            meeting_context,
            stt_quality,
        )
        return JobAcceptedResponse(job_id=job_id, status="processing")
    except HTTPException:
        if reserved:
            release_ai_job_reservation()
        raise
    except Exception as exc:
        if reserved:
            release_ai_job_reservation()
        raise to_http_error(exc) from exc


@app.get("/api/status/{job_id}", response_model=None)
async def get_process_status(job_id: str) -> JobProcessingResponse | dict:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id.")
    result_path = result_path_for_job(job_id)
    if not result_path.exists():
        progress_path = progress_path_for_job(job_id)
        if progress_path.exists():
            return await run_in_threadpool(read_progress_json, job_id)
        if not is_ai_job_running():
            return {
                "job_id": job_id,
                "status": "error",
                "step": "processing",
                "error": "Job is no longer running. It may have been interrupted by a server reload; please process the audio again.",
            }
        return JobProcessingResponse(status="processing")
    return await run_in_threadpool(read_result_json, job_id)


@app.post("/api/translate", response_model=TranslateResponse)
async def translate_text(payload: TranslateRequest) -> TranslateResponse:
    try:
        translated = await run_in_threadpool(
            translation_service.translate,
            payload.text,
            payload.direction,
            payload.max_new_tokens,
        )
        return TranslateResponse(direction=payload.direction, text=payload.text, translated_text=translated)
    except Exception as exc:
        raise to_http_error(exc) from exc


@app.post("/api/summarize", response_model=SummaryResponse)
async def summarize_text(payload: SummaryRequest) -> SummaryResponse:
    try:
        summary = await run_in_threadpool(
            summarization_service.summarize,
            payload.text,
            payload.max_new_tokens,
            payload.min_new_tokens,
        )
        return SummaryResponse(text=payload.text, summary=summary)
    except Exception as exc:
        raise to_http_error(exc) from exc
