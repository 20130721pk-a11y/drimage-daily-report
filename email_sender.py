"""
이메일 발송 모듈 (Gmail SMTP)
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def send_email(html_content: str, date_label: str) -> None:
    """Gmail SMTP로 HTML 리포트 발송"""

    smtp_user = os.environ["GMAIL_USER"]          # 발신 Gmail 주소
    smtp_password = os.environ["GMAIL_APP_PASSWORD"]  # Gmail 앱 비밀번호
    recipient = os.environ.get("REPORT_RECIPIENT", "moon.k@hybecorp.com")

    subject = f"[드림에이지] 게임 업계 동향 일일 리포트 — {date_label}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"드림에이지 리포트 <{smtp_user}>"
    msg["To"] = recipient

    # 텍스트 폴백
    text_part = MIMEText(
        f"[드림에이지] 게임 업계 동향 일일 리포트 — {date_label}\n"
        "HTML 형식을 지원하는 이메일 클라이언트에서 확인하세요.",
        "plain",
        "utf-8"
    )
    html_part = MIMEText(html_content, "html", "utf-8")

    msg.attach(text_part)
    msg.attach(html_part)

    print(f"[이메일 발송] 수신: {recipient} | 제목: {subject}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [recipient], msg.as_string())

    print("[이메일 발송 완료]")
