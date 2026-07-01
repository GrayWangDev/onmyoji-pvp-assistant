import json
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_LOG_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Onmyoji\log.txt",
    r"C:\Program Files\Steam\steamapps\common\Onmyoji\log.txt",
    r"D:\SteamLibrary\steamapps\common\Onmyoji\log.txt",
    r"E:\SteamLibrary\steamapps\common\Onmyoji\log.txt",
]

TIME_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\.(\d+)\]")
RESOURCE_PATH_RE = re.compile(
    r"(?P<path>(?:model|fx|scene|levelsets/dynamic|ui/bg)/[^\s'\"]+\.(?:gim|sfx|scn|png))",
    re.IGNORECASE,
)
SIDE_RE = re.compile(r"fx/common/duizhan_(lan|hong)\.sfx", re.IGNORECASE)
SKIN_PREFIX_RE = re.compile(r"^(?:s\d+|c\d+|j|q)_(.+)$", re.IGNORECASE)


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def time_to_seconds(match):
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def load_data():
    shikigami = load_json(DATA_DIR / "shikigami.json")
    mapping = load_json(DATA_DIR / "log-resource-map.json")
    names = {item["id"]: item["name"] for item in shikigami}
    return mapping, names


def path_to_candidates(raw_path):
    cleaned = raw_path.replace("\\", "/").strip()
    parts = cleaned.split("/")
    candidates = []

    if len(parts) >= 2:
        candidates.append(parts[-2])

    filename = parts[-1] if parts else cleaned
    stem = filename.rsplit(".", 1)[0]
    candidates.append(stem)

    if cleaned.lower().startswith("ui/bg/"):
        candidates.append(stem)

    return unique(candidates)


