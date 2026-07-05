# =============================================================================
#  AI 시각 연상 영어 회화 보조 프로그램 (Streamlit)
# -----------------------------------------------------------------------------
#  [내 컴퓨터에서 실행하기]
#   1) Python 3.8 이상 설치
#   2) 라이브러리 설치:  pip install -r requirements.txt
#   3) 실행:            streamlit run app.py
#      → 브라우저가 자동으로 열립니다. (http://localhost:8501)
#
#  [아이패드/아이폰에서 쓰기 (인터넷 배포)]
#   → README.md 의 "배포 가이드"를 따라 GitHub + Supabase + Streamlit Cloud 로
#     올리면 휴대폰/태블릿에서도 접속하고 사진을 업로드할 수 있습니다.
#
#  ※ API Key 불필요. 실제 AI 대화는 버튼으로 무료 ChatGPT 웹사이트로 이동(딥링크).
# =============================================================================

import base64
import io
import json
import os
import random
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps

import study_storage as storage  # 저장 백엔드 (로컬 SQLite / 클라우드 Supabase 자동 전환)

CHATGPT_BASE_URL = "https://chatgpt.com/"  # 무료 ChatGPT 웹사이트
MAX_KEYWORDS = 10
RECENT_REVIEW_DAYS = 14
MIXED_QUIZ_TARGET = 8       # 무작위 퀴즈에 넣을 표현 개수 목표
MIXED_QUIZ_MAX_PER_RECORD = 2  # 학습 기록(날짜)당 최대 표현 수


def prepare_upload_image(file_bytes: bytes, file_name: str):
    """
    아이폰/아이패드 사진의 회전(EXIF)을 픽셀에 반영하고,
    위치·촬영 정보 등 메타데이터는 제거한 뒤 저장용 바이트를 만든다.
    비정상 파일이면 ValueError 를 던진다.
    """
    ok, err = storage.validate_upload(file_name, file_bytes)
    if not ok:
        raise ValueError(err)

    try:
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)

        ext = os.path.splitext(file_name)[1].lower()
        if ext in (".jpg", ".jpeg"):
            fmt, out_ext = "JPEG", ".jpg"
        elif ext == ".webp":
            fmt, out_ext = "WEBP", ".webp"
        else:
            fmt, out_ext = "PNG", ".png"

        # EXIF/GPS 등 메타데이터 제거 — 픽셀만 새 이미지로 복사
        if img.mode in ("RGBA", "P") and fmt == "JPEG":
            img = img.convert("RGB")
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))

        buf = io.BytesIO()
        if fmt == "JPEG":
            clean.save(buf, format=fmt, quality=85, optimize=True)
        else:
            clean.save(buf, format=fmt)
        base = os.path.splitext(file_name)[0]
        out_bytes = buf.getvalue()
        ok, err = storage.validate_image_bytes(out_bytes)
        if not ok:
            raise ValueError(storage.INVALID_IMAGE_MESSAGE)
        return out_bytes, f"{base}{out_ext}"
    except ValueError:
        raise
    except Exception:
        raise ValueError(storage.INVALID_IMAGE_MESSAGE)


# -----------------------------------------------------------------------------
# ChatGPT 딥링크 / 프롬프트
# -----------------------------------------------------------------------------
def build_chatgpt_url(prompt_text: str) -> str:
    """프롬프트를 URL 인코딩하여 ChatGPT 입력창에 채운다. (줄바꿈은 한 줄로 합침)"""
    compact = " ".join(prompt_text.split())
    return f"{CHATGPT_BASE_URL}?q={urllib.parse.quote(compact)}"


def chatgpt_prompt_button(label: str, prompt: str, show_caption: bool = True):
    """
    미리보기와 동일한 프롬프트를 클립보드에 복사하고 ChatGPT를 연다.
    (아이패드·긴 프롬프트에서 URL만으로는 내용이 잘리는 문제 방지)
    """
    url = build_chatgpt_url(prompt)
    components.html(
        f"""
        <div style="margin:0.25rem 0">
          <button id="cgptBtn" type="button" style="width:100%;padding:0.65rem 1rem;
            background:#10a37f;color:#fff;border:none;border-radius:0.5rem;
            font-weight:600;font-size:0.95rem;cursor:pointer;">
            {label}
          </button>
        </div>
        <script>
        (function () {{
            const text = {json.dumps(prompt)};
            const url = {json.dumps(url)};
            document.getElementById('cgptBtn').onclick = function () {{
                const doc = window.parent.document;
                try {{
                    const ta = doc.createElement('textarea');
                    ta.value = text;
                    ta.style.cssText = 'position:fixed;left:-9999px;top:0';
                    doc.body.appendChild(ta);
                    ta.focus();
                    ta.select();
                    doc.execCommand('copy');
                    doc.body.removeChild(ta);
                }} catch (e) {{}}
                window.open(url, '_blank');
            }};
        }})();
        </script>
        """,
        height=52,
    )
    if show_caption:
        st.caption(
            "💡 ChatGPT 입력창 내용이 짧으면 **붙여넣기**(길게 누르기) 하세요. "
            "미리보기와 동일한 내용이 복사됩니다."
        )


