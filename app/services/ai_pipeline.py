from __future__ import annotations

import gc
import logging
import shutil
import subprocess
import threading
import traceback
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import requests
import soundfile as sf

from app.config import PROJECT_ROOT, settings
from app.services.audio import find_ffmpeg, read_waveform_for_pyannote
from app.services.diarization import extract_annotation
from app.services.job_store import (
    chunk_dir_for_job,
    normalized_path_for_job,
    write_progress_json,
    write_result_json,
)
from app.services.llm_service import llm_service
from app.services.summarization import summarization_service
from app.services.text_quality import LOW_INFORMATION_SUMMARY, is_low_information_transcript
from app.services.translation import Direction, translation_service


AI_JOB_LOCK = threading.Lock()
AI_JOB_STATE_LOCK = threading.Lock()
AI_JOB_RESERVED = False
logger = logging.getLogger("uvicorn.error")


LLM_STEP_TIMEOUT_SECONDS = 90
STTQuality = Literal["fast", "balanced", "accurate"]


def is_ai_job_running() -> bool:
    with AI_JOB_STATE_LOCK:
        return AI_JOB_RESERVED


def reserve_ai_job() -> bool:
    global AI_JOB_RESERVED
    with AI_JOB_STATE_LOCK:
        if AI_JOB_RESERVED:
            return False
        AI_JOB_RESERVED = True
        return True


def release_ai_job_reservation() -> None:
    global AI_JOB_RESERVED
    with AI_JOB_STATE_LOCK:
        AI_JOB_RESERVED = False


def write_job_progress(job_id: str, step: str, message: str, percent: int) -> None:
    write_progress_json(
        job_id,
        {
            "job_id": job_id,
            "status": "processing",
            "step": step,
            "message": message,
            "percent": percent,
        },
    )

CORRECTION_PROMPT = (
    "Bạn là chuyên gia hiệu đính. Hãy sửa lỗi chính tả từ văn bản thô do AI STT tạo ra. "
    "Sửa các lỗi nhầm lẫn âm sắc (s/x, l/n), trả lại nguyên bản từ mượn tiếng Anh, thêm dấu câu. "
    "TUYỆT ĐỐI KHÔNG tóm tắt hay thay đổi văn phong, nội dung gốc. Giữ nguyên nhãn người nói."
)


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


@dataclass(frozen=True)
class TranscriptTurn:
    id: int
    start: float
    end: float
    speaker: str
    text: str


class PipelineStepError(RuntimeError):
    def __init__(self, step: str, cause: Exception) -> None:
        self.step = step
        self.cause = cause
        super().__init__(f"{step} failed: {cause}")


