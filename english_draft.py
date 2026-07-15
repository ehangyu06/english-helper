"""영어회화 학습 등록 Draft — 재로그인·세션 종료 후에도 복구.

우선순위(쓰기): 앱 로컬 폴더 → (가능하면) Supabase Storage
우선순위(읽기): Supabase → 앱 로컬 폴더

Streamlit Cloud 에서도 동작하도록 shared/iCloud 에 의존하지 않는다.
"""
from __future__ import annotations

import json
import mimetypes
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_APP_DIR = Path(__file__).resolve().parent
LOCAL_DRAFT_DIR = _APP_DIR / ".working_draft"
LOCAL_PAYLOAD = LOCAL_DRAFT_DIR / "payload.json"
LOCAL_IMAGE = LOCAL_DRAFT_DIR / "image.bin"
LOCAL_IMAGE_META = LOCAL_DRAFT_DIR / "image_name.txt"

WORKING_DRAFT_ID = "study-today"
# 폴더 없이 버킷 루트 — RLS/정책 이슈를 줄이기 위함
SUPABASE_PAYLOAD = "_english_draft_payload.json"
SUPABASE_IMAGE = "_english_draft_image.jpg"

_LAST_ERROR: str = ""


def get_last_error() -> str:
    return _LAST_ERROR


def _set_error(msg: str) -> None:
    global _LAST_ERROR
    _LAST_ERROR = (msg or "")[:500]


def _clear_error() -> None:
    global _LAST_ERROR
    _LAST_ERROR = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _use_supabase() -> bool:
    try:
        import study_storage as storage

        return bool(storage.use_supabase())
    except Exception:
        return False


def _normalize_keywords(keywords: list | None) -> list[str]:
    if not keywords:
        return []
    return [str(k or "").strip() for k in keywords]


def build_title(keywords: list[str], *, has_image: bool) -> str:
    joined = ", ".join(k for k in keywords if k)
    if joined:
        return joined[:48] + ("…" if len(joined) > 48 else "")
    if has_image:
        return "사진만 업로드된 학습 Draft"
    return "빈 학습 Draft"


def is_meaningful(keywords: list[str], *, has_image: bool) -> bool:
    if has_image:
        return True
    return bool(", ".join(k for k in keywords if k).strip())


def _payload_dict(
    keywords: list[str],
    *,
    has_image: bool,
    image_name: str,
) -> dict[str, Any]:
    kw = _normalize_keywords(keywords)
    return {
        "keywords": kw,
        "image_name": image_name or ("image.jpg" if has_image else ""),
        "has_image": bool(has_image),
        "updated_at": _utc_now(),
        "title": build_title(kw, has_image=bool(has_image)),
        "draft_id": WORKING_DRAFT_ID,
    }


def _result_from_payload(
    payload: dict[str, Any],
    image_bytes: Optional[bytes],
    backend: str,
) -> Optional[dict[str, Any]]:
    keywords = _normalize_keywords(payload.get("keywords") or [])
    has_image = bool(image_bytes) if image_bytes is not None else bool(payload.get("has_image"))
    if image_bytes is None:
        has_image = False
    if not is_meaningful(keywords, has_image=has_image):
        return None
    return {
        "draft_id": WORKING_DRAFT_ID,
        "keywords": keywords,
        "image_bytes": image_bytes,
        "image_name": str(payload.get("image_name") or "image.jpg"),
        "has_image": has_image,
        "title": payload.get("title") or build_title(keywords, has_image=has_image),
        "updated_at": payload.get("updated_at") or "",
        "backend": backend,
    }


# --- 앱 로컬 (Streamlit Cloud 인스턴스 디스크 / 로컬 실행) -----------------
def _save_app_local(
    keywords: list[str],
    image_bytes: Optional[bytes],
    image_name: Optional[str],
) -> dict[str, Any]:
    LOCAL_DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    has_image = bool(image_bytes)
    name = image_name or ("image.jpg" if has_image else "")
    payload = _payload_dict(keywords, has_image=has_image, image_name=name)
    LOCAL_PAYLOAD.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if has_image and image_bytes is not None:
        LOCAL_IMAGE.write_bytes(image_bytes)
        LOCAL_IMAGE_META.write_text(name or "image.jpg", encoding="utf-8")
    else:
        if LOCAL_IMAGE.exists():
            LOCAL_IMAGE.unlink()
        if LOCAL_IMAGE_META.exists():
            LOCAL_IMAGE_META.unlink()
    return payload