def make_roleplay_prompt(keywords: str) -> str:
    """[기능 1 & 2] 롤플레잉 + 힌트 유도용 프롬프트"""
    return (
        f"안녕! 내가 방금 영어 교재에서 '{keywords}'라는 표현들을 공부했어. "
        "지금부터 이 표현들을 자연스럽게 사용할 수 있도록 나랑 가상의 롤플레잉 대화를 시작해줘. "
        "먼저 나에게 상황을 영어로 제시하면서 질문을 던져줘. "
        "내가 답변하면 내 문장도 교정해줘."
    )


def _quiz_rules_body() -> str:
    return (
        "이 표현들을 사용해서 **빈칸 넣기(fill-in-the-blank) 문장 퀴즈**를 내줘.\n"
        "규칙:\n"
        "1) 한 번에 퀴즈 3~5문제를 출제해줘.\n"
        "2) 각 문장에서 공부한 표현 부분을 ______ 빈칸으로 바꿔줘.\n"
        "3) 빈칸 아래에 (힌트: 첫 글자 또는 한국어 뜻)을 작게 적어줘.\n"
        "4) 내가 답을내면 정답을 알려주고, 틀린 부분은 교정해줘.\n"
        "5) 문장은 일상 회화나 교재 상황에 맞게 자연스럽게 만들어줘.\n"
        "먼저 첫 번째 문제부터 출제해줘."
    )


def make_quiz_prompt(keywords: str, studied_date: str = "", recent_only: bool = False) -> str:
    """단일 학습 기록용 빈칸 퀴즈 프롬프트."""
    if studied_date:
        if recent_only:
            scope = "최근 2주 안에 공부한 내용이야"
        else:
            scope = "지금까지 공부한 내용 중 무작위로 뽑은 거야"
        intro = (
            f"안녕! 내가 예전에({studied_date}) 공부했던 영어 표현들 중에서 "
            f"무작위로 뽑은 키워드가 '{keywords}'야. ({scope}.)"
        )
    else:
        intro = f"안녕! 오늘 교재를 보며 공부한 영어 표현이 '{keywords}'야."
    return f"{intro}\n\n{_quiz_rules_body()}"


def make_mixed_quiz_prompt(quiz: dict, recent_only: bool = False) -> str:
    """여러 날짜에서 골라 낸 표현들로 빈칸 퀴즈 프롬프트를 만든다."""
    scope = "최근 2주 안에 공부한" if recent_only else "지금까지 공부한"
    lines = "\n".join(f"- {item['date']}: {item['keyword']}" for item in quiz["items"])
    intro = (
        f"안녕! {scope} 표현들 중에서 **여러 날짜에 걸쳐** 무작위로 뽑은 표현들이야:\n"
        f"{lines}\n\n"
        f"(총 {len(quiz['items'])}개 — 날짜마다 1~2개씩 골랐어)"
    )
    return f"{intro}\n\n{_quiz_rules_body()}"


def render_random_quiz_block(
    title: str,
    caption: str,
    session_key: str,
    fetch_fn,
    pick_button_key: str,
    quiz_button_label: str,
    empty_message: str,
    recent_only: bool = False,
):
    """무작위 복습 퀴즈 블록 (최근 2주 / 전체 등 공통 UI)."""
    st.markdown(title)
    st.caption(caption)

    if session_key not in st.session_state:
        try:
            st.session_state[session_key] = fetch_fn()
        except Exception:
            st.session_state[session_key] = None

    quiz = st.session_state.get(session_key)
    if quiz is not None and not isinstance(quiz.get("items"), list):
        st.session_state[session_key] = fetch_fn()
        quiz = st.session_state.get(session_key)

    if quiz is None:
        st.info(empty_message)
    else:
        st.markdown("**📚 이번에 뽑은 표현 (날짜별):**")
        for item in quiz["items"]:
            st.markdown(f"- **{item['date']}** · `{item['keyword']}`")
        st.caption(f"총 {len(quiz['items'])}개 · 여러 날짜에서 1~2개씩 무작위 선택")
        prompt = make_mixed_quiz_prompt(quiz, recent_only)
        quiz_col, new_col = st.columns([3, 2])
        with quiz_col:
            chatgpt_prompt_button(quiz_button_label, prompt, show_caption=False)
        with new_col:
            st.markdown('<div style="height:0.3rem"></div>', unsafe_allow_html=True)
            if st.button("🔄 새롭게 하기", use_container_width=True, key=pick_button_key):
                st.session_state[session_key] = fetch_fn()
                st.rerun()
        st.caption(
            "💡 ChatGPT 입력창 내용이 짧으면 **붙여넣기**(길게 누르기) 하세요. "
            "문제를 다 풀었으면 **새롭게 하기**로 다른 표현을 뽑으세요."
        )
        with st.expander("🔎 프롬프트 미리보기"):
            st.code(prompt, language="text")


