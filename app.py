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

import io
import os
import urllib.parse

import streamlit as st
from PIL import Image, ImageOps

import storage  # 저장 백엔드 (로컬 SQLite / 클라우드 Supabase 자동 전환)

CHATGPT_BASE_URL = "https://chatgpt.com/"  # 무료 ChatGPT 웹사이트


def correct_orientation(file_bytes: bytes, file_name: str):
    """
    아이폰/아이패드 사진의 회전 정보(EXIF)를 실제 픽셀에 적용해 바로 세운다.
    보정된 (이미지 바이트, 저장용 파일명)을 반환한다.
    문제가 생기면 원본을 그대로 돌려준다.
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)  # EXIF 방향 정보를 픽셀에 반영

        ext = os.path.splitext(file_name)[1].lower()
        if ext in (".jpg", ".jpeg"):
            fmt, out_ext = "JPEG", ".jpg"
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
        elif ext == ".webp":
            fmt, out_ext = "WEBP", ".webp"
        else:
            fmt, out_ext = "PNG", ".png"

        buf = io.BytesIO()
        img.save(buf, format=fmt)
        base = os.path.splitext(file_name)[0]
        return buf.getvalue(), f"{base}{out_ext}"
    except Exception:
        return file_bytes, file_name


# -----------------------------------------------------------------------------
# ChatGPT 딥링크 / 프롬프트
# -----------------------------------------------------------------------------
def build_chatgpt_url(prompt_text: str) -> str:
    """프롬프트를 URL 인코딩하여 ChatGPT 입력창에 자동으로 채워지는 링크를 만든다."""
    return f"{CHATGPT_BASE_URL}?q={urllib.parse.quote(prompt_text)}"


def make_roleplay_prompt(keywords: str) -> str:
    """[기능 1 & 2] 롤플레잉 + 힌트 유도용 프롬프트"""
    return (
        f"안녕! 내가 방금 영어 교재에서 '{keywords}'라는 표현들을 공부했어. "
        "지금부터 이 표현들을 자연스럽게 사용할 수 있도록 나랑 가상의 롤플레잉 대화를 시작해줘. "
        "먼저 나에게 상황을 영어로 제시하면서 질문을 던져줘. "
        "내가 답변하면 내 문장도 교정해줘."
    )


def make_quiz_prompt(keywords: str) -> str:
    """[기능 3] 망각 곡선 기반 복습 퀴즈용 프롬프트"""
    return (
        f"안녕! 내가 일주일 전에 공부했던 사진의 키워드가 '{keywords}'였어. "
        "이 표현들을 내가 기억하고 있는지 테스트할 수 있도록 "
        "나에게 영어 기습 질문을 하나 던져줘."
    )


# -----------------------------------------------------------------------------
# UI 헬퍼
# -----------------------------------------------------------------------------
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


def show_image(src: str, **kwargs):
    """로컬 경로(파일 존재 확인 후) 또는 공개 URL 이미지를 표시한다."""
    if not src:
        st.warning("이미지 정보가 없습니다.")
        return
    if src.startswith("http://") or src.startswith("https://"):
        st.image(src, **kwargs)
    elif os.path.exists(src):
        st.image(src, **kwargs)
    else:
        st.warning("이미지 파일을 찾을 수 없습니다. (파일이 이동/삭제되었을 수 있어요)")


# -----------------------------------------------------------------------------
# 학습 기록 상세보기 + 수정 (전체 화면 팝업)
# -----------------------------------------------------------------------------
def render_detail(rec: dict):
    """선택한 학습 기록을 등록 화면과 같은 좌(사진)/우(수정) 구성으로 보여준다."""
    rid = rec["id"]

    # 사진은 왼쪽에 적당한 크기로, 수정 입력은 오른쪽에 (처음 등록 화면과 동일한 느낌)
    pcol, ecol = st.columns([2, 3], gap="medium")
    with pcol:
        show_image(rec["image_src"], use_container_width=True)
        st.caption(f"📅 저장일: {rec['created_at']}")
    with ecol:
        new_keywords = st.text_input(
            "핵심 키워드 (수정 가능)",
            value=rec["keywords"],
            key=f"edit_kw_{rid}",
        )
        replace = st.file_uploader(
            "사진 교체 (선택 사항 — 새 사진을 올리면 교체됩니다)",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"edit_img_{rid}",
        )
        link_button(
            "🔁 이 기록으로 ChatGPT 복습하기",
            build_chatgpt_url(make_quiz_prompt(new_keywords or rec["keywords"])),
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
                        fb, fn = correct_orientation(replace.getbuffer().tobytes(), replace.name)
                        storage.update_study(rid, new_keywords.strip(), fn, fb)
                    else:
                        storage.update_study(rid, new_keywords.strip())
                    st.session_state["detail_id"] = None
                    st.session_state["flash"] = "수정 내용을 저장했어요."
                    st.rerun()
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
# 화면 구성
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="AI 시각 연상 영어 회화 보조 프로그램",
        page_icon="🗣️",
        layout="wide",
    )

    storage.init_storage()

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
            "교재 사진을 업로드하세요 (촬영 또는 사진 보관함에서 선택)",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"uploader_{rnd}",
        )

        fixed_bytes, fixed_name = (None, None)
        if uploaded is not None:
            fixed_bytes, fixed_name = correct_orientation(
                uploaded.getbuffer().tobytes(), uploaded.name
            )

        def write_pane():
            """키워드 입력 + 저장/연습 버튼 묶음. (사진 옆 고정 패널로도, 단독으로도 사용)"""
            kw = st.text_input(
                "외우고 싶은 핵심 숙어/단어 키워드 (2~3개, 쉼표로 구분)",
                placeholder="예) hang out, on second thought, by the way",
                key=f"keywords_{rnd}",
            )
            if st.button("💾 학습 기록 저장하기", use_container_width=True, key=f"save_{rnd}"):
                if uploaded is None:
                    st.warning("먼저 교재 사진을 업로드해 주세요.")
                elif not kw.strip():
                    st.warning("핵심 키워드를 입력해 주세요.")
                else:
                    try:
                        storage.save_study(kw.strip(), fixed_name, fixed_bytes)
                        # 입력칸을 비우고 다음 학습을 바로 등록할 수 있도록 새 폼으로 전환
                        st.session_state["form_round"] += 1
                        st.session_state["flash"] = (
                            f"저장 완료! ‘{kw.strip()}’ — 이어서 다음 학습을 등록하세요."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 중 오류가 발생했어요: {e}")

            if kw.strip():
                link_button(
                    "💬 ChatGPT와 실전 연습하기",
                    build_chatgpt_url(make_roleplay_prompt(kw.strip())),
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
                preview_kw = kw.strip() if kw.strip() else "{입력한 키워드}"
                st.code(make_roleplay_prompt(preview_kw), language="text")
            return kw

        if uploaded is not None:
            # 사진(왼쪽 큰 화면) + 키워드 입력(오른쪽 고정 패널)
            pcol, wcol = st.columns([3, 2], gap="medium")
            with pcol:
                st.image(fixed_bytes, caption="업로드한 교재 사진", use_container_width=True)
            with wcol:
                # 이 마커가 있는 열을 CSS가 sticky(화면 고정)로 만들어 줍니다.
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
                        show_image(rec["image_src"], use_container_width=True)
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
    # [우측] 기능 3 : 망각 곡선 기반 랜덤 복습 퀴즈
    # =========================================================================
    with right:
        st.subheader("⚡ 오늘의 기습 복습 퀴즈")
        st.caption("저장된 지 일주일 이상 지난 과거의 사진을 무작위로 꺼내옵니다.")

        if st.button("🎲 복습 퀴즈 새로 뽑기", use_container_width=True):
            st.session_state["quiz_record"] = storage.fetch_review_record(min_days=7)

        if "quiz_record" not in st.session_state:
            try:
                st.session_state["quiz_record"] = storage.fetch_review_record(min_days=7)
            except Exception:
                st.session_state["quiz_record"] = None

        quiz = st.session_state.get("quiz_record")

        if quiz is None:
            st.info(
                "아직 복습할 과거 기록이 없습니다.\n\n"
                "왼쪽에서 학습을 등록하고 일주일이 지나면 "
                "이곳에 기습 복습 퀴즈가 나타납니다!"
            )
        else:
            show_image(quiz["image_src"], use_container_width=True)
            st.markdown(f"**📅 공부했던 날:** {quiz['created_at']}")
            st.markdown(f"**🔑 그때의 키워드:** `{quiz['keywords']}`")
            link_button(
                "🧠 이 사진으로 ChatGPT와 복습 퀴즈 풀기",
                build_chatgpt_url(make_quiz_prompt(quiz["keywords"])),
            )
            with st.expander("🔎 복습 프롬프트 미리보기"):
                st.code(make_quiz_prompt(quiz["keywords"]), language="text")

    st.divider()
    st.caption(
        "💡 사용 팁: 버튼을 누르면 새 창에서 ChatGPT 웹사이트가 열리고, "
        "준비된 질문이 입력창에 자동으로 채워집니다. (로그인 후 전송 버튼만 누르면 대화 시작!)"
    )


if __name__ == "__main__":
    main()
