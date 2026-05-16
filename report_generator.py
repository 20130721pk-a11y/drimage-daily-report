"""
드림에이지 게임 업계 동향 일일 리포트 생성기
매일 오전 10시 KST 실행 (GitHub Actions: 01:00 UTC)

확인된 DB 실제 값:
- community_posts.sentiment: '긍정' / '부정' / '중립'
- competitor_ads.competitor: 'Blizzard(오버워치2)' / 'EA(에이펙스 레전드)' /
    'Riot Games(발로란트)' / 'Epic Games(포트나이트)' / 'Krafton(배틀그라운드)' /
    'Nimble Neuron(이터널리턴)' / 'Riot Games(리그오브레전드)'
"""

import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import Counter
from supabase import create_client, Client

KST = ZoneInfo("Asia/Seoul")

# ── 자사 키워드 매핑 ──────────────────────────────────────────────
OWN_KEYWORDS = {
    "dreamage":  ["드림에이지", "DreamAge", "dreamage"],
    "arkheron":  ["아키텍트", "Arkheron", "arkheron", "알케론"],
    "alcheron":  ["알케론", "Alcheron", "alcheron"],
}

# ── 경쟁사 competitor_ads 컬럼값 → 표시명 매핑 ───────────────────
COMPETITOR_DISPLAY = {
    "Blizzard(오버워치2)":         {"name": "오버워치2",      "company": "Blizzard"},
    "EA(에이펙스 레전드)":          {"name": "에이펙스 레전드", "company": "EA"},
    "Riot Games(발로란트)":         {"name": "발로란트",       "company": "Riot Games"},
    "Epic Games(포트나이트)":       {"name": "포트나이트",     "company": "Epic Games"},
    "Krafton(배틀그라운드)":        {"name": "배틀그라운드",   "company": "Krafton"},
    "Nimble Neuron(이터널리턴)":    {"name": "이터널리턴",     "company": "Nimble Neuron"},
    "Riot Games(리그오브레전드)":   {"name": "리그오브레전드", "company": "Riot Games"},
}

# ── 감성 값 (DB 실제 한국어 값) ──────────────────────────────────
SENTIMENT_POSITIVE = "긍정"
SENTIMENT_NEGATIVE = "부정"
SENTIMENT_NEUTRAL  = "중립"


def calc_sentiment_ratio(posts: list) -> str:
    """게시글 리스트의 감성 비율 문자열 반환 (긍정X% 중립Y% 부정Z%)"""
    if not posts:
        return "데이터 없음"
    c = Counter(p.get("sentiment", "") for p in posts)
    total = len(posts)
    pos  = round(c.get(SENTIMENT_POSITIVE, 0) / total * 100)
    neg  = round(c.get(SENTIMENT_NEGATIVE, 0) / total * 100)
    neu  = 100 - pos - neg
    return f"긍정{pos}% 중립{neu}% 부정{neg}%"


def filter_own(posts_or_news: list, brand_key: str, field: str = "title") -> list:
    """자사 브랜드 키워드로 항목 필터링 (title / content / summary 모두 검색)"""
    kws = OWN_KEYWORDS.get(brand_key, [])
    def matches(item):
        search_text = " ".join([
            (item.get("title", "") or ""),
            (item.get("content", "") or ""),
            (item.get("summary", "") or ""),
        ]).lower()
        return any(kw.lower() in search_text for kw in kws)
    return [item for item in posts_or_news if matches(item)]


def get_date_range():
    """전날 KST 00:00 ~ 23:59:59 범위 반환"""
    now_kst = datetime.now(KST)
    yesterday = now_kst - timedelta(days=1)
    start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start.isoformat(), end.isoformat(), yesterday.strftime("%Y.%m.%d")


