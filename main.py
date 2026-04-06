"""
main.py — SBS아카데미 대전지점 교육과정 상담 및 설계 자동화 CLI
실행: python main.py
"""

from __future__ import annotations
import io
import sys
from pathlib import Path

# ── Windows UTF-8 강제 설정 ──────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Rich 의존성 체크 ─────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm
    from rich import box
    from rich.text import Text
    from rich.columns import Columns
except ImportError:
    print("Rich 라이브러리가 필요합니다: pip install rich")
    sys.exit(1)

from scraper import load_or_scrape
from calculator import Cart, CourseItem, fmt_won
from log_generator import generate_log

console = Console(legacy_windows=False, highlight=False)

BRAND = "[bold cyan]SBS아카데미[/bold cyan] [white]대전지점[/white]"
DIVIDER = "[dim]─" * 60 + "[/dim]"


# ── 유틸 ─────────────────────────────────────────────────────────────────────

def header(title: str) -> None:
    console.print()
    console.print(Panel(f"[bold yellow]{title}[/bold yellow]", subtitle=BRAND, style="cyan"))


def success(msg: str) -> None:
    console.print(f"[bold green][OK][/bold green]  {msg}")


def warn(msg: str) -> None:
    console.print(f"[bold yellow][!!][/bold yellow]  {msg}")


def error(msg: str) -> None:
    console.print(f"[bold red][XX][/bold red]  {msg}")


def pause() -> None:
    Prompt.ask("\n[dim]계속하려면 Enter를 누르세요[/dim]", default="")


# ── 화면 1: 과정 목록 표시 ───────────────────────────────────────────────────

def show_course_list(courses: list[dict]) -> None:
    header("전체 과정 목록")
    depts: dict[str, list] = {}
    for c in courses:
        depts.setdefault(c["department"], []).append(c)

    for dept, items in depts.items():
        t = Table(
            title=f"[bold magenta]{dept}[/bold magenta]",
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=True,
        )
        t.add_column("번호", justify="right", style="dim", width=5)
        t.add_column("과정명", min_width=20)
        t.add_column("정가", justify="right", style="green")

        for idx, item in enumerate(items):
            global_idx = courses.index(item) + 1
            t.add_row(str(global_idx), item["course"], fmt_won(item["price"]))

        console.print(t)
        console.print()


# ── 화면 2: 장바구니 & 할인 계산 ────────────────────────────────────────────

def show_cart(cart: Cart) -> None:
    header("현재 장바구니")
    if cart.is_empty():
        warn("선택된 과정이 없습니다.")
        return

    t = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan", show_lines=True)
    t.add_column("#", justify="right", style="dim", width=4)
    t.add_column("학과", style="magenta")
    t.add_column("과정명", min_width=18)
    t.add_column("정가", justify="right", style="yellow")
    t.add_column("할인율", justify="center")
    t.add_column("할인가", justify="right", style="green bold")
    t.add_column("절약", justify="right", style="cyan")

    for i, row in enumerate(cart.summary(), 1):
        t.add_row(
            str(i),
            row["department"],
            row["course"],
            fmt_won(row["price"]),
            f"{row['discount_rate']:.1f}%",
            fmt_won(row["discounted_price"]),
            f"-{fmt_won(row['discount_amount'])}",
        )

    console.print(t)
    console.print(f"  소계 (개별 할인 후): [yellow]{fmt_won(cart.subtotal)}[/yellow]")
    if cart.global_discount > 0:
        console.print(f"  추가 할인율: [cyan]{cart.global_discount:.1f}%[/cyan]")
    console.print(f"  [bold]최종 납부금액: [green]{fmt_won(cart.total)}[/green][/bold]")
    console.print(f"  총 할인금액:  [cyan]-{fmt_won(cart.total_discount_amount)}[/cyan]")


# ── 화면 3: 과정 선택 플로우 ─────────────────────────────────────────────────

def select_courses_flow(courses: list[dict], cart: Cart) -> None:
    header("과정 선택")
    show_course_list(courses)

    while True:
        console.print(DIVIDER)
        console.print(
            "[bold]번호[/bold]를 입력해 과정을 추가합니다. "
            "[dim](완료: 0, 장바구니 확인: c, 삭제: d)[/dim]"
        )
        raw = Prompt.ask("[cyan]>[/cyan]").strip().lower()

        if raw == "0":
            break
        if raw == "c":
            show_cart(cart)
            continue
        if raw == "d":
            _remove_from_cart(cart)
            continue

        if not raw.isdigit():
            warn("숫자 또는 명령어(0/c/d)를 입력하세요.")
            continue

        idx = int(raw) - 1
        if not (0 <= idx < len(courses)):
            error(f"1~{len(courses)} 사이의 번호를 입력하세요.")
            continue

        chosen = courses[idx]
        # 개별 할인율 입력 (기본 0)
        disc_raw = Prompt.ask(
            f"  [yellow]{chosen['course']}[/yellow] 개별 할인율(%)",
            default="0",
        )
        try:
            disc = float(disc_raw)
            if not 0 <= disc <= 100:
                raise ValueError
        except ValueError:
            error("0~100 사이의 숫자를 입력하세요.")
            continue

        cart.add(CourseItem(
            department=chosen["department"],
            course=chosen["course"],
            price=chosen["price"],
            discount_rate=disc,
        ))
        success(f"'{chosen['course']}' 추가됨 (할인율 {disc:.1f}%)")


