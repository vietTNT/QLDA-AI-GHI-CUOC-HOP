from __future__ import annotations

import re
from threading import Lock

from app.config import settings


MIN_SUMMARY_WORDS = 45
MAX_INPUT_TOKENS = 900
CHUNK_OVERLAP_TOKENS = 80
MAX_EXTRACTIVE_SENTENCES = 4

VIETNAMESE_STOPWORDS = {
    "các",
    "cho",
    "của",
    "đã",
    "để",
    "đến",
    "là",
    "một",
    "này",
    "nên",
    "những",
    "sẽ",
    "theo",
    "trong",
    "và",
    "về",
    "với",
}


class SummarizationService:
    def __init__(self) -> None:
        self._tokenizer = None
        self._model = None
        self._lock = Lock()

    def _load(self):
        if self._model is not None and self._tokenizer is not None:
            return self._tokenizer, self._model

        with self._lock:
            if self._model is None or self._tokenizer is None:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                if not (settings.summarization_model_dir / "config.json").exists():
                    raise FileNotFoundError(f"Summarization model is missing: {settings.summarization_model_dir}")
                self._tokenizer = AutoTokenizer.from_pretrained(
                    str(settings.summarization_model_dir),
                    local_files_only=True,
                )
                self._model = AutoModelForSeq2SeqLM.from_pretrained(
                    str(settings.summarization_model_dir),
                    local_files_only=True,
                )
                self._model.generation_config.max_length = None
                self._model.generation_config.min_length = None
                if self._model.generation_config.forced_bos_token_id is None and self._tokenizer.bos_token_id is not None:
                    self._model.generation_config.forced_bos_token_id = self._tokenizer.bos_token_id
                if hasattr(self._model.config, "max_length"):
                    self._model.config.max_length = None
                if hasattr(self._model.config, "min_length"):
                    self._model.config.min_length = None
                self._model.to("cpu")
                self._model.eval()
        return self._tokenizer, self._model

    def summarize(self, text: str, max_new_tokens: int = 160, min_new_tokens: int = 24) -> str:
        clean_text = " ".join(text.split())
        if not clean_text:
            return ""

        if len(clean_text.split()) < MIN_SUMMARY_WORDS:
            return clean_text

        tokenizer, _ = self._load()
        token_ids = tokenizer.encode(clean_text, add_special_tokens=False)
        if len(token_ids) <= MAX_INPUT_TOKENS:
            return self._summarize_chunk(clean_text, max_new_tokens, min_new_tokens)

        chunk_summaries = [
            self._summarize_chunk(chunk, max_new_tokens=max_new_tokens, min_new_tokens=min_new_tokens)
            for chunk in self._iter_chunks(token_ids)
            if chunk.strip()
        ]
        combined = " ".join(chunk_summaries)
        if len(combined.split()) < MIN_SUMMARY_WORDS:
            return combined
        return self._summarize_chunk(combined, max_new_tokens=max_new_tokens, min_new_tokens=min_new_tokens)

    def summarize_extractive(self, text: str, max_sentences: int = MAX_EXTRACTIVE_SENTENCES) -> str:
        sentences = split_summary_sentences(text)
        if not sentences:
            return ""
        if len(sentences) <= 2:
            return " ".join(sentences)

        frequencies = word_frequencies(sentences)
        scored = []
        for index, sentence in enumerate(sentences):
            words = normalized_words(sentence)
            if not words:
                continue
            score = sum(frequencies.get(word, 0) for word in words) / max(len(words), 1)
            score += max(0.0, 0.18 - index * 0.03)
            scored.append((score, index, sentence))

        chosen = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
        return " ".join(sentence for _, _, sentence in sorted(chosen, key=lambda item: item[1]))

    def _iter_chunks(self, token_ids: list[int]):
        tokenizer, _ = self._load()
        stride = MAX_INPUT_TOKENS - CHUNK_OVERLAP_TOKENS
        for start in range(0, len(token_ids), stride):
            chunk_ids = token_ids[start : start + MAX_INPUT_TOKENS]
            yield tokenizer.decode(chunk_ids, skip_special_tokens=True)
            if start + MAX_INPUT_TOKENS >= len(token_ids):
                break

    def _summarize_chunk(self, text: str, max_new_tokens: int, min_new_tokens: int) -> str:
        import torch

        tokenizer, model = self._load()
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024)
        input_length = int(inputs["input_ids"].shape[-1])
        safe_max = min(max_new_tokens, max(32, input_length // 2))
        safe_min = min(min_new_tokens, max(8, safe_max // 2))
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=safe_max,
                min_new_tokens=safe_min,
                no_repeat_ngram_size=3,
            )
        return tokenizer.decode(output_ids[0], skip_special_tokens=True)


def split_summary_sentences(text: str) -> list[str]:
    cleaned_lines: list[str] = []
    for line in text.splitlines() or [text]:
        line = re.sub(r"^\s*[^:\n]+?\s*\[[^\]]+\]:\s*", "", line.strip())
        if line:
            cleaned_lines.append(line)

    cleaned = " ".join(cleaned_lines)
    pieces = re.split(r"(?<=[.!?。！？])\s+|\n+", cleaned)
    sentences = [" ".join(piece.split()).strip() for piece in pieces if piece.strip()]
    return sentences


def normalized_words(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)
        if len(word) > 1 and word not in VIETNAMESE_STOPWORDS
    ]


def word_frequencies(sentences: list[str]) -> dict[str, int]:
    frequencies: dict[str, int] = {}
    for sentence in sentences:
        for word in normalized_words(sentence):
            frequencies[word] = frequencies.get(word, 0) + 1
    return frequencies


summarization_service = SummarizationService()
