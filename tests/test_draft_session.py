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
    draft_widget_prefix,
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

    def test_draft_widget_prefix_uses_form_round(self):
        self.assertEqual(draft_widget_prefix({"form_round": 0}), f"{DRAFT_KEY_PREFIX}_r0")
        self.assertEqual(draft_widget_prefix({"form_round": 4}), f"{DRAFT_KEY_PREFIX}_r4")

    def test_apply_clear_draft_removes_draft_keys(self):
        session = {
            "form_round": 2,
            f"{DRAFT_KEY_PREFIX}_r2_0": "hello",
            f"{DRAFT_KEY_PREFIX}_r2_1": "world",
            f"{DRAFT_KEY_PREFIX}_0": "legacy",
            DRAFT_IMAGE_BYTES: b"img",
            DRAFT_KEYWORDS: ["hello", "world"],
            "detail_id": 5,
        }
        apply_clear_draft(session)
        self.assertEqual(session["form_round"], 3)
        self.assertNotIn(f"{DRAFT_KEY_PREFIX}_r2_0", session)
        self.assertNotIn(f"{DRAFT_KEY_PREFIX}_0", session)
        self.assertNotIn(DRAFT_IMAGE_BYTES, session)
        self.assertNotIn(DRAFT_KEYWORDS, session)
        self.assertEqual(session["detail_id"], 5)
        # 다음 라운드 prefix 는 비어 있어야 새 사진 입력 시 잔상이 없다
        self.assertEqual(draft_widget_prefix(session), f"{DRAFT_KEY_PREFIX}_r3")

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
        prompt = make_mixed_roleplay_prompt(quiz, scope="recent")
        self.assertIn("롤플레잉", prompt)
        self.assertIn("pose a threat", prompt)
        self.assertIn("최근 2주", prompt)

    def test_chatgpt_url_embeds_current_keywords(self):
        from app import build_chatgpt_url, build_roleplay_prompt

        kw = "Many parents try to take a, Back when I was in college"
        prompt = build_roleplay_prompt(kw, mode="review")
        url = build_chatgpt_url(prompt)
        self.assertIn("chatgpt.com", url)
        self.assertIn("Many%20parents", url)
        self.assertNotIn("Raising%20and%20looking", url)


if __name__ == "__main__":
    unittest.main()
