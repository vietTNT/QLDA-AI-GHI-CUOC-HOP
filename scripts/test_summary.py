from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "summarization" / "bart-large-cnn"
REPO_ID = "facebook/bart-large-cnn"
LOCAL_CACHE_DIR = PROJECT_ROOT / ".cache"
LOCAL_TMP_DIR = LOCAL_CACHE_DIR / "tmp"
LOCAL_TMP_DIR.mkdir(exist_ok=True)
LOCAL_CACHE_DIR.mkdir(exist_ok=True)
os.environ.setdefault("TMP", str(LOCAL_TMP_DIR))
os.environ.setdefault("TEMP", str(LOCAL_TMP_DIR))
os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".hf"))
SAMPLE_TEXT = (
    "The team reviewed the meeting-minutes workflow. The backend will accept uploaded audio, "
    "run local speech recognition, detect speakers, translate when needed, and generate a concise "
    "summary with action items. The next phase is to build the FastAPI service and a simple UI."
)


def model_dir_has_files(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    model_files = list(path.glob("*.bin")) + list(path.glob("*.safetensors"))
    return (path / "config.json").exists() and bool(model_files)


def print_missing_model(path: Path) -> None:
    print(f"Summarization model is missing or incomplete: {path}")
    print("Activate the venv from Git Bash with:")
    print("  source .venv/Scripts/activate")
    print("Then download it with:")
    print(f"  hf download {REPO_ID} --local-dir models/summarization/bart-large-cnn")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test local BART summarization on CPU.")
    parser.add_argument("--text", default=SAMPLE_TEXT)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument("--min-new-tokens", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_dir = args.model_dir.resolve()

    if not model_dir_has_files(model_dir):
        print_missing_model(model_dir)
        return 2

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as exc:
        print("transformers or torch is not installed in the active environment.")
        print("Run: python -m pip install transformers torch")
        print(f"Import error: {exc}")
        return 1

    try:
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir), local_files_only=True)
        model.generation_config.max_length = None
        model.generation_config.min_length = None
        if model.generation_config.forced_bos_token_id is None and tokenizer.bos_token_id is not None:
            model.generation_config.forced_bos_token_id = tokenizer.bos_token_id
        if hasattr(model.config, "max_length"):
            model.config.max_length = None
        if hasattr(model.config, "min_length"):
            model.config.min_length = None
        model.to("cpu")
        model.eval()
        inputs = tokenizer(args.text, return_tensors="pt", truncation=True, max_length=1024)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                min_new_tokens=args.min_new_tokens,
                no_repeat_ngram_size=3,
            )
    except Exception as exc:
        print(f"Failed to run summarization from local model {model_dir}.")
        print(f"Error: {exc}")
        return 1

    print(tokenizer.decode(output_ids[0], skip_special_tokens=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
