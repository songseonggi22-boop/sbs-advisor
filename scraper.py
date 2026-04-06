"""
scraper.py — SBS아카데미 대전지점 수강료 페이지 크롤러
대상: https://daejeon.sbsart.com/customer/tuition_info.asp
"""

import json
import re
import sys
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("필요한 패키지가 없습니다. 'pip install requests beautifulsoup4' 를 실행하세요.")
    sys.exit(1)

TARGET_URL = "https://daejeon.sbsart.com/customer/tuition_info.asp"
OUTPUT_FILE = Path(__file__).parent / "courses.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _clean_price(text: str) -> int:
    """'150,000원' 또는 '150000' → 정수 반환. 숫자 없으면 0."""
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def scrape(url: str = TARGET_URL) -> list[dict]:
    """
    수강료 페이지를 파싱해 과정 목록을 반환한다.
    반환 형태: [{"department": str, "course": str, "price": int}, ...]
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
    except requests.RequestException as e:
        raise RuntimeError(f"페이지 로드 실패: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    courses: list[dict] = []

    # --- 1차 시도: <table> 구조 파싱 ---
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        current_dept = ""
        for row in rows:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            texts = [_clean_text(c.get_text()) for c in cells]

            # 학과 헤더 행 감지 (colspan 사용, td 1개)
            if len(cells) == 1:
                t = texts[0]
                if t and not re.search(r"\d{3,}", t):
                    current_dept = t
                continue

            # 과정명 + 수강료 행
            if len(texts) >= 2:
                course_name = texts[0]
                # 마지막 셀에서 금액 추출
                price_raw = texts[-1]
                price = _clean_price(price_raw)

                if course_name and price >= 10_000:
                    courses.append(
                        {
                            "department": current_dept or "미분류",
                            "course": course_name,
                            "price": price,
                        }
                    )

    # --- 2차 시도: 테이블 파싱 실패 시 텍스트 패턴으로 추출 ---
    if not courses:
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        dept = "미분류"
        for i, line in enumerate(lines):
            # 숫자가 없고 짧으면 학과명 후보
            if len(line) < 30 and not re.search(r"\d{4,}", line):
                dept = line
            price_match = re.search(r"(\d[\d,]+)\s*원?", line)
            if price_match:
                price = _clean_price(price_match.group(1))
                # 앞 줄을 과정명으로 간주
                course = lines[i - 1] if i > 0 else line
                if price >= 10_000:
                    courses.append(
                        {
                            "department": dept,
                            "course": _clean_text(course),
                            "price": price,
                        }
                    )

    return courses


def save(courses: list[dict], path: Path = OUTPUT_FILE) -> None:
    path.write_text(
        json.dumps(courses, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_or_scrape(force: bool = False) -> list[dict]:
    """저장된 courses.json이 있으면 읽고, 없거나 force=True이면 크롤링."""
    if not force and OUTPUT_FILE.exists():
        data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        if data:
            return data
    courses = scrape()
    if courses:
        save(courses)
    return courses


# ── 직접 실행 시 테스트 ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("크롤링 중...")
    result = load_or_scrape(force=True)
    print(f"수집된 과정 수: {len(result)}")
    for c in result[:5]:
        print(c)
