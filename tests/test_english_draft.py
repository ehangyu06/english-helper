"""영어회화 durable draft (재로그인 복구) 테스트."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import english_draft as ed  # noqa: E402


class EnglishDraftLocalTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        draft_dir = Path(self._td.name) / "working_draft"
        self._patches = [
            mock.patch.object(ed, "LOCAL_DRAFT_DIR", draft_dir),
            mock.patch.object(ed, "LOCAL_PAYLOAD", draft_dir / "payload.json"),
            mock.patch.object(ed, "LOCAL_IMAGE", draft_dir / "image.bin"),
            mock.patch.object(ed, "LOCAL_IMAGE_META", draft_dir / "image_name.txt"),
            mock.patch.object(ed, "_use_supabase", return_value=False),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def test_save_and_load_keywords_and_image(self):
        img = b"\xff\xd8\xfffakejpeg"
        saved = ed.save_working_draft(
            keywords=["pose a threat", "in use", ""],
            image_bytes=img,
            image_name="photo.jpg",
        )
        self.assertIsNotNone(saved)
        loaded = ed.load_working_draft()
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["keywords"][0], "pose a threat")
        self.assertEqual(loaded["keywords"][1], "in use")
        self.assertTrue(loaded["has_image"])
        self.assertEqual(loaded["image_bytes"], img)
        self.assertTrue(ed.has_recoverable_draft())
        self.assertEqual(loaded["backend"], "app_local")

    def test_clear_working_draft(self):
        ed.save_working_draft(keywords=["hello"], image_bytes=None, image_name=None)
        self.assertTrue(ed.has_recoverable_draft())
        ed.clear_working_draft()
        self.assertFalse(ed.has_recoverable_draft())
        self.assertIsNone(ed.load_working_draft())

    def test_empty_not_saved(self):
        self.assertIsNone(
            ed.save_working_draft(keywords=["", ""], image_bytes=None, image_name=None)
        )
        self.assertFalse(ed.has_recoverable_draft())

    def test_fingerprint_changes_with_content(self):
        a = ed.draft_fingerprint(["a"], has_image=False, image_nbytes=0)
        b = ed.draft_fingerprint(["b"], has_image=False, image_nbytes=0)
        c = ed.draft_fingerprint(["a"], has_image=True, image_nbytes=10)
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)

    def test_logout_then_load_restores(self):
        """로그아웃 후 새 세션처럼 비어 있어도 Draft에서 복구 가능."""
        ed.save_working_draft(
            keywords=["keep me", "also"],
            image_bytes=b"abc",
            image_name="x.jpg",
        )
        loaded = ed.load_working_draft()
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["keywords"][:2], ["keep me", "also"])
        self.assertEqual(loaded["image_bytes"], b"abc")


class AppRestoreHelpersTests(unittest.TestCase):
    def test_restore_helpers_importable(self):
        import app as english_app

        self.assertTrue(callable(english_app.persist_durable_draft_from_session))
        self.assertTrue(callable(english_app.restore_durable_draft_to_session))
        self.assertTrue(callable(english_app.maybe_auto_restore_draft))
        self.assertTrue(callable(english_app.render_draft_recovery_banner))
        self.assertTrue(callable(english_app._perform_logout))

    def test_maybe_auto_restore_does_not_fill_form(self):
        """자동 복구는 숙어 칸을 채우지 않는다 (이전 값이 기본값처럼 남는 버그 방지)."""
        import app as english_app

        session = {}

        class _FakeSession(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        fake = _FakeSession()
        with mock.patch.object(english_app, "st") as st_mock:
            st_mock.session_state = fake
            english_app.maybe_auto_restore_draft()
        self.assertTrue(fake.get("draft_auto_restore_done"))
        self.assertNotIn(english_app.DRAFT_KEYWORDS, fake)
        self.assertNotIn(f"{english_app.DRAFT_KEY_PREFIX}_0", fake)


if __name__ == "__main__":
    unittest.main()