def keywords_from_records(records: list) -> str:
    """여러 학습 기록에서 키워드를 모아 하나의 문자열로 만든다."""
    parts = []
    seen = set()
    for rec in records:
        for piece in (rec.get("keywords") or "").split(","):
            word = piece.strip()
            if word and word.lower() not in seen:
                seen.add(word.lower())
                parts.append(word)
    return ", ".join(parts)


def _keyword_list(keywords_str: str) -> list:
    return [p.strip() for p in (keywords_str or "").split(",") if p.strip()]


def build_mixed_random_quiz(records: list) -> Optional[dict]:
    """
    여러 학습 기록(날짜)에서 각각 1~2개 표현을 무작위로 골라 퀴즈 세트를 만든다.
    """
    pool = [r for r in records if _keyword_list(r.get("keywords", ""))]
    if not pool:
        return None

    random.shuffle(pool)
    picked = []
    seen = set()

    for rec in pool:
        if len(picked) >= MIXED_QUIZ_TARGET:
            break
        kws = _keyword_list(rec["keywords"])
        random.shuffle(kws)
        take_n = random.randint(1, min(MIXED_QUIZ_MAX_PER_RECORD, len(kws)))
        date_label = str(rec.get("created_at", ""))[:10]

        for kw in kws[:take_n]:
            if len(picked) >= MIXED_QUIZ_TARGET:
                break
            key = kw.lower()
            if key in seen:
                continue
            seen.add(key)
            picked.append({"date": date_label, "keyword": kw})

    if not picked:
        return None

    return {
        "items": picked,
        "keywords": ", ".join(p["keyword"] for p in picked),
    }


