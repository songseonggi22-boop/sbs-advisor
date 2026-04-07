"""
excel_loader.py — 수강료 엑셀 파일 로더 (SBS아카데미 대전지점)
'수강료.xlsx' 파일을 파싱해 과정 목록을 반환합니다.
"""
from __future__ import annotations
from pathlib import Path

EXCEL_PATH = Path(__file__).parent / "수강료.xlsx"

# ── 정적 폴백 데이터 (엑셀 파싱 실패 시 사용) ─────────────────────────────────
STATIC_COURSES: list[dict] = [
    # 자격증/OA
    {"department": "자격증/OA", "course": "모스",                   "price": 300000},
    {"department": "자격증/OA", "course": "컴활1급",                "price": 350000},
    {"department": "자격증/OA", "course": "컴활2급/주말",           "price": 300000},
    {"department": "자격증/OA", "course": "전산회계1급",            "price": 400000},
    {"department": "자격증/OA", "course": "전산세무2급",            "price": 400000},
    {"department": "자격증/OA", "course": "재경관리사",             "price": 700000},
    {"department": "자격증/OA", "course": "GTQ/주말",               "price": 350000},
    {"department": "자격증/OA", "course": "GTQi/주말",              "price": 350000},
    {"department": "자격증/OA", "course": "그래픽기능사/주말",      "price": 350000},
    {"department": "자격증/OA", "course": "컬러실기(산업기사)/주말","price": 400000},
    {"department": "자격증/OA", "course": "컬러실기(기사)/주말",    "price": 400000},
    # 아트웍
    {"department": "아트웍", "course": "발상과표현",       "price": 400000},
    {"department": "아트웍", "course": "색채학",           "price": 400000},
    {"department": "아트웍", "course": "해부학",           "price": 400000},
    {"department": "아트웍", "course": "디지털드로잉1~6", "price": 500000},
    {"department": "아트웍", "course": "디드포폴1~4",     "price": 600000},
    {"department": "아트웍", "course": "스토리보드",       "price": 500000},
    {"department": "아트웍", "course": "AI크리에이터-아트웍", "price": 500000},
    # 시각편집
    {"department": "시각편집", "course": "포토샵, 일러스트",     "price": 350000},
    {"department": "시각편집", "course": "포토웍스, 디일러",     "price": 400000},
    {"department": "시각편집", "course": "편집포폴1~2",          "price": 500000},
    {"department": "시각편집", "course": "인디자인",             "price": 350000},
    {"department": "시각편집", "course": "인포그래픽",           "price": 400000},
    {"department": "시각편집", "course": "그래픽아트웍",         "price": 400000},
    {"department": "시각편집", "course": "AI크리에이터-시각편집","price": 500000},
    # 웹/웹디자인
    {"department": "웹/웹디자인", "course": "웹1~3",             "price": 400000},
    {"department": "웹/웹디자인", "course": "UIUX1~3",           "price": 400000},
    {"department": "웹/웹디자인", "course": "웹포폴1~2",         "price": 500000},
    {"department": "웹/웹디자인", "course": "AI바이브코딩-웹",   "price": 500000},
    {"department": "웹/웹디자인", "course": "웹디자인개발기능사","price": 400000},
    # 건축/인테리어
    {"department": "건축/인테리어", "course": "캐드1~2",           "price": 400000},
    {"department": "건축/인테리어", "course": "스케치업1~2",       "price": 400000},
    {"department": "건축/인테리어", "course": "맥스1~3",           "price": 450000},
    {"department": "건축/인테리어", "course": "스케치1~4",         "price": 400000},
    {"department": "건축/인테리어", "course": "실내건축이론",       "price": 400000},
    {"department": "건축/인테리어", "course": "실내건축자격증",     "price": 400000},
    {"department": "건축/인테리어", "course": "인테리어포폴1~3",   "price": 500000},
    {"department": "건축/인테리어", "course": "BIM1~2/주말",       "price": 400000},
    {"department": "건축/인테리어", "course": "AI크리에이터-인테리어","price": 500000},
    {"department": "건축/인테리어", "course": "퓨전1~2/주말",      "price": 400000},
    {"department": "건축/인테리어", "course": "인벤터/주말",       "price": 400000},
    {"department": "건축/인테리어", "course": "전산응용건축제도/주말","price": 450000},
    {"department": "건축/인테리어", "course": "전산응용기계제도/주말","price": 450000},
    {"department": "건축/인테리어", "course": "기계설계산업기사/주말","price": 450000},
    {"department": "건축/인테리어", "course": "일반기계기사/주말", "price": 450000},
    {"department": "건축/인테리어", "course": "시공실무/주말",     "price": 300000},
    {"department": "건축/인테리어", "course": "캐드/주말",         "price": 600000},
    # 모션/영상
    {"department": "모션/영상", "course": "프리미어",          "price": 400000},
    {"department": "모션/영상", "course": "에펙",              "price": 450000},
    {"department": "모션/영상", "course": "모션에펙",          "price": 450000},
    {"department": "모션/영상", "course": "어드벤스 에펙",     "price": 450000},
    {"department": "모션/영상", "course": "블렌더1~2",         "price": 500000},
    {"department": "모션/영상", "course": "시포디1~4",         "price": 500000},
    {"department": "모션/영상", "course": "모션포폴1~3",       "price": 600000},
    {"department": "모션/영상", "course": "유크리 기초/심화",  "price": 400000},
    {"department": "모션/영상", "course": "AI크리에이터-영상모션","price": 500000},
    {"department": "모션/영상", "course": "AI크리에이터-유튜브",  "price": 500000},
    # 마야/CG
    {"department": "마야/CG", "course": "마야1~7",           "price": 600000},
    {"department": "마야/CG", "course": "마야포폴1~6",       "price": 600000},
    {"department": "마야/CG", "course": "AI크리에이터-CG마야","price": 500000},
    # 웹툰
    {"department": "웹툰", "course": "웹툰1~6", "price": 500000},
    # IT/프로그래밍
    {"department": "IT/프로그래밍", "course": "파이썬/주말",   "price": 400000},
    {"department": "IT/프로그래밍", "course": "C언어1~2/주말", "price": 400000},
    {"department": "IT/프로그래밍", "course": "자바1~2/주말",  "price": 400000},
    # AI 크리에이터
    {"department": "AI 크리에이터", "course": "AI프롬프트1~2",  "price": 600000},
    {"department": "AI 크리에이터", "course": "AI에이전트1-2",  "price": 600000},
]


