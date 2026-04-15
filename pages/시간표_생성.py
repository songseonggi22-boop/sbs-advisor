"""
pages/시간표_생성.py — SBS아카데미 개인 시간표 생성 페이지
Streamlit multi-page app: streamlit run app.py
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import io
import re

import pandas as pd
import streamlit as st
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv

load_dotenv()

# ── 경로 ──────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).parent.parent
TIMETABLE_PATH = ROOT / "시간표.xlsx"
TEMPLATE_PATH  = Path(r"c:\Users\SBS\Desktop\SBS컴퓨터\★전체시간표 (양식).xlsx")

# ── 시간 표시 정규화 ───────────────────────────────────────────────────────────
_TIME_DISPLAY: dict[str, str] = {
    "9시":               "09:00~12:00",
    "11시":              "11:00~14:00",
    "14시":              "14:00~17:00",
    "16시":              "16:00~19:00",
    "17시":              "17:00~20:00",
    "19시(월수)":        "19:00~22:00 (월·수)",
    "19시(화목)":        "19:00~22:00 (화·목)",
    "14시(월)*4H":       "14:00~18:00 (월)",
    "12시(월)*4D":       "12:00~16:00 (월)",
    "14시(월)*4D":       "14:00~18:00 (월)",
    "19시(화)*3D":       "19:00~22:00 (화)",
}

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="시간표 생성 | SBS아카데미",
    page_icon="🗓️",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
  html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
  .sbs-header {
    background: linear-gradient(120deg,#1e3a5f 0%,#1F4E79 60%,#2563a8 100%);
    padding: 1.4rem 2rem; border-radius: 14px; margin-bottom: 1.4rem;
    box-shadow: 0 4px 24px rgba(31,78,121,.35);
  }
  .sbs-header h1 { margin:0; color:#fff; font-size:1.5rem; font-weight:900; }
  .sbs-header p  { margin:.3rem 0 0; color:rgba(255,255,255,.8); font-size:.9rem; }
  .stButton > button { border-radius: 10px !important; font-weight: 700 !important; }
  .stDownloadButton > button {
    background: #1F4E79 !important; color: #fff !important;
    border-radius: 10px !important; font-weight: 700 !important;
  }
  hr { border-color: #e5e7eb; margin: .6rem 0; }
</style>
""", unsafe_allow_html=True)

# ── 헤더 ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sbs-header">
  <h1>🗓️ 개인 시간표 생성</h1>
  <p>수강생 이름과 과정을 선택하면 개인 맞춤 시간표 엑셀 파일을 자동 생성합니다</p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 데이터 로드
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_timetable_data() -> dict:
    """시간표.xlsx 파싱 → {'평일': [...], '주말': [...]}"""
    if not TIMETABLE_PATH.exists():
        return {"평일": [], "주말": []}

    wb  = openpyxl.load_workbook(TIMETABLE_PATH)
    out: dict[str, list] = {}

    # ── 평일 ──────────────────────────────────────────────────────────────────
    ws   = wb["평일"]
    row1 = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    row2 = [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]
    col_ym: dict[int, tuple] = {}
    cur_year: int | None = None
    for i, (y, m) in enumerate(zip(row1, row2)):
        if y and "년" in str(y):
            cur_year = int(str(y).replace("년", ""))
        if m and "월" in str(m):
            col_ym[i + 1] = (cur_year, int(str(m).replace("월", "")))

    rows: list[dict] = []
    cur_dept = cur_time = None
    for r in range(3, ws.max_row + 1):
        dv = ws.cell(r, 1).value
        tv = ws.cell(r, 2).value
        if dv: cur_dept = str(dv).strip()
        if tv: cur_time = str(tv).strip()
        if not (cur_dept and cur_time):
            continue
        for col, (y, m) in col_ym.items():
            v = ws.cell(r, col).value
            if v:
                rows.append({
                    "dept":   cur_dept,
                    "time":   cur_time,
                    "year":   y,
                    "month":  m,
                    "course": str(v).split("\n")[0].strip(),
                })
    out["평일"] = rows

    # ── 주말 ──────────────────────────────────────────────────────────────────
    ws2   = wb["주말"]
    row1w = [ws2.cell(1, c).value for c in range(1, ws2.max_column + 1)]
    row2w = [ws2.cell(2, c).value for c in range(1, ws2.max_column + 1)]
    col_ym2: dict[int, tuple] = {}
    cur_year = None
    for i, (y, m) in enumerate(zip(row1w, row2w)):
        if y and "년" in str(y):
            cur_year = int(str(y).replace("년", ""))
        if m and "월" in str(m) and i >= 3:
            col_ym2[i + 1] = (cur_year, int(str(m).replace("월", "")))

    rows2: list[dict] = []
    cur_hall = cur_time2 = None
    for r in range(5, ws2.max_row + 1):
        hv = ws2.cell(r, 1).value
        tv = ws2.cell(r, 3).value
        if hv: cur_hall  = str(hv).strip()
        if tv: cur_time2 = str(tv).strip()
        if not (cur_hall and cur_time2):
            continue
        for col, (y, m) in col_ym2.items():
            v = ws2.cell(r, col).value
            if v:
                rows2.append({
                    "dept":   cur_hall,
                    "time":   cur_time2,
                    "year":   y,
                    "month":  m,
                    "course": str(v).split("\n")[0].strip(),
                })
    out["주말"] = rows2
    return out


