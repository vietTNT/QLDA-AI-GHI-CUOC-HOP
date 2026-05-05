from __future__ import annotations

import re
import unicodedata


LOW_INFORMATION_SUMMARY = (
    "Đoạn ghi âm hiện chỉ có nội dung kiểm tra âm thanh, chưa có đủ nội dung cuộc họp để tóm tắt."
)

MIC_CHECK_REPLACEMENTS = (
    (re.compile(r"\b(?:alo|a\s*lô|à\s*lô|a\s*lộ|a\s*lôn|a\s*lâu)\b", re.IGNORECASE), "a lô"),
    (
        re.compile(
            r"\b(?:mot|mọt|một|mau|mọto)\s+(?:hai|áo\s*bò|hà\s*bò|hả\s*bòa|hề\s*bỏ|gà\s*bò)\b",
            re.IGNORECASE,
        ),
        "một hai",
    ),
    (re.compile(r"\bmột\s+hai\s+(?:boi|oi)\b", re.IGNORECASE), "một hai"),
    (re.compile(r"\bmột\s+(?:hai\s+bon|hả\s+hỏa|hề\s*bò\s*bõ)\b", re.IGNORECASE), "một hai"),
    (re.compile(r"\bunk\b", re.IGNORECASE), ""),
    (re.compile(r"\b(?:loại|bỏ|bòa)\b", re.IGNORECASE), ""),
)

MEETING_CONTENT_HINTS = {
    "hop",
    "du an",
    "tien do",
    "nhiem vu",
    "quyet dinh",
    "ket luan",
    "bao cao",
    "kiem thu",
    "deadline",
    "khach hang",
    "yeu cau",
    "rui ro",
}


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_for_matching(text: str) -> str:
    folded = strip_accents(text)
    folded = re.sub(r"[^\w\s]", " ", folded, flags=re.UNICODE)
    return re.sub(r"\s+", " ", folded).strip()


def normalize_microphone_check_text(text: str) -> str:
    if not is_probable_microphone_check(text):
        return " ".join(text.split())

    cleaned = text.strip().lower()
    for pattern, replacement in MIC_CHECK_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)

    cleaned = re.sub(r"\b(?:lột|lộn|lộ)\b", "a lô", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmột hai(?:\s+hai)+\b", "một hai", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\ba\s+lô\s+a\s+lô\b", "a lô a lô", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([.,!?])", r"\1", cleaned).strip(" .,")

    if "một hai" in cleaned and "a lô" not in cleaned and len(cleaned.split()) <= 8:
        cleaned = f"a lô {cleaned}"

    return cleaned[:1].upper() + cleaned[1:] + "."


def is_probable_microphone_check(text: str) -> bool:
    folded = normalize_for_matching(text)
    if not folded:
        return True

    words = folded.split()
    if len(words) > 28:
        return False

    if any(hint in folded for hint in MEETING_CONTENT_HINTS):
        return False

    mic_hits = sum(
        1
        for term in (
            "alo",
            "a lo",
            "mot hai",
            "kiem tra am thanh",
            "lot",
            "lon",
            "lo lo",
            "ao bo",
            "ha bo",
            "ha boa",
            "he bo",
        )
        if term in folded
    )
    return mic_hits >= 1 and len(words) <= 16


def is_low_information_transcript(text: str) -> bool:
    folded = normalize_for_matching(text)
    if not folded:
        return True

    words = folded.split()
    if is_probable_microphone_check(text):
        return True

    meaningful = [word for word in words if len(word) > 1]
    return len(meaningful) < 8
