# =============================================================================
#  storage.py  -  데이터 저장 백엔드 (로컬 SQLite  /  클라우드 Supabase 자동 전환)
# -----------------------------------------------------------------------------
#  - 클라우드(Streamlit Cloud)에 Supabase 비밀키(secrets)가 설정되어 있으면
#    Supabase(Postgres + Storage)에 사진과 기록을 "영구 보존" 합니다.
#  - 비밀키가 없으면(예: 내 컴퓨터에서 테스트할 때) 기존처럼 로컬 SQLite와
#    saved_images 폴더를 사용합니다.
#
#  앱 코드(app.py)는 이 모듈의 함수만 호출하면 되고,
#  어떤 백엔드를 쓰는지는 신경 쓸 필요가 없습니다.
# =============================================================================

import os
import sqlite3
import random
import mimetypes
from datetime import datetime, timedelta, timezone

import streamlit as st

# ----- 로컬(폴백) 저장 설정 -----
DB_PATH = "study_log.db"
IMAGE_DIR = "saved_images"

# ----- Supabase 저장 설정 -----
BUCKET = "study-images"          # Supabase Storage 버킷 이름
TABLE = "study_records"          # Supabase 테이블 이름


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


def backend_name() -> str:
    """현재 사용 중인 저장 방식 이름 (화면 안내용)."""
    return "클라우드(Supabase) · 영구 저장" if use_supabase() else "로컬(SQLite) · 이 컴퓨터에만 저장"


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
def save_study(keywords: str, file_name: str, file_bytes: bytes):
    """학습 기록 한 건을 저장한다. (사진 파일 + 키워드 + 날짜)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{file_name}"

    if use_supabase():
        client = _client()
        mime = mimetypes.guess_type(file_name)[0] or "image/jpeg"
        # 1) 사진을 Supabase Storage 버킷에 업로드
        client.storage.from_(BUCKET).upload(
            path=safe_name,
            file=file_bytes,
            file_options={"content-type": mime, "upsert": "true"},
        )
        # 2) 공개 URL 받아서 DB에 경로로 저장
        public_url = client.storage.from_(BUCKET).get_public_url(safe_name)
        client.table(TABLE).insert(
            {"keywords": keywords, "image_path": public_url}
        ).execute()
    else:
        os.makedirs(IMAGE_DIR, exist_ok=True)
        save_path = os.path.join(IMAGE_DIR, safe_name)
        with open(save_path, "wb") as f:
            f.write(file_bytes)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT INTO study_records (created_at, keywords, image_path) VALUES (?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), keywords, save_path),
            )
            conn.commit()
        finally:
            conn.close()


# -----------------------------------------------------------------------------
# 조회
# -----------------------------------------------------------------------------
def _normalize(row: dict) -> dict:
    """백엔드와 무관하게 동일한 형태(dict)로 반환한다."""
    return {
        "id": row["id"],
        "created_at": _format_dt(row["created_at"]),
        "keywords": row["keywords"],
        "image_src": row["image_path"],  # 로컬 경로 또는 공개 URL
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
