"""
app.py — SBS아카데미 대전지점 상담 시스템 (Streamlit 웹 대시보드)
실행: streamlit run app.py
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from design_engine import design, COURSE_ROLES, FIELDS
from excel_loader import load_courses as _excel_load_courses

# ── 경로 ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SBS아카데미 대전지점 · 상담 시스템",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 글로벌 CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── 사이드바 ── */
[data-testid="stSidebar"] { background:#111827; }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div { color:#e5e7eb !important; }
[data-testid="stSidebar"] h3  { color:#fff !important; font-weight:800; }
[data-testid="stSidebar"] hr  { border-color:#374151; }

/* ── 헤더 배너 ── */
.sbs-header {
    background: linear-gradient(120deg,#9b0010 0%,#e50012 55%,#ff3344 100%);
    padding:1.4rem 2rem; border-radius:14px; margin-bottom:1.2rem;
    box-shadow:0 4px 24px rgba(229,0,18,.30);
}
.sbs-header h1 { margin:0; color:#fff; font-size:1.75rem; font-weight:900; letter-spacing:-.5px; }
.sbs-header p  { margin:.25rem 0 0; color:rgba(255,255,255,.80); font-size:.9rem; }

/* ── 합계 카드 ── */
.total-card {
    background:linear-gradient(135deg,#9b0010,#e50012);
    border-radius:16px; padding:1.6rem 1.2rem;
    text-align:center; margin:0 0 1rem;
    box-shadow:0 6px 28px rgba(229,0,18,.35);
}
.total-label   { font-size:.85rem; color:rgba(255,255,255,.80); margin-bottom:.2rem; }
.total-amount  { font-size:2.8rem; font-weight:900; color:#fff; letter-spacing:-1.5px; line-height:1.1; }
.total-savings { font-size:.85rem; color:rgba(255,255,255,.75); margin-top:.4rem; }

/* ── 정보 카드 ── */
.info-card {
    background:#f9fafb; border:1.5px solid #e5e7eb;
    border-radius:12px; padding:1rem 1.2rem; margin-bottom:.8rem;
}
.info-card b { color:#e50012; }

/* ── 프리셋 버튼 ── */
div[data-testid="column"] button {
    width:100% !important; border-radius:10px !important;
    font-weight:700 !important; border:2px solid #e50012 !important;
    color:#e50012 !important; background:#fff5f5 !important;
    padding:.55rem .5rem !important; transition:all .15s !important;
}
div[data-testid="column"] button:hover {
    background:#e50012 !important; color:#fff !important;
}

/* ── 테이블 헤더 ── */
thead tr th {
    background:#e50012 !important; color:#fff !important;
    font-weight:700 !important;
}

/* ── 섹션 타이틀 ── */
.section-title {
    font-size:1.05rem; font-weight:800; color:#111827;
    border-left:4px solid #e50012; padding-left:.7rem;
    margin:1.2rem 0 .7rem;
}

/* ── 성공/경고 배너 ── */
.ok-banner {
    background:#f0fdf4; border:1.5px solid #16a34a;
    border-radius:10px; padding:.8rem 1.2rem; color:#15803d;
    font-weight:600; margin:.6rem 0;
}

/* ══ AI 설계 검색 ══════════════════════════════════════════ */
.ai-search-wrap {
    background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 100%);
    border-radius:16px; padding:1.5rem 1.8rem; margin-bottom:1.4rem;
    border:1px solid #312e81;
    box-shadow:0 4px 24px rgba(99,102,241,.25);
}
.ai-search-wrap h3 {
    color:#a5b4fc; font-size:1rem; font-weight:800;
    margin:0 0 .15rem; letter-spacing:.3px;
}
.ai-search-wrap p { color:#94a3b8; font-size:.82rem; margin:0 0 .8rem; }

/* 설계 결과 카드 공통 */
.design-card {
    border-radius:14px; padding:1.3rem 1.4rem;
    height:100%; box-shadow:0 4px 18px rgba(0,0,0,.10);
}
.design-card-min {
    background:#fff; border:2px solid #e50012;
}
.design-card-max {
    background:linear-gradient(160deg,#1a1a2e 0%,#16213e 100%);
    border:2px solid #6366f1; color:#e2e8f0;
}
.dc-badge-min {
    display:inline-block; background:#e50012; color:#fff;
    font-size:.72rem; font-weight:800; padding:.25rem .65rem;
    border-radius:20px; margin-bottom:.55rem; letter-spacing:.5px;
}
.dc-badge-max {
    display:inline-block;
    background:linear-gradient(90deg,#6366f1,#8b5cf6);
    color:#fff; font-size:.72rem; font-weight:800;
    padding:.25rem .65rem; border-radius:20px;
    margin-bottom:.55rem; letter-spacing:.5px;
}
.dc-field-label { font-size:.8rem; opacity:.65; margin-bottom:.2rem; }
.dc-price-min { font-size:2rem; font-weight:900; color:#e50012; letter-spacing:-1px; line-height:1.1; }
.dc-price-max { font-size:2rem; font-weight:900; color:#a5b4fc; letter-spacing:-1px; line-height:1.1; }
.dc-course-tag {
    display:inline-block; background:#f3f4f6; color:#1f2937;
    border-radius:6px; padding:.18rem .55rem;
    font-size:.78rem; font-weight:600; margin:.18rem .18rem 0 0;
}
.dc-course-tag-dark {
    display:inline-block;
    background:rgba(99,102,241,.18); color:#c7d2fe;
    border-radius:6px; padding:.18rem .55rem;
    font-size:.78rem; font-weight:600; margin:.18rem .18rem 0 0;
    border:1px solid rgba(99,102,241,.35);
}
.dc-intent-min {
    background:#fff5f5; border-left:3px solid #e50012;
    border-radius:0 8px 8px 0; padding:.65rem .9rem;
    font-size:.82rem; color:#374151; margin:.8rem 0;
    line-height:1.6;
}
.dc-intent-max {
    background:rgba(99,102,241,.12);
    border-left:3px solid #6366f1;
    border-radius:0 8px 8px 0; padding:.65rem .9rem;
    font-size:.82rem; color:#cbd5e1; margin:.8rem 0;
    line-height:1.6;
}
.dc-relation-title { font-size:.78rem; font-weight:700; opacity:.65; margin:.7rem 0 .3rem; }
.dc-relation-item  { font-size:.78rem; line-height:1.55; margin-bottom:.35rem; }

/* 힌트 칩 */
.hint-chip {
    display:inline-block; background:rgba(165,180,252,.12);
    border:1px solid rgba(165,180,252,.3); color:#a5b4fc;
    border-radius:20px; padding:.2rem .75rem; font-size:.78rem;
    margin:.15rem; cursor:default;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 데이터 & 상수
# ══════════════════════════════════════════════════════════════════════════════

PRESETS: dict[str, dict] = {
    "⚡ 영상·모션 최소": {
        "courses": ["프리미어", "에펙", "모션에펙"],
        "desc": "영상 편집 핵심 | 3개 과정 | 약 3~4개월",
    },
    "🚀 영상·모션 최대": {
        "courses": ["발상과표현", "포토샵, 일러스트", "프리미어", "에펙", "모션에펙", "어드벤스 에펙", "시포디1~4", "모션포폴1~3"],
        "desc": "풀스펙 모션 포트폴리오 | 8개 과정 | 약 10~12개월",
    },
    "✏️ 그래픽 최소": {
        "courses": ["포토샵, 일러스트", "포토웍스, 디일러"],
        "desc": "그래픽 기초 입문 | 2개 과정 | 약 2개월",
    },
    "🏠 인테리어 최소": {
        "courses": ["실내건축이론", "캐드1~2", "스케치업1~2"],
        "desc": "인테리어 입문 | 3개 과정 | 약 3~4개월",
    },
    "🌐 웹디자인 풀": {
        "courses": ["포토웍스, 디일러", "웹1~3", "UIUX1~3", "웹포폴1~2"],
        "desc": "웹 퍼블리셔 완성 | 4개 과정 | 약 5~6개월",
    },
    "🤖 AI 크리에이터": {
        "courses": ["AI프롬프트1~2", "AI크리에이터-영상모션", "AI크리에이터-아트웍"],
        "desc": "AI 기반 크리에이터 | 3개 과정 | 최신 트렌드",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# 데이터 로드 (캐시)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="수강료 데이터 로딩 중...")
def load_courses() -> list[dict]:
    """엑셀 파일에서 수강료 데이터를 로드합니다 (크롤링 없음)."""
    return _excel_load_courses()


def course_lookup(courses: list[dict]) -> dict[str, int]:
    return {c["course"]: c["price"] for c in courses}


def build_category_map(courses: list[dict]) -> dict[str, list[str]]:
    cat_map: dict[str, list[str]] = {}
    for c in courses:
        dept = c["department"]
        if dept not in cat_map:
            cat_map[dept] = []
        cat_map[dept].append(c["course"])
    return cat_map


# ══════════════════════════════════════════════════════════════════════════════
# 계산 유틸
# ══════════════════════════════════════════════════════════════════════════════

def fmt_won(n: int) -> str:
    return f"{n:,}원"


def build_df(selected_names: list[str], price_map: dict[str, int], discount_rate: float) -> pd.DataFrame:
    rows = []
    for name in selected_names:
        price = price_map.get(name, 0)
        disc_price = round(price * (1 - discount_rate / 100))
        rows.append({
            "과정명":   name,
            "정가":     fmt_won(price),
            "할인율":   f"{discount_rate:.0f}%",
            "할인가":   fmt_won(disc_price),
            "절약":     fmt_won(price - disc_price),
            "_price":   price,
            "_final":   disc_price,
        })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# 문서 생성 (MD / HTML)
# ══════════════════════════════════════════════════════════════════════════════

def build_md(name, contact, field, consultant, memo, df, total, subtotal, savings, disc_rate, today) -> str:
    lines = [
        "# SBS아카데미 대전지점 상담일지", "",
        f"> 작성일시: {today}  ",
        f"> 담당 상담사: {consultant}", "",
        "---", "",
        "## 상담생 정보", "",
        f"- **이름**: {name}",
        f"- **연락처**: {contact}",
        f"- **희망 분야**: {field}", "",
        "## 수강료 내역", "",
        "| 과정명 | 정가 | 할인율 | 할인가 | 절약 |",
        "|---|---|---|---|---|",
    ]
    for _, r in df.iterrows():
        lines.append(f"| {r['과정명']} | {r['정가']} | {r['할인율']} | {r['할인가']} | {r['절약']} |")
    lines += [
        "",
        f"- **소계**: {fmt_won(subtotal)}",
        f"- **할인율**: {disc_rate:.0f}%",
        f"- **최종 납부금액**: **{fmt_won(total)}**",
        f"- **총 절약금액**: {fmt_won(savings)}", "",
        "---", "",
        "## 상담 메모", "",
        memo.strip() or "*(메모 없음)*", "",
        "---", "",
        "## 팀장 확인 및 코멘트", "",
        "| 항목 | 내용 |",
        "|---|---|",
        "| 검토 여부 | ☐ 검토 완료 |",
        "| 등록 여부 | ☐ 등록 / ☐ 미등록 / ☐ 보류 |",
        "| 팀장 서명 | |",
        "| 코멘트 | |", "",
        "> *이 문서는 SBS아카데미 대전지점 내부용 상담 기록입니다.*",
    ]
    return "\n".join(lines)


def build_html(name, contact, field, consultant, memo, df, total, subtotal, savings, disc_rate, today) -> str:
    rows_html = "".join(
        f"<tr><td>{r['과정명']}</td><td>{r['정가']}</td>"
        f"<td style='color:#e50012'>{r['할인율']}</td>"
        f"<td style='font-weight:700'>{r['할인가']}</td>"
        f"<td style='color:#16a34a'>{r['절약']}</td></tr>"
        for _, r in df.iterrows()
    )
    memo_html = memo.strip().replace("\n", "<br>") or "<em>(메모 없음)</em>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>SBS아카데미 상담일지 – {name}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Malgun Gothic',Arial,sans-serif; color:#1f2937; padding:2.5rem; font-size:14px; }}
  .header {{ background:linear-gradient(120deg,#9b0010,#e50012); color:#fff; padding:1.5rem 2rem; border-radius:10px; margin-bottom:1.5rem; }}
  .header h1 {{ font-size:1.5rem; font-weight:900; }}
  .header p  {{ opacity:.85; margin-top:.3rem; font-size:.88rem; }}
  h2 {{ font-size:1rem; font-weight:800; color:#e50012; border-left:4px solid #e50012;
        padding-left:.6rem; margin:1.4rem 0 .7rem; }}
  .info-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:.5rem .5rem; margin-bottom:.5rem; }}
  .info-item {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:8px; padding:.6rem .9rem; }}
  .info-item span {{ font-size:.78rem; color:#6b7280; display:block; }}
  .info-item b   {{ font-size:.95rem; color:#111827; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:1rem; }}
  th {{ background:#e50012; color:#fff; padding:.6rem .8rem; text-align:left; font-size:.85rem; }}
  td {{ padding:.55rem .8rem; border-bottom:1px solid #f3f4f6; font-size:.88rem; }}
  tr:nth-child(even) td {{ background:#fef2f2; }}
  .summary-box {{ background:linear-gradient(135deg,#9b0010,#e50012); color:#fff;
                  border-radius:12px; padding:1.2rem 1.5rem; margin:1rem 0; text-align:center; }}
  .summary-box .lbl {{ font-size:.82rem; opacity:.8; }}
  .summary-box .amt {{ font-size:2.2rem; font-weight:900; letter-spacing:-1px; }}
  .summary-box .sav {{ font-size:.82rem; opacity:.8; margin-top:.2rem; }}
  .memo-box {{ background:#f9fafb; border:1.5px solid #e5e7eb; border-radius:10px; padding:1rem; margin-bottom:1rem; }}
  .check-table td {{ padding:.5rem .8rem; }}
  .footer {{ color:#9ca3af; font-size:.78rem; text-align:center; margin-top:2rem; border-top:1px solid #e5e7eb; padding-top:1rem; }}
  @media print {{
    body {{ padding:1rem; }}
    .no-print {{ display:none; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>🎓 SBS아카데미 대전지점 상담일지</h1>
  <p>작성일시: {today} &nbsp;|&nbsp; 담당 상담사: {consultant}</p>
</div>

<h2>상담생 정보</h2>
<div class="info-grid">
  <div class="info-item"><span>이름</span><b>{name}</b></div>
  <div class="info-item"><span>연락처</span><b>{contact}</b></div>
  <div class="info-item"><span>희망 분야</span><b>{field}</b></div>
  <div class="info-item"><span>담당 상담사</span><b>{consultant}</b></div>
</div>

<h2>수강료 내역</h2>
<table>
  <thead><tr><th>과정명</th><th>정가</th><th>할인율</th><th>할인가</th><th>절약</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>

<div class="summary-box">
  <div class="lbl">최종 납부금액</div>
  <div class="amt">{fmt_won(total)}</div>
  <div class="sav">할인율 {disc_rate:.0f}% 적용 · 총 {fmt_won(savings)} 절약</div>
</div>

<h2>상담 메모</h2>
<div class="memo-box">{memo_html}</div>

<h2>팀장 확인 및 코멘트</h2>
<table class="check-table">
  <tr><td style="width:140px;color:#6b7280">검토 여부</td><td>☐ 검토 완료</td></tr>
  <tr><td style="color:#6b7280">등록 여부</td><td>☐ 등록 &nbsp; ☐ 미등록 &nbsp; ☐ 보류</td></tr>
  <tr><td style="color:#6b7280">팀장 서명</td><td>&nbsp;</td></tr>
  <tr><td style="color:#6b7280">코멘트</td><td>&nbsp;</td></tr>
</table>

<p class="footer">이 문서는 SBS아카데미 대전지점 내부용 상담 기록입니다.</p>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Session State 초기화
# ══════════════════════════════════════════════════════════════════════════════

if "selected_courses" not in st.session_state:
    st.session_state.selected_courses: list[str] = []
if "preset_trigger" not in st.session_state:
    st.session_state.preset_trigger: str | None = None
if "ai_result" not in st.session_state:
    st.session_state.ai_result: dict | None = None
if "ai_query" not in st.session_state:
    st.session_state.ai_query: str = ""
if "ai_design_memo" not in st.session_state:
    st.session_state.ai_design_memo: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# 사이드바
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 🎓 SBS아카데미 대전지점")
    st.markdown("---")

    st.markdown("**👤 상담생 정보**")
    s_name       = st.text_input("성함",     placeholder="홍길동")
    s_contact    = st.text_input("연락처",   placeholder="010-0000-0000")
    s_field      = st.text_input("희망 분야", placeholder="영상편집 / UI디자인 …")
    s_consultant = st.text_input("담당 상담사", value="상담사", placeholder="김상담")

    st.markdown("---")
    st.markdown("**💸 할인 설정**")

    disc_type = st.radio(
        "할인 유형",
        ["일반 (과목수 자동)", "페북/구디비/종강생"],
        index=0,
        help="페북/구디비/종강생: 1~3과목 30%, 4과목 이상 40%",
    )
    extra_disc = st.select_slider(
        "추가 할인",
        options=[0, 5, 10],
        value=0,
        format_func=lambda x: f"+{x}%",
        help="10% 이내 자율 추가 할인 (5% 단위)",
    )
    review_on = st.checkbox("리뷰 할인 (최대 20,000원)", help="네이버·구글·카카오맵 리뷰 작성 시")
    review_won = st.number_input("리뷰 할인 금액(원)", 0, 20000, 10000, step=1000,
                                  label_visibility="collapsed") if review_on else 0
    ddaza_on = st.checkbox("따즈아 등록 할인 (최대 100,000원)",
                            help="오프라인 등록 할인율 적용 후 150만 이상인 경우 가능")
    ddaza_won = st.number_input("따즈아 할인 금액(원)", 0, 100000, 0, step=10000,
                                 label_visibility="collapsed") if ddaza_on else 0

    st.markdown("---")
    st.markdown("**📝 상담 메모**")
    _memo_default = st.session_state.get("ai_design_memo", "")
    s_memo = st.text_area("메모", value=_memo_default, height=160,
                           placeholder="수강 목표, 희망 수업 시간, 특이사항 등을 입력하세요.")

    st.markdown("---")
    if st.button("🔄 수강료 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── 할인율 계산 ───────────────────────────────────────────────────────────────
# (사이드바 렌더링 후 계산 — 과목 수는 아래에서 결정되므로 col_right에서 재계산)


# ══════════════════════════════════════════════════════════════════════════════
# 메인 화면
# ══════════════════════════════════════════════════════════════════════════════

# 헤더
st.markdown("""
<div class="sbs-header">
  <h1>🎓 SBS아카데미 대전지점 · 교육과정 상담 시스템</h1>
  <p>수강료 계산 · 커리큘럼 설계 · 상담일지 자동 생성</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AI 과정 설계 검색창
