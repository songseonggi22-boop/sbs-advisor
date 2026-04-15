"""
pages/시간표_생성.py — SBS아카데미 과정 검색 & 개인 시간표 생성
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import io, re
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv

load_dotenv()

ROOT           = Path(__file__).parent.parent
TIMETABLE_PATH = ROOT / "시간표.xlsx"
TEMPLATE_PATH  = Path(r"c:\Users\SBS\Desktop\SBS컴퓨터\★전체시간표 (양식).xlsx")

_TIME_DISPLAY: dict[str, str] = {
    "9시":         "09:00~12:00",
    "11시":        "11:00~14:00",
    "14시":        "14:00~17:00",
    "16시":        "16:00~19:00",
    "17시":        "17:00~20:00",
    "19시(월수)":  "19:00~22:00 (월·수)",
    "19시(화목)":  "19:00~22:00 (화·목)",
    "14시(금)*4H": "14:00~18:00 (금)",
    "12시(금)*4D": "12:00~16:00 (금)",
    "14시(금)*4D": "14:00~18:00 (금)",
    "19시(금)*3D": "19:00~22:00 (금)",
}

WEEKDAY_KR = {"월": "월", "화": "화", "수": "수", "목": "목", "금": "금", "토": "토", "일": "일"}

# ══════════════════════════════════════════════════════════════════════════════
# 데이터 모델
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CourseHit:
    """검색 결과 한 건."""
    course:   str          # 정규화된 과정명
    raw_name: str          # 원본 셀 텍스트
    sheet:    str          # "평일" / "주말"
    dept:     str          # 학과 or 강의장
    time:     str          # 원본 시간 키
    year:     int
    month:    int
    day:      int | None   # 주말만 있음
    weekday:  str | None   # "토" / "일"
    instructor: str | None # 강사명 (셀에 \n으로 붙어있는 경우)
    info:     str | None   # "3H*8일" 등 주말 부가정보

    @property
    def time_display(self) -> str:
        return _TIME_DISPLAY.get(self.time, self.time)

    @property
    def date_label(self) -> str:
        if self.day:
            return f"{self.year}년 {self.month}월 {self.day}일({self.weekday})"
        return f"{self.year}년 {self.month}월"


# ══════════════════════════════════════════════════════════════════════════════
# 파싱
# ══════════════════════════════════════════════════════════════════════════════

def _parse_cell(raw: str) -> tuple[str, str | None, str | None]:
    """셀 원본값 → (과정명, 강사명_or_None, 부가정보_or_None)
    예) "프리미어\n윤진"  → ("프리미어", "윤진", None)
        "에펙/주말\n3H*8일" → ("에펙",    None,   "3H*8일")
    """
    raw = raw.strip()
    lines = raw.split("\n")
    first = lines[0].strip()

    # 주말 과정: "과정명/주말"
    if "/주말" in first:
        name = first.split("/주말")[0].strip()
        info = lines[1].strip() if len(lines) > 1 else None
        return name, None, info

    # 평일: 두 번째 줄이 있으면 강사명
    name = first
    instructor = lines[1].strip() if len(lines) > 1 else None
    return name, instructor, None


@st.cache_resource(show_spinner=False)
def load_all_hits() -> list[CourseHit]:
    """시간표.xlsx 전체를 파싱해 CourseHit 리스트로 반환."""
    if not TIMETABLE_PATH.exists():
        return []

    wb   = openpyxl.load_workbook(TIMETABLE_PATH)
    hits: list[CourseHit] = []

    # ── 평일 ──────────────────────────────────────────────────────────────────
    ws = wb["평일"]
    r1 = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    r2 = [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]

    col_ym: dict[int, tuple[int, int]] = {}
    cy = None
    for i, (y, m) in enumerate(zip(r1, r2)):
        if y and "년" in str(y):
            cy = int(str(y).replace("년", ""))
        if m and "월" in str(m):
            col_ym[i + 1] = (cy, int(str(m).replace("월", "")))

    cur_dept = cur_time = None
    for r in range(3, ws.max_row + 1):
        dv = ws.cell(r, 1).value
        tv = ws.cell(r, 2).value
        if dv: cur_dept = str(dv).strip()
        if tv: cur_time = str(tv).strip()
        if not (cur_dept and cur_time):
            continue
        for col, (yr, mo) in col_ym.items():
            raw = ws.cell(r, col).value
            if not raw or not isinstance(raw, str):
                continue
            name, instr, info = _parse_cell(raw)
            if not name or len(name) > 25:
                continue
            hits.append(CourseHit(
                course=name, raw_name=raw,
                sheet="평일", dept=cur_dept, time=cur_time,
                year=yr, month=mo, day=None, weekday=None,
                instructor=instr, info=info,
            ))

    # ── 주말 ──────────────────────────────────────────────────────────────────
    ws2 = wb["주말"]
    r1w = [ws2.cell(1, c).value for c in range(1, ws2.max_column + 1)]
    r2w = [ws2.cell(2, c).value for c in range(1, ws2.max_column + 1)]
    r3w = [ws2.cell(3, c).value for c in range(1, ws2.max_column + 1)]
    r4w = [ws2.cell(4, c).value for c in range(1, ws2.max_column + 1)]

    col_date: dict[int, dict] = {}
    cy = cm = None
    for i, (y, m, wd, d) in enumerate(zip(r1w, r2w, r3w, r4w)):
        if y and "년" in str(y):
            cy = int(str(y).replace("년", ""))
        if m and "월" in str(m):
            cm = int(str(m).replace("월", ""))
        if i >= 3 and d and isinstance(d, (int, float)):
            col_date[i + 1] = {
                "year":    cy,
                "month":   cm,
                "day":     int(d),
                "weekday": str(wd).strip() if wd else "",
            }

    cur_hall = cur_time2 = None
    for r in range(5, ws2.max_row + 1):
        hv = ws2.cell(r, 1).value
        tv = ws2.cell(r, 3).value
        if hv: cur_hall  = str(hv).strip()
        if tv: cur_time2 = str(tv).strip()
        if not (cur_hall and cur_time2):
            continue
        for col, date_info in col_date.items():
            raw = ws2.cell(r, col).value
            if not raw or not isinstance(raw, str):
                continue
            name, instr, info = _parse_cell(raw)
            if not name or len(name) > 30:
                continue
            hits.append(CourseHit(
                course=name, raw_name=raw,
                sheet="주말", dept=cur_hall, time=cur_time2,
                year=date_info["year"], month=date_info["month"],
                day=date_info["day"], weekday=date_info["weekday"],
                instructor=instr, info=info,
            ))

    return hits


def build_search_index(hits: list[CourseHit]) -> dict[str, list[CourseHit]]:
    """과정명 → hits 역색인."""
    idx: dict[str, list[CourseHit]] = {}
    for h in hits:
        idx.setdefault(h.course, []).append(h)
    return idx


def search(index: dict[str, list[CourseHit]], keyword: str) -> dict[str, list[CourseHit]]:
    """포함 검색 (대소문자·공백 무시)."""
    kw = keyword.strip().lower().replace(" ", "")
    if not kw:
        return {}
    return {
        name: hits
        for name, hits in index.items()
        if kw in name.lower().replace(" ", "")
    }


# ══════════════════════════════════════════════════════════════════════════════
# 엑셀 생성
# ══════════════════════════════════════════════════════════════════════════════

def build_excel(student_name: str, cart: list[dict]) -> bytes:
    thin = Side(style="thin", color="000000")
    b    = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left   = Alignment(horizontal="left",   vertical="center", wrap_text=True)

    title_fill  = PatternFill("solid", fgColor="1F4E79")
    label_fill  = PatternFill("solid", fgColor="2E75B6")
    month_fill  = PatternFill("solid", fgColor="D6E4F0")
    row_fill    = PatternFill("solid", fgColor="EBF3FB")
    course_fill = PatternFill("solid", fgColor="FFFFFF")
    note_fill   = PatternFill("solid", fgColor="F0F4FA")

    # 워크북
    if TEMPLATE_PATH.exists():
        wb = openpyxl.load_workbook(TEMPLATE_PATH)
        ws = wb.active
        for rng in list(ws.merged_cells.ranges):
            ws.unmerge_cells(str(rng))
        for r in range(1, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                ws.cell(r, c).value = None
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
    ws.title = f"{student_name} 시간표"

    # 월 목록 수집 (cart 전체)
    all_months = sorted({
        (item["year"], item["month"])
        for item in cart
    })
    n = len(all_months)
    last_col = 1 + n

    # 열 너비
    ws.column_dimensions["A"].width = 22
    for i in range(n):
        ws.column_dimensions[get_column_letter(i + 2)].width = 12

    # 행1: 제목
    ws.row_dimensions[1].height = 32
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(last_col, 2))
    c = ws.cell(1, 1)
    c.value, c.font, c.alignment, c.fill, c.border = (
        f"SBS아카데미  {student_name}  개인 시간표",
        Font(name="맑은 고딕", size=17, bold=True, color="FFFFFF"),
        Alignment(horizontal="center", vertical="center"),
        title_fill, b,
    )

    # 행2: 구분 + 월 헤더
    ws.row_dimensions[2].height = 34
    hc = ws.cell(2, 1)
    hc.value, hc.font, hc.alignment, hc.fill, hc.border = (
        "과정명  /  월",
        Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF"),
        center, label_fill, b,
    )
    for i, (yr, mo) in enumerate(all_months):
        c = ws.cell(2, i + 2)
        c.value     = f"{yr}년\n{mo}월"
        c.font      = Font(name="맑은 고딕", size=10, bold=True)
        c.alignment = center
        c.fill      = month_fill
        c.border    = b

    # 데이터 행
    cur_row  = 3
    prev_sheet = None
    for item in cart:
        if item["sheet"] != prev_sheet and prev_sheet is not None:
            ws.row_dimensions[cur_row].height = 5
            cur_row += 1
        prev_sheet = item["sheet"]

        ws.row_dimensions[cur_row].height = 46

        disp_time = _TIME_DISPLAY.get(item["time"], item["time"])
        label = (
            f"{item['course']}\n"
            f"[{item['sheet']}] {item['dept']}\n"
            f"{disp_time}"
        )
        lc = ws.cell(cur_row, 1)
        lc.value, lc.font, lc.alignment, lc.fill, lc.border = (
            label,
            Font(name="맑은 고딕", size=9, bold=True),
            center, row_fill, b,
        )

        for i, (yr, mo) in enumerate(all_months):
            cell = ws.cell(cur_row, i + 2)
            # 이 과목이 해당 월에 있으면 과정명 표시
            val = item["course"] if (item["year"], item["month"]) == (yr, mo) else ""
            cell.value     = val
            cell.font      = Font(name="맑은 고딕", size=10)
            cell.alignment = center
            cell.fill      = course_fill
            cell.border    = b

        cur_row += 1

    # 비고
    cur_row += 1
    ws.row_dimensions[cur_row].height = 68
    nc = ws.cell(cur_row, 1)
    nc.value, nc.font, nc.alignment, nc.fill, nc.border = (
        "비고",
        Font(name="맑은 고딕", size=12, bold=True, color="FFFFFF"),
        center, label_fill, b,
    )
    if last_col > 1:
        ws.merge_cells(start_row=cur_row, start_column=2,
                       end_row=cur_row,   end_column=max(last_col, 2))
    note = ws.cell(cur_row, 2)
    note.font, note.alignment, note.fill, note.border = (
        Font(name="맑은 고딕", size=11), left, note_fill, b,
    )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# Streamlit 페이지
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="시간표 검색 | SBS아카데미",
    page_icon="🔍",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans KR',sans-serif;}
.sbs-header{
  background:linear-gradient(120deg,#1e3a5f 0%,#1F4E79 60%,#2563a8 100%);
  padding:1.2rem 2rem;border-radius:14px;margin-bottom:1.2rem;
  box-shadow:0 4px 24px rgba(31,78,121,.35);
}
.sbs-header h1{margin:0;color:#fff;font-size:1.45rem;font-weight:900;}
.sbs-header p{margin:.25rem 0 0;color:rgba(255,255,255,.8);font-size:.88rem;}
.hit-card{
  background:#f8fafc;border:1.5px solid #e2e8f0;
  border-radius:10px;padding:.7rem 1rem;margin-bottom:.5rem;
}
.hit-card:hover{border-color:#3b82f6;background:#eff6ff;}
.hit-title{font-size:1rem;font-weight:700;color:#1e3a5f;}
.hit-meta{font-size:.82rem;color:#64748b;margin-top:.2rem;}
.hit-dates{font-size:.82rem;color:#374151;margin-top:.3rem;}
.cart-item{
  background:#eff6ff;border:1.5px solid #bfdbfe;
  border-radius:8px;padding:.55rem .9rem;margin-bottom:.4rem;
  display:flex;justify-content:space-between;align-items:center;
}
.cart-title{font-weight:700;color:#1e40af;font-size:.93rem;}
.cart-meta{font-size:.78rem;color:#64748b;}
.stButton>button{border-radius:8px!important;}
.stDownloadButton>button{
  background:#1F4E79!important;color:#fff!important;
  border-radius:8px!important;font-weight:700!important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sbs-header">
  <h1>🔍 과정 검색 · 개인 시간표 생성</h1>
  <p>과정명을 검색하면 수업이 몇 월에 열리는지 바로 확인할 수 있습니다</p>
</div>
""", unsafe_allow_html=True)

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
if not TIMETABLE_PATH.exists():
    st.error("⚠️ 시간표.xlsx 파일을 찾을 수 없습니다.")
    st.stop()