def fetch_data(supabase: Client) -> dict:
    """Supabase에서 전날 데이터 수집 + 기본 전처리 통계 생성"""
    start, end, date_label = get_date_range()
    now_kst = datetime.now(KST)
    seven_days_ago = (now_kst - timedelta(days=7)).isoformat()

    print(f"[데이터 수집] 기준일: {date_label} | 범위: {start} ~ {end}")

    news = (
        supabase.table("news")
        .select("id, title, summary, url, source, published_at, collected_at, category, tags")
        .gte("published_at", start)
        .lte("published_at", end)
        .execute()
    )
    streams = (
        supabase.table("streams")
        .select("id, title, channel_name, platform, url, started_at, viewer_count, collected_at, category, tags, is_live")
        .gte("started_at", start)
        .lte("started_at", end)
        .execute()
    )
    community_posts = (
        supabase.table("community_posts")
        .select("id, title, content, url, community, sentiment, sentiment_reason, keyword, posted_at, collected_at, category, views, comments")
        .gte("collected_at", start)
        .lte("collected_at", end)
        .execute()
    )
    competitor_ads = (
        supabase.table("competitor_ads")
        .select("id, platform, competitor, title, description, ad_type, region, published_at, collected_at, views")
        .gte("collected_at", seven_days_ago)
        .execute()
    )

    news_data       = news.data or []
    streams_data    = streams.data or []
    posts_data      = community_posts.data or []
    ads_data        = competitor_ads.data or []

    # ── 자사 전처리 통계 (Python에서 계산 → Claude 프롬프트 토큰 절감) ──
    own_stats = {}
    for brand_key, brand_label in [("dreamage","드림에이지"), ("arkheron","아키텍트"), ("alcheron","알케론")]:
        brand_news    = filter_own(news_data,    brand_key, "title")
        brand_posts   = filter_own(posts_data,   brand_key, "title")
        brand_streams = filter_own(streams_data, brand_key, "title")
        own_stats[brand_key] = {
            "label":     brand_label,
            "news_cnt":  len(brand_news),
            "post_cnt":  len(brand_posts),
            "stream_cnt":len(brand_streams),
            "sentiment": calc_sentiment_ratio(brand_posts),
            "news_titles":   [n["title"] for n in brand_news[:5]],
            "post_titles":   [p["title"] for p in brand_posts[:5]],
        }

    # ── 광고 전처리 통계 ──────────────────────────────────────────
    ads_by_region   = Counter(a.get("region", "?") for a in ads_data)
    ads_by_comp     = Counter(a.get("competitor", "?") for a in ads_data)
    ads_by_type     = Counter(a.get("ad_type", "?") for a in ads_data)
    top_advertiser_raw = ads_by_comp.most_common(1)[0][0] if ads_by_comp else ""
    top_advertiser  = COMPETITOR_DISPLAY.get(top_advertiser_raw, {}).get("name", top_advertiser_raw)

    # ── 전체 감성 비율 ────────────────────────────────────────────
    # 자사 관련 게시글
    own_all_posts = []
    for bk in ["dreamage", "arkheron", "alcheron"]:
        own_all_posts.extend(filter_own(posts_data, bk, "title"))
    own_all_posts = list({p["id"]: p for p in own_all_posts}.values())  # 중복 제거

    comp_posts = [p for p in posts_data if p not in own_all_posts]

    result = {
        "date_label":      date_label,
        "news":            news_data,
        "streams":         streams_data,
        "community_posts": posts_data,
        "competitor_ads":  ads_data,
        # 전처리된 통계 (Claude 프롬프트에 직접 주입)
        "own_stats":       own_stats,
        "ads_stats": {
            "by_region":      dict(ads_by_region),
            "by_competitor":  {COMPETITOR_DISPLAY.get(k, {}).get("name", k): v
                               for k, v in ads_by_comp.items()},
            "by_type":        dict(ads_by_type),
            "top_advertiser": top_advertiser,
        },
        "sentiment_stats": {
            "own_total":        calc_sentiment_ratio(own_all_posts),
            "competitor_total": calc_sentiment_ratio(comp_posts),
        },
    }

    print(
        f"[수집 완료] 뉴스: {len(news_data)}건 | "
        f"방송: {len(streams_data)}건 | "
        f"커뮤니티: {len(posts_data)}건 | "
        f"광고: {len(ads_data)}건"
    )
    return result