# ══════════════════════════════════════════════════════════════════════════════

hint_examples = [
    "마야 과정 최소/최대 설계해줘",
    "웹디자인 취업 루트 짜줘",
    "영상편집 단기 과정 추천",
    "인테리어 풀 커리큘럼",
    "AI 크리에이터 입문",
    "유튜브 수익화 과정",
]

st.markdown("""
<div class="ai-search-wrap">
  <h3>🤖 AI 과정 설계 검색</h3>
  <p>희망 분야와 목표를 자유롭게 입력하면 최소·최대 커리큘럼을 자동으로 설계합니다.</p>
</div>
""", unsafe_allow_html=True)

# 힌트 칩 (클릭하면 입력창에 채워짐)
hint_cols = st.columns(len(hint_examples))
for col, hint in zip(hint_cols, hint_examples):
    with col:
        if st.button(hint, key=f"hint_{hint}", use_container_width=True):
            st.session_state.ai_query = hint

# 검색 입력창
with st.form("ai_search_form", clear_on_submit=False):
    ai_input = st.text_input(
        "검색",
        value=st.session_state.ai_query,
        placeholder="예: 마야 포트폴리오 과정 추천해줘 / 웹디자인 취업 루트",
        label_visibility="collapsed",
    )
    search_btn = st.form_submit_button("🔍 커리큘럼 설계", use_container_width=True, type="primary")

