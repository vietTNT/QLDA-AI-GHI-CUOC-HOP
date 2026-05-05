from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = PROJECT_ROOT / "models"
CACHE_DIR = PROJECT_ROOT / ".cache"
TMP_DIR = CACHE_DIR / "tmp"
DATA_DIR = PROJECT_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
DLL_DIRECTORIES = []


def path_exists_or_is_protected(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return True


def configure_ffmpeg_environment() -> None:
    candidate_bins: list[Path] = []
    configured = os.environ.get("FFMPEG_BINARY")
    if configured:
        candidate_bins.append(Path(configured).parent)

    winget_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    try:
        for package_dir in winget_root.glob("Gyan.FFmpeg.Shared*"):
            for release_dir in package_dir.iterdir():
                if release_dir.is_dir() and release_dir.name.startswith("ffmpeg-") and "shared" in release_dir.name:
                    candidate_bins.append(release_dir / "bin")
    except OSError:
        pass

    for bin_dir in candidate_bins:
        ffmpeg_exe = bin_dir / "ffmpeg.exe"
        if not path_exists_or_is_protected(ffmpeg_exe):
            continue

        if hasattr(os, "add_dll_directory"):
            try:
                DLL_DIRECTORIES.append(os.add_dll_directory(str(bin_dir)))
            except OSError:
                pass
        break


def configure_local_environment() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "matplotlib").mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("TMP", str(TMP_DIR))
    os.environ.setdefault("TEMP", str(TMP_DIR))
    os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))
    os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".hf"))
    os.environ.setdefault("HF_HUB_CACHE", str(PROJECT_ROOT / ".hf" / "hub"))
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    os.environ.setdefault("OLLAMA_MODEL", "qwen3.5:9b")
    os.environ.setdefault("OLLAMA_TIMEOUT_SECONDS", "300")
    os.environ.setdefault(
        "MEETING_CONTEXT",
        "Du an AI ghi bien ban cuoc hop: xu ly ghi am, nhan dien nguoi noi, STT, tom tat, dich, LLM, FastAPI, giao dien web.",
    )
    configure_ffmpeg_environment()


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Meeting Minutes API"
    stt_model_dir: Path = MODEL_ROOT / "stt" / "PhoWhisper-medium-ct2-int8"
    diarization_model_dir: Path = MODEL_ROOT / "diarization" / "speaker-diarization-community-1"
    translation_vi_en_dir: Path = MODEL_ROOT / "translation" / "opus-mt-vi-en"
    translation_en_vi_dir: Path = MODEL_ROOT / "translation" / "opus-mt-en-vi"
    summarization_model_dir: Path = MODEL_ROOT / "summarization" / "bart-large-cnn"
    default_language: str = "vi"
    stt_compute_type: str = "int8"
    stt_cpu_threads: int = 4
    stt_beam_size: int = 3
    stt_best_of: int = 3
    stt_initial_prompt: str = (
        "Biên bản cuộc họp tiếng Việt. Nội dung có thể gồm trao đổi công việc, "
        "thảo luận, ý kiến, nhiệm vụ, quyết định, rủi ro, tiến độ, kỹ thuật, khách hàng."
    )
    stt_hotwords: str = ""
    stt_vad_min_duration_seconds: float = 8.0
    min_diarization_duration_seconds: float = 8.0
    audio_sample_rate: int = 16000
    upload_dir: Path = UPLOAD_DIR
    processed_dir: Path = PROCESSED_DIR
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
    ollama_timeout_seconds: float = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "300"))
    meeting_context: str = os.environ.get("MEETING_CONTEXT", "")


configure_local_environment()
settings = Settings()
