"""
log_generator.py — 상담일지 마크다운 파일 생성기
저장 경로: logs/상담일지_이름_YYYYMMDD.md
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

from calculator import Cart, fmt_won

LOGS_DIR = Path(__file__).parent / "logs"


def _table_row(cols: list[str]) -> str:
    return "| " + " | ".join(cols) + " |"


def _divider(n: int) -> str:
    return "|" + "|".join(["---"] * n) + "|"


def generate_log(
    name: str,
    contact: str,
    field: str,
    memo: str,
    cart: Cart,
    consultant: str = "상담사",
) -> Path:
    """
    상담일지 마크다운 파일을 생성하고 저장 경로를 반환한다.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    time_str = today.strftime("%Y-%m-%d %H:%M")
    filename = f"상담일지_{name}_{date_str}.md"
    filepath = LOGS_DIR / filename

    lines: list[str] = []

    # ── 타이틀 ──────────────────────────────────────────────────────────────
    lines += [
        "# SBS아카데미 대전지점 상담일지",
        "",
        f"> 작성일시: {time_str}  ",
        f"> 담당 상담사: {consultant}",
        "",
        "---",
        "",
    ]

    # ── 상담생 정보 ──────────────────────────────────────────────────────────
    lines += [
        "## 상담생 정보",
        "",
        f"- **이름**: {name}",
        f"- **연락처**: {contact}",
        f"- **희망 분야**: {field}",
        "",
    ]

    # ── 수강료 내역 ──────────────────────────────────────────────────────────
    lines += [
        "## 수강료 내역",
        "",
    ]

    if cart.is_empty():
        lines.append("*(선택된 과정 없음)*")
    else:
        headers = ["학과", "과정명", "정가", "할인율", "할인가", "할인금액"]
        lines.append(_table_row(headers))
        lines.append(_divider(len(headers)))

        for row in cart.summary():
            lines.append(
                _table_row(
                    [
                        row["department"],
                        row["course"],
                        fmt_won(row["price"]),
                        f"{row['discount_rate']:.1f}%",
                        fmt_won(row["discounted_price"]),
                        fmt_won(row["discount_amount"]),
                    ]
                )
            )

        lines += [
            "",
            f"- **소계 (개별 할인 적용)**: {fmt_won(cart.subtotal)}",
        ]
        if cart.global_discount > 0:
            lines.append(
                f"- **추가 할인율**: {cart.global_discount:.1f}%"
            )
        lines += [
            f"- **최종 납부금액**: **{fmt_won(cart.total)}**",
            f"- **총 할인금액**: {fmt_won(cart.total_discount_amount)}",
            "",
        ]

    lines += ["---", ""]

    # ── 상담 메모 ────────────────────────────────────────────────────────────
    lines += [
        "## 상담 메모",
        "",
        memo if memo.strip() else "*(메모 없음)*",
        "",
        "---",
        "",
    ]

    # ── 팀장용 코멘트 섹션 ───────────────────────────────────────────────────
    lines += [
        "## 팀장 확인 및 코멘트",
        "",
        "| 항목 | 내용 |",
        "|---|---|",
        "| 검토 여부 | ☐ 검토 완료 |",
        "| 등록 여부 | ☐ 등록 / ☐ 미등록 / ☐ 보류 |",
        "| 팀장 서명 | |",
        "| 코멘트 | |",
        "",
        "> *이 문서는 SBS아카데미 대전지점 내부용 상담 기록입니다.*",
        "",
    ]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath
