from __future__ import annotations

import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pygame

APP_NAME = "Year Planner"
WINDOW_SIZE = (1280, 820)
MIN_SIZE = (1080, 760)
FPS, TRACKS = 60, 10
DAY_WIDTH = 18.0
YEAR_RANGE = range(1900, 2201)

C = {
    "bg": (246, 248, 251), "panel": (255, 255, 255),
    "text": (35, 43, 55), "muted": (112, 123, 138),
    "grid": (205, 213, 222), "month": (85, 98, 115),
    "week": (255, 225, 236), "accent": (0, 151, 220),
    "accent_dark": (0, 115, 175), "border": (190, 200, 211),
    "danger": (220, 75, 75),
}
PALETTE = ("#A8E51A", "#00A8E8", "#FF8A28", "#A77BEB", "#F15B78",
           "#18B99A", "#F2C230", "#6685E8", "#8B969F", "#E85BCE")
MONTHS = ("январь", "февраль", "март", "апрель", "май", "июнь",
          "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
FIELDS = {
    "name": "Название", "text": "Описание", "tag": "Тег",
    "start": "Дата начала (ГГГГ-ММ-ДД)", "track": "Трек (1–10)",
    "duration": "Длительность, дней", "intensity": "Напряжённость (1–5)",
}


def uid() -> str:
    return uuid.uuid4().hex[:8]


def rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().removeprefix("#")
    if len(value) != 6:
        raise ValueError("Цвет в формате #RRGGBB")
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError("Некорректный цвет") from exc


def number(value: str, label: str) -> int:
    try:
        return int(value.strip())
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Поле «{label}» должно быть целым числом") from exc


@dataclass(slots=True)
class Task:
    id: str
    track: int
    name: str
    text: str
    tag: str
    start: str
    duration: int
    intensity: int
    color: str

    @property
    def start_date(self) -> date:
        return date.fromisoformat(self.start)

    @start_date.setter
    def start_date(self, value: date) -> None:
        self.start = value.isoformat()

    @classmethod
    def create(cls, year: int) -> Task:
        return cls(uid(), 1, "Новая задача", "", "", date(year, 1, 1).isoformat(), 7, 3, PALETTE[0])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        if not isinstance(data, dict):
            raise ValueError("Некорректная запись задачи в JSON")
        task = cls(
            str(data.get("id") or uid()), int(data.get("track", 1)),
            str(data.get("name", "Новая задача")), str(data.get("text", "")),
            str(data.get("tag", "")), date.fromisoformat(str(data.get("start", date.today().isoformat()))).isoformat(),
            int(data.get("duration", 1)), int(data.get("intensity", 3)),
            str(data.get("color", PALETTE[0])),
        )
        if not 1 <= task.track <= TRACKS:
            raise ValueError(f"Некорректный таск у задачи «{task.name}»")
        if not 1 <= task.duration <= 3650:
            raise ValueError(f"Некорректная длительность у задачи «{task.name}»")
        if not 1 <= task.intensity <= 5:
            raise ValueError(f"Некорректная напряжённость у задачи «{task.name}»")
        rgb(task.color)
        return task


class TaskEditor:
    def __init__(self, task: Task, is_new: bool) -> None:
        self.task, self.is_new = task, is_new
        self.values = {key: str(getattr(task, key)) for key in FIELDS}
        self.focus, self.color, self.error = "name", task.color, ""
        if self.color not in PALETTE:
            self.color = PALETTE[0]

    def rects(self, width: int) -> dict[str, pygame.Rect]:
        box = pygame.Rect((width - 620) // 2, 86, 620, 650)
        result = {"box": box}
        for index, field in enumerate(FIELDS):
            result[field] = pygame.Rect(box.x + 178, box.y + 94 + index * 55, 410, 38)
        result["save"] = pygame.Rect(box.right - 220, box.bottom - 52, 100, 34)
        result["cancel"] = pygame.Rect(box.right - 108, box.bottom - 52, 90, 34)
        return result

    def handle(self, event: pygame.event.Event, app: Planner) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_TAB:
                fields = list(FIELDS)
                self.focus = fields[(fields.index(self.focus) + 1) % len(fields)]
            elif event.key == pygame.K_RETURN:
                app.save_task()
            else:
                value = self.values[self.focus]
                if event.key == pygame.K_BACKSPACE:
                    self.values[self.focus] = value[:-1]
                elif event.key == pygame.K_DELETE:
                    self.values[self.focus] = ""
                elif event.unicode and event.unicode.isprintable():
                    limit = 180 if self.focus in ("name", "text") else 40
                    if len(value) < limit:
                        self.values[self.focus] += event.unicode
            return True

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return True

        rects = self.rects(app.width)
        for field in FIELDS:
            if rects[field].collidepoint(event.pos):
                self.focus = field
                return True
        palette_x, palette_y = rects["box"].x + 180, rects["box"].y + 500
        for index, color in enumerate(PALETTE):
            if pygame.Rect(palette_x + index * 39, palette_y, 27, 27).collidepoint(event.pos):
                self.color = color
                return True
        if rects["save"].collidepoint(event.pos):
            app.save_task()
        elif rects["cancel"].collidepoint(event.pos) or not rects["box"].collidepoint(event.pos):
            return False
        return True

    def draw(self, app: Planner) -> None:
        overlay = pygame.Surface((app.width, app.height), pygame.SRCALPHA)
        overlay.fill((20, 29, 40, 115))
        app.screen.blit(overlay, (0, 0))
        rects = self.rects(app.width)
        box = rects["box"]
        pygame.draw.rect(app.screen, C["panel"], box, border_radius=14)
        pygame.draw.rect(app.screen, C["border"], box, 1, border_radius=14)
        title = "Новая задача" if self.is_new else "Параметры задачи"
        app.screen.blit(app.title_font.render(title, True, C["text"]), (box.x + 28, box.y + 20))
        app.screen.blit(app.small.render(f"ID: {self.task.id}", True, C["muted"]), (box.x + 28, box.y + 59))

        for field, label in FIELDS.items():
            rect = rects[field]
            app.screen.blit(app.small.render(label, True, C["muted"]), (box.x + 28, rect.y + 10))
            active = field == self.focus
            pygame.draw.rect(app.screen, C["panel"], rect, border_radius=6)
            pygame.draw.rect(app.screen, C["accent"] if active else C["border"], rect, 2 if active else 1, border_radius=6)
            app.screen.blit(app.font.render(self.values[field], True, C["text"]), (rect.x + 9, rect.y + 9))

        px, py = box.x + 180, box.y + 500
        app.screen.blit(app.small.render("Цвет задачи", True, C["muted"]), (box.x + 28, py + 6))
        for index, color in enumerate(PALETTE):
            rect = pygame.Rect(px + index * 39, py, 27, 27)
            pygame.draw.rect(app.screen, rgb(color), rect, border_radius=5)
            pygame.draw.rect(app.screen, C["text"] if color == self.color else C["border"],
                             rect, 3 if color == self.color else 1, border_radius=5)
        if self.error:
            app.screen.blit(app.small.render(self.error, True, C["danger"]), (box.x + 28, box.bottom - 46))
        app.button(rects["save"], "Сохранить", primary=True)
        app.button(rects["cancel"], "Отмена")


class Planner:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(APP_NAME)
        self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        # Prefer Apple's SF Pro when installed; otherwise use a clean Windows fallback.
        self.font_family = next(
            (name for name in ("SF Pro Text", "SF Pro", "Segoe UI", "Arial")
             if pygame.font.match_font(name)),
            "sans",
        )
        self.font = pygame.font.SysFont(self.font_family, 15, bold=True)
        self.small = pygame.font.SysFont(self.font_family, 13, bold=True)
        self.tiny = pygame.font.SysFont(self.font_family, 11, bold=True)
        self.bold = pygame.font.SysFont(self.font_family, 14, bold=True)
        self.title_font = pygame.font.SysFont(self.font_family, 22, bold=True)
        self.width, self.height = self.screen.get_size()
        self.year = date.today().year
        self.year_input, self.year_active = str(self.year), False
        self.tasks: list[Task] = []
        self.selected: str | None = None
        self.editor: TaskEditor | None = None
        self.current_file: Path | None = None
        self.status, self.status_until = "Готово", 0
        self.day_width, self.scroll_day = DAY_WIDTH, 31
        self.drag: dict[str, Any] | None = None
        self.scroll_drag, self.scroll_offset = False, 0
        self.last_click: tuple[str, int] | None = None
        self.hovered: Task | None = None
        self.layout: dict[str, Any] = {}
        self.running = True
        self.set_axis()
        self.layout_window()

    def set_axis(self) -> None:
        self.axis_start = date(self.year, 1, 1) - timedelta(days=31)
        self.axis_end = date(self.year + 1, 1, 1) + timedelta(days=30)
        self.total_days = (self.axis_end - self.axis_start).days + 1

    def layout_window(self) -> None:
        self.width, self.height = self.screen.get_size()
        left, top = 98, 168
        track_height = max(31, (self.height - 130 - top) // TRACKS)
        bottom = top + track_height * TRACKS
        width = self.width - left - 28
        self.layout = {
            "left": left, "right": left + width, "top": top, "bottom": bottom,
            "width": width, "track_h": track_height,
            "bar": pygame.Rect(left, bottom + 30, width, 12),
        }
        zoom_width, week_width, gap, right_margin = 30, 116, 6, 15
        controls_x = self.width - right_margin - 2 * week_width - 2 * zoom_width - 3 * gap
        self.buttons = [
            ("Открыть", pygame.Rect(18, 16, 86, 34), "open"),
            ("Сохранить", pygame.Rect(112, 16, 96, 34), "save"),
            ("+ Задача", pygame.Rect(218, 16, 105, 34), "new"),
            ("Изменить", pygame.Rect(333, 16, 100, 34), "edit"),
            ("Удалить", pygame.Rect(443, 16, 86, 34), "delete"),
            ("−", pygame.Rect(controls_x, 16, zoom_width, 34), "zoom_out"),
            ("+", pygame.Rect(controls_x + zoom_width + gap, 16, zoom_width, 34), "zoom_in"),
            ("Неделя <-", pygame.Rect(controls_x + 2 * (zoom_width + gap), 16, week_width, 34), "prev"),
            ("Неделя ->", pygame.Rect(controls_x + 2 * (zoom_width + gap) + week_width + gap,
                                            16, week_width, 34), "next"),
        ]
        self.layout.update(year=pygame.Rect(590, 17, 82, 32),
                           apply=pygame.Rect(679, 17, 76, 32))
        y = self.layout["bar"].bottom + 25
        self.layout["left_btn"] = pygame.Rect(left + 145, y, 110, 34)
        self.layout["right_btn"] = pygame.Rect(left + 267, y, 110, 34)
        self.clamp_scroll()

    def clamp_scroll(self) -> None:
        visible = max(1, int(self.layout.get("width", 1000) / self.day_width))
        self.max_scroll = max(0, self.total_days - visible)
        self.scroll_day = max(0, min(self.scroll_day, self.max_scroll))

    def set_year(self, year: int) -> None:
        if year not in YEAR_RANGE:
            raise ValueError("Год должен быть в диапазоне 1900–2200")
        self.year, self.year_input = year, str(year)
        self.set_axis()
        self.scroll_day = 31
        self.clamp_scroll()
        self.message(f"Выбран {year} год")

    def to_x(self, value: date) -> float:
        return self.layout["left"] + ((value - self.axis_start).days - self.scroll_day) * self.day_width

    def to_date(self, x: float) -> date:
        offset = (x - self.layout["left"]) / self.day_width + self.scroll_day
        return self.axis_start + timedelta(days=round(offset))

    def to_y(self, track: int) -> int:
        return self.layout["top"] + (track - 1) * self.layout["track_h"]

    def to_track(self, y: int) -> int:
        value = (y - self.layout["top"]) // self.layout["track_h"] + 1
        return max(1, min(TRACKS, value))

    def task_rect(self, task: Task) -> pygame.Rect:
        track_h = self.layout["track_h"]
        height = min(track_h - 8, 8 + task.intensity * 5)
        y = self.to_y(task.track) + (track_h - height) // 2
        return pygame.Rect(round(self.to_x(task.start_date)) + 1, y,
                           max(5, round(task.duration * self.day_width) - 3), height)

    def message(self, text: str, seconds: int = 3) -> None:
        self.status, self.status_until = text, pygame.time.get_ticks() + seconds * 1000

    def selected_task(self) -> Task | None:
        return next((task for task in self.tasks if task.id == self.selected), None)

    def edit_task(self, task: Task | None = None) -> None:
        is_new = task is None
        self.editor = TaskEditor(task or Task.create(self.year), is_new)

    def save_task(self) -> None:
        if not self.editor:
            return
        editor, fields = self.editor, self.editor.values
        try:
            name = fields["name"].strip()
            if not name:
                raise ValueError("У задачи должно быть название")
            try:
                start = date.fromisoformat(fields["start"].strip())
            except ValueError as exc:
                raise ValueError("Дата должна быть в формате ГГГГ-ММ-ДД") from exc
            track, duration = number(fields["track"], "Трек"), number(fields["duration"], "Длительность")
            intensity = number(fields["intensity"], "Напряжённость")
            if not 1 <= track <= TRACKS:
                raise ValueError("Номер трека должен быть от 1 до 10")
            if not 1 <= duration <= 3650:
                raise ValueError("Длительность должна быть от 1 до 3650 дней")
            if not 1 <= intensity <= 5:
                raise ValueError("Напряжённость должна быть от 1 до 5")
            task = Task(editor.task.id, track, name, fields["text"].strip(), fields["tag"].strip(),
                        start.isoformat(), duration, intensity, editor.color)
            index = next((i for i, item in enumerate(self.tasks) if item.id == task.id), None)
            if index is None:
                self.tasks.append(task)
            else:
                self.tasks[index] = task
            self.selected, self.editor = task.id, None
            self.message("Задача создана" if index is None else "Задача обновлена")
        except ValueError as exc:
            editor.error = str(exc)

    def delete_task(self) -> None:
        if not self.selected:
            self.message("Сначала выберите задачу")
            return
        self.tasks = [task for task in self.tasks if task.id != self.selected]
        self.selected = None
        self.message("Задача удалена")

    def duplicate_task(self, task: Task) -> Task:
        copy = Task.from_dict(asdict(task))
        copy.id = uid()
        self.tasks.append(copy)
        self.selected = copy.id
        return copy

    @staticmethod
    def file_dialog(save: bool) -> Path | None:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        options = {"title": "Сохранить план" if save else "Открыть план",
                   "defaultextension": ".json", "filetypes": (("JSON-файлы", "*.json"), ("Все файлы", "*.*")),
                   "initialfile": "plan.json"}
        try:
            path = filedialog.asksaveasfilename(**options) if save else filedialog.askopenfilename(**options)
            return Path(path) if path else None
        finally:
            root.destroy()

    def save_file(self) -> None:
        try:
            path = self.file_dialog(True)
            if path is None:
                return
            data = {"app": APP_NAME, "version": 1, "year": self.year,
                    "tasks": [asdict(task) for task in self.tasks]}
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.current_file = path
            self.message(f"Сохранено: {path.name}")
        except (OSError, RuntimeError) as exc:
            self.message(f"Ошибка сохранения: {exc}", 5)

    def load_file(self) -> None:
        try:
            path = self.file_dialog(False)
            if path is None:
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                tasks = [Task.from_dict(item) for item in data]
            elif isinstance(data, dict):
                year = int(data.get("year", self.year))
                if year not in YEAR_RANGE:
                    raise ValueError("В файле указан некорректный год")
                tasks = [Task.from_dict(item) for item in data.get("tasks", [])]
                self.set_year(year)
            else:
                raise ValueError("Неподдерживаемый формат JSON")
            self.tasks, self.selected, self.current_file = tasks, None, path
            self.message(f"Загружено задач: {len(tasks)}")
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            self.message(f"Ошибка загрузки JSON: {exc}", 5)

    def button(self, rect: pygame.Rect, label: str, primary: bool = False, danger: bool = False) -> None:
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if danger:
            fill, edge, color = ((255, 239, 239) if hover else (255, 247, 247)), (225, 130, 130), C["danger"]
        elif primary:
            fill, edge, color = (C["accent_dark"] if hover else C["accent"]), C["accent_dark"], C["panel"]
        else:
            fill, edge, color = ((237, 244, 249) if hover else C["panel"]), C["border"], C["text"]
        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        pygame.draw.rect(self.screen, edge, rect, 1, border_radius=8)
        text = self.font.render(label, True, color)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def draw_toolbar(self) -> None:
        pygame.draw.rect(self.screen, C["panel"], (0, 0, self.width, 65))
        pygame.draw.line(self.screen, (225, 230, 236), (0, 64), (self.width, 64))
        self.screen.blit(self.title_font.render(APP_NAME, True, C["text"]), (18, 73))
        for label, rect, action in self.buttons:
            self.button(rect, label, action == "new", action == "delete")
        self.screen.blit(self.small.render("Год:", True, C["muted"]), (550, 25))
        year_rect = self.layout["year"]
        pygame.draw.rect(self.screen, C["panel"], year_rect, border_radius=6)
        pygame.draw.rect(self.screen, C["accent"] if self.year_active else C["border"], year_rect,
                         2 if self.year_active else 1, border_radius=6)
        self.screen.blit(self.font.render(self.year_input, True, C["text"]), (year_rect.x + 9, year_rect.y + 7))
        self.button(self.layout["apply"], "Перейти")

    def draw_weeks(self, first: date, last: date) -> None:
        left, top = self.layout["left"], self.layout["top"]
        week = first - timedelta(days=first.weekday())
        while week <= last:
            rect = pygame.Rect(round(self.to_x(week)), top, round(7 * self.day_width),
                               self.layout["bottom"] - top)
            clipped = rect.clip(pygame.Rect(left, top, self.layout["width"], self.layout["bottom"] - top))
            if clipped.width:
                tint = pygame.Surface(clipped.size, pygame.SRCALPHA)
                tint.fill((*C["week"], 70))
                self.screen.blit(tint, clipped.topleft)
            week += timedelta(days=7)

    def draw_calendar_grid(self, first: date, last: date) -> None:
        left, right = self.layout["left"], self.layout["right"]
        top, bottom = 137, self.layout["bottom"]
        count = int(self.layout["width"] / self.day_width) + 3
        for offset in range(-1, count):
            current = first + timedelta(days=offset)
            x = round(left + offset * self.day_width)
            if not left <= x <= right:
                continue
            month_start = current.day == 1
            pygame.draw.line(self.screen, C["month"] if month_start else C["grid"],
                             (x, top), (x, bottom), 2 if month_start else 1)
            color = (190, 90, 120) if current.weekday() >= 5 else C["muted"]
            self.screen.blit(self.tiny.render(str(current.day), True, color), (x + 3, 143))

        month = date(first.year, first.month, 1)
        while month <= last:
            next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
            x1, x2 = max(left, self.to_x(month)), min(right, self.to_x(next_month))
            if x2 - x1 > 48:
                label = self.small.render(f"{MONTHS[month.month - 1]} {month.year}", True, C["text"])
                self.screen.blit(label, (int((x1 + x2 - label.get_width()) / 2), 108))
            month = next_month

    def draw_tracks(self) -> None:
        left, right = self.layout["left"], self.layout["right"]
        for track in range(1, TRACKS + 1):
            y = self.to_y(track)
            label = self.bold.render(str(track), True, C["accent_dark"])
            self.screen.blit(label, (66, y + (self.layout["track_h"] - label.get_height()) // 2))
            pygame.draw.line(self.screen, (123, 202, 224), (left, y), (right, y), 2)
        pygame.draw.line(self.screen, (123, 202, 224), (left, self.layout["bottom"]),
                         (right, self.layout["bottom"]), 2)

    def draw_tasks(self) -> None:
        left, top = self.layout["left"], self.layout["top"]
        clip = pygame.Rect(left, top, self.layout["width"], self.layout["bottom"] - top)
        previous_clip, mouse = self.screen.get_clip(), pygame.mouse.get_pos()
        self.screen.set_clip(clip)
        self.hovered = None
        for task in self.tasks:
            rect = self.task_rect(task)
            if rect.right < left or rect.left > self.layout["right"]:
                continue
            color = rgb(task.color)
            selected = task.id == self.selected
            edge = (24, 65, 90) if selected else tuple(max(0, channel - 35) for channel in color)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            pygame.draw.rect(self.screen, edge, rect, 2 if selected else 1, border_radius=4)
            if rect.width > 54:
                label = self.small.render(task.name, True, (28, 35, 42))
                self.screen.blit(label, (rect.x + 5, rect.y + max(0, (rect.height - label.get_height()) // 2)))
            if rect.collidepoint(mouse):
                self.hovered = task
        self.screen.set_clip(previous_clip)

    def draw_timeline(self) -> None:
        left, bottom, width = self.layout["left"], self.layout["bottom"], self.layout["width"]
        pygame.draw.rect(self.screen, C["panel"], (left, 104, width, bottom - 104))
        pygame.draw.rect(self.screen, (240, 244, 248), (left, 104, width, 59))
        first = self.axis_start + timedelta(days=self.scroll_day)
        last = first + timedelta(days=int(width / self.day_width) + 2)
        self.draw_weeks(first, last)
        self.draw_calendar_grid(first, last)
        self.draw_tracks()
        self.draw_tasks()
        pygame.draw.line(self.screen, C["month"], (self.layout["right"], 137),
                         (self.layout["right"], bottom), 2)
        pygame.draw.rect(self.screen, C["month"], (left, 137, width, bottom - 137), 2)

    def draw_scrollbar(self) -> None:
        bar = self.layout["bar"]
        pygame.draw.rect(self.screen, (224, 230, 236), bar, border_radius=6)
        visible = max(1, self.layout["width"] / self.day_width)
        thumb_w = max(64, int(bar.width * visible / self.total_days))
        travel = max(1, bar.width - thumb_w)
        x = bar.x + int(travel * self.scroll_day / max(1, self.max_scroll))
        thumb = pygame.Rect(x, bar.y - 3, thumb_w, bar.height + 6)
        pygame.draw.rect(self.screen, (104, 157, 183), thumb, border_radius=7)
        pygame.draw.rect(self.screen, (70, 125, 153), thumb, 1, border_radius=7)
        self.layout["thumb"] = thumb

    def draw_tooltip(self) -> None:
        if not self.hovered or self.editor or self.drag:
            return
        task, mouse = self.hovered, pygame.mouse.get_pos()
        lines = [task.name, f"{task.start} • {task.duration} дн. • трек {task.track}"]
        if task.tag:
            lines.append(f"Тег: {task.tag}")
        if task.text:
            lines.append(task.text[:90])
        rendered = [self.small.render(line, True, C["text"]) for line in lines]
        width, height = max(t.get_width() for t in rendered) + 18, len(lines) * 19 + 12
        x, y = min(mouse[0] + 16, self.width - width - 8), min(mouse[1] + 15, self.height - height - 8)
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, (255, 255, 248), rect, border_radius=7)
        pygame.draw.rect(self.screen, (135, 145, 155), rect, 1, border_radius=7)
        for index, line in enumerate(rendered):
            self.screen.blit(line, (x + 9, y + 6 + index * 19))

    def draw_footer(self) -> None:
        self.button(self.layout["left_btn"], "Влево")
        self.button(self.layout["right_btn"], "Вправо")
        if pygame.time.get_ticks() < self.status_until:
            label = self.small.render(self.status, True, C["muted"])
            self.screen.blit(label, (self.width - label.get_width() - 24, self.height - 25))

    def draw(self) -> None:
        self.screen.fill(C["bg"])
        self.draw_toolbar()
        self.draw_timeline()
        self.draw_scrollbar()
        self.draw_footer()
        self.draw_tooltip()
        if self.editor:
            self.editor.draw(self)
        pygame.display.flip()

    def scroll(self, days: int) -> None:
        self.scroll_day += days
        self.clamp_scroll()

    def zoom(self, factor: float) -> None:
        center = self.to_date(self.layout["left"] + self.layout["width"] / 2)
        self.day_width = max(8.0, min(34.0, self.day_width * factor))
        self.scroll_day = round((center - self.axis_start).days - self.layout["width"] / self.day_width / 2)
        self.clamp_scroll()

    def run_action(self, action: str) -> None:
        handlers = {
            "open": self.load_file, "save": self.save_file,
            "new": self.edit_task, "delete": self.delete_task,
            "zoom_in": lambda: self.zoom(1.2), "zoom_out": lambda: self.zoom(1 / 1.2),
            "prev": lambda: self.scroll(-7), "next": lambda: self.scroll(7),
        }
        if action == "edit":
            task = self.selected_task()
            self.edit_task(task) if task else self.message("Выберите задачу для изменения")
        elif action in handlers:
            handlers[action]()

    def start_drag(self, task: Task, x: int, y: int, copy: bool) -> None:
        task = self.duplicate_task(task) if copy else task
        if copy:
            self.message("Перетаскивается копия задачи")
        self.drag = {"id": task.id, "offset": x - self.task_rect(task).x, "mouse_y": y}

    def move_drag(self, x: int, y: int) -> None:
        if not self.drag:
            return
        task = next((item for item in self.tasks if item.id == self.drag["id"]), None)
        if task:
            task.start_date = self.to_date(x - self.drag["offset"] + 1)
            if abs(y - self.drag["mouse_y"]) >= self.layout["track_h"] // 2:
                task.track = self.to_track(y)

    def finish_drag(self) -> None:
        if self.drag:
            self.selected = self.drag["id"]
            self.drag = None
            self.message("Задача перемещена")

    def scroll_to_x(self, x: int) -> None:
        bar = self.layout["bar"]
        thumb_w = self.layout["thumb"].width
        travel = max(1, bar.width - thumb_w)
        ratio = (x - bar.x - thumb_w / 2) / travel
        self.scroll_day = round(max(0, min(1, ratio)) * self.max_scroll)
        self.clamp_scroll()

    def apply_year(self) -> None:
        try:
            self.set_year(int(self.year_input.strip()))
        except (ValueError, TypeError):
            self.year_input = str(self.year)
            self.message("Введите корректный год")

    def mouse_down(self, event: pygame.event.Event) -> None:
        x, y = event.pos
        if event.button == 3:
            task = next((t for t in reversed(self.tasks) if self.task_rect(t).collidepoint(event.pos)), None)
            if task:
                self.selected = task.id
                self.edit_task(task)
            return
        if event.button != 1:
            return
        if self.layout["year"].collidepoint(event.pos):
            self.year_active, self.year_input = True, ""
            return
        if self.layout["apply"].collidepoint(event.pos):
            self.apply_year()
            return
        if self.year_active:
            self.year_active, self.year_input = False, str(self.year)
        for label, rect, action in self.buttons:
            if rect.collidepoint(event.pos):
                self.run_action(action)
                return
        if self.layout["left_btn"].collidepoint(event.pos):
            self.scroll(-7)
            return
        if self.layout["right_btn"].collidepoint(event.pos):
            self.scroll(7)
            return
        bar, thumb = self.layout["bar"], self.layout["thumb"]
        if thumb.inflate(0, 10).collidepoint(event.pos):
            self.scroll_drag, self.scroll_offset = True, x - thumb.x
            return
        if bar.collidepoint(event.pos):
            self.scroll_to_x(x)
            self.scroll_drag, self.scroll_offset = True, thumb.width // 2
            return
        grid = pygame.Rect(self.layout["left"], self.layout["top"], self.layout["width"],
                           self.layout["bottom"] - self.layout["top"])
        if not grid.collidepoint(event.pos):
            return
        task = next((t for t in reversed(self.tasks) if self.task_rect(t).collidepoint(event.pos)), None)
        if not task:
            self.selected = None
            return
        now = pygame.time.get_ticks()
        double = bool(self.last_click and self.last_click[0] == task.id and now - self.last_click[1] < 350)
        self.selected = task.id
        if double:
            self.edit_task(task)
            self.last_click = None
            return
        self.last_click = (task.id, now)
        self.start_drag(task, x, y, bool(pygame.key.get_mods() & pygame.KMOD_CTRL))

    def key_down(self, event: pygame.event.Event) -> None:
        if self.editor:
            return
        if self.year_active:
            if event.key == pygame.K_RETURN:
                self.year_active = False
                self.apply_year()
            elif event.key == pygame.K_ESCAPE:
                self.year_active, self.year_input = False, str(self.year)
            elif event.key == pygame.K_BACKSPACE:
                self.year_input = self.year_input[:-1]
            elif event.unicode.isdigit() and len(self.year_input) < 4:
                self.year_input += event.unicode
            return
        mods = pygame.key.get_mods()
        if event.key == pygame.K_ESCAPE:
            self.selected = None
        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self.delete_task()
        elif event.key == pygame.K_RETURN:
            task = self.selected_task()
            if task:
                self.edit_task(task)
        elif event.key == pygame.K_LEFT:
            self.scroll(-1 if mods & pygame.KMOD_SHIFT else -7)
        elif event.key == pygame.K_RIGHT:
            self.scroll(1 if mods & pygame.KMOD_SHIFT else 7)
        elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.zoom(1.2)
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.zoom(1 / 1.2)
        elif mods & pygame.KMOD_CTRL and event.key == pygame.K_n:
            self.edit_task()
        elif mods & pygame.KMOD_CTRL and event.key == pygame.K_s:
            self.save_file()
        elif mods & pygame.KMOD_CTRL and event.key == pygame.K_o:
            self.load_file()

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            size = max(event.w, MIN_SIZE[0]), max(event.h, MIN_SIZE[1])
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
            self.layout_window()
        elif self.editor:
            if not self.editor.handle(event, self):
                self.editor = None
        elif event.type == pygame.KEYDOWN:
            self.key_down(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll(-3)
            elif event.button == 5:
                self.scroll(3)
            else:
                self.mouse_down(event)
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll(-event.y * 3)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.finish_drag()
            self.scroll_drag = False
        elif event.type == pygame.MOUSEMOTION:
            if self.drag:
                self.move_drag(*event.pos)
            elif self.scroll_drag:
                self.scroll_to_x(event.pos[0] - self.scroll_offset + self.layout["thumb"].width / 2)

    def run(self) -> None:
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle(event)
                self.draw()
                self.clock.tick(FPS)
        finally:
            pygame.quit()


if __name__ == "__main__":
    try:
        Planner().run()
    except pygame.error as error:
        print(f"Не удалось запустить {APP_NAME}: {error}", file=sys.stderr)
        raise SystemExit(1)