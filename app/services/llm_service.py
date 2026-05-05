from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.config import settings
from app.schemas import ActionItem, LLMRefinement, LLMTranscriptCorrection, TranscriptSegment, TranscriptionResponse


DEFAULT_SAMPLE_TRANSCRIPT = (
    "SPEAKER_00 [0.00s-8.20s]: Hom nay chung ta hop ve tien do backend va giao dien. "
    "Anh Nam se hoan thanh API upload truoc thu Sau. "
    "SPEAKER_01 [8.30s-14.00s]: Chi Lan phu trach kiem thu va bao cao loi vao ngay mai. "
    "Quyet dinh: uu tien sua loi diarization truoc khi demo."
)


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = settings.ollama_base_url
    model: str = settings.ollama_model
    timeout_seconds: float = settings.ollama_timeout_seconds
    retries: int = 2


class OllamaLLMService:
    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config or OllamaConfig()

    def refine_meeting(
        self,
        merged_transcript: str,
        existing_summary: str | None = None,
        translated_transcript: str | None = None,
        meeting_context: str | None = None,
    ) -> LLMRefinement:
        prompt = build_meeting_prompt(
            merged_transcript=merged_transcript,
            existing_summary=existing_summary,
            translated_transcript=translated_transcript,
            meeting_context=meeting_context,
        )
        try:
            raw_text = self._generate(prompt)
            return parse_llm_refinement(raw_text)
        except Exception as exc:
            return LLMRefinement(raw_text=None, parsed_json=False, error=str(exc))

    def correct_transcript(
        self,
        transcript: TranscriptionResponse,
        meeting_context: str | None = None,
    ) -> LLMTranscriptCorrection:
        if not transcript.segments:
            return LLMTranscriptCorrection(
                corrected_transcript=transcript,
                raw_text=None,
                parsed_json=True,
            )

        prompt = build_transcript_correction_prompt(transcript, meeting_context=meeting_context)
        try:
            raw_text = self._generate(prompt, response_format="json", temperature=0.0)
            return parse_transcript_correction(raw_text, transcript)
        except Exception as exc:
            return LLMTranscriptCorrection(raw_text=None, parsed_json=False, error=str(exc))

    def smoke_test(self, transcript: str | None = None) -> LLMRefinement:
        return self.refine_meeting(transcript or DEFAULT_SAMPLE_TRANSCRIPT)

    def _generate(
        self,
        prompt: str,
        response_format: str | None = "json",
        temperature: float = 0.1,
    ) -> str:
        url = f"{self.config.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": 1024,
            },
        }
        if response_format:
            payload["format"] = response_format
        data = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None

        for attempt in range(self.config.retries + 1):
            request = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    body = json.loads(response.read().decode("utf-8"))
                text = body.get("response")
                if not isinstance(text, str) or not text.strip():
                    thinking = body.get("thinking")
                    detail = " It only returned thinking tokens." if isinstance(thinking, str) and thinking.strip() else ""
                    raise OllamaError(
                        f"Ollama returned an empty response for model {self.config.model}.{detail}"
                    )
                return text.strip()
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = OllamaError(
                    f"Ollama HTTP {exc.code}. Check that model '{self.config.model}' is available. {detail}"
                )
            except urllib.error.URLError as exc:
                last_error = OllamaError(
                    f"Cannot connect to Ollama at {self.config.base_url}. Start Ollama and verify the endpoint. {exc}"
                )
            except TimeoutError as exc:
                last_error = OllamaError(
                    f"Ollama timed out after {self.config.timeout_seconds}s using model {self.config.model}."
                )
            except json.JSONDecodeError as exc:
                last_error = OllamaError(f"Ollama returned invalid JSON envelope: {exc}")

            if attempt < self.config.retries:
                time.sleep(0.75 * (attempt + 1))

        raise last_error or OllamaError("Unknown Ollama error.")


def build_meeting_prompt(
    merged_transcript: str,
    existing_summary: str | None = None,
    translated_transcript: str | None = None,
    meeting_context: str | None = None,
) -> str:
    context_blocks = [
        "Bạn là một Thư ký chuyên nghiệp, có nhiệm vụ viết biên bản cuộc họp bằng tiếng Việt.",
        "Chỉ sử dụng thông tin từ Transcript được cung cấp. TUYỆT ĐỐI KHÔNG tự bịa đặt thêm sự kiện.",
        "Bỏ qua các từ ngữ nhiễu do nhận diện giọng nói sai nếu nó không làm thay đổi ý nghĩa cuộc họp.",
        "Nếu Transcript chỉ là test mic như 'a lô', 'một hai', hãy điền chuỗi 'Không đủ nội dung họp' vào các trường.",
        "Nếu không có thông tin về người phụ trách, deadline, rủi ro hoặc quyết định, hãy dùng null hoặc mảng rỗng [].",
        "Chỉ trả về duy nhất một đối tượng JSON. Không dùng markdown, không giải thích gì thêm.",
        "Toàn bộ giá trị chuỗi (string) trong JSON bắt buộc phải viết bằng tiếng Việt.",
        "Định dạng JSON bắt buộc phải chính xác như sau:",
        json.dumps(
            {
                "summary": "...",
                "action_items": [{"task": "...", "assignee": None, "deadline": None}],
                "meeting_minutes": "...",
                "risks_or_blockers": [],
                "decisions": [],
            },
            ensure_ascii=False,
        ),
        "Transcript cuộc họp:",
        merged_transcript.strip() or "(trống)",
    ]
    if meeting_context:
        context_blocks.extend(["Ngữ cảnh bổ sung:", meeting_context.strip()])
    if translated_transcript:
        context_blocks.extend(["Translated transcript if helpful:", translated_transcript.strip()])
    if existing_summary:
        context_blocks.extend(["Existing extractive summary if helpful:", existing_summary.strip()])
    return "\n\n".join(context_blocks)