def unique(items):
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def strip_known_suffix_once(name):
    for suffix in ("_show", "_bat"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def drop_last_segment(name):
    parts = name.split("_")
    if len(parts) <= 1:
        return name
    if parts[0] == "sp" and len(parts) <= 2:
        return name
    return "_".join(parts[:-1])


def normalize_candidates(resource):
    queue = [resource]
    output = []
    seen = set()

    while queue:
        name = queue.pop(0)
        if not name or name in seen:
            continue
        seen.add(name)
        output.append(name)

        without_suffix = strip_known_suffix_once(name)
        if without_suffix != name:
            queue.append(without_suffix)

        skin_match = SKIN_PREFIX_RE.match(name)
        if skin_match:
            queue.append(skin_match.group(1))

        shorter = drop_last_segment(name)
        if shorter != name:
            queue.append(shorter)

    return output


class LogResolver:
    def __init__(self):
        self.mapping, self.names = load_data()
        self.shikigami_map = self.mapping.get("shikigami", {})
        self.onmyoji_map = self.mapping.get("onmyoji", {})
        self.label_map = self.mapping.get("labels", {})
        self.ignored = set(self.mapping.get("ignore", []))

    def resolve(self, resource):
        for candidate in normalize_candidates(resource):
            if candidate in self.ignored:
                return None
            shikigami_id = self.shikigami_map.get(candidate)
            if shikigami_id:
                return {
                    "resource": resource,
                    "matched_resource": candidate,
                    "id": shikigami_id,
                    "name": self.names.get(shikigami_id, shikigami_id),
                    "kind": "shikigami",
                }
            onmyoji = self.onmyoji_map.get(candidate)
            if onmyoji:
                name = onmyoji["name"]
                if onmyoji.get("skin"):
                    name = f"{name}（{onmyoji['skin']}）"
                return {
                    "resource": resource,
                    "matched_resource": candidate,
                    "id": "",
                    "name": name,
                    "kind": "onmyoji",
                }
            label = self.label_map.get(candidate)
            if label:
                return {
                    "resource": resource,
                    "matched_resource": candidate,
                    "id": "",
                    "name": label,
                    "kind": "label",
                }
        return None


class MatchState:
    def __init__(self):
        self.active = False
        self.start_seconds = None
        self.pending_event = None
        self.events = []
        self.unresolved_events = []
        self.markers = []
        self.round_starts = []
        self.has_ban_phase = False
        self.capture_until_seconds = None
        self.reset()

    def reset(self):
        self.active = False
        self.start_seconds = None
        self.pending_event = None
        self.events = []
        self.unresolved_events = []
        self.markers = []
        self.round_starts = []
        self.has_ban_phase = False
        self.capture_until_seconds = None

    def start(self, seconds, marker, has_ban_phase=False):
        self.active = True
        self.start_seconds = seconds
        self.pending_event = None
        self.events = []
        self.unresolved_events = []
        self.markers = [marker]
        self.round_starts = [seconds]
        self.has_ban_phase = has_ban_phase
        self.capture_until_seconds = None

    def add_round(self, seconds, marker):
        if not self.round_starts or seconds - self.round_starts[-1] > 2:
            self.round_starts.append(seconds)
            self.markers.append(marker)

    def mark_ban_phase(self, marker):
        self.has_ban_phase = True
        if marker not in self.markers:
            self.markers.append(marker)

    def finish(self, seconds, marker):
        self.markers.append(marker)
        self.active = False
        self.pending_event = None
        self.capture_until_seconds = seconds + 10

    def is_capturing(self, seconds):
        if self.active:
            return True
        return self.capture_until_seconds is not None and seconds <= self.capture_until_seconds

    def add_event(self, event):
        self.events.append(event)
        self.pending_event = event

    def add_unresolved(self, event):
        self.unresolved_events.append(event)
        if len(self.unresolved_events) > 200:
            self.unresolved_events = self.unresolved_events[-200:]

    def assign_pending_side(self, side):
        if self.pending_event:
            self.pending_event["side"] = side
            self.pending_event = None


def dedupe_events(events):
    deduped = []
    for event in events:
        duplicate = False
        for previous in reversed(deduped[-12:]):
            same_unit = previous.get("id") == event.get("id") and previous.get("side") == event.get("side")
            near = event["seconds"] - previous["seconds"] <= 2
            if same_unit and near:
                duplicate = True
                break
        if not duplicate:
            deduped.append(event)
    return deduped


def split_snapshot(match):
    events = dedupe_events([event for event in match.events if event["kind"] == "shikigami"])
    ban_window_end = (match.start_seconds or 0) + 18
    bans = {"我方": None, "敌方": None}

    has_ban_phase = match.has_ban_phase
    mode = "名士 BP" if has_ban_phase else "无 ban 选人"

    if has_ban_phase:
        for event in events:
            if event["seconds"] > ban_window_end:
                continue
            side = event.get("side")
            if side in bans and bans[side] is None:
                bans[side] = event

    ban_lines = {event["line_no"] for event in bans.values() if event}
    our_picks, enemy_picks = pick_round_choices(events, ban_lines, match)
    unknown = [event for event in events if event["line_no"] not in ban_lines and not event.get("side")]

    return mode, bans, our_picks[:5], enemy_picks[:5], unknown


def pick_round_choices(events, skipped_lines, match):
    enemy_picks = []
    enemy_seen = set()
    our_picks = []
    our_seen = set()

    round_starts = sorted(unique(match.round_starts or [match.start_seconds or 0]))
    if not round_starts:
        round_starts = [match.start_seconds or 0]

    for index, round_start in enumerate(round_starts):
        round_end = round_starts[index + 1] if index + 1 < len(round_starts) else float("inf")
        choices = {"我方": [], "敌方": []}

        for event in events:
            if event["line_no"] in skipped_lines:
                continue
            if not (round_start <= event["seconds"] < round_end):
                continue
            side = event.get("side")
            if side in choices:
                choices[side].append(event)

        our_choice = choices["我方"][-1] if choices["我方"] else None
        enemy_choice = choices["敌方"][-1] if choices["敌方"] else None

        if our_choice and our_choice["id"] not in our_seen:
            our_picks.append(our_choice)
            our_seen.add(our_choice["id"])
        if enemy_choice and enemy_choice["id"] not in enemy_seen:
            enemy_picks.append(enemy_choice)
            enemy_seen.add(enemy_choice["id"])

    return our_picks, enemy_picks


def process_log_line(line, match, resolver):
    time_match = TIME_RE.match(line)
    if not time_match:
        return None

    seconds = time_to_seconds(time_match)
    time_text = f"{time_match.group(1)}:{time_match.group(2)}:{time_match.group(3)}"

    if "Enter scene class:MasterPvpScene" in line:
        if match.active:
            match.mark_ban_phase(f"{time_text} 进入名士 BP")
            return "ban_phase"
        match.start(seconds, f"{time_text} 进入名士 BP", has_ban_phase=True)
        return "start"

    if "ZhongxinquBattleSelectRound" in line and match.active:
        match.add_round(seconds, f"{time_text} 新一轮选人")
        return "round"

    if "ZhongxinquBattlePreparePanel" in line or "ZhongxinquBattleSelectRound" in line:
        if match.active:
            return None
        match.start(seconds, f"{time_text} 进入 BP/选人")
        return "start"

    if ("openUI PvpSlainPanel" in line or "ZhongxinquBattleRoundBegin" in line) and match.active:
        match.finish(seconds, f"{time_text} BP 结束/进入战斗，继续补抓 10 秒")
        return "finish"

    side_match = SIDE_RE.search(line)
    if side_match and match.is_capturing(seconds):
        side = "我方" if side_match.group(1).lower() == "lan" else "敌方"
        match.assign_pending_side(side)
        return "side"

    if not match.is_capturing(seconds):
        return None

    for resource_path in RESOURCE_PATH_RE.findall(line):
        resource_path_lower = resource_path.lower()
        if not match.active and not resource_path_lower.startswith(("model/", "levelsets/dynamic/", "ui/bg/")):
            continue

        candidates = path_to_candidates(resource_path)
        for resource in candidates:
            resolved = resolver.resolve(resource)
            if not resolved or resolved["kind"] != "shikigami":
                continue
            event = {
                "time": time_text,
                "seconds": seconds,
                "line_no": len(match.events) + 1,
                "side": "",
                **resolved,
            }
            match.add_event(event)
            return "event"

        if resource_path_lower.startswith(("model/", "levelsets/dynamic/", "ui/bg/")):
            match.add_unresolved(
                {
                    "time": time_text,
                    "seconds": seconds,
                    "resource_path": resource_path,
                    "candidates": candidates,
                }
            )

    return None


class BPMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Onmyoji BP Log Monitor")
        self.root.geometry("980x680")
        self.resolver = LogResolver()
        self.match = MatchState()
        self.file = None
        self.file_path = tk.StringVar(value=self.find_default_log_path())
        self.running = False
        self.status = tk.StringVar(value="请选择 log.txt，然后点开始监听。")
        self.last_size = 0

        self.build_ui()
        self.render_snapshot()

    def find_default_log_path(self):
        for path in DEFAULT_LOG_PATHS:
            if Path(path).exists():
                return path
        return DEFAULT_LOG_PATHS[0] if sys.platform.startswith("win") else ""

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        top = ttk.Frame(self.root, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="日志文件").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.file_path).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(top, text="选择", command=self.choose_file).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(top, text="自动寻找", command=self.auto_find).grid(row=0, column=3, padx=(0, 6))
        self.start_button = ttk.Button(top, text="开始监听", command=self.toggle)
        self.start_button.grid(row=0, column=4)

        status_bar = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        status_bar.grid(row=1, column=0, sticky="ew")
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, textvariable=self.status).grid(row=0, column=0, sticky="w")
        ttk.Button(status_bar, text="导出本局", command=self.export_match).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(status_bar, text="清空当前局", command=self.clear_match).grid(row=0, column=2)

        content = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        content.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))

        left = ttk.Frame(content, padding=12)
        right = ttk.Frame(content, padding=12)
        content.add(left, weight=2)
        content.add(right, weight=3)

        self.match_title = tk.StringVar(value="等待 BP 场景")
        ttk.Label(left, textvariable=self.match_title, font=("", 16, "bold")).pack(anchor="w", pady=(0, 12))

        bans_frame = ttk.LabelFrame(left, text="Ban 位", padding=10)
        bans_frame.pack(fill="x", pady=(0, 12))
        self.our_ban = tk.StringVar(value="我方 ban：未识别")
        self.enemy_ban = tk.StringVar(value="敌方 ban：未识别")
        ttk.Label(bans_frame, textvariable=self.our_ban, font=("", 13)).pack(anchor="w", pady=2)
        ttk.Label(bans_frame, textvariable=self.enemy_ban, font=("", 13)).pack(anchor="w", pady=2)

        enemy_frame = ttk.LabelFrame(left, text="敌方选人", padding=10)
        enemy_frame.pack(fill="x", pady=(0, 12))
        self.enemy_pick_vars = [tk.StringVar(value=f"{i}. 未识别") for i in range(1, 6)]
        for var in self.enemy_pick_vars:
            ttk.Label(enemy_frame, textvariable=var, font=("", 13)).pack(anchor="w", pady=2)

        our_frame = ttk.LabelFrame(left, text="我方选人（辅助校验）", padding=10)
        our_frame.pack(fill="x")
        self.our_pick_vars = [tk.StringVar(value=f"{i}. 未识别") for i in range(1, 6)]
        for var in self.our_pick_vars:
            ttk.Label(our_frame, textvariable=var).pack(anchor="w", pady=2)

        ttk.Label(right, text="识别时间线", font=("", 13, "bold")).pack(anchor="w")
        columns = ("time", "side", "name", "resource", "matched")
        self.event_table = ttk.Treeview(right, columns=columns, show="headings", height=22)
        headings = {
            "time": "时间",
            "side": "侧",
            "name": "识别",
            "resource": "日志名",
            "matched": "命中规则",
        }
        widths = {
            "time": 78,
            "side": 54,
            "name": 140,
            "resource": 230,
            "matched": 170,
        }
        for col in columns:
            self.event_table.heading(col, text=headings[col])
            self.event_table.column(col, width=widths[col], anchor="w")
        self.event_table.pack(fill="both", expand=True, pady=(8, 0))

    def choose_file(self):
        path = filedialog.askopenfilename(title="选择阴阳师 log.txt", filetypes=[("Log files", "*.txt;log"), ("All files", "*.*")])
        if path:
            self.file_path.set(path)

    def auto_find(self):
        found = self.find_default_log_path()
        self.file_path.set(found)
        if found and Path(found).exists():
            self.status.set(f"找到日志：{found}")
        else:
            self.status.set("没有在常见 Steam 路径找到 log.txt，请手动选择。")

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        path = Path(self.file_path.get().strip().strip('"'))
        if not path.exists():
            messagebox.showerror("找不到日志文件", f"这个路径不存在：\n{path}")
            return
        try:
            self.file = path.open("r", encoding="utf-8", errors="ignore")
            self.file.seek(0, os.SEEK_END)
            self.last_size = path.stat().st_size
        except OSError as error:
            messagebox.showerror("无法打开日志", str(error))
            return
        self.running = True
        self.start_button.configure(text="停止监听")
        self.status.set("正在监听。进入斗技选人后，页面会实时刷新。")
        self.root.after(300, self.poll)

    def stop(self):
        self.running = False
        self.start_button.configure(text="开始监听")
        if self.file:
            self.file.close()
            self.file = None
        self.status.set("已停止监听。")

    def clear_match(self):
        self.match.reset()
        self.render_snapshot()

    def export_match(self):
        if self.match.start_seconds is None:
            messagebox.showinfo("没有本局数据", "当前还没有识别到 BP/选人。")
            return

        path = filedialog.asksaveasfilename(
            title="导出本局识别",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="onmyoji_bp_debug.txt",
        )
        if not path:
            return

        try:
            Path(path).write_text(build_match_report(self.match), encoding="utf-8")
        except OSError as error:
            messagebox.showerror("导出失败", str(error))
            return
        self.status.set(f"已导出本局识别：{path}")

    def poll(self):
        if not self.running or not self.file:
            return
        try:
            path = Path(self.file_path.get().strip().strip('"'))
            current_size = path.stat().st_size
            if current_size < self.last_size:
                self.file.seek(0, os.SEEK_SET)
            self.last_size = current_size

            while True:
                line = self.file.readline()
                if not line:
                    break
                self.process_line(line.rstrip("\n"))
            self.render_snapshot()
        except OSError as error:
            self.status.set(f"读取日志失败：{error}")
            self.stop()
            return
        self.root.after(500, self.poll)

    def process_line(self, line):
        result = process_log_line(line, self.match, self.resolver)
        if result == "start":
            self.status.set("检测到斗技选人场景。")
        elif result == "finish":
            self.status.set("BP 已结束，结果保留在页面上。")

    def render_snapshot(self):
        if self.match.start_seconds is None:
            self.match_title.set("等待 BP 场景")
        else:
            status = "监听中" if self.match.active else "已结束"
            mode, _, _, _, _ = split_snapshot(self.match)
            self.match_title.set(f"{mode}（{status}）")

        mode, bans, our_picks, enemy_picks, unknown = split_snapshot(self.match)
        if mode == "无 ban 选人":
            self.our_ban.set("我方 ban：无")
            self.enemy_ban.set("敌方 ban：无")
        else:
            self.our_ban.set(f"我方 ban：{format_event_name(bans['我方'])}")
            self.enemy_ban.set(f"敌方 ban：{format_event_name(bans['敌方'])}")

        for index, var in enumerate(self.enemy_pick_vars, start=1):
            var.set(format_pick_slot(index, enemy_picks))
        for index, var in enumerate(self.our_pick_vars, start=1):
            var.set(format_pick_slot(index, our_picks))

        for item in self.event_table.get_children():
            self.event_table.delete(item)

        for event in dedupe_events(self.match.events)[-120:]:
            self.event_table.insert(
                "",
                "end",
                values=(
                    event["time"],
                    event.get("side") or "?",
                    event["name"],
                    event["resource"],
                    event["matched_resource"],
                ),
            )


