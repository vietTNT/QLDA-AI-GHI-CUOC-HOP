from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "diarization" / "speaker-diarization-community-1"
REPO_ID = "pyannote/speaker-diarization-community-1"

LOCAL_CACHE_DIR = PROJECT_ROOT / ".cache"
LOCAL_TMP_DIR = LOCAL_CACHE_DIR / "tmp"
LOCAL_TMP_DIR.mkdir(exist_ok=True)
(LOCAL_CACHE_DIR / "matplotlib").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TMP", str(LOCAL_TMP_DIR))
os.environ.setdefault("TEMP", str(LOCAL_TMP_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(LOCAL_CACHE_DIR / "matplotlib"))
os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".hf"))


def model_dir_has_files(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    return (path / "config.yaml").exists() or any(path.glob("*.yaml"))


def print_missing_model(path: Path) -> None:
    print(f"Diarization model is missing or incomplete: {path}")
    print("This pyannote model may be gated. If download fails, accept the model conditions on Hugging Face first.")
    print("Activate the venv from Git Bash with:")
    print("  source .venv/Scripts/activate")
    print("Then log in and download:")
    print("  hf auth login")
    print(f"  hf download {REPO_ID} --local-dir models/diarization/speaker-diarization-community-1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test local pyannote diarization on CPU.")
    parser.add_argument("--audio", type=Path, help="Optional audio file to diarize.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    return parser.parse_args()


def is_access_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("401", "403", "gated", "private", "unauthorized", "forbidden"))


def main() -> int:
    args = parse_args()
    model_dir = args.model_dir.resolve()

    if not model_dir_has_files(model_dir):
        print_missing_model(model_dir)
        return 2

    try:
        import torch
        warnings.filterwarnings(
            "ignore",
            message=r"[\s\S]*torchcodec is not installed correctly[\s\S]*",
            category=UserWarning,
        )
        from pyannote.audio import Pipeline
    except ImportError as exc:
        print("pyannote.audio or torch is not installed in the active environment.")
        print("Run: python -m pip install pyannote.audio")
        print(f"Import error: {exc}")
        return 1

    try:
        pipeline = Pipeline.from_pretrained(str(model_dir))
        pipeline.to(torch.device("cpu"))
    except Exception as exc:
        print("Failed to load the diarization pipeline from the local folder.")
        if is_access_error(exc):
            print("You likely need to accept the pyannote model conditions on Hugging Face, then run hf auth login.")
        print(f"Error: {exc}")
        return 1

    if args.audio is None:
        print("Diarization pipeline loaded successfully on CPU.")
        print("Pass --audio path/to/file.wav to run a diarization smoke test.")
        return 0

    audio_path = args.audio.resolve()
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}")
        return 2

    diarization = pipeline(str(audio_path))
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        print(f"[{turn.start:.2f}s -> {turn.end:.2f}s] {speaker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