def fetch_mixed_recent_quiz(days: int = RECENT_REVIEW_DAYS):
    """최근 days 일 기록에서 여러 날짜의 표현을 골고루 무작위 선택."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    records = [
        r
        for r in storage.fetch_all_records()
        if str(r.get("created_at", ""))[:10] >= cutoff
    ]
    return build_mixed_random_quiz(records)


def fetch_mixed_all_quiz():
    """전체 기록에서 여러 날짜의 표현을 골고루 무작위 선택."""
    return build_mixed_random_quiz(storage.fetch_all_records())


def fetch_today_records():
    """오늘 저장한 학습 기록."""
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        r
        for r in storage.fetch_all_records()
        if str(r.get("created_at", "")).startswith(today)
    ]

# -----------------------------------------------------------------------------
# UI 헬퍼
# -----------------------------------------------------------------------------
def join_keywords(keyword_slots: list) -> str:
    """입력 칸 목록에서 비어 있지 않은 키워드만 쉼표로 이어 붙인다."""
    return ", ".join(k.strip() for k in keyword_slots if k and str(k).strip())


def split_keywords(keywords: str) -> list:
    """저장된 키워드 문자열을 최대 10칸 목록으로 나눈다."""
    parts = [p.strip() for p in (keywords or "").split(",") if p.strip()]
    return parts + [""] * (MAX_KEYWORDS - len(parts))


def _keyword_values_from_state(key_prefix: str, initial_values: list = None) -> list:
    """세션 상태(또는 초기값)에서 숙어 칸 값을 읽는다."""
    vals = []
    for i in range(MAX_KEYWORDS):
        k = f"{key_prefix}_{i}"
        if k in st.session_state:
            vals.append(st.session_state.get(k) or "")
        elif initial_values and i < len(initial_values):
            vals.append(initial_values[i] or "")
        else:
            vals.append("")
    return vals


def _visible_keyword_count(vals: list) -> int:
    """입력된 칸 다음 칸까지 보여 준다. (최소 1칸, 최대 10칸)"""
    visible = 1
    for i in range(MAX_KEYWORDS):
        if str(vals[i]).strip():
            visible = min(i + 2, MAX_KEYWORDS)
        else:
            break
    return visible


def _reveal_next_keyword_slot(key_prefix: str, index: int):
    """마지막 보이는 칸에 내용이 들어가면 다음 칸을 보이게 한다."""
    key = f"{key_prefix}_{index}"
    if str(st.session_state.get(key, "")).strip():
        st.rerun()


def render_keyword_inputs(key_prefix: str, initial_values: list = None) -> list:
    """핵심 숙어/단어 — 입력할 때마다 다음 칸이 나타난다 (최대 10개)."""
    vals = _keyword_values_from_state(key_prefix, initial_values)
    visible = _visible_keyword_count(vals)

    st.markdown('<div class="kw-panel-marker"></div>', unsafe_allow_html=True)
    st.caption("외우고 싶은 핵심 숙어/단어 (한 칸에 하나 · 입력하면 다음 칸이 나타남)")

    for i in range(visible):
        key = f"{key_prefix}_{i}"
        kwargs = {
            "label": f"{i + 1}",
            "placeholder": f"숙어/단어 {i + 1}",
            "key": key,
        }
        if key not in st.session_state and initial_values and i < len(initial_values):
            kwargs["value"] = initial_values[i]
        if i == visible - 1 and visible < MAX_KEYWORDS:
            kwargs["on_change"] = lambda idx=i, p=key_prefix: _reveal_next_keyword_slot(p, idx)

        st.text_input(**kwargs)

    inject_keyword_enter_navigation()
    return _keyword_values_from_state(key_prefix, initial_values)


def inject_keyword_enter_navigation():
    """숙어 입력 칸에서 Enter 를 누르면 다음 칸으로 포커스를 옮긴다."""
    components.html(
        """
        <script>
        (function () {
            const doc = window.parent.document;
            const attach = () => {
                const inputs = [...doc.querySelectorAll('section.main input[type="text"]')]
                    .filter((el) => (el.placeholder || "").includes("숙어/단어"));
                inputs.forEach((inp, idx) => {
                    if (inp.dataset.kwNav) return;
                    inp.dataset.kwNav = "1";
                    inp.addEventListener("keydown", (e) => {
                        if (e.key === "Enter") {
                            e.preventDefault();
                            if (inp.value.trim() && idx + 1 < inputs.length) {
                                inputs[idx + 1].focus();
                            }
                        }
                    });
                });
            };
            attach();
            setTimeout(attach, 400);
            setTimeout(attach, 1200);
        })();
        </script>
        """,
        height=0,
    )


def show_large_upload_image(image_bytes: bytes, file_name: str):
    """업로드 직후 교재 사진을 크게 보여준다."""
    valid, reason = storage.validate_image_bytes(image_bytes)
    if not valid:
        st.warning("이미지를 표시할 수 없습니다")
        return

    ext = os.path.splitext(file_name)[1].lower()
    if ext in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/png"
    b64 = base64.b64encode(image_bytes).decode()
    st.markdown(
        f'<div class="upload-preview"><img src="data:{mime};base64,{b64}" alt="업로드한 교재 사진" /></div>',
        unsafe_allow_html=True,
    )


def show_large_detail_image(image_path: str) -> str:
    """상세/수정 화면용 — 교재 사진을 크게 보여준다. 표시용 URL/경로를 반환."""
    reader = getattr(storage, "read_display_image_bytes", None)
    image_bytes = None
    if callable(reader):
        try:
            image_bytes = reader(image_path)
        except Exception:
            image_bytes = None

    if image_bytes is not None:
        file_name = os.path.basename(image_path) or "image.jpg"
        show_large_upload_image(image_bytes, file_name)
    else:
        src = storage.resolve_image_src(image_path)
        if src:
            try:
                st.image(src, use_container_width=True)
            except Exception:
                st.warning("이미지를 표시할 수 없습니다")
                return ""
        else:
            st.warning("이미지를 표시할 수 없습니다")
            return ""

    src = storage.resolve_image_src(image_path)
    if src and src.startswith(("http://", "https://")):
        return src
    if src and os.path.exists(src):
        return src
    return ""


def link_button(label: str, url: str):
    """새 창으로 열리는 링크 버튼 (구버전 Streamlit이면 HTML로 대체)."""
    if hasattr(st, "link_button"):
        st.link_button(label, url, use_container_width=True)
    else:
        st.markdown(
            f"""
            <a href="{url}" target="_blank" style="text-decoration:none;">
                <div style="background-color:#10a37f; color:white; padding:0.6rem 1rem;
                    border-radius:0.5rem; text-align:center; font-weight:600; margin:0.3rem 0;">
                    {label}
                </div>
            </a>
            """,
            unsafe_allow_html=True,
        )


def show_image(image_path: str, **kwargs):
    """로컬 경로 또는 Supabase Signed URL 이미지를 검증한 뒤 표시한다."""
    if not (image_path or "").strip():
        return

    reader = getattr(storage, "read_display_image_bytes", None)
    if callable(reader):
        try:
            image_bytes = reader(image_path)
        except Exception:
            image_bytes = None
        if image_bytes is None:
            st.warning("이미지를 표시할 수 없습니다")
            return
        try:
            st.image(io.BytesIO(image_bytes), **kwargs)
        except Exception:
            st.warning("이미지를 표시할 수 없습니다")
        return

    src = storage.resolve_image_src(image_path)
    if not src:
        st.warning("이미지를 표시할 수 없습니다")
        return
    try:
        st.image(src, **kwargs)
    except Exception:
        st.warning("이미지를 표시할 수 없습니다")


def show_record_thumbnail(image_path: str, **kwargs):
    """누적 기록 목록용 썸네일 — 깨진 이미지가 있어도 나머지 기록은 계속 표시."""
    if not (image_path or "").strip():
        st.markdown(
            '<div class="record-no-image">📝 사진 없음</div>',
            unsafe_allow_html=True,
        )
        return
    show_image(image_path, **kwargs)


# -----------------------------------------------------------------------------
# 학습 기록 상세보기 + 수정 (전체 화면 팝업)
# -----------------------------------------------------------------------------
def render_detail(rec: dict):
    """선택한 학습 기록 — 좌(큰 사진) / 우(숙어 입력) 2열 구성."""
    rid = rec["id"]

    img_col, kw_col = st.columns([5, 2], gap="small")

    with img_col:
        if (rec.get("image_path") or "").strip():
            src = show_large_detail_image(rec["image_path"])
            if src and (src.startswith("http://") or src.startswith("https://")):
                link_button("🔍 사진 원본 크게 보기 (새 창에서 확대)", src)
        else:
            st.markdown(
                '<div class="record-no-image">📝 사진 없음</div>',
                unsafe_allow_html=True,
            )
        st.caption(f"📅 저장일: {rec['created_at']}")

    with kw_col:
        st.markdown('<div class="kw-sticky-marker"></div>', unsafe_allow_html=True)
        new_kw_slots = render_keyword_inputs(
            f"edit_kw_{rid}", split_keywords(rec["keywords"])
        )
        new_keywords = join_keywords(new_kw_slots)

    replace = st.file_uploader(
        "사진 교체 (선택 사항 — 새 사진을 올리면 교체됩니다)",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"edit_img_{rid}",
    )
    link_button(
        "🔁 이 기록으로 빈칸 퀴즈 풀기",
        build_chatgpt_url(
            make_quiz_prompt(new_keywords or rec["keywords"], rec["created_at"])
        ),
    )

    st.divider()
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("💾 수정 저장", use_container_width=True, key=f"save_edit_{rid}"):
            if not new_keywords.strip():
                st.warning("키워드를 입력해 주세요.")
            else:
                try:
                    if replace is not None:
                        fb, fn = prepare_upload_image(
                            replace.getbuffer().tobytes(), replace.name
                        )
                        storage.update_study(rid, new_keywords.strip(), fn, fb)
                    else:
                        storage.update_study(rid, new_keywords.strip())
                    st.session_state["detail_id"] = None
                    st.session_state["flash"] = "저장되었습니다."
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"수정 중 오류가 발생했어요: {e}")

    with c2:
        if st.button("🗑️ 삭제", use_container_width=True, key=f"del_{rid}"):
            st.session_state[f"confirm_del_{rid}"] = True

    with c3:
        if st.button("닫기", use_container_width=True, key=f"close_{rid}"):
            st.session_state["detail_id"] = None
            st.rerun()

    if st.session_state.get(f"confirm_del_{rid}"):
        st.warning("정말 삭제할까요? 되돌릴 수 없습니다.")
        d1, d2 = st.columns(2)
        with d1:
            if st.button("예, 삭제합니다", use_container_width=True, key=f"del_yes_{rid}"):
                try:
                    storage.delete_study(rid)
                    st.session_state[f"confirm_del_{rid}"] = False
                    st.session_state["detail_id"] = None
                    st.session_state["flash"] = "기록을 삭제했어요."
                    st.rerun()
                except Exception as e:
                    st.error(f"삭제 중 오류가 발생했어요: {e}")
        with d2:
            if st.button("아니요", use_container_width=True, key=f"del_no_{rid}"):
                st.session_state[f"confirm_del_{rid}"] = False
                st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("📖 학습 기록 상세 / 수정", width="large")
    def open_detail(rec: dict):
        render_detail(rec)
else:
    def open_detail(rec: dict):
        with st.container(border=True):
            render_detail(rec)


# -----------------------------------------------------------------------------
# 앱 비밀번호 잠금 (secrets [auth] password)
# -----------------------------------------------------------------------------
def auth_password() -> str:
    """secrets [auth] password 가 있으면 반환. 없으면 빈 문자열(잠금 해제)."""
    try:
        cfg = st.secrets.get("auth", None)
        if not cfg:
            return ""
        return str(cfg.get("password", "") or "").strip()
    except Exception:
        return ""


def auth_enabled() -> bool:
    """앱 비밀번호 잠금이 켜져 있는지."""
    return bool(auth_password())


def require_auth() -> bool:
    """비밀번호가 설정되어 있으면 로그인 화면을 보여준다. 통과 시 True."""
    if not auth_enabled():
        return True
    if st.session_state.get("authenticated"):
        return True

    st.title("🔒 로그인")
    st.caption("이 앱은 비밀번호로 보호되어 있습니다. 본인만 접속할 수 있어요.")
    entered = st.text_input("비밀번호", type="password", key="login_password")
    if st.button("입장", use_container_width=True, type="primary"):
        if entered == auth_password():
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


def render_logout_control():
    """우측 상단 작은 잠금 메뉴 — 필요할 때만 로그아웃."""
    if not auth_enabled():
        return
    _, action_col = st.columns([11, 1])
    with action_col:
        if hasattr(st, "popover"):
            with st.popover("🔒", help="계정"):
                if st.button("로그아웃", key="logout_btn", use_container_width=True):
                    st.session_state["authenticated"] = False
                    st.rerun()
        elif st.button("로그아웃", key="logout_btn_compact", help="로그아웃"):
            st.session_state["authenticated"] = False
            st.rerun()


def render_storage_footer():
    """화면 하단에 저장 방식을 표시한다."""
    info = storage.get_storage_info()
    with st.expander("🗄️ 저장 위치", expanded=False):
        st.markdown(f"**{info['label']}**")
        if info["mode"] == "local":
            st.code(
                f"DB: {info['db_path']}\n이미지: {info['image_dir']}/",
                language="text",
            )


# -----------------------------------------------------------------------------
# 화면 구성
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="AI 시각 연상 영어 회화 보조 프로그램",
        page_icon="🗣️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    storage.init_storage()

    if not require_auth():
        return

    render_logout_control()

    st.session_state.setdefault("form_round", 0)   # 저장 후 입력칸 초기화용
    st.session_state.setdefault("detail_id", None)  # 상세보기 중인 기록 id
    st.session_state.setdefault("flash", None)      # 한 번 보여줄 안내 메시지

    st.title("🗣️ AI 시각 연상 영어 회화 보조 프로그램")
    st.caption(
        "교재 사진과 키워드를 저장하고, 무료 ChatGPT 웹사이트와 연동해 실전 회화·복습을 이어가세요. "
        "(API Key 불필요 · 딥링크 방식)"
    )
    st.caption(f"🗄️ 현재 저장 방식: **{storage.backend_name()}**")

    if st.session_state.get("flash"):
        st.success(st.session_state["flash"])
        st.session_state["flash"] = None

    # 사진 옆 키워드 입력 패널을, 사진을 스크롤해도 화면에 계속 붙어 있도록(sticky) 만든다.
    # (사진/입력 두 열 중 '입력 열'만 골라서 고정. 화면이 좁은 휴대폰 세로 모드에서는 적용 안 함.)
    st.markdown(
        """
        <style>
        @media (min-width: 768px) {
          div[data-testid="stHorizontalBlock"]:has(.kw-sticky-marker):not(:has(div[data-testid="stHorizontalBlock"] .kw-sticky-marker)) > div[data-testid="stColumn"]:last-child,
          div[data-testid="stHorizontalBlock"]:has(.kw-sticky-marker):not(:has(div[data-testid="stHorizontalBlock"] .kw-sticky-marker)) > div[data-testid="column"]:last-child {
              position: sticky;
              top: 4rem;
              align-self: flex-start;
              z-index: 1;
          }
        }
        .kw-sticky-marker { display: none; }
        /* 업로드·상세 사진 — 왼쪽을 크게 */
        .upload-preview img,
        .detail-preview img {
            max-height: 78vh;
            width: 100%;
            object-fit: contain;
            display: block;
            margin: 0 auto;
            border-radius: 8px;
        }
        /* 숙어 입력 칸 — 파란 테두리 */
        div[data-testid="stVerticalBlock"]:has(.kw-panel-marker) input[type="text"] {
            border: 2px solid #2563eb !important;
            background-color: #f8fafc !important;
            border-radius: 6px !important;
        }
        div[data-testid="stVerticalBlock"]:has(.kw-panel-marker) label[data-testid="stWidgetLabel"] p {
            font-weight: 700;
            color: #2563eb;
            min-width: 1.2rem;
        }
        /* 우측 상단 잠금(로그아웃) 버튼 — 작게 */
        div[data-testid="stPopover"] > button {
            min-height: 2rem;
            padding: 0.2rem 0.55rem;
            font-size: 0.95rem;
        }
        /* iPad / 터치 — 업로드·저장 버튼 크게 */
        div[data-testid="stFileUploader"] button,
        div[data-testid="stFileUploader"] section button {
            min-height: 3rem !important;
            font-size: 1.05rem !important;
            padding: 0.65rem 1rem !important;
        }
        .stButton > button {
            min-height: 2.75rem !important;
            font-size: 1rem !important;
        }
        .stButton > button[kind="primary"] {
            min-height: 3.1rem !important;
            font-size: 1.08rem !important;
            font-weight: 700 !important;
        }
        div[data-testid="stVerticalBlock"]:has(.kw-panel-marker) input[type="text"] {
            font-size: 1.1rem !important;
            min-height: 2.85rem !important;
            padding: 0.55rem 0.8rem !important;
        }
        .record-no-image {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 8rem;
            border: 2px dashed #cbd5e1;
            border-radius: 8px;
            background: #f8fafc;
            color: #64748b;
            font-size: 1rem;
            font-weight: 600;
            text-align: center;
            padding: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    left, right = st.columns([2, 1], gap="large")

    # =========================================================================
    # [좌측] 기능 1 & 2 : 사진 + 키워드 → ChatGPT 롤플레잉
    # =========================================================================
    with left:
        st.subheader("📷 오늘의 학습 등록 & 실전 연습")

        # 저장할 때마다 form_round가 1씩 늘어나며, 위젯 key가 바뀌어 입력칸이 깨끗하게 초기화됩니다.
        rnd = st.session_state["form_round"]
        uploaded = st.file_uploader(
            "교재 사진 업로드 (선택 — JPG/PNG/WEBP)",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"uploader_{rnd}",
        )

        fixed_bytes, fixed_name = (None, None)
        upload_error = None
        if uploaded is not None:
            try:
                fixed_bytes, fixed_name = prepare_upload_image(
                    uploaded.getbuffer().tobytes(), uploaded.name
                )
            except ValueError as exc:
                upload_error = str(exc)
                fixed_bytes, fixed_name = None, None

        def write_pane():
            """키워드 입력 + 저장/연습 버튼 묶음. (사진 옆 고정 패널로도, 단독으로도 사용)"""
            if upload_error:
                st.error(upload_error)

            kw_slots = render_keyword_inputs(f"kw_{rnd}")
            kw = join_keywords(kw_slots)
            if st.button(
                "💾 학습 기록 저장하기",
                use_container_width=True,
                key=f"save_{rnd}",
                type="primary",
            ):
                if not kw:
                    st.warning("핵심 키워드를 최소 1개 이상 입력해 주세요.")
                elif uploaded is not None and upload_error:
                    st.error(upload_error)
                else:
                    try:
                        if uploaded is not None and fixed_bytes is not None:
                            storage.save_study(kw, fixed_name, fixed_bytes)
                        else:
                            storage.save_study(kw)
                        st.session_state["form_round"] += 1
                        st.session_state["flash"] = "저장되었습니다."
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"저장 실패: {e}")

            if kw:
                link_button(
                    "💬 ChatGPT와 실전 연습하기",
                    build_chatgpt_url(make_roleplay_prompt(kw)),
                )
                link_button(
                    "📝 지금 입력한 단어로 빈칸 퀴즈",
                    build_chatgpt_url(make_quiz_prompt(kw)),
                )
            else:
                st.button(
                    "💬 ChatGPT와 실전 연습하기",
                    use_container_width=True,
                    disabled=True,
                    help="먼저 키워드를 입력하세요.",
                    key=f"practice_disabled_{rnd}",
                )

            with st.expander("🔎 ChatGPT에게 전달될 프롬프트 미리보기"):
                preview_kw = kw if kw else "{입력한 키워드}"
                st.code(make_roleplay_prompt(preview_kw), language="text")
            return kw

        if uploaded is not None and not upload_error:
            # 사진(왼쪽 넓게) + 숙어 입력(오른쪽 좁게)
            pcol, wcol = st.columns([5, 2], gap="small")
            with pcol:
                show_large_upload_image(fixed_bytes, fixed_name)
            with wcol:
                st.markdown('<div class="kw-sticky-marker"></div>', unsafe_allow_html=True)
                write_pane()
        else:
            write_pane()

        st.divider()

        st.subheader("📚 그동안 누적된 학습 기록")
        st.caption("사진을 누르면 크게 보면서 키워드·사진을 수정하거나 삭제할 수 있어요.")
        try:
            records = storage.fetch_all_records()
        except Exception as e:
            records = []
            st.error(f"기록을 불러오는 중 오류가 발생했어요: {e}")

        if not records:
            st.info("아직 저장된 학습 기록이 없습니다. 위에서 첫 기록을 등록해 보세요!")
        else:
            st.write(f"총 **{len(records)}건**의 기록이 저장되어 있습니다.")
            cols_per_row = 3
            for i in range(0, len(records), cols_per_row):
                row = records[i : i + cols_per_row]
                cols = st.columns(cols_per_row)
                for col, rec in zip(cols, row):
                    with col:
                        try:
                            show_record_thumbnail(rec["image_path"], use_container_width=True)
                        except Exception:
                            st.markdown(
                                '<div class="record-no-image">📝 사진 표시 오류</div>',
                                unsafe_allow_html=True,
                            )
                        short_kw = rec["keywords"]
                        if len(short_kw) > 16:
                            short_kw = short_kw[:16] + "…"
                        if st.button(
                            f"📝 {short_kw}",
                            use_container_width=True,
                            key=f"open_{rec['id']}",
                            help=f"{rec['created_at']} · {rec['keywords']}",
                        ):
                            st.session_state["detail_id"] = rec["id"]
                            st.rerun()

            # 선택된 기록이 있으면 상세보기/수정 팝업을 띄운다.
            if st.session_state.get("detail_id") is not None:
                selected = next(
                    (r for r in records if r["id"] == st.session_state["detail_id"]), None
                )
                if selected is not None:
                    open_detail(selected)
                else:
                    st.session_state["detail_id"] = None

    # =========================================================================
    # [우측] 빈칸 넣기 퀴즈 (ChatGPT)
    # =========================================================================
    with right:
        st.subheader("📝 빈칸 넣기 퀴즈")
        st.caption("ChatGPT가 공부한 표현으로 빈칸 문장 퀴즈를 냅니다.")

        st.markdown("**① 오늘 배운 표현**")
        try:
            today_records = fetch_today_records()
        except Exception:
            today_records = []

        if not today_records:
            st.info("오늘 저장한 학습이 없어요. 왼쪽에서 사진과 키워드를 저장해 보세요.")
        else:
            today_kw = keywords_from_records(today_records)
            st.markdown(f"**오늘 키워드:** `{today_kw}`")
            st.caption(f"오늘 저장 {len(today_records)}건")
            link_button(
                "📝 오늘 배운 단어로 빈칸 퀴즈",
                build_chatgpt_url(make_quiz_prompt(today_kw)),
            )
            with st.expander("🔎 프롬프트 미리보기"):
                st.code(make_quiz_prompt(today_kw), language="text")

        st.divider()

        render_random_quiz_block(
            title="**② 최근 2주 복습**",
            caption="최근 2주 기록에서 여러 날짜에 걸쳐 표현을 1~2개씩 무작위로 뽑습니다.",
            session_key="quiz_record_recent",
            fetch_fn=fetch_mixed_recent_quiz,
            pick_button_key="pick_recent_quiz",
            quiz_button_label="🧠 최근 2주 빈칸 퀴즈 풀기",
            empty_message=(
                "최근 2주 안에 저장한 학습 기록이 없습니다.\n\n"
                "왼쪽에서 학습을 등록하면 이곳에서 복습 퀴즈를 풀 수 있어요!"
            ),
            recent_only=True,
        )

        st.divider()

        render_random_quiz_block(
            title="**③ 전체 무작위 복습**",
            caption="전체 기록에서 여러 날짜에 걸쳐 표현을 1~2개씩 무작위로 뽑습니다.",
            session_key="quiz_record_all",
            fetch_fn=fetch_mixed_all_quiz,
            pick_button_key="pick_all_quiz",
            quiz_button_label="🧠 전체 무작위 빈칸 퀴즈 풀기",
            empty_message="아직 저장된 학습 기록이 없습니다. 왼쪽에서 첫 기록을 등록해 보세요!",
            recent_only=False,
        )

    st.divider()
    render_storage_footer()
    st.caption(
        "💡 사용 팁: 버튼을 누르면 새 창에서 ChatGPT 웹사이트가 열리고, "
        "준비된 질문이 입력창에 자동으로 채워집니다. (로그인 후 전송 버튼만 누르면 대화 시작!)"
    )


if __name__ == "__main__":
    main()