def process_local_ai_job(
    job_id: str,
    input_path: Path,
    language: str = "vi",
    include_diarization: bool = True,
    translate_to: Direction | None = None,
    include_summary: bool = True,
    include_llm: bool = True,
    num_speakers: int | None = None,
    meeting_context: str | None = None,
    stt_quality: STTQuality = "balanced",
) -> None:
    try:
        with AI_JOB_LOCK:
            result = run_local_ai_pipeline(
                job_id=job_id,
                input_path=input_path,
                language=language,
                include_diarization=include_diarization,
                translate_to=translate_to,
                include_summary=include_summary,
                include_llm=include_llm,
                num_speakers=num_speakers,
                meeting_context=meeting_context,
                stt_quality=stt_quality,
            )
        write_result_json(job_id, result)
    except Exception as exc:
        step = exc.step if isinstance(exc, PipelineStepError) else "unknown"
        write_result_json(
            job_id,
            {
                "job_id": job_id,
                "status": "error",
                "step": step,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
    finally:
        release_ai_job_reservation()


def run_local_ai_pipeline(
    job_id: str,
    input_path: Path,
    language: str = "vi",
    include_diarization: bool = True,
    translate_to: Direction | None = None,
    include_summary: bool = True,
    include_llm: bool = True,
    num_speakers: int | None = None,
    meeting_context: str | None = None,
    stt_quality: STTQuality = "balanced",
) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        write_job_progress(job_id, "audio_preprocessing", "Preparing audio", 5)
        logger.info("Job %s: audio preprocessing started", job_id)
        normalized_audio = normalize_audio_for_job(job_id, input_path)
        logger.info("Job %s: audio preprocessing finished", job_id)
    except Exception as exc:
        raise PipelineStepError("audio_preprocessing", exc) from exc

    diarization_segments: list[SpeakerTurn] = []
    if include_diarization:
        try:
            write_job_progress(job_id, "diarization", "Detecting speakers", 15)
            logger.info("Job %s: diarization started", job_id)
            audio_duration = get_audio_duration(normalized_audio)
            if audio_duration < settings.min_diarization_duration_seconds:
                warnings.append(
                    f"Diarization skipped because the recording is shorter than {settings.min_diarization_duration_seconds:.0f} seconds."
                )
            else:
                diarization_segments = diarize_with_memory_release(normalized_audio, num_speakers=num_speakers)
                logger.info("Job %s: diarization finished with %s speaker turns", job_id, len(diarization_segments))
        except Exception as exc:
            raise PipelineStepError("diarization", exc) from exc
    else:
        warnings.append("Diarization skipped by request.")

    try:
        write_job_progress(job_id, "speech_to_text", "Transcribing speech", 45)
        logger.info("Job %s: speech-to-text started", job_id)
        transcript_segments = transcribe_audio_with_speakers(
            audio_path=normalized_audio,
            diarization_segments=diarization_segments,
            language=language,
            quality=stt_quality,
        )
        logger.info("Job %s: speech-to-text finished with %s transcript turns", job_id, len(transcript_segments))
    except Exception as exc:
        raise PipelineStepError("speech_to_text", exc) from exc

    merged_transcript = format_transcript(transcript_segments)
    transcript_text = " ".join(turn.text for turn in transcript_segments).strip()
    corrected_transcript = merged_transcript
    if include_llm:
        try:
            write_job_progress(job_id, "llm_correction", "Correcting transcript with local LLM", 65)
            logger.info("Job %s: LLM correction started", job_id)
            corrected_transcript = correct_transcript_with_ollama(merged_transcript, meeting_context=meeting_context)
            logger.info("Job %s: LLM correction finished", job_id)
            if corrected_transcript and corrected_transcript != merged_transcript:
                warnings.append("Transcript was corrected by the local LLM. Review against the audio if exact wording matters.")
        except Exception as exc:
            warnings.append(f"LLM correction failed or timed out: {exc}")
            corrected_transcript = merged_transcript
    else:
        warnings.append("LLM correction skipped by request.")

    low_information = is_low_information_transcript(corrected_transcript or transcript_text)
    translated_transcript = None
    if translate_to is not None and corrected_transcript.strip() and not low_information:
        try:
            write_job_progress(job_id, "translation", "Translating transcript", 75)
            logger.info("Job %s: translation started", job_id)
            translated_transcript = translation_service.translate(corrected_transcript, translate_to)
            logger.info("Job %s: translation finished", job_id)
        except Exception as exc:
            warnings.append(f"Translation failed: {exc}")
    elif translate_to is not None and low_information:
        warnings.append("Translation skipped because the recording only contains a microphone check.")

    summary = None
    translated_summary = None
    if include_summary and (corrected_transcript.strip() or transcript_text):
        try:
            write_job_progress(job_id, "summary", "Creating summary", 82)
            logger.info("Job %s: summary started", job_id)
            language_hint = (language or "").lower()
            if low_information:
                summary = LOW_INFORMATION_SUMMARY
            elif language_hint.startswith("vi"):
                summary = summarization_service.summarize_extractive(corrected_transcript or merged_transcript)
            else:
                summary = summarization_service.summarize(transcript_text or corrected_transcript)
            if summary and not low_information and translate_to == "en-vi":
                translated_summary = translation_service.translate(summary, "en-vi")
            logger.info("Job %s: summary finished", job_id)
        except Exception as exc:
            warnings.append(f"Summary failed: {exc}")
    elif not include_summary:
        warnings.append("Summary skipped by request.")

    llm = None
    if include_llm and corrected_transcript.strip() and not low_information:
        write_job_progress(job_id, "llm_refinement", "Creating meeting minutes with local LLM", 90)
        llm = llm_service.refine_meeting(
            merged_transcript=corrected_transcript,
            existing_summary=summary,
            translated_transcript=translated_transcript,
            meeting_context=meeting_context or settings.meeting_context,
        )
        if llm.error:
            warnings.append(f"LLM refinement failed: {llm.error}")

    return {
        "job_id": job_id,
        "status": "completed",
        "input_audio_path": str(input_path),
        "normalized_audio_path": str(normalized_audio),
        "transcript": {
            "language": language,
            "language_probability": None,
            "segments": [turn.__dict__ for turn in transcript_segments],
            "text": transcript_text,
        },
        "original_transcript": None,
        "diarization": {"segments": [turn.__dict__ for turn in diarization_segments]} if include_diarization else None,
        "merged_transcript": merged_transcript,
        "corrected_transcript": corrected_transcript,
        "translated_transcript": translated_transcript,
        "translated_text": translated_transcript,
        "summary": summary,
        "translated_summary": translated_summary,
        "llm": llm.model_dump() if llm else None,
        "llm_summary": llm.summary if llm else None,
        "action_items": [item.model_dump() for item in llm.action_items] if llm else [],
        "meeting_minutes": llm.meeting_minutes if llm else corrected_transcript,
        "risks_or_blockers": llm.risks_or_blockers if llm else [],
        "decisions": llm.decisions if llm else [],
        "warnings": warnings,
    }


def normalize_audio_for_job(job_id: str, input_path: Path) -> Path:
    ffmpeg = find_ffmpeg()
    output_path = normalized_path_for_job(job_id)
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        str(settings.audio_sample_rate),
        "-vn",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=None,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to normalize audio: {completed.stderr.strip()}")
    return output_path


def diarize_with_memory_release(audio_path: Path, num_speakers: int | None = None) -> list[SpeakerTurn]:
    pipeline = None
    diarization_output = None
    annotation = None
    try:
        import torch
        from pyannote.audio import Pipeline

        model_ref = str(settings.diarization_model_dir)
        if not (settings.diarization_model_dir / "config.yaml").exists():
            model_ref = "pyannote/speaker-diarization-3.1"

        pipeline = Pipeline.from_pretrained(model_ref)
        pipeline.to(torch.device("cpu"))
        kwargs = {"num_speakers": num_speakers} if num_speakers else {}
        diarization_output = pipeline(read_waveform_for_pyannote(audio_path), **kwargs)
        annotation = extract_annotation(diarization_output)
        return [
            SpeakerTurn(
                start=round(float(turn.start), 3),
                end=round(float(turn.end), 3),
                speaker=str(speaker),
            )
            for turn, _, speaker in annotation.itertracks(yield_label=True)
        ]
    finally:
        # pyannote can keep sizeable torch modules and waveform tensors alive.
        # Drop all strong references before collecting so the next CPU model can fit in RAM.
        del annotation
        del diarization_output
        del pipeline
        release_ai_memory()


def transcribe_speaker_chunks(
    job_id: str,
    audio_path: Path,
    diarization_segments: list[SpeakerTurn],
    language: str = "vi",
) -> list[TranscriptTurn]:
    model = None
    audio = None
    try:
        from faster_whisper import WhisperModel
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Couldn't find ffmpeg or avconv.*",
                category=RuntimeWarning,
            )
            from pydub import AudioSegment

        chunk_dir = chunk_dir_for_job(job_id)
        if chunk_dir.exists():
            shutil.rmtree(chunk_dir)
        chunk_dir.mkdir(parents=True, exist_ok=True)

        AudioSegment.converter = find_ffmpeg()
        audio = AudioSegment.from_wav(str(audio_path))
        speaker_turns = diarization_segments or [
            SpeakerTurn(start=0.0, end=get_audio_duration(audio_path), speaker="SPEAKER_00")
        ]

        model_ref = str(settings.stt_model_dir)
        if not (settings.stt_model_dir / "model.bin").exists():
            model_ref = "vinai/phowhisper-medium"

        model = WhisperModel(
            model_ref,
            device="cpu",
            compute_type="int8",
            cpu_threads=settings.stt_cpu_threads,
        )

        transcript: list[TranscriptTurn] = []
        for index, turn in enumerate(speaker_turns):
            chunk_path = export_speaker_chunk(audio, turn, chunk_dir, index)
            if chunk_path is None:
                continue

            segments_iter, _ = model.transcribe(
                str(chunk_path),
                language=language,
                beam_size=settings.stt_beam_size,
                vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments_iter if segment.text.strip()).strip()
            if not text:
                continue
            transcript.append(
                TranscriptTurn(
                    id=len(transcript),
                    start=turn.start,
                    end=turn.end,
                    speaker=turn.speaker,
                    text=text,
                )
            )

        return transcript
    finally:
        # CTranslate2/faster-whisper allocates large CPU buffers. Keep the model
        # scoped to STT only, then force collection before calling the local LLM.
        del audio
        del model
        release_ai_memory()


def transcribe_audio_with_speakers(
    audio_path: Path,
    diarization_segments: list[SpeakerTurn],
    language: str = "vi",
    quality: STTQuality = "balanced",
) -> list[TranscriptTurn]:
    model = None
    try:
        from faster_whisper import WhisperModel

        model_ref = str(settings.stt_model_dir)
        if not (settings.stt_model_dir / "model.bin").exists():
            model_ref = "vinai/phowhisper-medium"

        model = WhisperModel(
            model_ref,
            device="cpu",
            compute_type="int8",
            cpu_threads=settings.stt_cpu_threads,
        )
        stt_options = stt_options_for_quality(quality)
        segments_iter, _ = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=stt_options["beam_size"],
            best_of=stt_options["best_of"],
            patience=stt_options["patience"],
            repetition_penalty=1.05,
            no_repeat_ngram_size=3,
            temperature=stt_options["temperature"],
            condition_on_previous_text=False,
            vad_filter=get_audio_duration(audio_path) >= settings.stt_vad_min_duration_seconds,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
            initial_prompt=settings.stt_initial_prompt,
            hotwords=settings.stt_hotwords,
            hallucination_silence_threshold=1.5,
        )

        transcript: list[TranscriptTurn] = []
        for segment in segments_iter:
            text = str(segment.text or "").strip()
            if not text:
                continue
            start = round(float(segment.start), 3)
            end = round(float(segment.end), 3)
            transcript.append(
                TranscriptTurn(
                    id=len(transcript),
                    start=start,
                    end=end,
                    speaker=best_speaker_for_segment(start, end, diarization_segments) or "SPEAKER",
                    text=text,
                )
            )
        return transcript
    finally:
        del model
        release_ai_memory()


