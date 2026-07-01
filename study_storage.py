# =============================================================================
#  study_storage.py  -  데이터 저장 백엔드 (로컬 SQLite  /  클라우드 Supabase 자동 전환)
# -----------------------------------------------------------------------------
#  - 클라우드(Streamlit Cloud)에 Supabase 비밀키(secrets)가 설정되어 있으면
#    Supabase(Postgres + Storage)에 사진과 기록을 "영구 보존" 합니다.
#  - 비밀키가 없으면(예: 내 컴퓨터에서 테스트할 때) 기존처럼 로컬 SQLite와
#    saved_images 폴더를 사용합니다.
#
#  보안 (Supabase 모드):
#  - Storage 버킷은 Private 로 두고, DB에는 파일명(객체 경로)만 저장합니다.
#  - 화면에 표시할 때만 만료되는 Signed URL 을 서버에서 발급합니다.
# =============================================================================

import os
import re
import uuid
import sqlite3
import random
import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Optional

import streamlit as st

# ----- 로컬(폴백) 저장 설정 -----
DB_PATH = "study_log.db"
IMAGE_DIR = "saved_images"

# study_storage v2 — Streamlit Cloud 모듈 캐시 갱신용
BUCKET = "study-images"          # Supabase Storage 버킷 이름
TABLE = "study_records"          # Supabase 테이블 이름
DEFAULT_SIGNED_URL_EXPIRES = 3600  # Signed URL 유효 시간(초). 기본 1시간


# -----------------------------------------------------------------------------
# 백엔드 판별
# -----------------------------------------------------------------------------
def use_supabase() -> bool:
    """Supabase 비밀키가 설정되어 있으면 True (클라우드 영구 저장 모드)."""
    try:
        cfg = st.secrets.get("supabase", None)
        return bool(cfg) and bool(cfg.get("url")) and bool(cfg.get("key"))
    except Exception:
        return False


@st.cache_resource
def _client():
    """Supabase 클라이언트를 한 번만 만들어 재사용한다."""
    from supabase import create_client

    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["key"])


def _signed_url_expires() -> int:
    """secrets 에서 Signed URL 만료 시간(초)을 읽는다."""
    try:
        cfg = st.secrets.get("supabase", {})
        return int(cfg.get("signed_url_expires", DEFAULT_SIGNED_URL_EXPIRES))
    except Exception:
        return DEFAULT_SIGNED_URL_EXPIRES


def backend_name() -> str:
    """현재 사용 중인 저장 방식 이름 (화면 안내용)."""
    if use_supabase():
        return "클라우드(Supabase) · Private + Signed URL"
    return "로컬(SQLite) · 이 컴퓨터에만 저장"

# -----------------------------------------------------------------------------
# 공통 유틸
# -----------------------------------------------------------------------------
def _format_dt(value) -> str:
    """다양한 형식의 날짜 문자열을 'YYYY-MM-DD HH:MM' 으로 보기 좋게 변환."""
    if not value:
        return ""
    try:
        v = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def _storage_object_path(image_path: str) -> Optional[str]:
    """
    DB 에 저장된 image_path 값에서 Supabase Storage 객체 경로를 추출한다.
    - 새 형식: 파일명만 (예: 20250101_xxx_img.jpg)
    - 구 형식: 공개 URL (마이그레이션 호환)
    - 로컬 경로: None 반환
    """
    if not image_path:
        return None
    if image_path.startswith(IMAGE_DIR) or os.path.isabs(image_path):
        return None
    if image_path.startswith("http://") or image_path.startswith("https://"):
        marker = f"/{BUCKET}/"
        if marker in image_path:
            return image_path.split(marker, 1)[1].split("?")[0]
        return image_path.rstrip("/").split("/")[-1]
    return image_path


