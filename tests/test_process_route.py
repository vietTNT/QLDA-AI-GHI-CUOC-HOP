from __future__ import annotations

import io
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_pipeline import SpeakerTurn, best_speaker_for_segment


def make_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)
    return buffer.getvalue()


class ProcessRouteTests(unittest.TestCase):
    def test_process_forwards_ui_options_to_background_job(self) -> None:
        captured: dict[str, object] = {}

        def fake_add_task(func, *args, **kwargs) -> None:
            captured["func"] = func
            captured["args"] = args
            captured["kwargs"] = kwargs

        with (
            patch("app.main.reserve_ai_job", return_value=True),
            patch("app.main.BackgroundTasks.add_task", side_effect=fake_add_task),
        ):
            response = TestClient(app).post(
                "/api/process",
                params={
                    "language": "vi",
                    "include_diarization": "false",
                    "translate_to": "vi-en",
                    "include_summary": "false",
                    "include_llm": "false",
                    "num_speakers": "2",
                    "meeting_context": "Ten du an QLDA",
                },
                files={"file": ("sample.wav", make_wav_bytes(), "audio/wav")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "processing")
        args = captured["args"]
        self.assertEqual(args[2], "vi")
        self.assertFalse(args[3])
        self.assertEqual(args[4], "vi-en")
        self.assertFalse(args[5])
        self.assertFalse(args[6])
        self.assertEqual(args[7], 2)
        self.assertEqual(args[8], "Ten du an QLDA")
        self.assertIsInstance(args[1], Path)

    def test_best_speaker_uses_largest_overlap(self) -> None:
        speaker = best_speaker_for_segment(
            3.0,
            8.0,
            [
                SpeakerTurn(start=0.0, end=4.0, speaker="SPEAKER_00"),
                SpeakerTurn(start=4.0, end=9.0, speaker="SPEAKER_01"),
            ],
        )

        self.assertEqual(speaker, "SPEAKER_01")

    def test_status_reports_interrupted_job_instead_of_polling_forever(self) -> None:
        with (
            patch("app.main.result_path_for_job", return_value=Path("missing-result.json")),
            patch("app.main.is_ai_job_running", return_value=False),
        ):
            response = TestClient(app).get("/api/status/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertIn("interrupted", body["error"])


if __name__ == "__main__":
    unittest.main()
