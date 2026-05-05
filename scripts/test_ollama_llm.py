from __future__ import annotations

import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SAMPLE_TRANSCRIPT = (
    "SPEAKER_00 [0.00s-8.20s]: Hom nay chung ta hop ve tien do backend va giao dien. "
    "Anh Nam se hoan thanh API upload truoc thu Sau. "
    "SPEAKER_01 [8.30s-14.00s]: Chi Lan phu trach kiem thu va bao cao loi vao ngay mai. "
    "Quyet dinh: uu tien sua loi diarization truoc khi demo."
)


def main() -> int:
    from app.services.llm_service import llm_service

    result = llm_service.refine_meeting(SAMPLE_TRANSCRIPT)
    print(f"model: {llm_service.config.model}")
    print(f"base_url: {llm_service.config.base_url}")
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0 if result.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
