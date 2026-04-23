"""
pages/시간표_생성.py — SBS아카데미 과정 검색 & 개인 시간표 생성
데이터 소스: SBS평일/*.xls, SBS주말/*.xls (HTML 형식 강의시간표)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import io, re

import pandas as pd
import streamlit as st
import openpyxl
from bs4 import BeautifulSoup
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

ROOT           = Path(__file__).parent.parent
WEEKDAY_DIR    = ROOT / "SBS평일"
WEEKEND_DIR    = ROOT / "SBS주말"
TEMPLATE_PATH  = ROOT / "★전체시간표 (양식).xlsx"

# ══════════════════════════════════════════════════════════════════════════════
# 데이터 모델
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CourseEntry:
    name:       str          # 과정명
    room:       str          # 강의실 (A-1 등)
    start_time: str          # 시작 시간 (09:00)
    end_time:   str          # 종료 시간 (11:00)
    instructor: str          # 강사명
    days:       str          # 수업 요일 (월~목, 토/일 등)
    start_date: str          # 개강일 YYYY-MM-DD
    end_date:   str          # 종강일 YYYY-MM-DD
    capacity:   str          # 정원
    enrolled:   str          # 배정
    sheet:      str          # "평일" / "주말"
    source:     str          # 파일명

    @property
    def period_label(self) -> str:
        """2026-04-13 ~ 2026-05-11 형태."""
        if self.start_date and self.end_date:
            return f"{self.start_date}  ~  {self.end_date}"
        return self.start_date or self.end_date or "-"

    @property
    def month_label(self) -> str:
        """4월 ~ 5월 형태."""
        try:
            s = datetime.strptime(self.start_date, "%Y-%m-%d")
            e = datetime.strptime(self.end_date,   "%Y-%m-%d")
            if s.month == e.month:
                return f"{s.year}년 {s.month}월"
            return f"{s.year}년 {s.month}월 ~ {e.month}월"
        except Exception:
            return self.period_label


# ══════════════════════════════════════════════════════════════════════════════
# 파싱
# ══════════════════════════════════════════════════════════════════════════════

def _calc_end_time(start_time: str, rowspan: int) -> str:
    """시작 시간(HH:MM) + rowspan × 30분 → 종료 시간."""
    from datetime import timedelta
    try:
        dt = datetime.strptime(start_time, "%H:%M")
        dt += timedelta(minutes=30 * rowspan)
        return dt.strftime("%H:%M")
    except Exception:
        return ''


def _parse_cell_text(text: str) -> tuple[str, str, str, str, str] | None:
    """
    셀 텍스트 → (과정명, 강사, 요일, 개강일, 종강일) or None
    예) "에펙전체출석율 : 60%...배정:28윤진3월~목개:2026-04-13종:2026-05-11"
    """
    text = text.strip()
    if not text:
        return None

    # 과정명: "전체출석율" 또는 "수업없음" 앞
    m_name = re.match(r'^(.+?)(?:전체출석율|수업없음)', text)
    if not m_name:
        return None
    name = m_name.group(1).strip()
    # /주말 제거
    name = re.sub(r'/주말.*', '', name).strip()
    if not name or len(name) > 40:
        return None
    # 숫자·특수문자만인 것 제외
    if re.fullmatch(r'[\d\W]+', name):
        return None

    # 개강·종강일
    m_start = re.search(r'개:(\d{4}-\d{2}-\d{2})', text)
    m_end   = re.search(r'종:(\d{4}-\d{2}-\d{2})', text)
    start_date = m_start.group(1) if m_start else ''
    end_date   = m_end.group(1)   if m_end   else ''

    # 강사명 + 요일 패턴
    # "배정:28윤진3월~목" 또는 "배정:12(W:0,R:1)김혜정5토/일"
    m_instr = re.search(
        r'배정:\d+(?:\([^)]*\))?([가-힣]{2,5})\d*([월화수목금토일][~\/][월화수목금토일])',
        text
    )
    instructor = m_instr.group(1) if m_instr else ''
    days       = m_instr.group(2) if m_instr else ''

    return name, instructor, days, start_date, end_date


def _load_xls_file(fp: Path, sheet: str) -> list[CourseEntry]:
    """HTML 형식 .xls 파일 하나 파싱 → CourseEntry 리스트."""
    entries: list[CourseEntry] = []
    try:
        raw  = fp.read_bytes().decode('utf-8', errors='replace')
        soup = BeautifulSoup(raw, 'html.parser')
        tbl  = soup.find('table')
        if not tbl:
            return entries

        rows = tbl.find_all('tr')
        if len(rows) < 4:
            return entries

        # 헤더 행들에서 강의실(서브룸) 이름 추출 (행2 기준)
        room_map: dict[int, str] = {}   # col_index → room_name
        sub_row = rows[1] if len(rows) > 1 else rows[0]
        col_idx = 0
        for td in sub_row.find_all(['td', 'th']):
            span = int(td.get('colspan', 1))
            val  = td.get_text(strip=True)
            if val and val not in ('', '정원'):
                for k in range(span):
                    room_map[col_idx + k] = val
            col_idx += span

        # 데이터 행 (행4 이후: 시간 + 강의실별 과정)
        cur_time = ''
        for row in rows[3:]:
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue

            # 첫 번째 셀: 시간
            first_val = cells[0].get_text(strip=True)
            if re.match(r'^\d{2}:\d{2}$', first_val):
                cur_time = first_val

            # 나머지 셀들
            data_col = 1   # room_map 인덱스: row1의 첫 셀(빈 코너셀)이 col0이므로 1부터 시작
            for i, td in enumerate(cells[1:], start=1):
                span    = int(td.get('colspan', 1))
                rowspan = int(td.get('rowspan', 1))
                text    = td.get_text(strip=True)
                room    = room_map.get(data_col, f'Col{data_col}')
                parsed  = _parse_cell_text(text)
                if parsed:
                    name, instr, days, sd, ed = parsed
                    end_time = _calc_end_time(cur_time, rowspan)
                    entries.append(CourseEntry(
                        name=name, room=room,
                        start_time=cur_time,
                        end_time=end_time,
                        instructor=instr, days=days,
                        start_date=sd, end_date=ed,
                        capacity='', enrolled='',
                        sheet=sheet, source=fp.name,
                    ))
                data_col += span

    except Exception:
        pass
    return entries


@st.cache_resource(show_spinner=False)
def load_all_courses() -> list[CourseEntry]:
    """SBS평일, SBS주말 폴더의 모든 .xls 파일 파싱."""
    all_entries: list[CourseEntry] = []

    for folder, sheet in [(WEEKDAY_DIR, '평일'), (WEEKEND_DIR, '주말')]:
        if not folder.exists():
            continue
        for fp in sorted(folder.glob('*.xls')):
            all_entries.extend(_load_xls_file(fp, sheet))

    # 중복 제거: (과정명+강의실+시간+개강일) 기준
    seen: set[tuple] = set()
    unique: list[CourseEntry] = []
    for e in all_entries:
        key = (e.name, e.room, e.start_time, e.start_date)
        if key not in seen:
            seen.add(key)
            unique.append(e)

    # 개강일 기준 정렬
    unique.sort(key=lambda x: (x.start_date, x.name))
    return unique


def search_courses(entries: list[CourseEntry], keyword: str) -> list[CourseEntry]:
    """과정명 포함 검색 (대소문자·공백 무시)."""
    kw = keyword.strip().lower().replace(' ', '')
    if not kw:
        return []
    return [e for e in entries if kw in e.name.lower().replace(' ', '')]


# ══════════════════════════════════════════════════════════════════════════════
# 수강료 로드 & 매칭
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def load_price_map() -> dict:
    """수강료.xlsx → {과정명: {'평일': 가격, '주말': 가격}} 딕셔너리."""
    fp = ROOT / "수강료.xlsx"
    if not fp.exists():
        return {}

    pm: dict[str, dict[str, int]] = {}

    def _register(raw_name: str, price_val, sheet: str) -> None:
        if not raw_name or not isinstance(price_val, (int, float)) or price_val <= 0:
            return
        # 방학 특강은 별도 키 '방학'으로 등록 → 일반 수강료 덮어쓰기 방지
        is_vacation = '방학' in raw_name
        base = re.sub(r'/주말|/방학|\(방학\)', '', raw_name).strip()
        effective_sheet = '방학' if is_vacation else sheet
        # 쉼표 구분 과목 개별 등록 ("포토샵, 일러스트" → 포토샵, 일러스트 각각)
        for part in [p.strip() for p in base.split(',')]:
            if part:
                # setdefault: 먼저 등록된 가격 우선 (방학 가격으로 덮어쓰기 방지)
                pm.setdefault(part, {}).setdefault(effective_sheet, int(price_val))

    try:
        wb  = openpyxl.load_workbook(fp, data_only=True)
        ws  = wb['수강료'] if '수강료' in wb.sheetnames else wb.active
        cur = '평일'   # 현재 구분 추적

        for row in ws.iter_rows(values_only=True):
            # ── 왼쪽 테이블 (B=1, C=2, D=3, E=4) ──────────────────────────
            sect_l = str(row[1] or '').replace('\n', ' ').strip()
            if sect_l:
                if '주말' in sect_l:
                    cur = '주말'
                elif '평일' in sect_l:
                    cur = '평일'
            name_l  = str(row[3] or '').strip()
            sheet_l = '주말' if '/주말' in name_l else cur
            _register(name_l, row[4], sheet_l)

            # ── 오른쪽 테이블 (J=9, K=10, L=11, M=12) ─────────────────────
            name_r  = str(row[11] or '').strip() if len(row) > 11 else ''
            price_r = row[12] if len(row) > 12 else None
            sheet_r = '주말' if '/주말' in name_r else '평일'
            _register(name_r, price_r, sheet_r)

    except Exception:
        pass

    return pm


def find_price(course_name: str, sheet: str, pm: dict) -> int | None:
    """
    과정명 + 구분(평일/주말) → 수강료(원) or None.
    국비/계약 과정은 -1 반환 (무료 마커).
    """
    if not pm:
        return None
    if re.match(r'^\(국\)|^\(계\)', course_name):
        return -1  # 국비훈련

    def _lookup(name: str) -> int | None:
        entry = pm.get(name)
        if entry:
            return entry.get(sheet) or entry.get('평일') or next(iter(entry.values()), None)
        return None

    # 1) 정확 일치
    p = _lookup(course_name)
    if p:
        return p

    # 2) 공백 제거 후 일치
    name_ns = course_name.replace(' ', '')
    for key, entry in pm.items():
        if key.replace(' ', '') == name_ns:
            return entry.get(sheet) or entry.get('평일') or next(iter(entry.values()), None)

    # 3) 끝 숫자 제거: 마야3 → 마야, 블렌더1 → 블렌더
    name_base = re.sub(r'\d+$', '', course_name).strip()
    if name_base and name_base != course_name:
        p = _lookup(name_base)
        if p:
            return p

    # 4) 퍼지: 과정명이 price key의 시작이거나 price key가 과정명의 시작
    for key, entry in pm.items():
        k = key.replace(' ', '').lower()
        n = name_ns.lower()
        n_base = name_base.replace(' ', '').lower()
        if n.startswith(k) or k.startswith(n) or (n_base and k.startswith(n_base)):
            return entry.get(sheet) or entry.get('평일') or next(iter(entry.values()), None)

    return None


# ══════════════════════════════════════════════════════════════════════════════
# 엑셀 생성
# ══════════════════════════════════════════════════════════════════════════════

def build_excel(student_name: str, cart: list[dict]) -> bytes:
    """★전체시간표 (양식).xlsx 기반으로 개인 시간표를 생성합니다."""

    # ── 템플릿 로드 ──────────────────────────────────────────────────────────
    if TEMPLATE_PATH.exists():
        wb = openpyxl.load_workbook(TEMPLATE_PATH)
        ws = wb.active
        for rng in list(ws.merged_cells.ranges):
            ws.unmerge_cells(str(rng))
        ws.delete_rows(1, ws.max_row)
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
    ws.title = f"{student_name} 시간표"

    # ── 공통 스타일 ──────────────────────────────────────────────────────────
    thin  = Side(style='thin', color='000000')
    bdr   = Border(left=thin, right=thin, top=thin, bottom=thin)
    ca    = Alignment(horizontal='center', vertical='center', wrap_text=True)
    la    = Alignment(horizontal='left',   vertical='center', wrap_text=True)
    ta    = Alignment(horizontal='left',   vertical='top',    wrap_text=True)

    def fill(color): return PatternFill('solid', fgColor=color)
    def font(size=10, bold=False, color='000000'):
        return Font(name='맑은 고딕', size=size, bold=bold, color=color)

    # ── 열 너비 (A~K = 11열, 템플릿 동일) ───────────────────────────────────
    #   A:번호  B~C:과정명  D~E:수업기간  F~G:시간  H:요일  I:강의실  J:강사  K:(여백)
    for col, w in zip('ABCDEFGHIJK', [5, 20, 4, 15, 3, 9, 3, 8, 10, 8, 4]):
        ws.column_dimensions[col].width = w

    row = 1

    # ── 행1~2: 제목 ─────────────────────────────────────────────────────────
    ws.row_dimensions[1].height = 14
    ws.row_dimensions[2].height = 14
    ws.merge_cells(f'A1:K2')
    c = ws.cell(1, 1)
    c.value     = f'SBS아카데미  {student_name}  개인 시간표'
    c.font      = font(16, bold=True, color='FFFFFF')
    c.alignment = ca
    c.fill      = fill('1F4E79')
    c.border    = bdr
    row = 3

    # ── 행3: 연도 ────────────────────────────────────────────────────────────
    ws.row_dimensions[row].height = 20
    ws.merge_cells(f'A{row}:K{row}')
    c = ws.cell(row, 1)
    c.value     = f'{datetime.now().year}년'
    c.font      = font(13, bold=True, color='FFFFFF')
    c.alignment = ca
    c.fill      = fill('2E75B6')
    c.border    = bdr
    row += 1

    # ── 섹션별 데이터 작성 헬퍼 ─────────────────────────────────────────────
    COL_HEADERS = ['#', '과정명', '', '수업기간', '', '시간', '', '요일', '강의실', '강사', '']
    MERGES_HDR  = [('B', 'C'), ('D', 'E'), ('F', 'G')]   # 헤더/데이터 행 병합 쌍

    def write_section(label: str, courses: list[dict],
                      sec_color: str, row_color: str) -> None:
        nonlocal row

        # 섹션 헤더
        ws.row_dimensions[row].height = 22
        ws.merge_cells(f'A{row}:K{row}')
        c = ws.cell(row, 1)
        c.value     = f'  {label}'
        c.font      = font(12, bold=True, color='FFFFFF')
        c.alignment = la
        c.fill      = fill(sec_color)
        c.border    = bdr
        row += 1

        if not courses:
            ws.row_dimensions[row].height = 26
            ws.merge_cells(f'A{row}:K{row}')
            c = ws.cell(row, 1)
            c.value     = '(선택된 과목 없음)'
            c.font      = font(10, color='94A3B8')
            c.alignment = ca
            c.fill      = fill('F8FAFC')
            c.border    = bdr
            row += 1
            return

        # 컬럼 헤더 행
        ws.row_dimensions[row].height = 20
        h_fill = fill('2E75B6')
        for ci, h in enumerate(COL_HEADERS, 1):
            c = ws.cell(row, ci)
            c.font      = font(9, bold=True, color='FFFFFF')
            c.alignment = ca
            c.fill      = h_fill
            c.border    = bdr
        for sc, ec in MERGES_HDR:
            ws.merge_cells(f'{sc}{row}:{ec}{row}')
        ws.cell(row, 2).value = '과정명'
        ws.cell(row, 4).value = '수업기간'
        ws.cell(row, 6).value = '시간'
        ws.cell(row, 8).value = '요일'
        ws.cell(row, 9).value = '강의실'
        ws.cell(row, 10).value = '강사'
        row += 1

        # 데이터 행
        for idx, item in enumerate(courses, 1):
            ws.row_dimensions[row].height = 36
            et       = item.get('end_time', '')
            time_str = f"{item['start_time']}~{et}" if et else item['start_time']
            rf       = fill(row_color)

            data = [
                idx,
                item['name'], '',
                f"{item['start_date']} ~ {item['end_date']}", '',
                time_str, '',
                item.get('days', ''),
                item.get('room', ''),
                item.get('instructor', ''),
                '',
            ]
            for ci, v in enumerate(data, 1):
                c = ws.cell(row, ci)
                c.value     = v
                c.font      = font(10)
                c.fill      = rf
                c.border    = bdr
                c.alignment = ca

            # 과정명·기간·시간 셀 병합 후 정렬 보정
            for sc, ec in MERGES_HDR:
                ws.merge_cells(f'{sc}{row}:{ec}{row}')
            ws.cell(row, 2).alignment = la   # 과정명 좌측 정렬
            row += 1

    wd = [item for item in cart if item['sheet'] == '평일']
    we = [item for item in cart if item['sheet'] == '주말']
    write_section('평 일', wd, '1F4E79', 'DBEAFE')
    write_section('주 말', we, '1A6035', 'DCFCE7')

    # ── 비고 행 ──────────────────────────────────────────────────────────────
    row += 1
    ws.row_dimensions[row].height = 60
    c = ws.cell(row, 1)
    c.value     = '비고'
    c.font      = font(11, bold=True)
    c.alignment = ca
    c.fill      = fill('F0F4FA')
    c.border    = bdr

    ws.merge_cells(f'B{row}:K{row}')
    c = ws.cell(row, 2)
    c.value     = ''
    c.alignment = ta
    c.fill      = fill('FFFFFF')
    c.border    = bdr

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# Streamlit UI
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title='시간표 검색 | SBS아카데미',
    page_icon='🔍',
    layout='wide',
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans KR',sans-serif;}

/* ── 상단 헤더 ── */
.sbs-header{
  background:linear-gradient(120deg,#1e3a5f 0%,#1F4E79 60%,#2563a8 100%);
  padding:1.1rem 1.8rem;border-radius:12px;margin-bottom:1rem;
  box-shadow:0 4px 20px rgba(31,78,121,.28);
}
.sbs-header h1{margin:0;color:#fff;font-size:1.35rem;font-weight:900;}
.sbs-header p{margin:.2rem 0 0;color:rgba(255,255,255,.78);font-size:.84rem;}

/* ── 월 구분 헤더 ── */
.month-header{
  display:flex;align-items:center;gap:.6rem;
  background:linear-gradient(90deg,#1e3a5f,#2563a8 80%,transparent 100%);
  color:#fff;border-radius:8px;padding:.45rem 1rem;
  margin:1.1rem 0 .45rem;
}
.month-title{font-size:1.05rem;font-weight:900;letter-spacing:-.3px;}
.month-cnt{
  background:rgba(255,255,255,.22);border-radius:20px;
  padding:.05rem .55rem;font-size:.75rem;font-weight:700;
}

/* ── 과정 카드 ── */
.course-card{
  border-left:4px solid #ccc;
  background:#fff;border-radius:0 9px 9px 0;
  padding:.6rem .9rem .5rem;margin-bottom:.35rem;
  box-shadow:0 1px 4px rgba(0,0,0,.07);
  transition:box-shadow .15s;
}
.course-card:hover{box-shadow:0 3px 12px rgba(0,0,0,.12);}
.course-card.wd{border-left-color:#2563a8;}
.course-card.we{border-left-color:#059669;}

.course-title-row{
  display:flex;align-items:center;flex-wrap:wrap;gap:.4rem;
  margin-bottom:.3rem;
}
.course-name{font-size:.98rem;font-weight:800;color:#0f172a;}
.badge{
  display:inline-flex;align-items:center;
  border-radius:5px;padding:.05rem .4rem;
  font-size:.72rem;font-weight:700;white-space:nowrap;
}
.badge-wd{background:#dbeafe;color:#1d4ed8;}
.badge-we{background:#dcfce7;color:#15803d;}
.badge-time{background:#f1f5f9;color:#475569;}
.badge-room{background:#fef3c7;color:#92400e;}

.course-detail-row{
  display:flex;align-items:center;flex-wrap:wrap;gap:.5rem 1.2rem;
  font-size:.79rem;color:#64748b;line-height:1.5;
}
.period-text{font-weight:700;color:#1e3a5f;}

/* ── 장바구니 카드 ── */
.cart-card{
  background:#f0f7ff;border:1.5px solid #bfdbfe;
  border-left:4px solid #2563a8;
  border-radius:0 9px 9px 0;padding:.55rem .9rem;margin-bottom:.4rem;
}
.cart-card.we{border-left-color:#059669;background:#f0fdf4;border-color:#bbf7d0;}
.cart-name{font-weight:800;color:#1e40af;font-size:.93rem;}
.cart-meta{font-size:.77rem;color:#64748b;line-height:1.7;margin-top:.15rem;}
.cart-period{font-weight:700;color:#1e3a5f;}

.price-tag{
  margin-left:auto;
  background:#fef9c3;color:#78350f;
  border:1.5px solid #fde68a;border-radius:6px;
  padding:.08rem .6rem;font-size:.85rem;font-weight:900;
  white-space:nowrap;letter-spacing:-.5px;
}
.price-tag.free{background:#dcfce7;color:#15803d;border-color:#bbf7d0;}
.price-tag.unknown{background:#f1f5f9;color:#94a3b8;border-color:#e2e8f0;font-weight:500;}

/* 장바구니 합계 */
.cart-total{
  background:linear-gradient(90deg,#1e3a5f,#2563a8);
  color:#fff;border-radius:8px;padding:.55rem 1rem;
  display:flex;justify-content:space-between;align-items:center;
  margin-bottom:.5rem;
}
.cart-total-label{font-size:.82rem;opacity:.85;}
.cart-total-amount{font-size:1.1rem;font-weight:900;letter-spacing:-.5px;}

.tag{
  display:inline-block;border-radius:5px;
  padding:.06rem .38rem;font-size:.7rem;font-weight:700;margin-right:.25rem;
}
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
  <p>과정명을 입력하면 개강일 · 종강일 · 강사 · 강의실을 즉시 확인할 수 있습니다</p>
</div>
""", unsafe_allow_html=True)

