"""오늘 학습 등록 — 임시 입력(session_state) 유지 로직 테스트."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import (  # noqa: E402
    DRAFT_IMAGE_BYTES,
    DRAFT_KEYWORDS,
    DRAFT_KEY_PREFIX,
    apply_clear_draft,
    draft_state_keys_to_clear,
    has_draft_content,
    join_keywords,
    make_mixed_roleplay_prompt,
)


class DraftSessionTests(unittest.TestCase):
    def test_has_draft_content_with_image(self):
        self.assertTrue(has_draft_content(b"jpeg", [""]))

    def test_has_draft_content_with_keywords(self):
        self.assertTrue(has_draft_content(None, ["hello", ""]))

    def test_has_draft_content_empty(self):
        self.assertFalse(has_draft_content(None, ["", ""]))

    def test_join_keywords_filters_blanks(self):
        self.assertEqual(join_keywords([" a ", "", "b"]), "a, b")

    def test_apply_clear_draft_removes_draft_keys(self):
        session = {
            "form_round": 2,
            f"{DRAFT_KEY_PREFIX}_0": "hello",
            f"{DRAFT_KEY_PREFIX}_1": "world",
            DRAFT_IMAGE_BYTES: b"img",
            DRAFT_KEYWORDS: ["hello", "world"],
            "detail_id": 5,
        }
        apply_clear_draft(session)
        self.assertEqual(session["form_round"], 3)
        self.assertNotIn(f"{DRAFT_KEY_PREFIX}_0", session)
        self.assertNotIn(DRAFT_IMAGE_BYTES, session)
        self.assertNotIn(DRAFT_KEYWORDS, session)
        self.assertEqual(session["detail_id"], 5)

    def test_draft_state_keys_to_clear_complete(self):
        keys = set(draft_state_keys_to_clear())
        self.assertIn(DRAFT_IMAGE_BYTES, keys)
        self.assertIn(DRAFT_KEYWORDS, keys)

    def test_mixed_roleplay_prompt(self):
        quiz = {
            "items": [
                {"date": "2026-07-01", "keyword": "pose a threat"},
                {"date": "2026-07-05", "keyword": "in use"},
            ]
        }
        prompt = make_mixed_roleplay_prompt(quiz, recent_only=True)
        self.assertIn("롤플레잉", prompt)
        self.assertIn("pose a threat", prompt)
        self.assertIn("최근 2주", prompt)


if __name__ == "__main__":
    unittest.main()
