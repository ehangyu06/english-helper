# 🗣️ AI 시각 연상 영어 회화 보조 프로그램

영어를 **독학하는 학습자**를 위한 웹 기반 학습 도우미입니다.
교재 사진과 핵심 키워드를 저장해두고, **무료 ChatGPT 웹사이트**와 연동(딥링크)하여
실전 롤플레잉 회화와 복습 퀴즈를 이어갈 수 있습니다.

> 💸 **API Key가 필요 없습니다.** 버튼을 누르면 무료 ChatGPT 웹사이트로 이동하면서
> 질문(프롬프트)이 입력창에 자동으로 채워지는 **딥링크 방식**을 사용합니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| **① 사진 + 키워드 등록** | 교재 사진을 업로드하고 외우고 싶은 핵심 숙어/단어를 저장합니다. |
| **② 실전 롤플레잉 연습** | `ChatGPT와 실전 연습하기` 버튼 → 키워드 기반 롤플레잉 프롬프트가 담긴 ChatGPT 새 창이 열립니다. |
| **③ 망각 곡선 복습 퀴즈** | 저장된 지 **일주일 이상 지난** 과거 사진을 무작위로 꺼내 기습 복습 퀴즈를 제공합니다. |

---

## 🗄️ 저장 방식 (자동 전환)

이 앱은 두 가지 저장 방식을 자동으로 골라 씁니다.

- **로컬(SQLite)**: 비밀키가 없으면, 내 컴퓨터의 `study_log.db` + `saved_images/` 폴더에 저장. (테스트용)
- **클라우드(Supabase)**: 비밀키가 설정되면, 인터넷 DB와 저장소에 **영구 보존**. (아이패드/아이폰에서 써도 데이터 유지)

> 화면 상단에 현재 어떤 방식으로 저장 중인지 표시됩니다.

---

## 🚀 A. 내 컴퓨터에서 먼저 실행해 보기

```bash
pip install -r requirements.txt
streamlit run app.py
```

실행하면 브라우저가 자동으로 열립니다. (`http://localhost:8501`)
이 상태에서는 데이터가 내 컴퓨터에만 저장됩니다.

---

## 📱 B. 아이패드/아이폰에서 쓰기 (인터넷 배포)

휴대폰·태블릿에서 접속하고 사진을 업로드하려면 인터넷에 배포해야 합니다.
**무료**로 가능하며, 아래 3단계만 따라 하면 됩니다.

### 1단계 — Supabase 준비 (데이터 영구 저장소, 무료)

1. [supabase.com](https://supabase.com) 가입 → **New project** 생성 (지역은 가까운 곳, 비밀번호 메모).
2. 왼쪽 메뉴 **SQL Editor** → 아래 SQL을 붙여넣고 **Run** (기록 테이블 생성):

```sql
create table if not exists study_records (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  keywords    text not null,
  image_path  text not null
);
```

3. 왼쪽 메뉴 **Storage** → **New bucket** →
   - 이름: `study-images`
   - **Public bucket** 체크 ✅ (사진을 화면에 표시하려면 공개 필요)
   - **Create bucket**
4. 왼쪽 메뉴 **Project Settings → API** 에서 아래 2가지를 복사해 둡니다:
   - **Project URL** (예: `https://abcd1234.supabase.co`)
   - **service_role** 키 (`Project API keys` 항목의 `service_role` · `secret`)
     > ⚠️ service_role 키는 강력한 권한을 가집니다. 외부에 공개하지 마세요.
     > (Streamlit 비밀 설정에만 넣으며, 사용자 브라우저에는 노출되지 않습니다.)

### 2단계 — GitHub에 코드 올리기

1. [github.com](https://github.com) 가입 → **New repository** 생성 (예: `english-helper`, Public 또는 Private).
2. 이 폴더의 파일들을 업로드합니다. (웹에서 끌어다 놓기 또는 git 사용)

```bash
git init
git add .
git commit -m "AI 영어 회화 보조 프로그램"
git branch -M main
git remote add origin https://github.com/<내아이디>/english-helper.git
git push -u origin main
```

> `.gitignore` 덕분에 `secrets.toml`, `study_log.db`, `saved_images/` 는 올라가지 않습니다. (정상)

### 3단계 — Streamlit Community Cloud 배포 (무료)

1. [share.streamlit.io](https://share.streamlit.io) 에 **GitHub 계정으로 로그인**.
2. **Create app → Deploy a public app from GitHub** 선택.
3. 방금 만든 저장소 / 브랜치(`main`) / 메인 파일(`app.py`) 지정.
4. **Advanced settings → Secrets** 칸에 아래 내용을 붙여넣고 값을 채웁니다:

```toml
[supabase]
url = "https://여기에-프로젝트-주소.supabase.co"
key = "여기에-service_role-키-붙여넣기"
```

5. **Deploy!** → 1~2분 뒤 `https://...streamlit.app` 주소가 생깁니다.
6. 그 주소를 아이폰/아이패드 사파리에서 열고, **공유 → 홈 화면에 추가**하면 앱처럼 쓸 수 있어요. 📲

---

## 📂 폴더 구조

```
영어회화/
├── app.py                          # 메인 화면 (UI)
├── storage.py                      # 저장 백엔드 (로컬/Supabase 자동 전환)
├── requirements.txt                # 설치할 라이브러리
├── README.md                       # 사용 설명서 (이 파일)
├── .gitignore                      # GitHub에 안 올릴 파일 목록
├── .streamlit/
│   └── secrets.toml.example        # 비밀키 작성 예시 (복사해서 secrets.toml 로 사용)
├── study_log.db                    # (로컬 자동 생성) SQLite DB
└── saved_images/                   # (로컬 자동 생성) 업로드 이미지
```

---

## 💡 사용 팁
1. 왼쪽에서 교재 사진을 올리고 키워드(2~3개)를 입력한 뒤 **저장**하세요.
2. **`ChatGPT와 실전 연습하기`** 버튼 → 새 창에서 ChatGPT가 열리고 질문이 자동 입력됩니다.
3. 며칠 뒤 다시 접속하면 오른쪽 **`오늘의 기습 복습 퀴즈`** 에서 예전 학습을 다시 만나요!

## ❓ 자주 묻는 문제
- **사진이 안 보여요** → Supabase 버킷이 **Public** 인지 확인하세요.
- **저장이 안 돼요 / 권한 오류** → `service_role` 키를 넣었는지, 테이블 이름이 `study_records` 인지 확인하세요.
- **데이터가 사라졌어요** → 비밀키 없이(로컬 모드) 클라우드에 배포하면 데이터가 임시 저장되어 사라집니다. 반드시 Supabase 비밀키를 설정하세요.