# ── 데이터 체크 ───────────────────────────────────────────────────────────────
if not WEEKDAY_DIR.exists() and not WEEKEND_DIR.exists():
    st.error('⚠️ SBS평일 / SBS주말 폴더를 프로젝트 루트에 넣어주세요.')
    st.stop()

all_courses = load_all_courses()
if not all_courses:
    st.error('⚠️ 강의시간표 파일을 읽을 수 없습니다.')
    st.stop()

price_map = load_price_map()

# ── 세션 상태 ─────────────────────────────────────────────────────────────────
if 'cart' not in st.session_state:
    st.session_state.cart = []


def add_to_cart(e: CourseEntry, price: int | None):
    key = (e.name, e.room, e.start_time, e.start_date)
    if not any(
        (c['name'], c['room'], c['start_time'], c['start_date']) == key
        for c in st.session_state.cart
    ):
        st.session_state.cart.append({
            'name':       e.name,
            'room':       e.room,
            'start_time': e.start_time,
            'end_time':   e.end_time,
            'instructor': e.instructor,
            'days':       e.days,
            'start_date': e.start_date,
            'end_date':   e.end_date,
            'sheet':      e.sheet,
            'source':     e.source,
            'price':      price,
        })


# ── 레이아웃 ──────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2], gap='large')

