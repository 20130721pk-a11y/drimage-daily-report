# 드림에이지 게임 업계 동향 일일 리포트

매일 오전 10시 KST, Supabase 데이터를 기반으로 Claude AI가 리포트를 생성하여 이메일로 발송합니다.

---

## 파일 구조

```
├── main.py                          # 메인 실행 파일
├── report_generator.py              # 데이터 수집 + Claude 리포트 생성 + HTML 빌드
├── email_sender.py                  # Gmail SMTP 발송
├── requirements.txt
└── .github/
    └── workflows/
        └── daily-report.yml         # GitHub Actions (매일 01:00 UTC = 10:00 KST)
```

---

## 초기 설정

### 1. GitHub Secrets 등록

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름 | 값 |
|---|---|
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_KEY` | Supabase anon key |
| `ANTHROPIC_API_KEY` | Anthropic API 키 |
| `GMAIL_USER` | 발신 Gmail 주소 (예: drimage.report@gmail.com) |
| `GMAIL_APP_PASSWORD` | Gmail 앱 비밀번호 (16자리) |

### 2. Gmail 앱 비밀번호 발급

1. Google 계정 → 보안 → 2단계 인증 활성화
2. [앱 비밀번호 생성](https://myaccount.google.com/apppasswords)
3. 앱: **메일** / 기기: **기타(직접 입력)** → `drimage-report`
4. 생성된 16자리 비밀번호를 `GMAIL_APP_PASSWORD` Secret에 등록

---

## 수동 실행 (테스트)

GitHub 저장소 → **Actions → 드림에이지 일일 리포트 → Run workflow**

또는 로컬:

```bash
export SUPABASE_URL="..."
export SUPABASE_KEY="..."
export ANTHROPIC_API_KEY="..."
export GMAIL_USER="..."
export GMAIL_APP_PASSWORD="..."

pip install -r requirements.txt
python main.py
```

---

## 리포트 구성

| 섹션 | 내용 |
|---|---|
| ① 오늘의 핵심 요약 | 당일 주요 변화 3가지 |
| ② 자사 동향 | 드림에이지·아키텍트·알케론 언급량 및 감성 |
| ③ 경쟁사 동향 | 7개 경쟁사 언급량 순위 + 주목 이슈 |
| ④ 광고 활동 | 권역별 신규 광고 건수, 최다 광고 경쟁사 |
| ⑤ 커뮤니티 감성 | 감성 분포 및 부정 키워드 |
| ⑥ 주목 뉴스 | 중요도 상위 3~5건 |

---

## 관련 저장소

- 크롤러: `20130721pk-a11y/dongchun`
- 대시보드: `20130721pk-a11y/drimage-dashboard`
