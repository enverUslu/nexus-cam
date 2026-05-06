#!/usr/bin/env python3
"""Desktop launcher for Nexus.cam."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import math
import random
import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser

from samsung_wifi_web import APP_NAME, APP_VERSION, AppHandler, HOST, PORT


BG = "#080807"
PANEL = "#12110f"
PANEL_DARK = "#1b1915"
INK = "#f7f3e8"
MUTED = "#9f9a8e"
LINE = "#ded6c6"
BAD = "#8f2f2f"
DISPLAY_FONT = "Impact"
TEXT_FONT = "Helvetica Neue"
MONO_FONT = "Menlo"


class FlatButton(tk.Label):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: object,
        bg: str,
        fg: str,
        hover_bg: str,
        hover_fg: str,
        padx: int = 16,
        pady: int = 8,
    ) -> None:
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=(MONO_FONT, 9, "bold"),
            padx=padx,
            pady=pady,
            highlightbackground=LINE,
            highlightthickness=2,
            cursor="pointinghand",
        )
        self.command = command
        self.normal = {"bg": bg, "fg": fg}
        self.hover = {"bg": hover_bg, "fg": hover_fg}
        self.enabled = True
        self.inside = False
        self.animation_job: str | None = None
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled:
            self.config(cursor="pointinghand")
            self._paint(self.normal)
        else:
            self.config(cursor="arrow", bg=PANEL_DARK, fg="#555555")

    def _paint(self, colors: dict[str, str]) -> None:
        self.config(bg=colors["bg"], fg=colors["fg"])

    def _enter(self, _event: tk.Event) -> None:
        self.inside = True
        if self.enabled:
            self._animate(self.hover)

    def _leave(self, _event: tk.Event) -> None:
        self.inside = False
        if self.enabled:
            self._animate(self.normal)

    def _press(self, _event: tk.Event) -> None:
        if self.enabled:
            self._paint(self.hover)

    def _release(self, _event: tk.Event) -> None:
        if self.enabled:
            self.command()
            target = self.hover if self.inside else self.normal
            self.after(80, lambda: self._animate(target) if self.enabled else None)

    def _animate(self, target: dict[str, str], step: int = 0, steps: int = 6) -> None:
        if self.animation_job:
            self.after_cancel(self.animation_job)
            self.animation_job = None
        start_bg = self.cget("bg")
        start_fg = self.cget("fg")

        def tick(index: int) -> None:
            blend = index / steps
            self.config(
                bg=self._mix(start_bg, target["bg"], blend),
                fg=self._mix(start_fg, target["fg"], blend),
            )
            if index < steps:
                self.animation_job = self.after(18, lambda: tick(index + 1))
            else:
                self.animation_job = None

        tick(step)

    @staticmethod
    def _mix(start: str, end: str, amount: float) -> str:
        start_rgb = tuple(int(start[i : i + 2], 16) for i in (1, 3, 5))
        end_rgb = tuple(int(end[i : i + 2], 16) for i in (1, 3, 5))
        mixed = tuple(round(a + (b - a) * amount) for a, b in zip(start_rgb, end_rgb))
        return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


class MyceliumCreditsBackground:
    def __init__(self, canvas: tk.Canvas, width: int, height: int) -> None:
        self.canvas = canvas
        self.width = width
        self.height = height
        self.node_count = 64
        self.link_distance = 132
        self.pointer_radius = 125
        self.cell = 16
        self.nodes = [
            {
                "x": random.random() * width,
                "y": (i % 9) * (height / 8) + random.uniform(-62, 62),
                "phase": random.random() * math.tau,
                "vx": 0.0,
                "vy": 0.0,
                "corruption": 0.0,
            }
            for i in range(self.node_count)
        ]
        self.pointer = {"x": -999.0, "y": -999.0, "active": False}
        self.flashes: list[dict[str, float | str]] = []
        self.tick_count = 0
        self.job: str | None = None
        self.palette = ["#d8ff2f", "#ff5a24", "#f1f1e8", "#00e5ff", "#ff2fcf"]
        self.ascii = {
            "link": [".", ":", "-", "=", "+"],
            "node": ["o", "O", "0", "#"],
            "pulse": ["*", "+", "x"],
            "signal": ["!", "$", "~", "^", "?"],
            "noise": [".", ",", "`", "'"],
        }
        self.canvas.bind("<Motion>", self.move_pointer)
        self.canvas.bind("<Leave>", self.leave_pointer)
        self.canvas.bind("<Button-1>", lambda event: self.apply_pointer_force(event, "pull"))
        self.canvas.bind("<Button-2>", lambda event: self.apply_pointer_force(event, "push"))
        self.canvas.bind("<Button-3>", lambda event: self.apply_pointer_force(event, "push"))
        self.draw()

    def move_pointer(self, event: tk.Event) -> None:
        self.pointer = {"x": float(event.x), "y": float(event.y), "active": True}

    def leave_pointer(self, _event: tk.Event | None) -> None:
        self.pointer = {"x": -999.0, "y": -999.0, "active": False}

    def apply_pointer_force(self, event: tk.Event, direction: str) -> str:
        x = float(event.x)
        y = float(event.y)
        color = "#d8ff2f" if direction == "pull" else "#ff5a24"
        for node in self.nodes:
            dx = float(node["x"]) - x
            dy = float(node["y"]) - y
            distance = max(1.0, math.hypot(dx, dy))
            if distance > 170:
                continue
            force = (1 - distance / 170) * 4.8
            sign = -1 if direction == "pull" else 1
            node["vx"] = float(node["vx"]) + sign * (dx / distance) * force
            node["vy"] = float(node["vy"]) + sign * (dy / distance) * force
        self.flashes = [{"x": x, "y": y, "age": 0.0, "color": color, "label": direction.upper()}]
        return "break"

    def draw(self) -> None:
        self.sync_pointer()
        self.canvas.delete("mycelium")
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill="#080806", outline="", tags="mycelium")
        self.draw_ascii_frame()
        self.draw_noise()
        self.update_nodes()
        self.draw_links()
        self.draw_flashes()
        self.draw_nodes()
        self.draw_pointer()
        self.canvas.tag_lower("mycelium")
        self.tick_count += 1
        self.job = self.canvas.after(24, self.draw)

    def sync_pointer(self) -> None:
        root_x = self.canvas.winfo_rootx()
        root_y = self.canvas.winfo_rooty()
        pointer_x = self.canvas.winfo_pointerx() - root_x
        pointer_y = self.canvas.winfo_pointery() - root_y
        if 0 <= pointer_x <= self.width and 0 <= pointer_y <= self.height:
            self.pointer = {"x": float(pointer_x), "y": float(pointer_y), "active": True}
        elif self.pointer["active"]:
            self.leave_pointer(None)

    def draw_ascii_frame(self) -> None:
        for x in range(16, self.width - 12, self.cell):
            self.canvas.create_text(x, 18, text="-", fill="#514b40", font=(MONO_FONT, 8, "bold"), tags="mycelium")
            self.canvas.create_text(x, self.height - 18, text="-", fill="#514b40", font=(MONO_FONT, 8, "bold"), tags="mycelium")
        for y in range(20, self.height - 16, self.cell):
            self.canvas.create_text(16, y, text="|", fill="#514b40", font=(MONO_FONT, 8, "bold"), tags="mycelium")
            self.canvas.create_text(self.width - 16, y, text="|", fill="#514b40", font=(MONO_FONT, 8, "bold"), tags="mycelium")

    def draw_noise(self) -> None:
        for i in range(38):
            x = (i * 47 + self.tick_count * 2) % self.width
            y = (i * 31 + self.tick_count) % self.height
            self.canvas.create_text(
                x,
                y,
                text=self.ascii["noise"][(i + self.tick_count) % len(self.ascii["noise"])],
                fill="#302b23",
                font=(MONO_FONT, 9, "bold"),
                tags="mycelium",
            )

    def update_nodes(self) -> None:
        t = self.tick_count * 0.045
        for node in self.nodes:
            node["x"] = float(node["x"]) + math.sin(t + float(node["phase"])) * 0.34 + float(node["vx"])
            node["y"] = float(node["y"]) + math.cos(t * 0.8 + float(node["phase"])) * 0.28 + float(node["vy"])

            if self.pointer["active"]:
                dx = float(node["x"]) - float(self.pointer["x"])
                dy = float(node["y"]) - float(self.pointer["y"])
                distance = max(1.0, math.hypot(dx, dy))
                if distance < self.pointer_radius:
                    force = (1 - distance / self.pointer_radius) * 0.55
                    node["vx"] = float(node["vx"]) + (dx / distance) * force
                    node["vy"] = float(node["vy"]) + (dy / distance) * force

            node["vx"] = float(node["vx"]) * 0.84
            node["vy"] = float(node["vy"]) * 0.84
            node["x"] = (float(node["x"]) + 18) % (self.width + 36) - 18
            node["y"] = (float(node["y"]) + 18) % (self.height + 36) - 18

    def draw_links(self) -> None:
        for i, a in enumerate(self.nodes):
            candidates: list[tuple[float, dict[str, float]]] = []
            for b in self.nodes[i + 1 :]:
                ax, ay = float(a["x"]), float(a["y"])
                bx, by = float(b["x"]), float(b["y"])
                distance = math.hypot(ax - bx, ay - by)
                if distance <= self.link_distance:
                    candidates.append((distance, b))
            for distance, b in sorted(candidates, key=lambda item: item[0])[:4]:
                ax, ay = float(a["x"]), float(a["y"])
                bx, by = float(b["x"]), float(b["y"])
                mx = (ax + bx) / 2
                my = (ay + by) / 2
                pointer = self.distance_to_segment(float(self.pointer["x"]), float(self.pointer["y"]), ax, ay, bx, by)
                hot = bool(self.pointer["active"]) and pointer < self.pointer_radius
                fill = "#d8ff2f" if hot else "#9d9484"
                strength = max(0.0, 1 - distance / self.link_distance)
                char = "+" if hot else self.link_char(ax, ay, bx, by, strength)
                steps = min(5, max(2, int(distance / self.cell)))
                for step in range(1, steps + 1):
                    if not hot and step % 3 == 0:
                        continue
                    blend = step / (steps + 1)
                    wobble = math.sin(self.tick_count * 0.04 + step + float(a["phase"])) * 2.2
                    angle = math.atan2(by - ay, bx - ax) + math.pi / 2
                    x = ax + (bx - ax) * blend + math.cos(angle) * wobble
                    y = ay + (by - ay) * blend + math.sin(angle) * wobble
                    self.canvas.create_text(
                        x,
                        y,
                        text=char,
                        fill=fill,
                        font=(MONO_FONT, 10, "bold"),
                        tags="mycelium",
                    )

    def draw_flashes(self) -> None:
        next_flashes: list[dict[str, float | str]] = []
        for flash in self.flashes:
            age = float(flash["age"]) + 1
            x = float(flash["x"])
            y = float(flash["y"])
            color = str(flash["color"])
            label = str(flash["label"])
            if age <= 12:
                self.canvas.create_text(
                    x,
                    y - age * 1.8,
                    text=label,
                    fill=color,
                    font=(MONO_FONT, 13, "bold"),
                    tags="mycelium",
                )
                next_flashes.append({"x": x, "y": y, "age": age, "color": color, "label": label})
        self.flashes = next_flashes

    def draw_nodes(self) -> None:
        for i, node in enumerate(self.nodes):
            x = float(node["x"])
            y = float(node["y"])
            pointer = math.hypot(x - float(self.pointer["x"]), y - float(self.pointer["y"]))
            hot = bool(self.pointer["active"]) and pointer < 92
            fill = self.palette[i % len(self.palette)] if hot else "#f7f3e8"
            char = self.ascii["node"][(i + self.tick_count // 8) % len(self.ascii["node"])]
            self.canvas.create_text(
                x + 1,
                y + 1,
                text=char,
                fill="#2c2820",
                font=(MONO_FONT, 14, "bold"),
                tags="mycelium",
            )
            self.canvas.create_text(
                x,
                y,
                text=char,
                fill=fill,
                font=(MONO_FONT, 14, "bold"),
                tags="mycelium",
            )

    def draw_pointer(self) -> None:
        if not self.pointer["active"]:
            return
        x = float(self.pointer["x"])
        y = float(self.pointer["y"])
        for i, char in enumerate(["[", "+", "]"]):
            self.canvas.create_text(
                x + (i - 1) * 12,
                y,
                text=char,
                fill="#d8ff2f",
                font=(MONO_FONT, 10, "bold"),
                tags="mycelium",
            )

    def link_char(self, ax: float, ay: float, bx: float, by: float, strength: float) -> str:
        angle = abs(math.atan2(by - ay, bx - ax))
        if angle < math.pi * 0.16:
            return "-"
        if angle > math.pi * 0.34 and angle < math.pi * 0.66:
            return "|"
        return self.ascii["link"][min(4, max(0, int(strength * len(self.ascii["link"]))))]

    @staticmethod
    def distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        dx = bx - ax
        dy = by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def stop(self) -> None:
        if self.job:
            self.canvas.after_cancel(self.job)
            self.job = None


class NexusCamApp:
    def __init__(self) -> None:
        self.url = f"http://{HOST}:{PORT}"
        self.server: ThreadingHTTPServer | None = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.server_ready = False
        self.credits_window: tk.Toplevel | None = None
        self.credits_background: MyceliumCreditsBackground | None = None

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        try:
            self.root.tk.call("::tk::unsupported::MacWindowStyle", "style", self.root._w, "plain", "none")
        except tk.TclError:
            pass
        self.root.geometry("560x360")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        self.shell = tk.Frame(self.root, bg=PANEL, highlightbackground=LINE, highlightthickness=3)
        self.shell.pack(fill="both", expand=True, padx=12, pady=12)
        self.shell.bind("<ButtonPress-1>", self.start_drag)
        self.shell.bind("<B1-Motion>", self.drag)

        body = tk.Frame(self.shell, bg=PANEL, padx=22, pady=22)
        body.pack(fill="both", expand=True)
        body.bind("<ButtonPress-1>", self.start_drag)
        body.bind("<B1-Motion>", self.drag)

        top = tk.Frame(body, bg=PANEL)
        top.pack(fill="x")
        top.bind("<ButtonPress-1>", self.start_drag)
        top.bind("<B1-Motion>", self.drag)

        self.title_canvas = tk.Canvas(
            top,
            width=355,
            height=218,
            bg=PANEL,
            highlightthickness=0,
            bd=0,
        )
        self.title_canvas.pack(side="left")
        self.draw_camera_mark(self.title_canvas, 0, 58)
        self.title_canvas.create_text(70, -16, text="NEXUS", anchor="nw", fill=INK, font=(DISPLAY_FONT, 70))
        self.title_canvas.create_text(0, 88, text="CAM", anchor="nw", fill=INK, font=(DISPLAY_FONT, 78))
        self.title_canvas.bind("<ButtonPress-1>", self.start_drag)
        self.title_canvas.bind("<B1-Motion>", self.drag)

        version = tk.Label(top, text=f"v{APP_VERSION}", bg=PANEL, fg=MUTED, font=(MONO_FONT, 12, "bold"))
        version.pack(side="right")
        version.bind("<ButtonPress-1>", self.start_drag)
        version.bind("<B1-Motion>", self.drag)

        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(side="bottom", fill="x", pady=(8, 0))

        button_stack = tk.Frame(buttons, bg=PANEL)
        button_stack.pack(side="left")

        self.open_button = FlatButton(
            button_stack,
            text="OPEN BROWSER",
            command=self.open_browser,
            bg=INK,
            fg="#000000",
            hover_bg="#00f5ff",
            hover_fg="#000000",
            pady=5,
        )
        self.open_button.set_enabled(False)
        self.open_button.pack(anchor="w", fill="x")

        self.credits_button = FlatButton(
            button_stack,
            text="ABOUT/CREDITS",
            command=self.show_credits,
            bg=PANEL_DARK,
            fg=LINE,
            hover_bg="#ff4fd8",
            hover_fg="#000000",
            pady=4,
        )
        self.credits_button.pack(anchor="w", fill="x", pady=(8, 0))

        stop_button = FlatButton(
            buttons,
            text="STOP",
            command=self.stop,
            bg=BAD,
            fg=INK,
            hover_bg="#ff4fd8",
            hover_fg="#000000",
            pady=5,
        )
        stop_button.pack(side="right")

        self.center()
        self.root.deiconify()
        self.root.lift()
        self.root.after(250, lambda: self.root.attributes("-topmost", False))

    def draw_camera_mark(self, canvas: tk.Canvas, x: int, y: int) -> None:
        canvas.create_rectangle(x + 4, y + 18, x + 56, y + 54, outline=INK, width=5)
        canvas.create_rectangle(x + 15, y + 8, x + 33, y + 20, fill=INK, outline=INK)
        canvas.create_oval(x + 20, y + 25, x + 42, y + 47, outline=INK, width=5)
        canvas.create_rectangle(x + 47, y + 25, x + 51, y + 29, fill=INK, outline=INK)

    def start_server(self) -> None:
        try:
            self.server = ThreadingHTTPServer((HOST, PORT), AppHandler)
        except OSError as error:
            self.server_ready = False
            messagebox.showerror(APP_NAME, f"Could not start {APP_NAME} on {self.url}\n\n{error}")
            self.root.after(100, self.root.destroy)
            return

        self.server_ready = True
        self.open_button.set_enabled(True)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def center(self) -> None:
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def start_drag(self, event: tk.Event) -> None:
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def drag(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self.drag_start_x
        y = self.root.winfo_y() + event.y - self.drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def open_browser(self) -> None:
        webbrowser.open(self.url)

    def show_credits(self) -> None:
        if self.credits_window and self.credits_window.winfo_exists():
            self.credits_window.lift()
            return

        popup = tk.Toplevel(self.root)
        self.credits_window = popup
        popup.title("Credits")
        popup.overrideredirect(True)
        try:
            popup.tk.call("::tk::unsupported::MacWindowStyle", "style", popup._w, "plain", "none")
        except tk.TclError:
            pass
        popup.resizable(False, False)
        popup.configure(bg="#080806")
        popup.protocol("WM_DELETE_WINDOW", self.close_credits)
        popup.bind("<Escape>", lambda _event: self.close_credits())

        width = 820
        height = 520
        canvas = tk.Canvas(
            popup,
            width=width,
            height=height,
            bg="#080806",
            highlightthickness=3,
            highlightbackground=LINE,
            bd=0,
        )
        canvas.pack()
        self.credits_background = MyceliumCreditsBackground(canvas, width, height)
        canvas.create_rectangle(54, 58, width - 54, height - 70, fill="", outline="#f1f1e8", width=2)
        self.backed_canvas_text(canvas, 410, 126, "NEXUS.CAM", "#d8ff2f", (DISPLAY_FONT, 58), padx=18, pady=6)
        self.backed_canvas_text(canvas, 413, 129, "NEXUS.CAM", "#ff5a24", (DISPLAY_FONT, 58), padx=18, pady=6)
        self.backed_canvas_text(canvas, 410, 190, "local camera bridge", INK, (MONO_FONT, 15, "bold"))
        self.backed_canvas_text(canvas, 410, 226, "read-only DLNA transfer", "#f1f1e8", (MONO_FONT, 13))
        self.backed_canvas_text(canvas, 410, 282, "built by enverUslu", "#f7f3e8", (MONO_FONT, 11, "bold"))
        repo_id = self.backed_canvas_text(canvas, 410, 312, "github.com/enverUslu/nexus-cam", "#00e5ff", (MONO_FONT, 10, "bold"))
        canvas.tag_bind(repo_id, "<Button-1>", lambda _event: webbrowser.open("https://github.com/enverUslu/nexus-cam"))
        canvas.tag_bind(repo_id, "<Enter>", lambda _event: canvas.config(cursor="pointinghand"))
        canvas.tag_bind(repo_id, "<Leave>", lambda _event: canvas.config(cursor=""))
        self.backed_canvas_text(canvas, 410, 340, "MIT License", "#d8ff2f", (MONO_FONT, 10, "bold"))
        self.backed_canvas_text(canvas, 410, 368, "Issues & contributions welcome", "#f7f3e8", (MONO_FONT, 10, "bold"))
        self.backed_canvas_text(canvas, 410, 420, "v0.1.0 -> v1.0.0", "#ff5a24", (MONO_FONT, 11, "bold"))
        close_id = canvas.create_text(
            24,
            26,
            text="[X] CLOSE",
            anchor="w",
            fill="#ff4d4d",
            font=(MONO_FONT, 12, "bold"),
            tags=("credits-close",),
        )
        bbox = canvas.bbox(close_id)
        if bbox:
            hitbox = canvas.create_rectangle(
                bbox[0] - 8,
                bbox[1] - 6,
                bbox[2] + 8,
                bbox[3] + 6,
                fill="",
                outline="",
                tags=("credits-close",),
            )
            canvas.tag_lower(hitbox, close_id)
        canvas.tag_bind("credits-close", "<Button-1>", lambda _event: self.close_credits())
        canvas.tag_bind("credits-close", "<Enter>", lambda _event: canvas.config(cursor="pointinghand"))
        canvas.tag_bind("credits-close", "<Leave>", lambda _event: canvas.config(cursor=""))
        popup.transient(self.root)
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")
        popup.lift()

    def backed_canvas_text(
        self,
        canvas: tk.Canvas,
        x: int,
        y: int,
        text: str,
        fill: str,
        font: tuple,
        padx: int = 10,
        pady: int = 4,
    ) -> int:
        text_id = canvas.create_text(x, y, text=text, fill=fill, font=font)
        bbox = canvas.bbox(text_id)
        if bbox:
            rect_id = canvas.create_rectangle(
                bbox[0] - padx,
                bbox[1] - pady,
                bbox[2] + padx,
                bbox[3] + pady,
                fill="#080806",
                outline="",
            )
            canvas.tag_lower(rect_id, text_id)
        return text_id

    def close_credits(self) -> None:
        if self.credits_background:
            self.credits_background.stop()
            self.credits_background = None
        if self.credits_window and self.credits_window.winfo_exists():
            self.credits_window.destroy()
        self.credits_window = None

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.root.destroy()

    def run(self) -> None:
        self.root.after(100, self.start_server)
        self.root.mainloop()


def main() -> int:
    NexusCamApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
