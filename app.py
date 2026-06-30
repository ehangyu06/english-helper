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
# 화면 구성
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="AI 시각 연상 영어 회화 보조 프로그램",
        page_icon="🗣️",
        layout="wide",
    )

    storage.init_storage()

    st.title("🗣️ AI 시각 연상 영어 회화 보조 프로그램")
    st.caption(
        "교재 사진과 키워드를 저장하고, 무료 ChatGPT 웹사이트와 연동해 실전 회화·복습을 이어가세요. "
        "(API Key 불필요 · 딥링크 방식)"
    )
    st.caption(f"🗄️ 현재 저장 방식: **{storage.backend_name()}**")
    st.divider()

    left, right = st.columns([2, 1], gap="large")

    # =========================================================================
    # [좌측] 기능 1 & 2 : 사진 + 키워드 → ChatGPT 롤플레잉
    # =========================================================================
    with left:
        st.subheader("📷 오늘의 학습 등록 & 실전 연습")

        uploaded = st.file_uploader(
            "교재 사진을 업로드하세요 (촬영 또는 사진 보관함에서 선택)",
            type=["jpg", "jpeg", "png", "webp"],
        )
        keywords = st.text_input(
            "외우고 싶은 핵심 숙어/단어 키워드 (2~3개, 쉼표로 구분)",
            placeholder="예) hang out, on second thought, by the way",
        )

        fixed_bytes, fixed_name = (None, None)
        if uploaded is not None:
            fixed_bytes, fixed_name = correct_orientation(
                uploaded.getbuffer().tobytes(), uploaded.name
            )
            st.image(fixed_bytes, caption="업로드한 교재 사진 미리보기", use_container_width=True)

        col_save, col_practice = st.columns(2)

        with col_save:
            if st.button("💾 학습 기록 저장하기", use_container_width=True):
                if uploaded is None:
                    st.warning("먼저 교재 사진을 업로드해 주세요.")
                elif not keywords.strip():
                    st.warning("핵심 키워드를 입력해 주세요.")
                else:
                    try:
                        storage.save_study(keywords.strip(), fixed_name, fixed_bytes)
                        st.success(f"저장 완료! (키워드: {keywords.strip()})")
                    except Exception as e:
                        st.error(f"저장 중 오류가 발생했어요: {e}")

        with col_practice:
            if keywords.strip():
                link_button(
                    "💬 ChatGPT와 실전 연습하기",
                    build_chatgpt_url(make_roleplay_prompt(keywords.strip())),
                )
            else:
                st.button(
                    "💬 ChatGPT와 실전 연습하기",
                    use_container_width=True,
                    disabled=True,
                    help="먼저 키워드를 입력하세요.",
                )

        with st.expander("🔎 ChatGPT에게 전달될 프롬프트 미리보기"):
            preview_kw = keywords.strip() if keywords.strip() else "{입력한 키워드}"
            st.code(make_roleplay_prompt(preview_kw), language="text")

        st.divider()

        st.subheader("📚 그동안 누적된 학습 기록")
        try:
            records = storage.fetch_all_records()
        except Exception as e:
            records = []
            st.error(f"기록을 불러오는 중 오류가 발생했어요: {e}")

        if not records:
            st.info("아직 저장된 학습 기록이 없습니다. 위에서 첫 기록을 등록해 보세요!")
        else:
            st.write(f"총 **{len(records)}건**의 기록이 저장되어 있습니다.")
            for rec in records:
                with st.expander(f"🗓️ {rec['created_at']}  ·  {rec['keywords']}"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        show_image(rec["image_src"], use_container_width=True)
                    with c2:
                        st.write(f"**키워드:** {rec['keywords']}")
                        st.write(f"**저장일:** {rec['created_at']}")
                        link_button(
                            "🔁 이 기록으로 ChatGPT 복습하기",
                            build_chatgpt_url(make_quiz_prompt(rec["keywords"])),
                        )

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