def _load_app_local() -> Optional[dict[str, Any]]:
    if not LOCAL_PAYLOAD.is_file():
        return None
    try:
        payload = json.loads(LOCAL_PAYLOAD.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    image_bytes = None
    if LOCAL_IMAGE.is_file():
        try:
            image_bytes = LOCAL_IMAGE.read_bytes()
        except OSError:
            image_bytes = None
    if payload.get("has_image") and image_bytes is None:
        # 메타만 있고 파일이 없으면 이미지 없는 것으로 취급
        payload = dict(payload)
        payload["has_image"] = False
    return _result_from_payload(payload, image_bytes, "app_local")


def _clear_app_local() -> None:
    for path in (LOCAL_PAYLOAD, LOCAL_IMAGE, LOCAL_IMAGE_META):
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass


# --- Supabase Storage -------------------------------------------------------
def _storage_upload(path: str, data: bytes, content_type: str) -> None:
    import study_storage as storage

    client = storage._client()
    bucket = client.storage.from_(storage.BUCKET)
    options = {"content-type": content_type, "upsert": "true"}
    try:
        bucket.upload(path=path, file=data, file_options=options)
        return
    except Exception:
        # upsert 실패 시 삭제 후 재업로드
        try:
            bucket.remove([path])
        except Exception:
            pass
        bucket.upload(path=path, file=data, file_options=options)


def _save_supabase(
    keywords: list[str],
    image_bytes: Optional[bytes],
    image_name: Optional[str],
) -> dict[str, Any]:
    import study_storage as storage

    has_image = bool(image_bytes)
    name = image_name or ("image.jpg" if has_image else "")
    payload = _payload_dict(keywords, has_image=has_image, image_name=name)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    _storage_upload(SUPABASE_PAYLOAD, body, "application/json")
    if has_image and image_bytes is not None:
        mime = mimetypes.guess_type(name or "image.jpg")[0] or "image/jpeg"
        _storage_upload(SUPABASE_IMAGE, image_bytes, mime)
    else:
        try:
            storage._client().storage.from_(storage.BUCKET).remove([SUPABASE_IMAGE])
        except Exception:
            pass
    return payload


def _download_supabase_bytes(path: str) -> Optional[bytes]:
    import study_storage as storage

    try:
        data = storage._client().storage.from_(storage.BUCKET).download(path)
        if data is None:
            return None
        if isinstance(data, bytes):
            return data
        return bytes(data)
    except Exception:
        return None


def _load_supabase() -> Optional[dict[str, Any]]:
    raw = _download_supabase_bytes(SUPABASE_PAYLOAD)
    if not raw:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    image_bytes = None
    if payload.get("has_image"):
        image_bytes = _download_supabase_bytes(SUPABASE_IMAGE)
    return _result_from_payload(payload, image_bytes, "supabase")


def _clear_supabase() -> None:
    import study_storage as storage

    try:
        storage._client().storage.from_(storage.BUCKET).remove(
            [SUPABASE_PAYLOAD, SUPABASE_IMAGE]
        )
    except Exception:
        pass


# --- 공개 API ---------------------------------------------------------------
def save_working_draft(
    *,
    keywords: list[str],
    image_bytes: Optional[bytes] = None,
    image_name: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """의미 있는 임시 입력을 저장. 로컬은 항상, Supabase는 가능하면."""
    _clear_error()
    kw = _normalize_keywords(keywords)
    has_image = bool(image_bytes)
    if not is_meaningful(kw, has_image=has_image):
        return None

    local_payload = None
    try:
        local_payload = _save_app_local(kw, image_bytes, image_name)
    except Exception as exc:
        _set_error(f"로컬 Draft 저장 실패: {exc}")

    if _use_supabase():
        try:
            return _save_supabase(kw, image_bytes, image_name)
        except Exception as exc:
            _set_error(
                f"클라우드 Draft 저장 실패: {exc}\n{traceback.format_exc()[-300:]}"
            )
            # 로컬이라도 성공했으면 그걸 반환
            return local_payload

    return local_payload


def load_working_draft() -> Optional[dict[str, Any]]:
    """Supabase 우선, 없으면 앱 로컬."""
    _clear_error()
    if _use_supabase():
        try:
            draft = _load_supabase()
            if draft:
                return draft
        except Exception as exc:
            _set_error(f"클라우드 Draft 읽기 실패: {exc}")
    try:
        return _load_app_local()
    except Exception as exc:
        _set_error(f"로컬 Draft 읽기 실패: {exc}")
        return None


def has_recoverable_draft() -> bool:
    return load_working_draft() is not None


def clear_working_draft() -> None:
    _clear_error()
    try:
        _clear_app_local()
    except Exception:
        pass
    if _use_supabase():
        try:
            _clear_supabase()
        except Exception:
            pass


def draft_fingerprint(
    keywords: list[str],
    *,
    has_image: bool,
    image_nbytes: int = 0,
) -> str:
    kw = "|".join(_normalize_keywords(keywords))
    return f"{kw}::{int(has_image)}::{image_nbytes}"