# ── 공개 API ──────────────────────────────────────────────────────────────────

def load_courses() -> list[dict]:
    """
    수강료 데이터를 로드합니다.
    '수강료.xlsx'가 있으면 엑셀에서 파싱하고, 없거나 오류 시 정적 데이터를 반환합니다.
    반환 형태: [{"department": str, "course": str, "price": int}, ...]
    """
    if EXCEL_PATH.exists():
        try:
            result = _load_from_excel()
            if result:
                return result
        except Exception:
            pass
    return STATIC_COURSES


# ── 내부 파싱 ──────────────────────────────────────────────────────────────────

def _load_from_excel() -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb["수강료"]
    return _parse_sheet(ws)


def _parse_sheet(ws) -> list[dict]:
    HEADER = {"구분", "학과", "학원과정명", "일반수강료", "일수", "일시간", "총시간"}

    seen: dict[str, dict] = {}
    l_sched = l_dept = r_sched = r_dept = None

    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 16:
            continue

        _l_sched, _l_dept, l_name, l_price = row[1], row[2], row[3], row[4]
        _r_sched, _r_dept, r_name, r_price = row[9], row[10], row[11], row[12]

        # 현재 구분/학과 추적 (헤더 텍스트는 무시)
        if _l_sched is not None and str(_l_sched).strip() not in HEADER:
            l_sched = str(_l_sched).replace("\n", " ").strip()
        if _l_dept is not None and str(_l_dept).strip() not in HEADER:
            l_dept = str(_l_dept).replace("\n", " ").strip()
        if _r_sched is not None and str(_r_sched).strip() not in HEADER:
            r_sched = str(_r_sched).replace("\n", " ").strip()
        if _r_dept is not None and str(_r_dept).strip() not in HEADER:
            r_dept = str(_r_dept).replace("\n", " ").strip()

        # 왼쪽 과정 처리
        _add_course(seen, l_name, l_price, l_dept)
        # 오른쪽 과정 처리
        _add_course(seen, r_name, r_price, r_dept)

    return list(seen.values())


def _add_course(seen: dict, name, price, dept: str | None) -> None:
    HEADER = {"구분", "학과", "학원과정명", "일반수강료", "일수", "일시간", "총시간", None}
    if name is None or str(name).strip() in HEADER:
        return
    name_str = str(name).strip()
    if not name_str or name_str in seen:
        return
    try:
        price_int = int(price)
        if price_int < 10000:
            return
        seen[name_str] = {
            "department": (dept or "기타").strip(),
            "course":     name_str,
            "price":      price_int,
        }
    except (ValueError, TypeError):
        pass
