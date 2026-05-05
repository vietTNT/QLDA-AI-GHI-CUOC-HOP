from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.config import settings


def upload_path_for_job(job_id: str, original_name: str) -> Path:
    suffix = Path(original_name).suffix.lower() or ".audio"
    return settings.upload_dir / f"{job_id}{suffix}"


def normalized_path_for_job(job_id: str) -> Path:
    return settings.upload_dir / f"{job_id}_16k_mono.wav"


def result_path_for_job(job_id: str) -> Path:
    return settings.upload_dir / f"{job_id}_result.json"


def progress_path_for_job(job_id: str) -> Path:
    return settings.upload_dir / f"{job_id}_progress.json"


def chunk_dir_for_job(job_id: str) -> Path:
    return settings.upload_dir / f"{job_id}_chunks"


def write_result_json(job_id: str, payload: dict[str, Any]) -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_path_for_job(job_id)
    tmp_path = result_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, result_path)
    return result_path


def write_progress_json(job_id: str, payload: dict[str, Any]) -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    progress_path = progress_path_for_job(job_id)
    tmp_path = progress_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, progress_path)
    return progress_path


def read_result_json(job_id: str) -> dict[str, Any]:
    return json.loads(result_path_for_job(job_id).read_text(encoding="utf-8"))


def read_progress_json(job_id: str) -> dict[str, Any]:
    return json.loads(progress_path_for_job(job_id).read_text(encoding="utf-8"))