# 데이터 로드 (검색 전에 필요)
courses       = load_courses()
price_map     = course_lookup(courses)
all_courses   = [c["course"] for c in courses]
CATEGORY_MAP  = build_category_map(courses)
COURSE_TO_CAT = {c: cat for cat, cs in CATEGORY_MAP.items() for c in cs}

# ── 검색 실행 ─────────────────────────────────────────────────────────────────
if search_btn and ai_input.strip():
    st.session_state.ai_query = ai_input.strip()
    result = design(ai_input.strip(), price_map)
    st.session_state.ai_result = result
    if result is None:
        st.warning(
            "인식된 분야가 없습니다. "
            "**마야, 웹, 영상, 인테리어, 그래픽, 유튜브, AI, 블렌더, 파이썬** 등의 키워드를 포함해 입력해 주세요."
        )

# ── 설계 결과 카드 표시 ───────────────────────────────────────────────────────
ai_res = st.session_state.ai_result

if ai_res:
    plan_min = ai_res["min"]
    plan_max = ai_res["max"]
    style    = ai_res["style"]

    st.markdown(
        f'<div class="section-title">✨ AI 설계 결과 — {ai_res["field_label"]}</div>',
        unsafe_allow_html=True,
    )

    show_min = style in ("both", "min")
    show_max = style in ("both", "max")
    card_cols = st.columns(2) if (show_min and show_max) else st.columns(1)

    def _course_tags(names: list[str], price_map: dict, dark: bool) -> str:
        tag_cls = "dc-course-tag-dark" if dark else "dc-course-tag"
        return "".join(
            f'<span class="{tag_cls}">{n} <b style="opacity:.7">{price_map.get(n,0):,}원</b></span>'
            for n in names
        )

    def _relation_html(relations: list[tuple], dark: bool) -> str:
        color = "#94a3b8" if dark else "#6b7280"
        rows = ""
        for course, desc in relations:
            # desc 안에 \n이 있으면 줄바꿈 처리
            desc_html = desc.replace("\n", "<br>")
            rows += (
                f'<div class="dc-relation-item" style="color:{color}">'
                f'<b style="color:{"#a5b4fc" if dark else "#e50012"}">{course}</b> — {desc_html}</div>'
            )
        return rows

    # ── 최소 카드 ─────────────────────────────────────────────────────────────
    if show_min:
        col = card_cols[0] if (show_min and show_max) else card_cols[0]
        with col:
            tags  = _course_tags(plan_min["courses"], price_map, dark=False)
            rels  = _relation_html(plan_min["relations"], dark=False)
            cnt   = len(plan_min["courses"])
            st.markdown(f"""
<div class="design-card design-card-min">
  <span class="dc-badge-min">⚡ 최소 과정</span>
  <div class="dc-field-label">{ai_res['field_label']}</div>
  <div class="dc-price-min">{fmt_won(plan_min['total'])}</div>
  <div style="color:#6b7280;font-size:.78rem;margin-bottom:.7rem">{cnt}개 과정</div>
  <div style="margin-bottom:.5rem">{tags}</div>
  <div class="dc-intent-min">{plan_min['intent']}</div>
  <div class="dc-relation-title">📌 과목별 설계 의도</div>
  {rels}
</div>
""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⚡ 최소 과정으로 적용하기", key="apply_ai_min",
                         use_container_width=True, type="primary"):
                st.session_state.selected_courses = plan_min["courses"]
                memo_lines = [f"[AI 설계 — {ai_res['field_label']} 최소 과정]", "",
                               plan_min["intent"], "",
                               "■ 과목별 설계 의도"] + \
                             [f"• {c}: {d.split(chr(10))[0]}" for c, d in plan_min["relations"]]
                st.session_state.ai_design_memo = "\n".join(memo_lines)
                st.rerun()

    # ── 최대 카드 ─────────────────────────────────────────────────────────────
    if show_max:
        col = card_cols[1] if (show_min and show_max) else card_cols[0]
        with col:
            tags  = _course_tags(plan_max["courses"], price_map, dark=True)
            rels  = _relation_html(plan_max["relations"], dark=True)
            cnt   = len(plan_max["courses"])
            st.markdown(f"""
<div class="design-card design-card-max">
  <span class="dc-badge-max">🚀 최대 과정</span>
  <div class="dc-field-label" style="color:#94a3b8">{ai_res['field_label']}</div>
  <div class="dc-price-max">{fmt_won(plan_max['total'])}</div>
  <div style="color:#64748b;font-size:.78rem;margin-bottom:.7rem">{cnt}개 과정</div>
  <div style="margin-bottom:.5rem">{tags}</div>
  <div class="dc-intent-max">{plan_max['intent']}</div>
  <div class="dc-relation-title" style="color:#94a3b8">📌 과목별 설계 의도</div>
  {rels}
</div>
""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 최대 과정으로 적용하기", key="apply_ai_max",
                         use_container_width=True):
                st.session_state.selected_courses = plan_max["courses"]
                memo_lines = [f"[AI 설계 — {ai_res['field_label']} 최대 과정]", "",
                               plan_max["intent"], "",
                               "■ 과목별 설계 의도"] + \
                             [f"• {c}: {d.split(chr(10))[0]}" for c, d in plan_max["relations"]]
                st.session_state.ai_design_memo = "\n".join(memo_lines)
                st.rerun()

    # 초기화 버튼
    if st.button("✕ 설계 결과 닫기", key="clear_ai_result"):
        st.session_state.ai_result = None
        st.session_state.ai_design_memo = ""
        st.rerun()

    st.markdown("---")


