# SBS아카데미 대전지점 — 교육과정 상담 자동화 도구 계획안

> 작성일: 2026-04-06  
> 대상 사이트: https://daejeon.sbsart.com/

---

## 1. 프로젝트 개요

SBS아카데미 대전지점 상담사가 터미널에서 과정 목록을 조회하고, 수강료를 계산하며,
상담 결과를 마크다운 문서로 남길 수 있도록 돕는 **CLI 기반 자동화 도구**이다.

---

## 2. 디렉토리 구조

```
sbs_advisor/
├── main.py            # CLI 진입점 (Rich 메뉴)
├── scraper.py         # 수강료 페이지 크롤러
├── calculator.py      # 수강료 계산 & 할인 로직
├── log_generator.py   # 상담일지 마크다운 생성기
├── courses.json       # 크롤링 결과 캐시 (자동 생성)
├── requirements.txt   # 패키지 의존성
├── PLAN.md            # 본 계획서
└── logs/
    └── 상담일지_홍길동_20260406.md   # 상담일지 예시 (자동 생성)
```

---

## 3. 기능별 설계

### 3-1. 데이터 수집 (`scraper.py`)

| 항목 | 내용 |
|------|------|
| 대상 URL | `https://daejeon.sbsart.com/customer/tuition_info.asp` |
| 라이브러리 | `requests` + `BeautifulSoup4` |
| 파싱 전략 1 | `<table>` 태그 순회 → 학과 헤더 행 / 과정·금액 행 분리 |
| 파싱 전략 2 | 테이블 실패 시 전체 텍스트에서 금액 패턴(`\d[\d,]+원`) 추출 |
| 출력 | `courses.json` (학과명·과정명·정가 배열) |
| 캐시 정책 | `courses.json` 존재 시 재사용, `force=True` 시 재크롤링 |
| 폴백 | 크롤링 실패 시 `main.py` 내 샘플 데이터 10개로 대체 |

**수집 데이터 스키마**

```json
[
  {
    "department": "그래픽디자인",
    "course": "포토샵+일러스트레이터",
    "price": 1000000
  }
]
```

---

### 3-2. 수강료 계산 (`calculator.py`)

**핵심 클래스**

```
CourseItem
  ├── department: str
  ├── course: str
  ├── price: int          ← 정가
  ├── discount_rate: float  ← 개별 할인율(%)
  ├── discounted_price (property)
  └── discount_amount  (property)

Cart
  ├── items: list[CourseItem]
  ├── global_discount: float   ← 전체 추가 할인율(%)
  ├── subtotal   ← 개별 할인 합산
  ├── total      ← 전체 할인 적용 최종액
  └── summary()  ← Rich 테이블용 딕셔너리 리스트
```

**할인 적용 순서**

```
정가 → (개별 할인율 적용) → 소계 → (전체 추가 할인율 적용) → 최종 납부액
```

---

### 3-3. 상담일지 생성 (`log_generator.py`)

| 항목 | 내용 |
|------|------|
| 저장 경로 | `logs/상담일지_{이름}_{YYYYMMDD}.md` |
| 입력값 | 상담생 이름·연락처·희망 분야·상담 메모·담당 상담사 |
| 출력 형식 | 마크다운 (타이틀, 상담생 정보, 수강료 표, 메모, 팀장 코멘트 섹션) |

**마크다운 구조**

```
# SBS아카데미 대전지점 상담일지
> 작성일시 / 담당 상담사

## 상담생 정보
## 수강료 내역  ← 마크다운 표 (학과|과정|정가|할인율|할인가|절약액)
## 상담 메모
## 팀장 확인 및 코멘트  ← 체크박스 테이블 포함
```

---

### 3-4. CLI 인터페이스 (`main.py`)

| 메뉴 번호 | 기능 |
|-----------|------|
| 1 | 전체 과정 목록 보기 (학과별 Rich 테이블) |
| 2 | 과정 선택 및 장바구니 관리 (번호 입력 → 개별 할인율) |
| 3 | 장바구니 확인 (합계·할인 요약) |
| 4 | 전체 추가 할인율 설정 |
| 5 | 상담일지 생성 (정보 입력 → MD 파일 저장) |
| 6 | 수강료 데이터 재크롤링 |
| 0 | 종료 |

**Rich 구성 요소**

- `Panel` — 브랜드 헤더 및 메뉴 프레임
- `Table` — 과정 목록, 장바구니, 상담일지 수강료 표
- `Prompt` / `IntPrompt` / `FloatPrompt` — 사용자 입력
- `console.status` — 크롤링 중 스피너 애니메이션

---

## 4. 의존 패키지

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `requests` | ≥ 2.31 | HTTP 크롤링 |
| `beautifulsoup4` | ≥ 4.12 | HTML 파싱 |
| `rich` | ≥ 13.7 | 터미널 UI |

설치:
```bash
pip install -r requirements.txt
```

---

## 5. 실행 방법

```bash
cd sbs_advisor
pip install -r requirements.txt
python main.py
```

---

## 6. 예외 처리 전략

| 상황 | 처리 방식 |
|------|-----------|
| 크롤링 네트워크 오류 | `RuntimeError` → `warn` 메시지 + 샘플 데이터 폴백 |
| 페이지 구조 변경 | 2차 텍스트 패턴 파싱으로 자동 전환 |
| 잘못된 할인율 입력 | 0~100 범위 검증 후 재입력 요청 |
| 장바구니 비어있을 때 상담일지 생성 | `warn` 후 메인 메뉴 복귀 |
| `logs/` 디렉토리 없음 | `mkdir(parents=True, exist_ok=True)` 자동 생성 |

---

## 7. 확장 가능성 (향후 고려)

- **Excel 출력**: `openpyxl`로 상담일지를 `.xlsx`로도 저장
- **이메일 발송**: `smtplib`으로 팀장에게 자동 전송
- **웹 대시보드**: FastAPI + Jinja2로 브라우저 UI 전환
- **DB 연동**: SQLite로 상담 이력 누적 관리
- **스케줄 크롤링**: 주간 단위로 수강료 변동 자동 감지
