"""
auto_pilot.py — SBS아카데미 블로그 자동 발행 파일럿
실행: python auto_pilot.py

동작:
  1. keywords.txt 에서 키워드를 한 줄씩 읽어온다.
  2. Gemini 2.5 Flash로 SEO 최적화 원고를 생성한다.
  3. 생성된 원고를 워드프레스에 즉시 publish 상태로 업로드한다.
  4. 포스팅 완료 후 3600초(1시간) 대기 후 다음 키워드로 넘어간다.
  5. 모든 과정은 automation.log에 기록된다.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import google.generativeai as genai
import markdown as md_lib
import requests
from dotenv import load_dotenv

# ── 환경변수 로드 ──────────────────────────────────────────────────────────────
load_dotenv()
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
WP_URL          = os.getenv("WP_URL", "")
WP_USERNAME     = os.getenv("WP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")

# ── 경로 ──────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent
KEYWORDS_FILE = ROOT / "keywords.txt"
LOG_FILE      = ROOT / "automation.log"

# ── 대기 시간 ─────────────────────────────────────────────────────────────────
SLEEP_SECONDS = 3600  # 1시간

# ── 로깅 설정 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),          # 터미널에도 동시 출력
    ],
)
log = logging.getLogger(__name__)

# ── 시스템 프롬프트 (app.py의 BLOG_DEFAULT_PROMPT와 동일) ──────────────────────
SYSTEM_PROMPT = """\
# Role
너는 네이버 SEO + 구글 SEO에 동시에 최적화된 한국어 블로그 콘텐츠 라이터이자 편집자다. 특히 네이버 블로그 모바일 화면에서 가독성이 좋아지도록 "짧은 문단 + 잦은 줄바꿈"을 기본 규칙으로 원고를 작성한다. 후기형(리뷰 톤)으로 자연스럽게 쓰되, 구조(H1~H4)와 맞춤법·띄어쓰기·오탈자 품질을 최상으로 유지한다.

# Context
사용자가 메인키워드 1개를 주면, 네이버 SEO(가독성/체류시간/목차/후기형 문장/키워드 분산) + 구글 SEO(명확한 헤딩 계층, 스캐너블 구성, Q&A)를 만족하는 글을 작성한다.
- 이모티콘/이모지 완전 금지(숫자 이모지 포함 모든 유니코드 이모지 금지)
- 본문에 마크다운 표 최소 1개 포함
- 결과물은 바로 복사-붙여넣기 가능한 마크다운으로만 출력
- 홍보 대상: SBS아카데미컴퓨터학원 대전점
- 문단 규칙: 한 문단 1~3문장, 220자 이내 준수

# Task
- 구성: 제목(H1), 도입, 목차, 본문(H2/H3/H4), 표, Q&A(5개), 마무리, CTA(1개)
- CTA는 마지막 줄에 "SBS아카데미컴퓨터학원 대전점" 문의 유도로 고정
"""


# ── 유틸 함수 ─────────────────────────────────────────────────────────────────

def extract_title(md_text: str) -> str:
    """마크다운 첫 번째 H1 줄을 포스트 제목으로 반환합니다."""
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return "SBS아카데미 블로그 포스트"


def generate_post(keyword: str) -> str:
    """Gemini 2.5 Flash로 블로그 원고를 생성합니다."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(f"결과를 작성할 메인 키워드: {keyword}")
    return response.text


def post_to_wordpress(title: str, content: str, status: str = "publish") -> dict:
    """워드프레스 REST API로 포스트를 발행합니다."""
    endpoint = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
    resp = requests.post(
        endpoint,
        auth=(WP_USERNAME, WP_APP_PASSWORD),
        json={"title": title, "content": content, "status": status},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def load_keywords() -> list[str]:
    """keywords.txt에서 빈 줄과 주석(#)을 제외하고 키워드 목록을 반환합니다."""
    if not KEYWORDS_FILE.exists():
        log.error(f"keywords.txt 파일을 찾을 수 없습니다: {KEYWORDS_FILE}")
        return []
    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    keywords = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    log.info(f"키워드 {len(keywords)}개 로드 완료: {KEYWORDS_FILE}")
    return keywords


def validate_env() -> bool:
    """필수 환경변수가 모두 설정됐는지 확인합니다."""
    missing = [
        name for name, val in [
            ("GEMINI_API_KEY",  GEMINI_API_KEY),
            ("WP_URL",          WP_URL),
            ("WP_USERNAME",     WP_USERNAME),
            ("WP_APP_PASSWORD", WP_APP_PASSWORD),
        ]
        if not val
    ]
    if missing:
        log.error(f".env에 다음 항목이 누락되었습니다: {', '.join(missing)}")
        return False
    return True


# ── 메인 루프 ─────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("auto_pilot.py 시작")
    log.info("=" * 60)

    if not validate_env():
        log.error("환경변수 오류로 종료합니다. .env 파일을 확인해 주세요.")
        return

    keywords = load_keywords()
    if not keywords:
        log.error("처리할 키워드가 없습니다. keywords.txt를 확인해 주세요.")
        return

    total = len(keywords)
    for idx, keyword in enumerate(keywords, start=1):
        log.info(f"[{idx}/{total}] 키워드 처리 시작: '{keyword}'")

        # ① 원고 생성
        try:
            log.info("  → Gemini 원고 생성 중...")
            md_content = generate_post(keyword)
            title = extract_title(md_content)
            log.info(f"  → 원고 생성 완료 | 제목: '{title}' | {len(md_content)}자")
        except Exception as e:
            log.error(f"  → 원고 생성 실패: {e}")
            log.info(f"  → {SLEEP_SECONDS}초 대기 후 다음 키워드로 넘어갑니다.")
            time.sleep(SLEEP_SECONDS)
            continue

        # ② HTML 변환
        html_content = md_lib.markdown(
            md_content,
            extensions=["tables", "fenced_code"],
        )

        # ③ 워드프레스 발행
        try:
            log.info("  → 워드프레스 발행 중...")
            result = post_to_wordpress(title, html_content)
            post_id   = result.get("id")
            post_link = result.get("link", "")
            log.info(f"  → 발행 완료! 포스트 ID: {post_id} | URL: {post_link}")
        except requests.HTTPError as e:
            log.error(
                f"  → 발행 실패 (HTTP {e.response.status_code}): "
                f"{e.response.text[:300]}"
            )
        except Exception as e:
            log.error(f"  → 발행 실패: {e}")

        # ④ 대기 (마지막 키워드는 대기 없이 종료)
        if idx < total:
            log.info(f"  → {SLEEP_SECONDS // 60}분 대기 중... (다음 키워드: '{keywords[idx]}')")
            time.sleep(SLEEP_SECONDS)

    log.info("=" * 60)
    log.info("모든 키워드 처리 완료. auto_pilot.py 종료.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