# ── 프리셋 트리거 처리 ────────────────────────────────────────────────────────
if st.session_state.preset_trigger:
    preset_courses = PRESETS[st.session_state.preset_trigger]["courses"]
    st.session_state.selected_courses = [c for c in preset_courses if c in price_map]
    st.session_state.preset_trigger = None


# ── 레이아웃: 과정 선택 | 합계 카드 ──────────────────────────────────────────
col_left, col_right = st.columns([3, 1.4], gap="large")

with col_left:
    st.markdown('<div class="section-title">📚 학과 선택</div>', unsafe_allow_html=True)

    all_cats = list(CATEGORY_MAP.keys())
    sel_depts = st.multiselect(
        "학과를 선택하세요 (복수 선택 가능)",
        options=all_cats,
        default=all_cats,
        label_visibility="collapsed",
    )

    # 선택 학과에 속하는 과정 필터
    filtered_courses = [
        c for c in all_courses
        if COURSE_TO_CAT.get(c, "기타") in (sel_depts or all_cats)
    ]

    # 현재 세션의 selected_courses 중 filtered에 있는 것만 default로
    current_valid = [c for c in st.session_state.selected_courses if c in filtered_courses]

    st.markdown('<div class="section-title">✅ 상세 과정 선택</div>', unsafe_allow_html=True)
    chosen = st.multiselect(
        "수강할 과정을 선택하세요",
        options=filtered_courses,
        default=current_valid,
        label_visibility="collapsed",
        key="course_multiselect",
    )
    st.session_state.selected_courses = chosen


