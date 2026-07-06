"""영어회화 저장·이미지 검증 smoke tests (unittest)."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import study_storage as storage  # noqa: E402


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color=(30, 120, 200)).save(buf, format="JPEG")
    return buf.getvalue()


class StudyStorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._root = Path(self._tmp.name)
        (self._root / "data" / "english").mkdir(parents=True)
        (self._root / "data" / "attachments" / "english").mkdir(parents=True)
        self._env = patch.dict(os.environ, {"MYKNOWLEDGE_DB_ROOT": str(self._root)})
        self._env.start()
        storage._local_paths_ready = False
        storage.DB_PATH = ""
        storage.IMAGE_DIR = ""
        storage.init_storage()

    def tearDown(self):
        self._env.stop()
        storage._local_paths_ready = False
        self._tmp.cleanup()

    @patch.object(storage, "use_supabase", return_value=False)
    def test_validate_upload_rejects_tiny_file(self, _mock_sb):
        ok, msg = storage.validate_upload("sample.jpg", b"tiny")
        self.assertFalse(ok)
        self.assertEqual(msg, storage.INVALID_IMAGE_MESSAGE)

    @patch.object(storage, "use_supabase", return_value=False)
    def test_validate_upload_rejects_bad_extension(self, _mock_sb):
        ok, msg = storage.validate_upload("notes.txt", b"hello world")
        self.assertFalse(ok)
        self.assertIn("JPG", msg)

    @patch.object(storage, "use_supabase", return_value=False)
    def test_validate_upload_accepts_jpeg(self, _mock_sb):
        ok, fmt = storage.validate_upload("photo.jpg", _jpeg_bytes())
        self.assertTrue(ok)
        self.assertEqual(fmt, "JPEG")

    @patch.object(storage, "use_supabase", return_value=False)
    def test_save_keywords_only_without_image(self, _mock_sb):
        storage.save_study("hello, world")
        records = storage.fetch_all_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["keywords"], "hello, world")
        self.assertEqual(records[0]["image_path"], "")

    @patch.object(storage, "use_supabase", return_value=False)
    def test_save_rejects_keywords_missing(self, _mock_sb):
        with self.assertRaises(ValueError):
            storage.save_study("   ")

    @patch.object(storage, "use_supabase", return_value=False)
    def test_save_rejects_invalid_image(self, _mock_sb):
        with self.assertRaises(ValueError):
            storage.save_study("vocab", "bad.jpg", b"not-image")

    @patch.object(storage, "use_supabase", return_value=False)
    def test_save_with_valid_image(self, _mock_sb):
        storage.save_study("apple", "apple.jpg", _jpeg_bytes())
        records = storage.fetch_all_records()
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["image_path"])
        self.assertTrue(Path(records[0]["image_path"]).is_file())

    @patch.object(storage, "use_supabase", return_value=False)
    def test_read_local_image_bytes_returns_none_for_broken_file(self, _mock_sb):
        broken = Path(storage.IMAGE_DIR) / "broken.jpg"
        broken.write_bytes(b"123456789")
        self.assertIsNone(storage.read_local_image_bytes(str(broken)))

    @patch.object(storage, "use_supabase", return_value=False)
    def test_read_display_image_bytes_local_valid(self, _mock_sb):
        path = Path(storage.IMAGE_DIR) / "good.jpg"
        path.write_bytes(_jpeg_bytes())
        result = storage.read_display_image_bytes(str(path))
        self.assertIsNotNone(result)

    @patch.object(storage, "use_supabase", return_value=False)
    def test_read_display_image_bytes_local_broken(self, _mock_sb):
        broken = Path(storage.IMAGE_DIR) / "broken.jpg"
        broken.write_bytes(b"123456789")
        self.assertIsNone(storage.read_display_image_bytes(str(broken)))

    @patch.object(storage, "use_supabase", return_value=False)
    def test_normalize_png_screenshot_to_small_jpeg(self, _mock_sb):
        """스크린샷(PNG)도 작은 JPEG 로 저장되어 용량을 줄인다."""
        buf = io.BytesIO()
        Image.new("RGB", (2048, 1536), color=(240, 240, 240)).save(buf, format="PNG")
        out_bytes, out_name = storage.normalize_image_bytes(buf.getvalue(), "screenshot.png")
        self.assertEqual(out_name.endswith(".jpg"), True)
        self.assertLess(len(out_bytes), len(buf.getvalue()))
        with Image.open(io.BytesIO(out_bytes)) as img:
            img.load()
            self.assertEqual(img.format, "JPEG")
            self.assertLessEqual(max(img.size), storage.MAX_UPLOAD_LONG_EDGE)

    @patch.object(storage, "use_supabase", return_value=False)
    def test_normalize_large_iphone_jpeg(self, _mock_sb):
        """아이폰 카메라급 고해상도 JPEG도 업로드 정규화가 가능해야 한다."""
        buf = io.BytesIO()
        Image.new("RGB", (4032, 3024), color=(120, 80, 40)).save(buf, format="JPEG", quality=90)
        raw = buf.getvalue()
        out_bytes, out_name = storage.normalize_image_bytes(raw, "IMG_1234.jpeg")
        self.assertTrue(out_name.endswith(".jpg"))
        self.assertTrue(len(out_bytes) > storage.MIN_IMAGE_BYTES)
        with Image.open(io.BytesIO(out_bytes)) as img:
            img.load()
            self.assertLessEqual(max(img.size), storage.MAX_UPLOAD_LONG_EDGE)

    @patch.object(storage, "use_supabase", return_value=False)
    def test_normalize_detects_jpeg_without_extension(self, _mock_sb):
        buf = io.BytesIO()
        Image.new("RGB", (200, 150), color=(10, 20, 30)).save(buf, format="JPEG")
        out_bytes, out_name = storage.normalize_image_bytes(buf.getvalue(), "image")
        self.assertTrue(out_name.endswith(".jpg"))
        self.assertTrue(out_bytes)

    @patch.object(storage, "use_supabase", return_value=False)
    def test_fetch_records_page(self, _mock_sb):
        for i in range(30):
            storage.save_study(f"word{i}", "a.jpg", _jpeg_bytes())
        page1, total = storage.fetch_records_page(1, 10)
        page2, _ = storage.fetch_records_page(2, 10)
        self.assertEqual(total, 30)
        self.assertEqual(len(page1), 10)
        self.assertEqual(len(page2), 10)
        self.assertNotEqual(page1[0]["id"], page2[0]["id"])

    @patch.object(storage, "use_supabase", return_value=False)
    def test_fetch_record_by_id(self, _mock_sb):
        storage.save_study("hello", "a.jpg", _jpeg_bytes())
        records = storage.fetch_all_records()
        found = storage.fetch_record_by_id(records[0]["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["keywords"], "hello")

    @patch.object(storage, "use_supabase", return_value=False)
    def test_thumbnail_data_uri_local(self, _mock_sb):
        storage.save_study("thumb", "t.jpg", _jpeg_bytes())
        rec = storage.fetch_all_records()[0]
        uri = storage.thumbnail_data_uri(rec["image_path"])
        self.assertTrue(uri.startswith("data:image/jpeg;base64,"))

    @patch.object(storage, "use_supabase", return_value=False)
    def test_get_storage_info_paths(self, _mock_sb):
        info = storage.get_storage_info()
        self.assertEqual(info["mode"], "local")
        self.assertTrue(info["db_path"].endswith("study_log.db"))
        self.assertTrue(info["image_dir"].endswith("attachments/english"))


class SupabaseStorageTests(unittest.TestCase):
    def setUp(self):
        storage._local_paths_ready = False
        storage.DB_PATH = ""
        storage.IMAGE_DIR = ""

    @patch.object(storage, "use_supabase", return_value=True)
    @patch.object(storage, "_client")
    def test_resolve_image_src_returns_signed_url(self, mock_client_fn, _mock_sb):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        signed = "https://cdn.example/study-images/photo.jpg?token=abc"
        mock_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": signed,
        }

        url = storage.resolve_image_src("photo.jpg")
        self.assertEqual(url, signed)
        mock_client.storage.from_.assert_called_with(storage.BUCKET)
        mock_client.storage.from_.return_value.create_signed_url.assert_called_once()

    @patch.object(storage, "use_supabase", return_value=True)
    def test_get_storage_info_supabase_label(self, _mock_sb):
        info = storage.get_storage_info()
        self.assertEqual(info["mode"], "supabase")
        self.assertEqual(info["label"], "클라우드(Supabase) · Private + Signed URL")
        self.assertEqual(info["db_path"], "")

    @patch.object(storage, "use_supabase", return_value=True)
    @patch.object(storage, "_client")
    @patch.object(storage, "_fetch_url_bytes")
    def test_read_display_image_bytes_valid_supabase(
        self, mock_fetch, mock_client_fn, _mock_sb
    ):
        jpeg = _jpeg_bytes()
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        signed = "https://cdn.example/study-images/ok.jpg?token=1"
        mock_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": signed,
        }
        mock_fetch.return_value = jpeg

        result = storage.read_display_image_bytes("ok.jpg")
        self.assertEqual(result, jpeg)
        mock_fetch.assert_called_once_with(signed)

    @patch.object(storage, "use_supabase", return_value=True)
    @patch.object(storage, "_client")
    @patch.object(storage, "_fetch_url_bytes", return_value=b"not-an-image")
    def test_read_display_image_bytes_rejects_invalid_supabase(
        self, _mock_fetch, mock_client_fn, _mock_sb
    ):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://cdn.example/bad.jpg",
        }
        self.assertIsNone(storage.read_display_image_bytes("bad.jpg"))

    @patch.object(storage, "use_supabase", return_value=True)
    @patch.object(storage, "_client")
    @patch.object(storage, "_fetch_url_bytes", return_value=None)
    def test_read_display_image_bytes_fetch_failure(
        self, _mock_fetch, mock_client_fn, _mock_sb
    ):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://cdn.example/missing.jpg",
        }
        self.assertIsNone(storage.read_display_image_bytes("missing.jpg"))

    @patch.object(storage, "use_supabase", return_value=True)
    @patch.object(storage, "_client")
    def test_save_study_supabase_keywords_only(self, mock_client_fn, _mock_sb):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        storage.save_study("hello only")

        mock_client.table.assert_called_with(storage.TABLE)
        mock_client.table.return_value.insert.assert_called_once_with(
            {"keywords": "hello only", "image_path": ""}
        )
        mock_client.table.return_value.insert.return_value.execute.assert_called_once()

    @patch.object(storage, "use_supabase", return_value=True)
    @patch.object(storage, "_client")
    def test_save_study_supabase_with_image(self, mock_client_fn, _mock_sb):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        bucket = mock_client.storage.from_.return_value

        storage.save_study("apple", "apple.jpg", _jpeg_bytes())

        mock_client.storage.from_.assert_called_with(storage.BUCKET)
        bucket.upload.assert_called_once()
        payload = mock_client.table.return_value.insert.call_args.args[0]
        self.assertEqual(payload["keywords"], "apple")
        self.assertTrue(payload["image_path"].endswith(".jpg"))
        self.assertNotIn("http", payload["image_path"])


if __name__ == "__main__":
    unittest.main()