def get_schedule_map(data: list[dict], dept: str, time_slot: str) -> dict:
    """(year, month) → course_name 딕셔너리."""
    sched: dict[tuple, str] = {}
    for row in data:
        if row["dept"] == dept and row["time"] == time_slot:
            key = (row["year"], row["month"])
            if key not in sched:
                sched[key] = row["course"]
    return dict(sorted(sched.items()))


# ══════════════════════════════════════════════════════════════════════════════
# 엑셀 생성
# ══════════════════════════════════════════════════════════════════════════════

def build_schedule_excel(student_name: str, entries: list[dict]) -> bytes:
    """개인 시간표 Excel 생성."""
    thin       = Side(style="thin", color="000000")
    border_all = Border(left=thin, right=thin, top=thin, bottom=thin)

    title_fill  = PatternFill("solid", fgColor="1F4E79")
    label_fill  = PatternFill("solid", fgColor="2E75B6")
    month_fill  = PatternFill("solid", fgColor="D6E4F0")
    type_fill   = PatternFill("solid", fgColor="BDD7EE")
    course_fill = PatternFill("solid", fgColor="FFFFFF")
    note_fill   = PatternFill("solid", fgColor="F0F4FA")

    # ── 워크북 준비 ───────────────────────────────────────────────────────────
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

    # ── 월 목록 ──────────────────────────────────────────────────────────────
    all_months = sorted({ym for e in entries for ym in e["schedule"].keys()})
    n_months   = len(all_months)
    last_col   = 1 + n_months

    # ── 열 너비 ──────────────────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 20
    for i in range(n_months):
        ws.column_dimensions[get_column_letter(i + 2)].width = 11

    # ── 행1: 제목 ────────────────────────────────────────────────────────────
    ws.row_dimensions[1].height = 32
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1,   end_column=max(last_col, 2))
    c           = ws.cell(1, 1)
    c.value     = f"SBS아카데미  {student_name}  개인 시간표"
    c.font      = Font(name="맑은 고딕", size=17, bold=True, color="FFFFFF")
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.fill      = title_fill
    c.border    = border_all

    # ── 행2: 구분 + 월 헤더 ──────────────────────────────────────────────────
    ws.row_dimensions[2].height = 32
    hdr = ws.cell(2, 1)
    hdr.value     = "구분  /  월"
    hdr.font      = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
    hdr.alignment = Alignment(horizontal="center", vertical="center")
    hdr.fill      = label_fill
    hdr.border    = border_all

    for i, (y, m) in enumerate(all_months):
        col = i + 2
        c   = ws.cell(2, col)
        c.value     = f"{y}년\n{m}월"
        c.font      = Font(name="맑은 고딕", size=10, bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.fill      = month_fill
        c.border    = border_all

    # ── 데이터 행 ─────────────────────────────────────────────────────────────
    cur_row  = 3
    prev_typ = None
    for entry in entries:
        # 평일/주말 구분선
        if entry["type"] != prev_typ and prev_typ is not None:
            ws.row_dimensions[cur_row].height = 6
            cur_row += 1
        prev_typ = entry["type"]

        disp_time  = _TIME_DISPLAY.get(entry["time"], entry["time"])
        label_text = f"[{entry['type']}]\n{entry['dept']}\n{disp_time}"

        ws.row_dimensions[cur_row].height = 56

        c = ws.cell(cur_row, 1)
        c.value     = label_text
        c.font      = Font(name="맑은 고딕", size=10, bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.fill      = type_fill
        c.border    = border_all

        for i, ym in enumerate(all_months):
            col  = i + 2
            cell = ws.cell(cur_row, col)
            cell.value     = entry["schedule"].get(ym, "")
            cell.font      = Font(name="맑은 고딕", size=10)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.fill      = course_fill
            cell.border    = border_all

        cur_row += 1

    # ── 비고 행 ──────────────────────────────────────────────────────────────
    cur_row += 1
    ws.row_dimensions[cur_row].height = 72

    c = ws.cell(cur_row, 1)
    c.value     = "비고"
    c.font      = Font(name="맑은 고딕", size=12, bold=True, color="FFFFFF")
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.fill      = label_fill
    c.border    = border_all

    if last_col > 1:
        ws.merge_cells(
            start_row=cur_row, start_column=2,
            end_row=cur_row,   end_column=max(last_col, 2),
        )
    note = ws.cell(cur_row, 2)
    note.value       = ""
    note.font        = Font(name="맑은 고딕", size=11)
    note.alignment   = Alignment(horizontal="left", vertical="center", wrap_text=True)
    note.fill        = note_fill
    note.border      = border_all

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

tt_data = load_timetable_data()

if not tt_data["평일"] and not tt_data["주말"]:
    st.error("⚠️ 시간표.xlsx 파일을 찾을 수 없습니다. 프로젝트 폴더를 확인해 주세요.")
    st.stop()

# ── 수강생 이름 ───────────────────────────────────────────────────────────────
st.markdown("### 👤 수강생 정보")
col_name, _ = st.columns([1, 2])
with col_name:
    student_name = st.text_input(
        "수강생 이름",
        placeholder="홍길동",
        help="생성될 파일 제목에 사용됩니다.",
    )

st.markdown("---")

# ── 과정 선택 ─────────────────────────────────────────────────────────────────
st.markdown("### 📋 수강 과정 선택")
st.caption("평일·주말 각각 최대 3개 과정을 선택할 수 있습니다.")

entries: list[dict] = []


def course_selector(slot_key: str, sheet_type: str, sheet_data: list[dict]):
    """학과·시간 선택 UI → entry dict 반환."""
    depts = sorted({r["dept"] for r in sheet_data})
    if not depts:
        st.info(f"{sheet_type} 데이터 없음")
        return None

    col_a, col_b = st.columns([1, 1])
    with col_a:
        dept = st.selectbox(
            "학과 / 강의장",
            ["(선택 안 함)"] + depts,
            key=f"dept_{slot_key}",
        )
    if dept == "(선택 안 함)":
        return None

    times = sorted({r["time"] for r in sheet_data if r["dept"] == dept})
    with col_b:
        time_sel = st.selectbox(
            "시간대",
            times,
            format_func=lambda t: f"{t}  →  {_TIME_DISPLAY.get(t, t)}",
            key=f"time_{slot_key}",
        )

    schedule = get_schedule_map(sheet_data, dept, time_sel)

    if schedule:
        preview = [{"연도": y, "월": f"{m}월", "과정": c} for (y, m), c in schedule.items()]
        with st.expander(
            f"📅 [{dept}] {time_sel} 커리큘럼 미리보기 — {len(schedule)}개월",
            expanded=False,
        ):
            st.dataframe(pd.DataFrame(preview), hide_index=True, use_container_width=True)

    return {"type": sheet_type, "dept": dept, "time": time_sel, "schedule": schedule}


# 평일
with st.expander("📌 평일 과정", expanded=True):
    for idx in range(3):
        st.markdown(f"**평일 과정 {idx + 1}**")
        entry = course_selector(f"wd_{idx}", "평일", tt_data["평일"])
        if entry and entry["schedule"]:
            entries.append(entry)
        if idx < 2:
            st.markdown("<hr>", unsafe_allow_html=True)

# 주말
with st.expander("📌 주말 과정", expanded=False):
    for idx in range(3):
        st.markdown(f"**주말 과정 {idx + 1}**")
        entry = course_selector(f"we_{idx}", "주말", tt_data["주말"])
        if entry and entry["schedule"]:
            entries.append(entry)
        if idx < 2:
            st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("---")

# ── 생성 버튼 ─────────────────────────────────────────────────────────────────
if st.button("📥 시간표 엑셀 생성", type="primary", use_container_width=True):
    if not student_name.strip():
        st.warning("⚠️ 수강생 이름을 입력해 주세요.")
    elif not entries:
        st.warning("⚠️ 평일 또는 주말 과정을 최소 1개 선택해 주세요.")
    else:
        with st.spinner("엑셀 파일 생성 중..."):
            xlsx_bytes = build_schedule_excel(student_name.strip(), entries)

        safe_name = re.sub(r'[\\/:*?"<>|]', "_", student_name.strip())
        fname     = f"SBS_{safe_name}_시간표_{datetime.now().strftime('%Y%m%d')}.xlsx"

        st.success(f"✅ **{student_name}** 수강생 개인 시간표 생성 완료!")

        # 과정 요약
        rows_html = ""
        for e in entries:
            disp   = _TIME_DISPLAY.get(e["time"], e["time"])
            months = sorted(e["schedule"].keys())
            s_ym   = f"{months[0][0]}년 {months[0][1]}월" if months else "-"
            e_ym   = f"{months[-1][0]}년 {months[-1][1]}월" if months else "-"
            rows_html += (
                f"<tr><td style='padding:.3rem .8rem'><b>[{e['type']}]</b></td>"
                f"<td style='padding:.3rem .8rem'>{e['dept']}</td>"
                f"<td style='padding:.3rem .8rem'>{disp}</td>"
                f"<td style='padding:.3rem .8rem'>{s_ym} ~ {e_ym}</td>"
                f"<td style='padding:.3rem .8rem;text-align:center'>{len(e['schedule'])}개월</td></tr>"
            )
        st.markdown(
            f"<div style='background:#eff6ff;border:1.5px solid #3b82f6;"
            f"border-radius:10px;padding:1rem 1.2rem;margin:.8rem 0;overflow-x:auto'>"
            f"<b>📋 선택 과정 요약</b>"
            f"<table style='width:100%;border-collapse:collapse;margin-top:.6rem;font-size:.9rem'>"
            f"<thead><tr style='background:#dbeafe'>"
            f"<th style='padding:.3rem .8rem;text-align:left'>구분</th>"
            f"<th style='padding:.3rem .8rem;text-align:left'>학과</th>"
            f"<th style='padding:.3rem .8rem;text-align:left'>시간</th>"
            f"<th style='padding:.3rem .8rem;text-align:left'>기간</th>"
            f"<th style='padding:.3rem .8rem'>개월수</th></tr></thead>"
            f"<tbody>{rows_html}</tbody></table></div>",
            unsafe_allow_html=True,
        )

        st.download_button(
            label="⬇️ 시간표 다운로드",
            data=xlsx_bytes,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

# ── 푸터 ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#9ca3af;font-size:.8rem'>"
    "SBS아카데미 대전지점 &nbsp;|&nbsp; 시간표 생성 시스템</p>",
    unsafe_allow_html=True,
)