def generate_report(data: dict) -> dict:
    """순수 Python 집계로 리포트 데이터 생성 (Claude API 불필요)"""
    own_stats  = data["own_stats"]
    ads_stats  = data["ads_stats"]
    sent_stats = data["sentiment_stats"]
    news       = data["news"]
    posts      = data["community_posts"]
    ads        = data["competitor_ads"]

    # ── 경쟁사 언급량 집계 (뉴스 + 커뮤니티 키워드 검색) ──────────
    COMP_KEYWORDS = {
        "오버워치2":      ["오버워치", "overwatch", "OW2"],
        "에이펙스 레전드": ["에이펙스", "apex"],
        "발로란트":       ["발로란트", "valorant"],
        "포트나이트":     ["포트나이트", "fortnite"],
        "배틀그라운드":   ["배틀그라운드", "pubg", "배그"],
        "이터널리턴":     ["이터널리턴", "eternal return"],
        "리그오브레전드": ["리그오브레전드", "롤", " lol ", "league of legends"],
    }
    COMP_COMPANY = {
        "오버워치2": "Blizzard", "에이펙스 레전드": "EA",
        "발로란트": "Riot Games", "포트나이트": "Epic Games",
        "배틀그라운드": "Krafton", "이터널리턴": "Nimble Neuron",
        "리그오브레전드": "Riot Games",
    }

    def count_mentions(items, keywords, fields=("title","summary","content")):
        cnt = 0
        for item in items:
            text = " ".join((item.get(f,"") or "") for f in fields).lower()
            if any(kw.lower() in text for kw in keywords):
                cnt += 1
        return cnt

    competitors = []
    for game, kws in COMP_KEYWORDS.items():
        n = count_mentions(news, kws) + count_mentions(posts, kws)
        competitors.append({
            "name": game,
            "company": COMP_COMPANY[game],
            "total_mentions": n,
            "highlight": "특이사항 없음",
        })
    competitors.sort(key=lambda x: x["total_mentions"], reverse=True)

    # ── 자사 동향 요약 (상위 뉴스 제목 나열) ────────────────────────
    def own_summary(brand_key):
        titles = own_stats[brand_key].get("news_titles", []) + own_stats[brand_key].get("post_titles", [])
        if not titles:
            return "언급 없음"
        return " / ".join(titles[:3])

    # ── 부정 키워드 집계 ─────────────────────────────────────────
    neg_posts = [p for p in posts if p.get("sentiment") == SENTIMENT_NEGATIVE]
    kw_counter = Counter()
    for p in neg_posts:
        kw = p.get("keyword", "")
        if kw:
            for k in str(kw).split(","):
                k = k.strip()
                if k:
                    kw_counter[k] += 1
    negative_keywords = [k for k, _ in kw_counter.most_common(5)]

    # ── 커뮤니티별 반응 ──────────────────────────────────────────
    comm_counter = Counter(p.get("community","") for p in posts if p.get("community"))
    community_highlights = [
        {"community": comm, "reaction": f"게시글 {cnt}건 수집"}
        for comm, cnt in comm_counter.most_common(4)
    ]

    # ── 주목 뉴스 상위 5건 ───────────────────────────────────────
    top_news = [
        {
            "title":   n.get("title", ""),
            "source":  n.get("source", ""),
            "summary": n.get("summary", "")[:60] + "..." if n.get("summary","") and len(n.get("summary","")) > 60 else n.get("summary",""),
            "url":     n.get("url", "#"),
        }
        for n in news[:5]
    ]

    # ── 오늘의 핵심 요약 3줄 자동 생성 ──────────────────────────
    top_comp = competitors[0] if competitors else {}
    own_total_cnt = sum(
        own_stats[b]["news_cnt"] + own_stats[b]["post_cnt"] + own_stats[b]["stream_cnt"]
        for b in ["dreamage","arkheron","alcheron"]
    )
    summary_3 = [
        f"전체 수집 데이터: 뉴스 {len(news)}건 · 커뮤니티 {len(posts)}건 · 방송 {len(data['streams'])}건 · 광고 {len(ads)}건",
        f"경쟁사 언급량 1위: {top_comp.get('name','—')} {top_comp.get('total_mentions',0)}건 ({top_comp.get('company','—')})",
        f"자사 전체 언급 {own_total_cnt}건 | 감성 — 자사: {sent_stats['own_total']} / 경쟁사: {sent_stats['competitor_total']}",
    ]

    # ── 광고 유형 한국어 변환 ────────────────────────────────────
    type_map = {"video": "동영상", "image": "이미지", "text": "텍스트"}
    type_dist_kr = {type_map.get(k, k): v for k, v in ads_stats["by_type"].items()}

    return {
        "summary_3": summary_3,
        "own_company": {
            "dreamage": {
                "news":      own_stats["dreamage"]["news_cnt"],
                "community": own_stats["dreamage"]["post_cnt"],
                "stream":    own_stats["dreamage"]["stream_cnt"],
                "sentiment": own_stats["dreamage"]["sentiment"],
                "summary":   own_summary("dreamage"),
            },
            "arkheron": {
                "news":      own_stats["arkheron"]["news_cnt"],
                "community": own_stats["arkheron"]["post_cnt"],
                "stream":    own_stats["arkheron"]["stream_cnt"],
                "sentiment": own_stats["arkheron"]["sentiment"],
                "summary":   own_summary("arkheron"),
            },
            "alcheron": {
                "news":      own_stats["alcheron"]["news_cnt"],
                "community": own_stats["alcheron"]["post_cnt"],
                "stream":    own_stats["alcheron"]["stream_cnt"],
                "sentiment": own_stats["alcheron"]["sentiment"],
                "summary":   own_summary("alcheron"),
            },
        },
        "competitors": competitors,
        "ads": {
            "by_region":     {r: ads_stats["by_region"].get(r, 0) for r in ["KR","US","JP","TW","GB","DE","BR"]},
            "top_advertiser": ads_stats["top_advertiser"],
            "type_dist":     type_dist_kr,
        },
        "sentiment": {
            "own_total":           sent_stats["own_total"],
            "competitor_total":    sent_stats["competitor_total"],
            "negative_keywords":   negative_keywords,
            "community_highlights": community_highlights,
        },
        "top_news": top_news,
    }


