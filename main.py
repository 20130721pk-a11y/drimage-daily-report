"""
드림에이지 일일 리포트 메인 실행 파일
"""

import os
import sys
from supabase import create_client

from report_generator import fetch_data, generate_report_with_claude, build_html_email
from email_sender import send_email


def main():
    print("=" * 50)
    print("드림에이지 일일 리포트 생성 시작")
    print("=" * 50)

    # 환경변수 체크
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "ANTHROPIC_API_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"[오류] 누락된 환경변수: {', '.join(missing)}")
        sys.exit(1)

    # Supabase 연결
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

    # 1) 데이터 수집
    data = fetch_data(supabase)

    # 2) Claude로 리포트 생성
    print("[Claude API] 리포트 생성 중...")
    report_json = generate_report_with_claude(data)
    print("[Claude API] 생성 완료")

    # 3) HTML 이메일 빌드
    html = build_html_email(report_json, data["date_label"])

    # 4) 발송
    send_email(html, data["date_label"])

    print("=" * 50)
    print("리포트 생성 및 발송 완료")
    print("=" * 50)


if __name__ == "__main__":
    main()