def format_event_name(event):
    if not event:
        return "未识别"
    resource = event.get("matched_resource") or event.get("resource")
    side = event.get("side") or "?"
    return f"{event['name']}  ({side} · {resource})"


def format_pick_slot(index, picks):
    if index <= len(picks):
        event = picks[index - 1]
        resource = event.get("matched_resource") or event.get("resource")
        return f"{index}. {event['name']}  ({resource})"
    return f"{index}. 未识别"


def build_match_report(match):
    mode, bans, our_picks, enemy_picks, unknown = split_snapshot(match)
    lines = [
        f"模式: {mode}",
        f"状态: {'进行中' if match.active else '已结束'}",
        "",
        "[Ban]",
        f"我方 ban: {format_event_name(bans['我方']) if bans['我方'] else '无/未识别'}",
        f"敌方 ban: {format_event_name(bans['敌方']) if bans['敌方'] else '无/未识别'}",
        "",
        "[敌方选人]",
    ]

    for index in range(1, 6):
        lines.append(format_pick_slot(index, enemy_picks))

    lines.append("")
    lines.append("[我方选人]")
    for index in range(1, 6):
        lines.append(format_pick_slot(index, our_picks))

    lines.append("")
    lines.append("[轮次节点]")
    for marker in match.markers:
        lines.append(marker)

    lines.append("")
    lines.append("[识别时间线]")
    for event in dedupe_events(match.events):
        side = event.get("side") or "?"
        lines.append(
            f"{event['time']} | {side} | {event['name']} | "
            f"resource={event['resource']} | matched={event['matched_resource']} | line={event['line_no']}"
        )

    if unknown:
        lines.append("")
        lines.append("[未分侧记录]")
        for event in unknown:
            lines.append(f"{event['time']} | {event['name']} | {event['resource']} | {event['matched_resource']}")

    if match.unresolved_events:
        lines.append("")
        lines.append("[未识别模型资源]")
        for event in match.unresolved_events:
            candidates = ", ".join(event["candidates"])
            lines.append(f"{event['time']} | {event['resource_path']} | candidates={candidates}")

    return "\n".join(lines) + "\n"


def main():
    root = tk.Tk()
    BPMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