def stt_options_for_quality(quality: STTQuality) -> dict[str, Any]:
    if quality == "fast":
        return {"beam_size": 1, "best_of": 1, "patience": 1.0, "temperature": 0.0}
    if quality == "accurate":
        return {"beam_size": 5, "best_of": 5, "patience": 1.2, "temperature": [0.0, 0.2]}
    return {"beam_size": settings.stt_beam_size, "best_of": settings.stt_best_of, "patience": 1.1, "temperature": [0.0, 0.2]}


def best_speaker_for_segment(
    start: float,
    end: float,
    diarization_segments: list[SpeakerTurn],
) -> str | None:
    speaker_scores: dict[str, float] = {}
    for diarization_segment in diarization_segments:
        overlap_start = max(start, diarization_segment.start)
        overlap_end = min(end, diarization_segment.end)
        overlap = max(0.0, overlap_end - overlap_start)
        if overlap > 0:
            speaker_scores[diarization_segment.speaker] = (
                speaker_scores.get(diarization_segment.speaker, 0.0) + overlap
            )
    return max(speaker_scores, key=speaker_scores.get) if speaker_scores else None


def export_speaker_chunk(
    audio: AudioSegment,
    turn: SpeakerTurn,
    chunk_dir: Path,
    index: int,
) -> Path | None:
    start_ms = max(0, int(turn.start * 1000))
    end_ms = min(len(audio), int(turn.end * 1000))
    if end_ms <= start_ms:
        return None

    chunk = audio[start_ms:end_ms]
    chunk_path = chunk_dir / f"{index:05d}_{turn.speaker}.wav"
    chunk.export(
        str(chunk_path),
        format="wav",
        parameters=["-ac", "1", "-ar", str(settings.audio_sample_rate)],
    )
    return chunk_path


def correct_transcript_with_ollama(merged_transcript: str, meeting_context: str | None = None) -> str:
    if not merged_transcript.strip():
        return ""

    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    prompt = "\n\n".join(
        part
        for part in (
            CORRECTION_PROMPT,
            f"Ngữ cảnh dự án/người dùng: {meeting_context or settings.meeting_context}",
            f"Văn bản thô:\n{merged_transcript}",
        )
        if part
    )
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": 4096,
            "num_predict": 1024,
        },
    }
    response = requests.post(
        url,
        json=payload,
        timeout=min(settings.ollama_timeout_seconds, LLM_STEP_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    data = response.json()
    corrected = data.get("response")
    if not isinstance(corrected, str):
        raise RuntimeError("Ollama response does not contain a text 'response' field.")
    return corrected.strip()


def format_transcript(transcript: list[TranscriptTurn]) -> str:
    return "\n".join(
        f"{turn.speaker} [{turn.start:.2f}s-{turn.end:.2f}s]: {turn.text}"
        for turn in transcript
    )


def get_audio_duration(audio_path: Path) -> float:
    info = sf.info(str(audio_path))
    return float(info.frames) / float(info.samplerate) if info.samplerate else 0.0


def release_ai_memory() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
