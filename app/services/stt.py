from __future__ import annotations

from pathlib import Path
from threading import Lock

import soundfile as sf

from app.config import settings
from app.schemas import TranscriptSegment, TranscriptionResponse
from app.services.text_quality import normalize_microphone_check_text


class STTService:
    def __init__(self) -> None:
        self._model = None
        self._lock = Lock()

    def _load(self):
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                if not (settings.stt_model_dir / "model.bin").exists():
                    raise FileNotFoundError(f"STT model is missing: {settings.stt_model_dir}")
                self._model = WhisperModel(
                    str(settings.stt_model_dir),
                    device="cpu",
                    compute_type=settings.stt_compute_type,
                    cpu_threads=settings.stt_cpu_threads,
                )
        return self._model

    def transcribe(self, audio_path: Path, language: str | None = None) -> TranscriptionResponse:
        model = self._load()
        duration = get_audio_duration(audio_path)
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=language or settings.default_language,
            task="transcribe",
            beam_size=settings.stt_beam_size,
            best_of=settings.stt_best_of,
            patience=1.0,
            repetition_penalty=1.05,
            no_repeat_ngram_size=3,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=duration >= settings.stt_vad_min_duration_seconds,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
            initial_prompt=settings.stt_initial_prompt,
            hotwords=settings.stt_hotwords,
            hallucination_silence_threshold=1.5,
        )
        segments: list[TranscriptSegment] = []
        for index, segment in enumerate(segments_iter):
            if is_unreliable_segment(segment):
                continue
            text = normalize_microphone_check_text(segment.text)
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    id=index,
                    start=round(float(segment.start), 3),
                    end=round(float(segment.end), 3),
                    text=text,
                )
            )

        return TranscriptionResponse(
            language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
            segments=segments,
            text=" ".join(segment.text for segment in segments),
        )


def get_audio_duration(audio_path: Path) -> float:
    try:
        info = sf.info(str(audio_path))
        if info.samplerate:
            return float(info.frames) / float(info.samplerate)
    except Exception:
        return 0.0
    return 0.0


def is_unreliable_segment(segment) -> bool:
    no_speech_prob = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
    avg_logprob = float(getattr(segment, "avg_logprob", 0.0) or 0.0)
    compression_ratio = float(getattr(segment, "compression_ratio", 0.0) or 0.0)
    return no_speech_prob > 0.85 and avg_logprob < -1.0 or compression_ratio > 3.2


stt_service = STTService()
