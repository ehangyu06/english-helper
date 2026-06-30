# 📱 배포 체크리스트 (아이패드/아이폰용)

아래 순서대로 체크하면서 진행하세요. **전부 무료**입니다.

---

## ✅ 1단계: Supabase (데이터 영구 저장)

### 1-1. 가입 & 프로젝트 생성
1. 브라우저에서 [https://supabase.com](https://supabase.com) 접속
2. **Start your project** → GitHub 또는 이메일로 가입
3. **New project** 클릭
4. 입력 예시:
   - **Name**: `english-helper` (아무 이름)
   - **Database Password**: 강한 비밀번호 (메모해 두세요)
   - **Region**: `Northeast Asia (Seoul)` 또는 가까운 지역
5. **Create new project** → 1~2분 대기

### 1-2. 테이블 만들기 (SQL)
1. 왼쪽 메뉴 **SQL Editor** 클릭
2. **New query** 클릭
3. 이 프로젝트의 `supabase/setup.sql` 파일 내용을 **전체 복사**해서 붙여넣기
4. 오른쪽 **Run** (또는 Ctrl+Enter)
5. 하단에 `Success` 나오면 OK

### 1-3. 사진 저장 버킷 만들기
1. 왼쪽 메뉴 **Storage** 클릭
2. **New bucket** 클릭
3. 설정:
   - **Name**: `study-images` (정확히 이 이름!)
   - **Public bucket**: **ON** (체크 필수 — 사진 화면 표시용)
4. **Create bucket**

### 1-4. API 키 복사 (나중에 Streamlit에 넣음)
1. 왼쪽 하단 **Project Settings** (톱니바퀴) 클릭
2. **API** 메뉴 클릭
3. 아래 두 값을 메모장에 복사:
   - **Project URL** → 예: `https://abcdefgh.supabase.co`
   - **service_role** (secret) → `eyJ...` 로 시작하는 긴 문자열
     - ⚠️ `anon` 키가 아니라 **`service_role`** 키입니다
     - ⚠️ 이 키는 절대 GitHub에 올리지 마세요

---

## ✅ 2단계: GitHub (코드 올리기)

### 2-1. 저장소 만들기
1. [https://github.com/new](https://github.com/new) 접속
2. **Repository name**: `english-helper` (또는 원하는 이름)
3. **Public** 선택 (Streamlit Cloud 무료 배포용)
4. ⚠️ **Add a README file** 체크하지 마세요 (이미 코드 있음)
5. **Create repository** 클릭

### 2-2. 터미널에서 코드 올리기
GitHub에서 만든 저장소 주소를 복사한 뒤, 이 폴더에서:

```bash
cd "/Users/kimhangyu/Desktop/기업소개/영어회화"
git init
git add .
git commit -m "AI 영어 회화 보조 프로그램 초기 버전"
git branch -M main
git remote add origin https://github.com/<내아이디>/english-helper.git
git push -u origin main
```

> `<내아이디>`를 본인 GitHub 아이디로 바꾸세요.

---

## ✅ 3단계: Streamlit Cloud (인터넷에 공개)

### 3-1. 배포
1. [https://share.streamlit.io](https://share.streamlit.io) 접속
2. **Continue with GitHub** 로그인
3. **Create app** → **Deploy a public app from GitHub**
4. 설정:
   - **Repository**: 방금 올린 `english-helper`
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. **Advanced settings** 펼치기 → **Secrets** 칸에 아래 입력:

```toml
[supabase]
url = "https://여기에-Project-URL-붙여넣기.supabase.co"
key = "여기에-service_role-키-붙여넣기"
```

6. **Deploy!** 클릭 → 1~3분 대기
7. 완료되면 `https://english-helper-xxxx.streamlit.app` 같은 주소가 생깁니다

### 3-2. 아이폰/아이패드에서 앱처럼 쓰기
1. 사파리에서 배포된 주소 열기
2. 하단 **공유** 버튼 → **홈 화면에 추가**
3. 홈 화면 아이콘으로 앱처럼 실행 가능

---

## ✅ 4단계: 동작 확인

배포된 앱에서 확인할 것:
- [ ] 화면 상단에 `클라우드(Supabase) · 영구 저장` 표시
- [ ] 사진 업로드 + 키워드 저장 성공
- [ ] Supabase **Table Editor** → `study_records`에 행 추가됨
- [ ] Supabase **Storage** → `study-images`에 사진 파일 있음
- [ ] `ChatGPT와 실전 연습하기` 버튼 → 새 창에서 ChatGPT 열림

---

## ❓ 문제 해결

| 증상 | 해결 |
|------|------|
| 저장 오류 | `service_role` 키인지, 버킷 이름이 `study-images`인지 확인 |
| 사진 안 보임 | Storage 버킷이 **Public** 인지 확인 |
| 데이터 사라짐 | Streamlit Secrets에 Supabase 설정이 있는지 확인 |
| Git push 실패 | GitHub 로그인 / Personal Access Token 필요할 수 있음 |
