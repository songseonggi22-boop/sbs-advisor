"""
calculator.py — 수강료 계산 및 할인 로직
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


def course_level_count(course_name: str) -> int:
    """
    과정명에서 레벨(단계) 수를 추출합니다.
    '마야1~7' → 7, '웹1~3' → 3, '에펙' → 1
    """
    # 틸드 범위: 마야1~7, 웹1~3, C언어1~2/주말 등
    m = re.search(r'(\d+)~(\d+)', course_name)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        return max(1, end - start + 1)
    # 하이픈 범위: AI에이전트1-2 등 (양쪽 모두 숫자인 경우만)
    m = re.search(r'(\d+)-(\d+)', course_name)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        if end > start:
            return end - start + 1
    return 1


@dataclass
class CourseItem:
    department: str
    course: str
    price: int           # 정가 (원)
    discount_rate: float = 0.0   # 0.0 ~ 100.0 (%)

    @property
    def discounted_price(self) -> int:
        return round(self.price * (1 - self.discount_rate / 100))

    @property
    def discount_amount(self) -> int:
        return self.price - self.discounted_price


@dataclass
class Cart:
    items: list[CourseItem] = field(default_factory=list)
    global_discount: float = 0.0   # 전체 할인율 (%)

    # ── 아이템 관리 ─────────────────────────────────────────────────────────
    def add(self, item: CourseItem) -> None:
        self.items.append(item)

    def remove(self, index: int) -> CourseItem:
        return self.items.pop(index)

    def clear(self) -> None:
        self.items.clear()

    # ── 합계 계산 ────────────────────────────────────────────────────────────
    @property
    def subtotal(self) -> int:
        """개별 할인 적용 후 합계."""
        return sum(i.discounted_price for i in self.items)

    @property
    def total(self) -> int:
        """전체 할인율 추가 적용 후 최종 금액."""
        return round(self.subtotal * (1 - self.global_discount / 100))

    @property
    def total_discount_amount(self) -> int:
        original = sum(i.price for i in self.items)
        return original - self.total

    def set_global_discount(self, rate: float) -> None:
        if not 0 <= rate <= 100:
            raise ValueError("할인율은 0~100 사이여야 합니다.")
        self.global_discount = rate

    # ── 요약 데이터 ──────────────────────────────────────────────────────────
    def summary(self) -> list[dict]:
        """Rich 테이블 출력용 딕셔너리 리스트 반환."""
        rows = []
        for item in self.items:
            rows.append(
                {
                    "department": item.department,
                    "course": item.course,
                    "price": item.price,
                    "discount_rate": item.discount_rate,
                    "discounted_price": item.discounted_price,
                    "discount_amount": item.discount_amount,
                }
            )
        return rows

    def is_empty(self) -> bool:
        return len(self.items) == 0


def fmt_won(amount: int) -> str:
    """정수 원화 포맷: 1500000 → '1,500,000원'"""
    return f"{amount:,}원"