# ══════════════════════════════════════════════════════════════════════════════
# 왼쪽: 검색 (월별 그룹핑)
# ══════════════════════════════════════════════════════════════════════════════
with col_left:
    st.markdown('### 🔍 과정 검색')

    keyword = st.text_input(
        '과정명 입력',
        placeholder='에펙, 캐드, 마야, 컴활, 포토샵 ...',
        label_visibility='collapsed',
    )

    if keyword.strip():
        results = search_courses(all_courses, keyword)

        if not results:
            st.markdown(
                "<div style='background:#fff7ed;border:1.5px solid #fed7aa;"
                "border-radius:9px;padding:1rem 1.2rem;color:#9a3412;font-size:.88rem'>"
                "검색 결과가 없습니다. 다른 키워드를 입력해 보세요.</div>",
                unsafe_allow_html=True,
            )
        else:
            # ── 월별 그룹핑 ───────────────────────────────────────────────
            from collections import defaultdict
            groups: dict[tuple, list] = defaultdict(list)
            for e in results:
                try:
                    s = datetime.strptime(e.start_date, "%Y-%m-%d")
                    key = (s.year, s.month)
                except Exception:
                    key = (0, 0)
                groups[key].append(e)

            total = len(results)
            months = len(groups)
            st.markdown(
                f"<p style='color:#64748b;font-size:.83rem;margin:.2rem 0 .1rem'>"
                f"<b style='color:#1e3a5f'>{total}개</b> 검색됨 &nbsp;·&nbsp; "
                f"<b style='color:#1e3a5f'>{months}개월</b> 기간</p>",
                unsafe_allow_html=True,
            )

            for (yr, mo), group_entries in sorted(groups.items()):
                # 월 헤더
                if yr == 0:
                    month_label = "날짜 미정"
                else:
                    month_label = f"{yr}년 &nbsp;{mo}월"

                st.markdown(
                    f"<div class='month-header'>"
                    f"<span class='month-title'>📅 {month_label}</span>"
                    f"<span class='month-cnt'>{len(group_entries)}개 과정</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                # 해당 월의 과정 목록
                for e in group_entries:
                    is_wd     = e.sheet == '평일'
                    card_cls  = 'wd' if is_wd else 'we'
                    badge_cls = 'badge-wd' if is_wd else 'badge-we'

                    # 날짜 포맷
                    try:
                        sd = datetime.strptime(e.start_date, "%Y-%m-%d")
                        ed = datetime.strptime(e.end_date,   "%Y-%m-%d")
                        if sd.month == ed.month:
                            period_str = f"{sd.month}월 {sd.day}일 ~ {ed.day}일"
                        else:
                            period_str = f"{sd.month}월 {sd.day}일 ~ {ed.month}월 {ed.day}일"
                    except Exception:
                        period_str = e.period_label

                    # 수강료
                    price     = find_price(e.name, e.sheet, price_map)
                    if price == -1:
                        price_html = "<span class='price-tag free'>국비훈련 무료</span>"
                        price_disp = -1
                    elif price:
                        price_html = f"<span class='price-tag'>{price:,}원</span>"
                        price_disp = price
                    else:
                        price_html = "<span class='price-tag unknown'>수강료 문의</span>"
                        price_disp = None

                    info_html = (
                        f"<div class='course-card {card_cls}'>"
                        f"<div class='course-title-row'>"
                        f"<span class='course-name'>{e.name}</span>"
                        f"<span class='badge {badge_cls}'>{e.sheet}</span>"
                        f"<span class='badge badge-time'>⏰ {e.start_time}{'~'+e.end_time if e.end_time else ''}</span>"
                        f"<span class='badge badge-room'>📍 {e.room}</span>"
                        f"{price_html}"
                        f"</div>"
                        f"<div class='course-detail-row'>"
                        f"<span>👨‍🏫 {e.instructor or '미정'}</span>"
                        f"<span>📆 {e.days or '-'}</span>"
                        f"<span class='period-text'>🗓 {period_str}</span>"
                        f"</div>"
                        f"</div>"
                    )

                    col_card, col_btn = st.columns([5, 1])
                    with col_card:
                        st.markdown(info_html, unsafe_allow_html=True)
                    with col_btn:
                        st.markdown("<div style='margin-top:.35rem'></div>", unsafe_allow_html=True)
                        btn_key = f"add_{e.name}_{e.room}_{e.start_date}_{e.start_time}"
                        if st.button('＋ 추가', key=btn_key, use_container_width=True):
                            add_to_cart(e, price_disp)
                            st.rerun()

    else:
        # 검색 전: 전체 과정명 태그 구름
        names = sorted({e.name for e in all_courses})
        st.markdown(
            f"<p style='color:#64748b;font-size:.83rem;margin-bottom:.5rem'>"
            f"총 <b style='color:#1e3a5f'>{len(names)}개</b> 과정이 등록되어 있습니다. "
            f"과정명을 입력해 검색하세요.</p>",
            unsafe_allow_html=True,
        )
        tags = ''.join(
            f"<span style='background:#e2e8f0;border-radius:5px;"
            f"padding:.12rem .5rem;font-size:.8rem;margin:.18rem .12rem;"
            f"display:inline-block;color:#374151;font-weight:500'>{n}</span>"
            for n in names
        )
        st.markdown(
            f"<div style='line-height:2.4;margin-top:.2rem'>{tags}</div>",
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# 오른쪽: 장바구니
# ══════════════════════════════════════════════════════════════════════════════
with col_right:
    cart = st.session_state.cart
    st.markdown(f'### 🛒 선택 과목 &nbsp;<span style="font-size:.85rem;color:#64748b;font-weight:500">({len(cart)}개)</span>', unsafe_allow_html=True)

    if not cart:
        st.markdown(
            "<div style='background:#f8fafc;border:2px dashed #cbd5e1;"
            "border-radius:10px;padding:2rem;text-align:center;color:#94a3b8'>"
            "<div style='font-size:2rem;margin-bottom:.5rem'>🛒</div>"
            "<div style='font-weight:600;margin-bottom:.3rem'>선택한 과목이 없어요</div>"
            "<small>왼쪽 검색 결과에서 <b>＋ 추가</b>를 누르세요</small>"
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for i, item in enumerate(cart):
            is_wd     = item['sheet'] == '평일'
            card_cls  = 'wd' if is_wd else 'we'
            badge_cls = 'badge-wd' if is_wd else 'badge-we'

            try:
                sd = datetime.strptime(item['start_date'], "%Y-%m-%d")
                ed = datetime.strptime(item['end_date'],   "%Y-%m-%d")
                if sd.month == ed.month:
                    period_str = f"{sd.year}년 {sd.month}월 {sd.day}일 ~ {ed.day}일"
                else:
                    period_str = f"{sd.month}월 {sd.day}일 ~ {ed.month}월 {ed.day}일"
            except Exception:
                period_str = f"{item['start_date']} ~ {item['end_date']}"

            # 가격 표시
            p = item.get('price')
            if p == -1:
                price_html = "<span class='price-tag free' style='font-size:.75rem'>국비훈련 무료</span>"
            elif isinstance(p, int) and p > 0:
                price_html = f"<span class='price-tag' style='font-size:.78rem'>{p:,}원</span>"
            else:
                price_html = "<span class='price-tag unknown' style='font-size:.75rem'>수강료 문의</span>"

            col_info, col_del = st.columns([6, 1])
            with col_info:
                st.markdown(
                    f"<div class='cart-card {card_cls}'>"
                    f"<div style='display:flex;align-items:center;gap:.4rem;margin-bottom:.2rem'>"
                    f"<span class='cart-name'>{item['name']}</span>"
                    f"<span class='badge {badge_cls}'>{item['sheet']}</span>"
                    f"{price_html}"
                    f"</div>"
                    f"<div class='cart-meta'>"
                    f"⏰ {item['start_time']}{'~'+item['end_time'] if item.get('end_time') else ''} &nbsp;·&nbsp; "
                    f"📍 {item['room']} &nbsp;·&nbsp; "
                    f"👨‍🏫 {item['instructor'] or '미정'} &nbsp;·&nbsp; "
                    f"📆 {item['days'] or '-'}<br>"
                    f"<span class='cart-period'>🗓 {period_str}</span>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
            with col_del:
                st.markdown("<div style='margin-top:.4rem'></div>", unsafe_allow_html=True)
                if st.button('✕', key=f'del_{i}', help='제거'):
                    st.session_state.cart.pop(i)
                    st.rerun()

        # ── 수강료 합계 ──────────────────────────────────────────────────────
        known_prices = [
            item['price'] for item in cart
            if isinstance(item.get('price'), int) and item['price'] > 0
        ]
        gov_count  = sum(1 for item in cart if item.get('price') == -1)
        unknown_count = len(cart) - len(known_prices) - gov_count

        if known_prices or gov_count:
            total_str = f"{sum(known_prices):,}원"
            if gov_count:
                total_str += f" + 국비 {gov_count}개"
            if unknown_count:
                total_str += f" + 문의 {unknown_count}개"
            note = ""
            if gov_count:
                note = " (국비훈련 제외)"
            elif unknown_count:
                note = " (문의 제외)"
            st.markdown(
                f"<div class='cart-total'>"
                f"<span class='cart-total-label'>💰 예상 수강료 합계{note}</span>"
                f"<span class='cart-total-amount'>{total_str}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top:.3rem'></div>", unsafe_allow_html=True)
        if st.button('🗑️ 전체 비우기', use_container_width=True):
            st.session_state.cart = []
            st.rerun()

        st.markdown('---')

        # ── 엑셀 생성 ────────────────────────────────────────────────────────
        st.markdown('#### 📥 시간표 생성')
        sname = st.text_input(
            '수강생 이름',
            placeholder='홍길동',
            key='sname',
        )
        if st.button('📊 엑셀 시간표 만들기', type='primary', use_container_width=True):
            if not sname.strip():
                st.warning('수강생 이름을 입력해 주세요.')
            else:
                with st.spinner('생성 중...'):
                    xlsx = build_excel(sname.strip(), cart)
                safe  = re.sub(r'[\\/:*?"<>|]', '_', sname.strip())
                fname = f"SBS_{safe}_시간표_{datetime.now().strftime('%Y%m%d')}.xlsx"
                st.success('✅ 생성 완료!')
                st.download_button(
                    '⬇️ 다운로드',
                    data=xlsx,
                    file_name=fname,
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    use_container_width=True,
                )

# ── 푸터 ──────────────────────────────────────────────────────────────────────
st.markdown('---')
st.markdown(
    "<p style='text-align:center;color:#9ca3af;font-size:.78rem'>"
    'SBS아카데미 대전지점 · 시간표 검색 시스템</p>',
    unsafe_allow_html=True,
)
