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
TEMPLATE_PATH  = Path(r"c:\Users\SBS\Desktop\SBS컴퓨터\★전체시간표 (양식).xlsx")

# ══════════════════════════════════════════════════════════════════════════════
# 데이터 모델
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CourseEntry:
    name:       str          # 과정명
    room:       str          # 강의실 (A-1 등)
    start_time: str          # 시작 시간 (09:00)
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
                span  = int(td.get('colspan', 1))
                text  = td.get_text(strip=True)
                room  = room_map.get(data_col, f'Col{data_col}')
                parsed = _parse_cell_text(text)
                if parsed:
                    name, instr, days, sd, ed = parsed
                    entries.append(CourseEntry(
                        name=name, room=room,
                        start_time=cur_time,
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
# 엑셀 생성
# ══════════════════════════════════════════════════════════════════════════════

def build_excel(student_name: str, cart: list[dict]) -> bytes:
    thin = Side(style='thin', color='000000')
    b    = Border(left=thin, right=thin, top=thin, bottom=thin)
    ca   = Alignment(horizontal='center', vertical='center', wrap_text=True)
    la   = Alignment(horizontal='left',   vertical='center', wrap_text=True)

    t_fill  = PatternFill('solid', fgColor='1F4E79')
    h_fill  = PatternFill('solid', fgColor='2E75B6')
    wd_fill = PatternFill('solid', fgColor='DBEAFE')
    we_fill = PatternFill('solid', fgColor='DCFCE7')
    w_fill  = PatternFill('solid', fgColor='FFFFFF')
    n_fill  = PatternFill('solid', fgColor='F0F4FA')

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

    # 열 너비
    col_widths = [22, 14, 12, 12, 14, 28, 12]
    headers    = ['과정명', '구분', '강의실', '시간', '강사', '수업기간', '요일']
    for i, (w, h) in enumerate(zip(col_widths, headers), 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # 행1: 제목
    ws.row_dimensions[1].height = 30
    ws.merge_cells('A1:G1')
    c = ws.cell(1, 1)
    c.value, c.font, c.alignment, c.fill, c.border = (
        f'SBS아카데미  {student_name}  개인 시간표',
        Font(name='맑은 고딕', size=16, bold=True, color='FFFFFF'),
        Alignment(horizontal='center', vertical='center'),
        t_fill, b,
    )

    # 행2: 헤더
    ws.row_dimensions[2].height = 24
    for i, h in enumerate(headers, 1):
        c = ws.cell(2, i)
        c.value, c.font, c.alignment, c.fill, c.border = (
            h,
            Font(name='맑은 고딕', size=10, bold=True, color='FFFFFF'),
            ca, h_fill, b,
        )

    # 데이터
    for ri, item in enumerate(cart, 3):
        ws.row_dimensions[ri].height = 40
        row_fill = wd_fill if item['sheet'] == '평일' else we_fill
        vals = [
            item['name'],
            item['sheet'],
            item['room'],
            item['start_time'],
            item['instructor'],
            f"{item['start_date']} ~ {item['end_date']}",
            item['days'],
        ]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(ri, ci)
            c.value, c.font, c.alignment, c.fill, c.border = (
                v,
                Font(name='맑은 고딕', size=10),
                ca if ci != 6 else la,
                row_fill if ci == 1 else w_fill,
                b,
            )

    # 비고
    note_row = len(cart) + 4
    ws.row_dimensions[note_row].height = 60
    ws.merge_cells(f'A{note_row}:G{note_row}')
    c = ws.cell(note_row, 1)
    c.value, c.font, c.alignment, c.fill, c.border = (
        '비고',
        Font(name='맑은 고딕', size=11, bold=True),
        la, n_fill, b,
    )

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
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans KR',sans-serif;}
.sbs-header{
  background:linear-gradient(120deg,#1e3a5f 0%,#1F4E79 60%,#2563a8 100%);
  padding:1.2rem 2rem;border-radius:14px;margin-bottom:1.2rem;
  box-shadow:0 4px 24px rgba(31,78,121,.32);
}
.sbs-header h1{margin:0;color:#fff;font-size:1.4rem;font-weight:900;}
.sbs-header p{margin:.25rem 0 0;color:rgba(255,255,255,.8);font-size:.87rem;}
.hit-card{
  background:#f8fafc;border:1.5px solid #e2e8f0;border-radius:10px;
  padding:.7rem 1rem .5rem;margin-bottom:.5rem;transition:border-color .15s;
}
.hit-card:hover{border-color:#3b82f6;background:#eff6ff;}
.hit-name{font-size:.97rem;font-weight:800;color:#1e3a5f;margin-bottom:.15rem;}
.hit-meta{font-size:.8rem;color:#475569;line-height:1.7;}
.cart-wrap{
  background:#eff6ff;border:1.5px solid #bfdbfe;border-radius:9px;
  padding:.5rem .85rem;margin-bottom:.4rem;
}
.cart-name{font-weight:800;color:#1e40af;font-size:.92rem;}
.cart-meta{font-size:.76rem;color:#64748b;line-height:1.6;}
.tag{
  display:inline-block;border-radius:5px;
  padding:.08rem .4rem;font-size:.72rem;font-weight:700;margin-right:.3rem;
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

# ── 세션 상태 ─────────────────────────────────────────────────────────────────
if 'cart' not in st.session_state:
    st.session_state.cart = []


def add_to_cart(e: CourseEntry):
    key = (e.name, e.room, e.start_time, e.start_date)
    if not any(
        (c['name'], c['room'], c['start_time'], c['start_date']) == key
        for c in st.session_state.cart
    ):
        st.session_state.cart.append({
            'name':       e.name,
            'room':       e.room,
            'start_time': e.start_time,
            'instructor': e.instructor,
            'days':       e.days,
            'start_date': e.start_date,
            'end_date':   e.end_date,
            'sheet':      e.sheet,
            'source':     e.source,
        })


# ── 레이아웃 ──────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2], gap='large')

# ══════════════════════════════════════════════════════════════════════════════
# 왼쪽: 검색
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
            st.info('검색 결과가 없습니다. 다른 키워드를 입력해 보세요.')
        else:
            st.caption(f'**{len(results)}개** 검색됨')

            for e in results:
                sheet_color = '#2563a8' if e.sheet == '평일' else '#059669'
                sheet_bg    = '#dbeafe' if e.sheet == '평일' else '#dcfce7'

                st.markdown(
                    f"<div class='hit-card'>"
                    f"<div class='hit-name'>"
                    f"<span class='tag' style='background:{sheet_color};color:#fff'>{e.sheet}</span>"
                    f"{e.name}"
                    f"</div>"
                    f"<div class='hit-meta'>"
                    f"📍 {e.room} &nbsp;|&nbsp; ⏰ {e.start_time} &nbsp;|&nbsp; "
                    f"👨‍🏫 {e.instructor or '-'} &nbsp;|&nbsp; 📆 {e.days or '-'}"
                    f"<br>📅 <b>{e.month_label}</b> &nbsp;({e.period_label})"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                btn_key = f"add_{e.name}_{e.room}_{e.start_date}_{e.start_time}"
                if st.button(
                    f'+ 장바구니 추가',
                    key=btn_key,
                    use_container_width=False,
                ):
                    add_to_cart(e)
                    st.rerun()

    else:
        # 검색 전: 전체 과정명 태그
        names = sorted({e.name for e in all_courses})
        st.caption(f'총 **{len(names)}개** 과정 등록됨')
        tags = ' '.join(
            f"<span style='background:#e2e8f0;border-radius:5px;"
            f"padding:.12rem .45rem;font-size:.78rem;margin:.1rem .1rem;"
            f"display:inline-block'>{n}</span>"
            for n in names
        )
        st.markdown(
            f"<div style='line-height:2.2;margin-top:.4rem'>{tags}</div>",
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# 오른쪽: 장바구니
# ══════════════════════════════════════════════════════════════════════════════
with col_right:
    cart = st.session_state.cart
    st.markdown(f'### 🛒 선택 과목 ({len(cart)}개)')

    if not cart:
        st.markdown(
            "<div style='background:#f8fafc;border:2px dashed #cbd5e1;"
            "border-radius:10px;padding:2rem;text-align:center;color:#94a3b8'>"
            "아직 선택한 과목이 없어요<br>"
            "<small>검색 결과에서 + 버튼을 눌러 추가하세요</small>"
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for i, item in enumerate(cart):
            sc = '#2563a8' if item['sheet'] == '평일' else '#059669'
            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f"<div class='cart-wrap'>"
                    f"<span class='cart-name'>{item['name']}</span> "
                    f"<span class='tag' style='background:{sc};color:#fff'>{item['sheet']}</span>"
                    f"<div class='cart-meta'>"
                    f"📍 {item['room']} &nbsp;·&nbsp; ⏰ {item['start_time']} &nbsp;·&nbsp; 👨‍🏫 {item['instructor'] or '-'}<br>"
                    f"📅 {item['start_date']} ~ {item['end_date']}"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button('✕', key=f'del_{i}', help='제거'):
                    st.session_state.cart.pop(i)
                    st.rerun()

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