with col_right:
    # ── 할인율 계산 (과목 수 기반) ─────────────────────────────────────────
    n = len(st.session_state.selected_courses)
    if disc_type == "페북/구디비/종강생":
        base_disc = 40 if n >= 4 else 30
    else:
        if n <= 1:   base_disc = 0
        elif n <= 3: base_disc = 10
        elif n <= 5: base_disc = 15
        elif n <= 7: base_disc = 20
        else:        base_disc = 25
    s_discount = min(base_disc + extra_disc, 40)

    df = build_df(st.session_state.selected_courses, price_map, s_discount)
    subtotal   = int(df["_price"].sum())  if not df.empty else 0
    after_pct  = int(df["_final"].sum())  if not df.empty else 0
    fixed_disc = int(review_won) + int(ddaza_won)
    total      = max(0, after_pct - fixed_disc)
    savings    = subtotal - total

    st.markdown('<div class="section-title">💰 합계</div>', unsafe_allow_html=True)

    # 따즈아 할인 조건 경고
    if ddaza_on and after_pct < 1_500_000:
        st.warning("따즈아 할인은 할인 적용 후 150만원 이상 시 가능합니다.")

    st.markdown(f"""
    <div class="total-card">
      <div class="total-label">최종 납부금액</div>
      <div class="total-amount">{fmt_won(total)}</div>
      <div class="total-savings">
        정가 합계 {fmt_won(subtotal)}<br>
        할인율 {s_discount}% · 절약 {fmt_won(savings)}
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.metric("선택 과정 수", f"{n}개  →  기본할인 {base_disc}%+{extra_disc}%")
    st.metric("정가 합계",   fmt_won(subtotal))
    if fixed_disc:
        st.metric("% 할인 후", fmt_won(after_pct))
        st.metric("추가 금액 할인", f"-{fmt_won(fixed_disc)}", delta_color="inverse")
    st.metric("최종 금액",   fmt_won(total),   delta=f"-{fmt_won(savings)}" if savings else None,
              delta_color="inverse")


# ── 수강료 테이블 ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📋 선택 과정 수강료 내역</div>', unsafe_allow_html=True)

if df.empty:
    st.info("위에서 과정을 선택하면 수강료 내역이 자동으로 표시됩니다.")
else:
    display_df = df[["과정명","정가","할인율","할인가","절약"]].reset_index(drop=True)
    display_df.index += 1
    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(38 * (len(display_df) + 2) + 10, 500),
    )


# ── 최소/최대 추천 커리큘럼 프리셋 ────────────────────────────────────────────
st.markdown('<div class="section-title">🎯 추천 커리큘럼 프리셋</div>', unsafe_allow_html=True)

preset_cols = st.columns(len(PRESETS))
for col, (label, info) in zip(preset_cols, PRESETS.items()):
    with col:
        st.markdown(f"<small style='color:#6b7280'>{info['desc']}</small>", unsafe_allow_html=True)
        if st.button(label, use_container_width=True, key=f"preset_{label}"):
            st.session_state.preset_trigger = label
            st.rerun()


# ── 저장 섹션 ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-title">💾 상담일지 저장</div>', unsafe_allow_html=True)

if df.empty:
    st.warning("과정을 선택한 뒤 저장할 수 있습니다.")
else:
    today_str   = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_file   = datetime.now().strftime("%Y%m%d_%H%M")
    client_name = s_name.strip() or "미입력"

    md_content   = build_md(client_name, s_contact, s_field, s_consultant, s_memo,
                             df, total, subtotal, savings, s_discount, today_str)
    html_content = build_html(client_name, s_contact, s_field, s_consultant, s_memo,
                               df, total, subtotal, savings, float(s_discount), today_str)

    btn_col1, btn_col2, btn_col3 = st.columns(3)

    # ① MD 저장 (파일 + 다운로드)
    with btn_col1:
        if st.button("📄 상담일지 MD 저장", use_container_width=True, type="primary"):
            fname = LOGS_DIR / f"상담일지_{client_name}_{date_file}.md"
            fname.write_text(md_content, encoding="utf-8")
            st.markdown(f'<div class="ok-banner">✅ 저장 완료: <code>{fname.name}</code></div>',
                        unsafe_allow_html=True)

        st.download_button(
            "⬇️ MD 다운로드",
            data=md_content.encode("utf-8"),
            file_name=f"상담일지_{client_name}_{date_file}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    # ② HTML 저장 (브라우저에서 인쇄 → PDF 가능)
    with btn_col2:
        if st.button("🌐 HTML 보고서 저장", use_container_width=True, type="primary"):
            fname = LOGS_DIR / f"상담일지_{client_name}_{date_file}.html"
            fname.write_text(html_content, encoding="utf-8")
            st.markdown(f'<div class="ok-banner">✅ 저장 완료: <code>{fname.name}</code><br>'
                        f'<small>브라우저에서 열고 Ctrl+P → PDF로 저장하세요.</small></div>',
                        unsafe_allow_html=True)

        st.download_button(
            "⬇️ HTML 다운로드",
            data=html_content.encode("utf-8"),
            file_name=f"상담일지_{client_name}_{date_file}.html",
            mime="text/html",
            use_container_width=True,
        )

    # ③ 두 파일 동시 저장
    with btn_col3:
        if st.button("💾 MD + HTML 동시 저장", use_container_width=True):
            for ext, content, enc in [
                ("md",   md_content,   "utf-8"),
                ("html", html_content, "utf-8"),
            ]:
                p = LOGS_DIR / f"상담일지_{client_name}_{date_file}.{ext}"
                p.write_text(content, encoding=enc)
            st.markdown(
                f'<div class="ok-banner">✅ 두 파일 저장 완료<br>'
                f'<code>logs/상담일지_{client_name}_{date_file}.md</code><br>'
                f'<code>logs/상담일지_{client_name}_{date_file}.html</code></div>',
                unsafe_allow_html=True,
            )
        st.caption("logs/ 폴더에 두 형식 모두 저장됩니다.")


# ── 푸터 ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#9ca3af;font-size:.8rem'>"
    "SBS아카데미 대전지점 상담 자동화 시스템 &nbsp;|&nbsp; "
    "데이터 출처: 수강료 엑셀 (2026.04.01 기준)</p>",
    unsafe_allow_html=True,
)
