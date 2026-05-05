from __future__ import annotations

import shutil
import subprocess
import uuid
import os
from pathlib import Path

import soundfile as sf

from app.config import PROJECT_ROOT, settings


def safe_upload_name(original_name: str) -> str:
    suffix = Path(original_name).suffix.lower() or ".audio"
    return f"{uuid.uuid4().hex}{suffix}"


def find_ffmpeg() -> str:
    candidates: list[str] = []
    configured = os.environ.get("FFMPEG_BINARY")
    if configured:
        configured = normalize_windows_path(configured)
        try:
            if Path(configured).exists():
                candidates.append(configured)
        except OSError:
            candidates.append(configured)

    found = shutil.which("ffmpeg")
    if found:
        candidates.append(found)

    try:
        import imageio_ffmpeg

        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass

    candidate_roots = [
        Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages",
        Path("C:/Users/Lenovo/AppData/Local/Microsoft/WinGet/Packages"),
    ]
    users_root = Path("C:/Users")
    if users_root.exists():
        candidate_roots.extend(
            user_dir / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
            for user_dir in users_root.iterdir()
            if user_dir.is_dir()
        )

    for winget_root in candidate_roots:
        if not winget_root.exists():
            continue
        matches = sorted(winget_root.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"))
        candidates.extend(str(match) for match in matches)

    for candidate in dict.fromkeys(candidates):
        if can_execute_ffmpeg(candidate):
            return candidate

    raise RuntimeError(
        "ffmpeg was not found on PATH. Install it or add the Gyan.FFmpeg bin folder to PATH."
    )


def normalize_windows_path(value: str) -> str:
    if len(value) >= 3 and value[0] == "/" and value[2] == "/" and value[1].isalpha():
        return f"{value[1].upper()}:\\{value[3:].replace('/', '\\')}"
    return value


def can_execute_ffmpeg(candidate: str) -> bool:
    try:
        completed = subprocess.run(
            [candidate, "-version"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def save_upload_bytes(data: bytes, filename: str) -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.upload_dir / safe_upload_name(filename)
    output_path.write_bytes(data)
    return output_path


def normalize_audio(input_path: Path) -> Path:
    ffmpeg = find_ffmpeg()
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.processed_dir / f"{input_path.stem}_16k_mono.wav"
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
    completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to normalize audio: {completed.stderr.strip()}")
    return output_path


def read_waveform_for_pyannote(audio_path: Path):
    import torch

    samples, sample_rate = sf.read(str(audio_path), dtype="float32", always_2d=True)
    mono = samples.mean(axis=1)
    waveform = torch.from_numpy(mono).unsqueeze(0)
    return {"waveform": waveform, "sample_rate": sample_rate}