def build_transcript_correction_prompt(
    transcript: TranscriptionResponse,
    meeting_context: str | None = None,
) -> str:
    segments = [
        {
            "id": segment.id,
            "start": segment.start,
            "end": segment.end,
            "speaker": segment.speaker,
            "text": segment.text,
        }
        for segment in transcript.segments
    ]
    return "\n\n".join(
        [
            "Bạn là bộ sửa lỗi nhận dạng giọng nói tiếng Việt cho ứng dụng ghi biên bản cuộc họp.",
            "Nhiệm vụ: sửa lỗi chính tả, dấu câu, từ bị nghe nhầm, và cụm từ vô nghĩa do ASR gây ra.",
            "Ngữ cảnh thường gặp: họp dự án phần mềm, phân công nhiệm vụ, tiến độ, kiểm thử, báo cáo lỗi, deadline, quyết định, rủi ro, khách hàng, giao diện, backend, API, cơ sở dữ liệu.",
            f"Ngữ cảnh dự án/người dùng cung cấp: {meeting_context.strip() if meeting_context else settings.meeting_context}",
            "Quy tắc rất quan trọng:",
            "- Chỉ sửa khi có cơ sở từ ngữ cảnh và câu tiếng Việt hợp lý.",
            "- Không thêm sự kiện, tên người, con số, deadline, quyết định, hay nội dung không có trong transcript.",
            "- Nếu một đoạn quá nhiễu hoặc không thể suy ra chắc chắn, giữ nguyên text của đoạn đó.",
            "- Giữ nguyên id, thứ tự, timestamp, và speaker. Chỉ thay trường text.",
            "- Viết tiếng Việt có dấu, tự nhiên, phù hợp văn bản biên bản họp.",
            "Trả về JSON nghiêm ngặt, không markdown, đúng schema:",
            json.dumps({"segments": [{"id": 0, "text": "..."}]}, ensure_ascii=False),
            "Transcript ASR:",
            json.dumps({"segments": segments}, ensure_ascii=False),
        ]
    )


def parse_transcript_correction(
    raw_text: str,
    original: TranscriptionResponse,
) -> LLMTranscriptCorrection:
    raw_text = raw_text.strip()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        data = extract_json_object(raw_text)
        if data is None:
            return LLMTranscriptCorrection(raw_text=raw_text, parsed_json=False)

    if not isinstance(data, dict):
        return LLMTranscriptCorrection(raw_text=raw_text, parsed_json=False)

    corrections = data.get("segments")
    if not isinstance(corrections, list):
        return LLMTranscriptCorrection(raw_text=raw_text, parsed_json=False)

    text_by_id: dict[int, str] = {}
    for item in corrections:
        if not isinstance(item, dict):
            continue
        try:
            segment_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            text_by_id[segment_id] = text

    corrected_segments = [
        segment.model_copy(update={"text": text_by_id.get(segment.id, segment.text)})
        for segment in original.segments
    ]
    corrected = original.model_copy(
        update={
            "segments": corrected_segments,
            "text": " ".join(segment.text for segment in corrected_segments),
        }
    )
    return LLMTranscriptCorrection(
        corrected_transcript=corrected,
        raw_text=raw_text,
        parsed_json=True,
    )


def parse_llm_refinement(raw_text: str) -> LLMRefinement:
    raw_text = raw_text.strip()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        data = extract_json_object(raw_text)
        if data is None:
            return LLMRefinement(
                summary=raw_text,
                meeting_minutes=raw_text,
                raw_text=raw_text,
                parsed_json=False,
            )

    try:
        return normalize_refinement_dict(data, raw_text)
    except (TypeError, ValidationError, ValueError):
        return LLMRefinement(
            summary=raw_text,
            meeting_minutes=raw_text,
            raw_text=raw_text,
            parsed_json=False,
        )


def extract_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def normalize_refinement_dict(data: dict[str, Any], raw_text: str) -> LLMRefinement:
    action_items = []
    for item in data.get("action_items") or []:
        if not isinstance(item, dict):
            continue
        task = item.get("task")
        if not task:
            continue
        action_items.append(
            ActionItem(
                task=str(task),
                assignee=string_or_none(item.get("assignee")),
                deadline=string_or_none(item.get("deadline")),
            )
        )

    return LLMRefinement(
        summary=string_or_none(data.get("summary")),
        action_items=action_items,
        meeting_minutes=string_or_none(data.get("meeting_minutes")),
        risks_or_blockers=string_list(data.get("risks_or_blockers")),
        decisions=string_list(data.get("decisions")),
        raw_text=raw_text,
        parsed_json=True,
    )


def string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    return text


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


llm_service = OllamaLLMService()
