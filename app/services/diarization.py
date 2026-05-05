from __future__ import annotations

from pathlib import Path
from threading import Lock
import warnings

from app.config import settings
from app.schemas import DiarizationResponse, DiarizationSegment, TranscriptSegment
from app.services.audio import read_waveform_for_pyannote
from app.services.stt import get_audio_duration


class DiarizationService:
    def __init__(self) -> None:
        self._pipeline = None
        self._lock = Lock()

    def _load(self):
        if self._pipeline is not None:
            return self._pipeline

        with self._lock:
            if self._pipeline is None:
                import torch

                warnings.filterwarnings(
                    "ignore",
                    message=r"[\s\S]*torchcodec is not installed correctly[\s\S]*",
                    category=UserWarning,
                )
                warnings.filterwarnings(
                    "ignore",
                    message=r".*degrees of freedom is <= 0.*",
                    category=UserWarning,
                )
                from pyannote.audio import Pipeline

                if not (settings.diarization_model_dir / "config.yaml").exists():
                    raise FileNotFoundError(f"Diarization model is missing: {settings.diarization_model_dir}")
                pipeline = Pipeline.from_pretrained(str(settings.diarization_model_dir))
                pipeline.to(torch.device("cpu"))
                self._pipeline = pipeline
        return self._pipeline

    def diarize(self, audio_path: Path, num_speakers: int | None = None) -> DiarizationResponse:
        if get_audio_duration(audio_path) < settings.min_diarization_duration_seconds:
            return DiarizationResponse(segments=[])

        pipeline = self._load()
        kwargs = {"num_speakers": num_speakers} if num_speakers else {}
        diarization_output = pipeline(read_waveform_for_pyannote(audio_path), **kwargs)
        diarization = extract_annotation(diarization_output)
        segments = [
            DiarizationSegment(
                start=round(float(turn.start), 3),
                end=round(float(turn.end), 3),
                speaker=str(speaker),
            )
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        ]
        return DiarizationResponse(segments=segments)


def extract_annotation(diarization_output):
    if hasattr(diarization_output, "itertracks"):
        return diarization_output

    for attribute in ("exclusive_speaker_diarization", "speaker_diarization"):
        annotation = getattr(diarization_output, attribute, None)
        if annotation is not None and hasattr(annotation, "itertracks"):
            return annotation

    raise TypeError(f"Unsupported diarization output type: {type(diarization_output)!r}")


def attach_speakers(
    transcript_segments: list[TranscriptSegment],
    diarization_segments: list[DiarizationSegment],
) -> list[TranscriptSegment]:
    output: list[TranscriptSegment] = []
    for segment in transcript_segments:
        speaker_scores: dict[str, float] = {}
        for diarization_segment in diarization_segments:
            overlap_start = max(segment.start, diarization_segment.start)
            overlap_end = min(segment.end, diarization_segment.end)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > 0:
                speaker_scores[diarization_segment.speaker] = (
                    speaker_scores.get(diarization_segment.speaker, 0.0) + overlap
                )
        speaker = max(speaker_scores, key=speaker_scores.get) if speaker_scores else None
        output.append(segment.model_copy(update={"speaker": speaker}))
    return output


diarization_service = DiarizationService()