def _extract_signed_url(response) -> str:
    """Supabase create_signed_url 응답에서 URL 문자열을 꺼낸다."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("signedURL", "signedUrl", "signed_url"):
            if response.get(key):
                return str(response[key])
    for attr in ("signed_url", "signedURL", "signedUrl"):
        if hasattr(response, attr):
            val = getattr(response, attr)
            if val:
                return str(val)
    return ""


def resolve_image_src(image_path: str) -> str:
    """
    화면 표시용 이미지 주소를 반환한다.
    - 로컬: 파일 경로 그대로
    - Supabase: 만료되는 Signed URL (Private 버킷)
    """
    if not image_path:
        return ""

    if not use_supabase():
        return image_path

    obj_path = _storage_object_path(image_path)
    if not obj_path:
        return image_path

    try:
        client = _client()
        res = client.storage.from_(BUCKET).create_signed_url(
            obj_path, _signed_url_expires()
        )
        signed = _extract_signed_url(res)
        if signed:
            return signed
    except Exception:
        pass

    # 구 공개 URL 이 DB 에 남아 있고 버킷이 아직 Public 인 경우 폴백
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    return ""


# -----------------------------------------------------------------------------
# 초기화
# -----------------------------------------------------------------------------
def init_storage():
    """폴더/DB가 없으면 자동 생성 (로컬 모드). Supabase 모드는 사전 설정 사용."""
    if use_supabase():
        return  # 테이블/버킷은 README 가이드에 따라 미리 만들어 둠
    os.makedirs(IMAGE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                keywords    TEXT NOT NULL,
                image_path  TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 저장 (사진 업로드 + 기록)
# -----------------------------------------------------------------------------
def _unique_name(file_name: str) -> str:
    """
    파일명을 항상 고유하게 만든다.
    아이패드 사진은 이름이 모두 'image.jpg'처럼 같게 올라오는 경우가 많아,
    날짜+마이크로초+무작위 코드를 붙여 절대 겹치지 않도록 한다.
    한글/공백/특수문자도 Supabase가 안전하게 받도록 정리한다.
    """
    base, ext = os.path.splitext(file_name)
    ext = ext.lower() if ext else ".jpg"
    base = re.sub(r"[^A-Za-z0-9._-]", "", base)[:30] or "img"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{stamp}_{uuid.uuid4().hex[:8]}_{base}{ext}"


def _store_image(file_name: str, file_bytes: bytes) -> str:
    """사진을 저장하고, DB에 기록할 경로(로컬 경로 또는 Storage 객체 경로)를 돌려준다."""
    safe_name = _unique_name(file_name)

    if use_supabase():
        client = _client()
        mime = mimetypes.guess_type(safe_name)[0] or "image/jpeg"
        client.storage.from_(BUCKET).upload(
            path=safe_name,
            file=file_bytes,
            file_options={"content-type": mime, "upsert": "true"},
        )
        return safe_name  # Private 버킷: 파일명만 DB에 저장
    else:
        os.makedirs(IMAGE_DIR, exist_ok=True)
        save_path = os.path.join(IMAGE_DIR, safe_name)
        with open(save_path, "wb") as f:
            f.write(file_bytes)
        return save_path


def save_study(keywords: str, file_name: str, file_bytes: bytes):
    """학습 기록 한 건을 저장한다. (사진 파일 + 키워드 + 날짜)"""
    image_path = _store_image(file_name, file_bytes)

    if use_supabase():
        client = _client()
        client.table(TABLE).insert(
            {"keywords": keywords, "image_path": image_path}
        ).execute()
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT INTO study_records (created_at, keywords, image_path) VALUES (?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), keywords, image_path),
            )
            conn.commit()
        finally:
            conn.close()


def update_study(record_id, keywords: str, file_name: str = None, file_bytes: bytes = None):
    """기존 학습 기록을 수정한다. (키워드는 항상, 사진은 새로 올린 경우에만 교체)"""
    new_path = None
    if file_name is not None and file_bytes is not None:
        new_path = _store_image(file_name, file_bytes)

    if use_supabase():
        client = _client()
        payload = {"keywords": keywords}
        if new_path is not None:
            payload["image_path"] = new_path
        client.table(TABLE).update(payload).eq("id", record_id).execute()
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            if new_path is not None:
                conn.execute(
                    "UPDATE study_records SET keywords = ?, image_path = ? WHERE id = ?",
                    (keywords, new_path, record_id),
                )
            else:
                conn.execute(
                    "UPDATE study_records SET keywords = ? WHERE id = ?",
                    (keywords, record_id),
                )
            conn.commit()
        finally:
            conn.close()


def delete_study(record_id):
    """학습 기록 한 건을 삭제한다. (DB 행 삭제)"""
    if use_supabase():
        client = _client()
        client.table(TABLE).delete().eq("id", record_id).execute()
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("DELETE FROM study_records WHERE id = ?", (record_id,))
            conn.commit()
        finally:
            conn.close()


# -----------------------------------------------------------------------------
# 조회
# -----------------------------------------------------------------------------
def _normalize(row: dict) -> dict:
    """백엔드와 무관하게 동일한 형태(dict)로 반환한다."""
    image_path = row["image_path"]
    return {
        "id": row["id"],
        "created_at": _format_dt(row["created_at"]),
        "keywords": row["keywords"],
        "image_path": image_path,
        "image_src": resolve_image_src(image_path),
    }


def fetch_all_records():
    """모든 학습 기록을 최신순으로 가져온다."""
    if use_supabase():
        client = _client()
        res = (
            client.table(TABLE)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return [_normalize(r) for r in (res.data or [])]
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, created_at, keywords, image_path FROM study_records ORDER BY created_at DESC"
            ).fetchall()
            return [_normalize(dict(r)) for r in rows]
        finally:
            conn.close()


def fetch_today_records():
    """오늘 저장한 학습 기록을 최신순으로 가져온다."""
    today = datetime.now().strftime("%Y-%m-%d")
    return [r for r in fetch_all_records() if str(r.get("created_at", "")).startswith(today)]


RECENT_REVIEW_DAYS = 14  # 무작위 복습: 최근 N일 이내 학습만


def fetch_random_recent_record(days: int = RECENT_REVIEW_DAYS):
    """최근 days 일 이내 학습 기록 중 무작위로 한 건을 가져온다."""
    if use_supabase():
        client = _client()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        res = client.table(TABLE).select("*").gte("created_at", cutoff).execute()
        rows = res.data or []
        if not rows:
            return None
        return _normalize(random.choice(rows))
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.row_factory = sqlite3.Row
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                "SELECT id, created_at, keywords, image_path FROM study_records WHERE created_at >= ?",
                (cutoff,),
            ).fetchall()
            if not rows:
                return None
            return _normalize(dict(random.choice(rows)))
        finally:
            conn.close()


def fetch_random_record():
    """전체 학습 기록 중 무작위로 한 건을 가져온다."""
    if use_supabase():
        client = _client()
        res = client.table(TABLE).select("*").execute()
        rows = res.data or []
        if not rows:
            return None
        return _normalize(random.choice(rows))
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, created_at, keywords, image_path FROM study_records"
            ).fetchall()
            if not rows:
                return None
            return _normalize(dict(random.choice(rows)))
        finally:
            conn.close()


def fetch_review_record(min_days: int = 7):
    """
    저장된 지 min_days 일 이상 지난 과거 기록 중 하나를 무작위로 가져온다.
    조건에 맞는 기록이 없으면 전체 기록 중 무작위로 하나를 반환한다.
    """
    if use_supabase():
        client = _client()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=min_days)).isoformat()
        res = client.table(TABLE).select("*").lte("created_at", cutoff).execute()
        rows = res.data or []
        if not rows:
            res = client.table(TABLE).select("*").execute()
            rows = res.data or []
        if not rows:
            return None
        return _normalize(random.choice(rows))
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.row_factory = sqlite3.Row
            cutoff = (datetime.now() - timedelta(days=min_days)).strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                "SELECT id, created_at, keywords, image_path FROM study_records WHERE created_at <= ?",
                (cutoff,),
            ).fetchall()
            if not rows:
                rows = conn.execute(
                    "SELECT id, created_at, keywords, image_path FROM study_records"
                ).fetchall()
            if not rows:
                return None
            return _normalize(dict(random.choice(rows)))
        finally:
            conn.close()