def build_html_email(report: dict, date_label: str) -> str:
    """HTML 이메일 템플릿 생성"""

    def safe(val, default="데이터 없음"):
        return val if val else default

    # ① 오늘의 요약
    summary_items = "".join(
        f'<li style="margin:4px 0; padding:6px 10px; background:#f0f7ff; border-left:3px solid #2563eb; border-radius:3px;">'
        f'<span style="color:#1e3a5f;">{s}</span></li>'
        for s in report.get("summary_3", [])
    )

    # ② 자사 동향
    own = report.get("own_company", {})
    def own_row(label, key):
        d = own.get(key, {})
        return f"""
        <tr>
          <td style="padding:8px 10px; font-weight:600; color:#374151; border-bottom:1px solid #e5e7eb;">{label}</td>
          <td style="padding:8px 10px; text-align:center; border-bottom:1px solid #e5e7eb;">{d.get('news', 0)}</td>
          <td style="padding:8px 10px; text-align:center; border-bottom:1px solid #e5e7eb;">{d.get('community', 0)}</td>
          <td style="padding:8px 10px; text-align:center; border-bottom:1px solid #e5e7eb;">{d.get('stream', 0)}</td>
          <td style="padding:8px 10px; color:#6b7280; font-size:12px; border-bottom:1px solid #e5e7eb;">{safe(d.get('sentiment'))}</td>
          <td style="padding:8px 10px; color:#374151; font-size:12px; border-bottom:1px solid #e5e7eb;">{safe(d.get('summary'))}</td>
        </tr>"""

    # ③ 경쟁사 순위
    competitors = sorted(
        report.get("competitors", []),
        key=lambda x: x.get("total_mentions", 0),
        reverse=True
    )
    comp_rows = ""
    for i, c in enumerate(competitors, 1):
        highlight = c.get("highlight", "없음")
        hl_style = 'color:#dc2626; font-weight:600;' if highlight != "없음" else 'color:#9ca3af;'
        comp_rows += f"""
        <tr>
          <td style="padding:7px 10px; text-align:center; font-weight:700; color:#6b7280; border-bottom:1px solid #e5e7eb;">{i}</td>
          <td style="padding:7px 10px; font-weight:600; border-bottom:1px solid #e5e7eb;">{c.get('name','')}</td>
          <td style="padding:7px 10px; color:#6b7280; font-size:12px; border-bottom:1px solid #e5e7eb;">{c.get('company','')}</td>
          <td style="padding:7px 10px; text-align:center; font-weight:700; color:#2563eb; border-bottom:1px solid #e5e7eb;">{c.get('total_mentions',0)}</td>
          <td style="padding:7px 10px; font-size:12px; border-bottom:1px solid #e5e7eb; {hl_style}">{highlight}</td>
        </tr>"""

    # ④ 광고
    ads = report.get("ads", {})
    region_data = ads.get("by_region", {})
    region_cells = "".join(
        f'<td style="padding:6px 8px; text-align:center; border:1px solid #e5e7eb;">'
        f'<div style="font-size:10px; color:#9ca3af;">{r}</div>'
        f'<div style="font-weight:700; color:#1e3a5f;">{region_data.get(r,0)}</div></td>'
        for r in ["KR", "US", "JP", "TW", "GB", "DE", "BR"]
    )
    type_dist = ads.get("type_dist", {})
    type_str = " | ".join(f"{k} {v}건" for k, v in type_dist.items() if v)

    # ⑤ 커뮤니티 감성
    sentiment = report.get("sentiment", {})
    neg_kws = sentiment.get("negative_keywords", [])
    neg_kw_str = ", ".join(f"<span style='background:#fee2e2;color:#dc2626;padding:2px 6px;border-radius:10px;font-size:11px;'>{k}</span>" for k in neg_kws) if neg_kws else "없음"

    community_hl = "".join(
        f'<div style="margin:4px 0; font-size:12px;"><b style="color:#374151;">{h.get("community","")}</b> — {h.get("reaction","")}</div>'
        for h in sentiment.get("community_highlights", [])
    )

    # ⑥ 주목 뉴스
    news_items = ""
    for n in report.get("top_news", [])[:5]:
        url = n.get("url", "#")
        news_items += f"""
        <tr>
          <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">
            <a href="{url}" style="color:#2563eb; text-decoration:none; font-weight:600; font-size:13px;">{n.get('title','')}</a>
            <div style="font-size:11px; color:#9ca3af; margin-top:2px;">{n.get('source','')} · {n.get('summary','')}</div>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>[드림에이지] 게임 업계 동향 일일 리포트 — {date_label}</title>
</head>
<body style="margin:0; padding:0; background:#f3f4f6; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6; padding:24px 0;">
<tr><td align="center">
<table width="680" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">

  <!-- 헤더 -->
  <tr>
    <td style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%); padding:24px 30px;">
      <div style="color:#93c5fd; font-size:11px; font-weight:600; letter-spacing:2px; text-transform:uppercase;">DRIMAGE DAILY REPORT</div>
      <div style="color:#ffffff; font-size:20px; font-weight:700; margin-top:6px;">[드림에이지] 게임 업계 동향 일일 리포트</div>
      <div style="color:#bfdbfe; font-size:13px; margin-top:4px;">{date_label} 기준 · 자동 생성 리포트</div>
    </td>
  </tr>

  <tr><td style="padding:24px 30px 0;">

    <!-- ① 오늘의 요약 -->
    <div style="margin-bottom:24px;">
      <div style="font-size:13px; font-weight:700; color:#2563eb; letter-spacing:1px; margin-bottom:10px;">① 오늘의 핵심 요약</div>
      <ul style="margin:0; padding:0; list-style:none;">{summary_items}</ul>
    </div>

    <!-- ② 자사 동향 -->
    <div style="margin-bottom:24px;">
      <div style="font-size:13px; font-weight:700; color:#2563eb; letter-spacing:1px; margin-bottom:10px;">② 자사 동향</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb; border-radius:6px; overflow:hidden; font-size:13px;">
        <tr style="background:#f8fafc;">
          <th style="padding:8px 10px; text-align:left; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">브랜드</th>
          <th style="padding:8px 10px; text-align:center; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">뉴스</th>
          <th style="padding:8px 10px; text-align:center; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">커뮤니티</th>
          <th style="padding:8px 10px; text-align:center; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">방송</th>
          <th style="padding:8px 10px; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">감성</th>
          <th style="padding:8px 10px; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">주요 내용</th>
        </tr>
        {own_row("드림에이지", "dreamage")}
        {own_row("아키텍트", "arkheron")}
        {own_row("알케론", "alcheron")}
      </table>
    </div>

    <!-- ③ 경쟁사 동향 -->
    <div style="margin-bottom:24px;">
      <div style="font-size:13px; font-weight:700; color:#2563eb; letter-spacing:1px; margin-bottom:10px;">③ 경쟁사 동향 (언급량 순위)</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb; border-radius:6px; overflow:hidden; font-size:13px;">
        <tr style="background:#f8fafc;">
          <th style="padding:8px 10px; text-align:center; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">순위</th>
          <th style="padding:8px 10px; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">게임</th>
          <th style="padding:8px 10px; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">개발사</th>
          <th style="padding:8px 10px; text-align:center; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">언급량</th>
          <th style="padding:8px 10px; color:#9ca3af; font-weight:600; font-size:11px; border-bottom:2px solid #e5e7eb;">주목 이슈</th>
        </tr>
        {comp_rows}
      </table>
    </div>

    <!-- ④ 광고 활동 -->
    <div style="margin-bottom:24px;">
      <div style="font-size:13px; font-weight:700; color:#2563eb; letter-spacing:1px; margin-bottom:10px;">④ 광고 활동 (최근 7일)</div>
      <div style="background:#f8fafc; border:1px solid #e5e7eb; border-radius:6px; padding:14px 16px;">
        <table cellpadding="0" cellspacing="0" style="margin-bottom:10px;">
          <tr>{region_cells}</tr>
        </table>
        <div style="font-size:12px; color:#374151;">
          <b>최다 광고:</b> {safe(ads.get('top_advertiser'))} &nbsp;·&nbsp;
          <b>유형 분포:</b> {type_str if type_str else '데이터 없음'}
        </div>
      </div>
    </div>

    <!-- ⑤ 커뮤니티 감성 -->
    <div style="margin-bottom:24px;">
      <div style="font-size:13px; font-weight:700; color:#2563eb; letter-spacing:1px; margin-bottom:10px;">⑤ 커뮤니티 감성</div>
      <div style="background:#f8fafc; border:1px solid #e5e7eb; border-radius:6px; padding:14px 16px;">
        <div style="display:flex; gap:24px; margin-bottom:10px; font-size:12px; flex-wrap:wrap;">
          <div><b style="color:#374151;">자사 전체:</b> <span style="color:#059669;">{safe(sentiment.get('own_total'))}</span></div>
          <div><b style="color:#374151;">경쟁사 전체:</b> <span style="color:#6b7280;">{safe(sentiment.get('competitor_total'))}</span></div>
        </div>
        <div style="font-size:12px; margin-bottom:8px;"><b style="color:#374151;">부정 키워드:</b> {neg_kw_str}</div>
        <div style="font-size:12px; color:#6b7280; border-top:1px solid #e5e7eb; padding-top:8px; margin-top:4px;">
          {community_hl if community_hl else '<span style="color:#9ca3af;">데이터 없음</span>'}
        </div>
      </div>
    </div>

    <!-- ⑥ 주목 뉴스 -->
    <div style="margin-bottom:28px;">
      <div style="font-size:13px; font-weight:700; color:#2563eb; letter-spacing:1px; margin-bottom:10px;">⑥ 주목 뉴스</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb; border-radius:6px; overflow:hidden;">
        {news_items if news_items else '<tr><td style="padding:12px; color:#9ca3af; font-size:13px;">수집된 뉴스 없음</td></tr>'}
      </table>
    </div>

  </td></tr>

  <!-- 푸터 -->
  <tr>
    <td style="background:#f8fafc; border-top:1px solid #e5e7eb; padding:14px 30px;">
      <div style="font-size:11px; color:#9ca3af; text-align:center;">
        본 리포트는 드림에이지 마케팅팀 내부 자동화 시스템에 의해 생성되었습니다 · {date_label} 데이터 기준
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    return html