def _remove_from_cart(cart: Cart) -> None:
    if cart.is_empty():
        warn("장바구니가 비어 있습니다.")
        return
    show_cart(cart)
    try:
        n = IntPrompt.ask("삭제할 항목 번호 (취소: 0)", default=0)
        if n == 0:
            return
        removed = cart.remove(n - 1)
        success(f"'{removed.course}' 삭제됨")
    except (IndexError, ValueError):
        error("올바른 번호를 입력하세요.")


# ── 화면 4: 전체 할인율 설정 ─────────────────────────────────────────────────

def set_global_discount_flow(cart: Cart) -> None:
    header("전체 추가 할인 설정")
    show_cart(cart)
    console.print()
    try:
        rate = FloatPrompt.ask("전체 추가 할인율(%) 입력", default=0.0)
        cart.set_global_discount(rate)
        success(f"전체 할인율 {rate:.1f}% 적용됨")
        show_cart(cart)
    except ValueError as e:
        error(str(e))


# ── 화면 5: 상담일지 생성 ────────────────────────────────────────────────────

def create_log_flow(cart: Cart) -> None:
    header("상담일지 생성")

    if cart.is_empty():
        warn("선택된 과정이 없습니다. 과정을 먼저 선택해주세요.")
        pause()
        return

    show_cart(cart)
    console.print()

    name       = Prompt.ask("[cyan]상담생 이름[/cyan]")
    contact    = Prompt.ask("[cyan]연락처[/cyan]")
    field      = Prompt.ask("[cyan]희망 분야[/cyan]")
    consultant = Prompt.ask("[cyan]담당 상담사 이름[/cyan]", default="상담사")
    console.print("[cyan]상담 메모[/cyan] (여러 줄 입력 후 빈 줄 Enter로 완료):")

    memo_lines: list[str] = []
    while True:
        line = input()
        if line == "":
            break
        memo_lines.append(line)
    memo = "\n".join(memo_lines)

    path = generate_log(
        name=name,
        contact=contact,
        field=field,
        memo=memo,
        cart=cart,
        consultant=consultant,
    )
    success(f"상담일지 저장 완료: [underline]{path}[/underline]")
    pause()


# ── 메인 메뉴 ────────────────────────────────────────────────────────────────

MENU_ITEMS = [
    ("1", "과정 목록 보기"),
    ("2", "과정 선택 / 장바구니"),
    ("3", "장바구니 확인"),
    ("4", "전체 추가 할인 설정"),
    ("5", "상담일지 생성"),
    ("6", "데이터 새로 고침 (재크롤링)"),
    ("0", "종료"),
]


def main_menu() -> None:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column("key", style="bold cyan", width=4)
    t.add_column("label")
    for key, label in MENU_ITEMS:
        t.add_row(key, label)
    console.print(Panel(t, title=BRAND, subtitle="교육과정 상담 자동화 시스템", style="cyan"))


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main() -> None:
    console.clear()
    console.print(Panel(
        "[bold cyan]SBS아카데미 대전지점[/bold cyan]\n"
        "[white]교육과정 상담 및 설계 자동화 도구[/white]",
        style="bold cyan",
        padding=(1, 4),
    ))

    # 데이터 로드
    with console.status("[bold cyan]수강료 데이터 로딩 중...[/bold cyan]"):
        try:
            courses = load_or_scrape()
        except RuntimeError as e:
            error(str(e))
            courses = []

    if not courses:
        warn("수강료 데이터를 불러오지 못했습니다. 샘플 데이터로 시작합니다.")
        courses = _sample_courses()

    success(f"과정 {len(courses)}개 로드 완료")

    cart = Cart()

    while True:
        console.print()
        main_menu()
        choice = Prompt.ask("[cyan]메뉴 선택[/cyan]", default="0").strip()

        if choice == "1":
            show_course_list(courses)
            pause()

        elif choice == "2":
            select_courses_flow(courses, cart)

        elif choice == "3":
            show_cart(cart)
            pause()

        elif choice == "4":
            set_global_discount_flow(cart)
            pause()

        elif choice == "5":
            create_log_flow(cart)

        elif choice == "6":
            with console.status("[bold cyan]재크롤링 중...[/bold cyan]"):
                try:
                    courses = load_or_scrape(force=True)
                    success(f"업데이트 완료: 과정 {len(courses)}개")
                except RuntimeError as e:
                    error(str(e))

        elif choice == "0":
            console.print("\n[bold cyan]이용해 주셔서 감사합니다.[/bold cyan]\n")
            break

        else:
            warn("올바른 메뉴 번호를 입력하세요.")


# ── 샘플 데이터 (크롤링 실패 시 폴백) ────────────────────────────────────────

def _sample_courses() -> list[dict]:
    return [
        {"department": "영상·편집", "course": "영상편집(프리미어+애프터이펙트)", "price": 1_200_000},
        {"department": "영상·편집", "course": "유튜브 크리에이터 과정",            "price": 800_000},
        {"department": "그래픽디자인", "course": "포토샵+일러스트레이터",           "price": 1_000_000},
        {"department": "그래픽디자인", "course": "UI/UX 디자인(피그마)",           "price": 1_100_000},
        {"department": "3D·애니메이션", "course": "3ds Max 기초",                 "price": 1_300_000},
        {"department": "3D·애니메이션", "course": "마야(Maya) 캐릭터 애니메이션",  "price": 1_500_000},
        {"department": "웹디자인", "course": "웹퍼블리셔(HTML/CSS/JS)",           "price": 1_200_000},
        {"department": "웹디자인", "course": "반응형 웹디자인",                   "price": 900_000},
        {"department": "실내건축", "course": "AutoCAD 2D/3D",                    "price": 700_000},
        {"department": "실내건축", "course": "스케치업+V-Ray 인테리어",            "price": 1_000_000},
    ]


if __name__ == "__main__":
    main()