all_hits = load_all_hits()
idx      = build_search_index(all_hits)

# ── session_state 초기화 ──────────────────────────────────────────────────────
if "cart" not in st.session_state:
    st.session_state.cart = []   # list of dict


def add_to_cart(hit: CourseHit):
    item = {
        "course":  hit.course,
        "sheet":   hit.sheet,
        "dept":    hit.dept,
        "time":    hit.time,
        "year":    hit.year,
        "month":   hit.month,
        "day":     hit.day,
        "weekday": hit.weekday,
        "info":    hit.info,
        "instructor": hit.instructor,
    }
    # 중복 체크 (같은 과정+학과+시간+연월)
    key = (item["course"], item["dept"], item["time"], item["year"], item["month"])
    exists = any(
        (c["course"], c["dept"], c["time"], c["year"], c["month"]) == key
        for c in st.session_state.cart
    )
    if not exists:
        st.session_state.cart.append(item)


# ══════════════════════════════════════════════════════════════════════════════
# 레이아웃: 좌(검색) / 우(장바구니)
# ══════════════════════════════════════════════════════════════════════════════
col_search, col_cart = st.columns([3, 2], gap="large")

# ── 왼쪽: 검색 ───────────────────────────────────────────────────────────────
with col_search:
    st.markdown("### 🔍 과정 검색")

    keyword = st.text_input(
        "과정명 입력",
        placeholder="에펙, 캐드, 마야1, 컴활1급 ...",
        label_visibility="collapsed",
    )

    if keyword.strip():
        results = search(idx, keyword)

        if not results:
            st.info("검색 결과가 없습니다. 다른 키워드를 입력해 보세요.")
        else:
            st.caption(f"**{len(results)}개** 과정 검색됨")

            for course_name, hits in sorted(results.items()):
                # 같은 과정을 (sheet, dept, time)별로 묶기
                groups: dict[tuple, list[CourseHit]] = {}
                for h in hits:
                    gk = (h.sheet, h.dept, h.time)
                    groups.setdefault(gk, []).append(h)

                for (sheet, dept, time), g_hits in groups.items():
                    disp_time = _TIME_DISPLAY.get(time, time)

                    # 날짜 목록 구성
                    if sheet == "주말":
                        date_strs = [
                            f"{h.year}년 {h.month}월 {h.day}일({h.weekday})"
                            for h in sorted(g_hits, key=lambda x: (x.year, x.month, x.day or 0))
                        ]
                        dates_text = ", ".join(date_strs[:5])
                        if len(date_strs) > 5:
                            dates_text += f" 외 {len(date_strs)-5}일"
                        extra = g_hits[0].info or ""
                    else:
                        months_sorted = sorted(
                            {(h.year, h.month) for h in g_hits}
                        )
                        dates_text = "  /  ".join(
                            f"{y}년 {m}월" for y, m in months_sorted
                        )
                        extra = g_hits[0].instructor or ""

                    instr_badge = (
                        f" &nbsp;<span style='color:#7c3aed;font-size:.78rem'>"
                        f"👨‍🏫 {extra}</span>"
                    ) if extra else ""

                    sheet_color = "#2563a8" if sheet == "평일" else "#059669"
                    sheet_badge = (
                        f"<span style='background:{sheet_color};color:#fff;"
                        f"border-radius:5px;padding:.1rem .45rem;font-size:.75rem;"
                        f"font-weight:700;margin-right:.4rem'>{sheet}</span>"
                    )

                    st.markdown(
                        f"<div class='hit-card'>"
                        f"<div class='hit-title'>{sheet_badge}{course_name}{instr_badge}</div>"
                        f"<div class='hit-meta'>📍 {dept} &nbsp;·&nbsp; {disp_time}</div>"
                        f"<div class='hit-dates'>📅 {dates_text}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                    # 평일: 월별로 추가 버튼 / 주말: 전체 한꺼번에 추가
                    if sheet == "평일":
                        months_sorted = sorted(
                            {(h.year, h.month) for h in g_hits}
                        )
                        btn_cols = st.columns(min(len(months_sorted), 6))
                        for i, (yr, mo) in enumerate(months_sorted):
                            rep_hit = next(
                                (h for h in g_hits if h.year == yr and h.month == mo),
                                g_hits[0],
                            )
                            with btn_cols[i % len(btn_cols)]:
                                if st.button(
                                    f"+ {yr}년 {mo}월",
                                    key=f"add_{course_name}_{dept}_{time}_{yr}_{mo}",
                                    use_container_width=True,
                                ):
                                    add_to_cart(rep_hit)
                                    st.rerun()
                    else:
                        if st.button(
                            f"+ {course_name} 전체 일정 추가 ({len(date_strs)}일)",
                            key=f"add_{course_name}_{dept}_{time}_all",
                            use_container_width=True,
                        ):
                            for h in sorted(g_hits, key=lambda x: (x.year, x.month, x.day or 0)):
                                add_to_cart(h)
                            st.rerun()

    else:
        # 검색 전: 전체 과정 목록 요약
        all_courses = sorted(idx.keys())
        st.caption(f"총 **{len(all_courses)}개** 과정이 등록되어 있습니다")
        tags_html = " ".join(
            f"<span style='background:#e2e8f0;border-radius:5px;"
            f"padding:.15rem .5rem;font-size:.8rem;margin:.1rem .1rem;"
            f"display:inline-block'>{c}</span>"
            for c in all_courses
        )
        st.markdown(
            f"<div style='line-height:2;margin-top:.5rem'>{tags_html}</div>",
            unsafe_allow_html=True,
        )


# ── 오른쪽: 장바구니 ──────────────────────────────────────────────────────────
with col_cart:
    cart = st.session_state.cart
    n_cart = len(cart)

    st.markdown(f"### 🛒 선택한 과목 ({n_cart}개)")

    if not cart:
        st.markdown(
            "<div style='background:#f8fafc;border:2px dashed #cbd5e1;"
            "border-radius:10px;padding:2rem;text-align:center;color:#94a3b8'>"
            "아직 선택한 과목이 없어요<br>"
            "<span style='font-size:.85rem'>검색 결과에서 + 버튼을 눌러 추가하세요</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        for i, item in enumerate(cart):
            disp_time = _TIME_DISPLAY.get(item["time"], item["time"])
            sheet_color = "#2563a8" if item["sheet"] == "평일" else "#059669"

            if item.get("day"):
                date_str = f"{item['year']}년 {item['month']}월 {item['day']}일({item.get('weekday','')})"
            else:
                date_str = f"{item['year']}년 {item['month']}월"

            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f"<div class='cart-item'>"
                    f"<div>"
                    f"<span class='cart-title'>{item['course']}</span> "
                    f"<span style='background:{sheet_color};color:#fff;border-radius:4px;"
                    f"padding:.05rem .35rem;font-size:.72rem;font-weight:700'>{item['sheet']}</span><br>"
                    f"<span class='cart-meta'>📍 {item['dept']} · {disp_time}</span><br>"
                    f"<span class='cart-meta'>📅 {date_str}</span>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("✕", key=f"del_{i}", help="제거"):
                    st.session_state.cart.pop(i)
                    st.rerun()

        if st.button("🗑️ 전체 비우기", use_container_width=True):
            st.session_state.cart = []
            st.rerun()

        st.markdown("---")

        # ── 엑셀 생성 ────────────────────────────────────────────────────────
        st.markdown("#### 📥 시간표 생성")
        student_name = st.text_input(
            "수강생 이름",
            placeholder="홍길동",
            key="student_name_input",
        )

        if st.button("📊 엑셀 시간표 만들기", type="primary", use_container_width=True):
            if not student_name.strip():
                st.warning("수강생 이름을 입력해 주세요.")
            else:
                with st.spinner("생성 중..."):
                    xlsx = build_excel(student_name.strip(), cart)

                safe = re.sub(r'[\\/:*?"<>|]', "_", student_name.strip())
                fname = f"SBS_{safe}_시간표_{datetime.now().strftime('%Y%m%d')}.xlsx"
                st.success("✅ 생성 완료!")
                st.download_button(
                    "⬇️ 다운로드",
                    data=xlsx,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

# ── 푸터 ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#9ca3af;font-size:.78rem'>"
    "SBS아카데미 대전지점 · 시간표 검색 시스템</p>",
    unsafe_allow_html=True,
)
