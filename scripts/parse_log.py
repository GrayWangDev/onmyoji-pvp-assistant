import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

TIME_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\.(\d+)\]")
RESOURCE_RE = re.compile(r"(model|fx|scene)/([^/\s]+)/")
SKILL_RE = re.compile(r"/(skill\d[^/\s]*)", re.IGNORECASE)
SIDE_RE = re.compile(r"fx/common/duizhan_(lan|hong)\.sfx")


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_shikigami_names():
    by_id = {}
    for item in load_json(DATA_DIR / "shikigami.json"):
        by_id[item["id"]] = item["name"]
    return by_id


def seconds_from_match(match):
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def time_label(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def bucket_start(seconds, bucket_size):
    return seconds - (seconds % bucket_size)


def display_resource(resource, mapping, shikigami_names):
    shikigami_id = mapping["shikigami"].get(resource)
    if shikigami_id:
        return shikigami_names.get(shikigami_id, shikigami_id), shikigami_id

    label = mapping.get("labels", {}).get(resource)
    if label:
        return label, None

    onmyoji = mapping.get("onmyoji", {}).get(resource)
    if onmyoji:
        name = onmyoji["name"]
        if onmyoji.get("skin"):
            name = f'{name}（{onmyoji["skin"]}）'
        return name, None

    return resource, None


def parse_log(path, mapping, shikigami_names, bucket_size):
    ignored = set(mapping.get("ignore", []))
    buckets = {}
    unknown = Counter()
    all_events = []

    for line_no, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
        time_match = TIME_RE.match(line)
        if not time_match:
            continue

        resource_match = RESOURCE_RE.search(line)
        if not resource_match:
            if "beginBattle" in line or "Enter scene" in line or "openUI PvpPanel" in line:
                seconds = seconds_from_match(time_match)
                start = bucket_start(seconds, bucket_size)
                bucket = buckets.setdefault(start, new_bucket())
                bucket["markers"].append((time_label(seconds), line.strip()))
            continue

        kind, resource = resource_match.groups()
        if resource in ignored:
            continue

        seconds = seconds_from_match(time_match)
        start = bucket_start(seconds, bucket_size)
        bucket = buckets.setdefault(start, new_bucket())
        display_name, shikigami_id = display_resource(resource, mapping, shikigami_names)

        skill_match = SKILL_RE.search(line)
        skill_name = skill_match.group(1) if skill_match else ""

        event = {
            "time": time_label(seconds),
            "line_no": line_no,
            "kind": kind,
            "resource": resource,
            "display": display_name,
            "shikigami_id": shikigami_id,
            "skill": skill_name,
        }
        all_events.append(event)

        if shikigami_id:
            bucket["shikigami"][display_name] += 1
        elif resource in mapping.get("labels", {}):
            bucket["labels"][display_name] += 1
        elif resource in mapping.get("onmyoji", {}):
            bucket["onmyoji"][display_name] += 1
        else:
            bucket["unknown"][resource] += 1
            unknown[resource] += 1

        if kind == "model":
            bucket["models"][display_name] += 1
        if kind == "fx" and skill_name:
            bucket["skills"][(display_name, skill_name)] += 1

    return buckets, unknown, all_events


def new_bucket():
    return {
        "shikigami": Counter(),
        "labels": Counter(),
        "onmyoji": Counter(),
        "models": Counter(),
        "skills": Counter(),
        "unknown": Counter(),
        "markers": [],
    }


def format_counter(counter, limit=12):
    if not counter:
        return "无"
    return " / ".join(f"{name}×{count}" for name, count in counter.most_common(limit))


def print_report(buckets, unknown, bucket_size):
    if not buckets:
        print("没有解析到可用资源记录。")
        return

    print(f"按 {bucket_size} 秒分组的日志解析结果")
    print()

    for start in sorted(buckets):
        bucket = buckets[start]
        total = sum(bucket["shikigami"].values()) + sum(bucket["labels"].values()) + sum(bucket["skills"].values())
        if total == 0 and not bucket["markers"]:
            continue

        end = start + bucket_size - 1
        print(f"## {time_label(start)} - {time_label(end)}")

        if bucket["markers"]:
            print("场景标记:")
            for t, marker in bucket["markers"][:5]:
                print(f"- {t} {marker}")

        print(f"检测到式神: {format_counter(bucket['shikigami'])}")
        if bucket["labels"]:
            print(f"未入字典但有标签: {format_counter(bucket['labels'])}")
        if bucket["onmyoji"]:
            print(f"阴阳师/皮肤: {format_counter(bucket['onmyoji'])}")
        if bucket["models"]:
            print(f"模型加载: {format_counter(bucket['models'])}")
        if bucket["skills"]:
            skill_counter = Counter({f"{name} {skill}": count for (name, skill), count in bucket["skills"].items()})
            print(f"技能/特效: {format_counter(skill_counter, limit=18)}")
        if bucket["unknown"]:
            print(f"未知资源: {format_counter(bucket['unknown'], limit=10)}")
        print()

    if unknown:
        print("## 未知资源汇总")
        print(format_counter(unknown, limit=30))


def extract_bp_segments(path, mapping, shikigami_names):
    lines = path.read_text(errors="ignore").splitlines()
    ignored = set(mapping.get("ignore", []))
    segments = []
    active = None
    pending_model = None

    for line_no, line in enumerate(lines, start=1):
        time_match = TIME_RE.match(line)
        if not time_match:
            continue

        seconds = seconds_from_match(time_match)

        if "Enter scene class:MasterPvpScene" in line:
            active = {
                "start": seconds,
                "end": None,
                "events": [],
                "markers": [(time_label(seconds), line.strip())],
            }
            segments.append(active)
            pending_model = None
            continue

        if active and "openUI PvpSlainPanel" in line:
            active["end"] = seconds
            active["markers"].append((time_label(seconds), line.strip()))
            pending_model = None
            continue

        if not active or active.get("end"):
            continue

        resource_match = RESOURCE_RE.search(line)
        if not resource_match:
            continue

        kind, resource = resource_match.groups()
        side_match = SIDE_RE.search(line)
        if side_match and pending_model:
            pending_model["side"] = "我方" if side_match.group(1) == "lan" else "敌方"
            pending_model = None
            continue

        if kind != "model" or resource in ignored:
            continue

        display_name, shikigami_id = display_resource(resource, mapping, shikigami_names)
        is_known = shikigami_id or resource in mapping.get("onmyoji", {})
        if not is_known:
            continue

        event = {
            "time": time_label(seconds),
            "seconds": seconds,
            "line_no": line_no,
            "resource": resource,
            "display": display_name,
            "shikigami_id": shikigami_id,
            "side": "",
        }
        active["events"].append(event)
        pending_model = event

    return segments


def dedupe_bp_events(events):
    deduped = []
    for event in events:
        duplicate = False
        for previous in reversed(deduped[-8:]):
            if (
                previous["display"] == event["display"]
                and previous["side"] == event["side"]
                and event["seconds"] - previous["seconds"] <= 2
            ):
                duplicate = True
                break
        if not duplicate:
            deduped.append(event)
    return deduped


def split_bp_events(events):
    shikigami_events = [event for event in events if event["shikigami_id"]]
    onmyoji_events = [event for event in events if not event["shikigami_id"]]

    bans = shikigami_events[:2]
    candidates = shikigami_events[2:]
    picks = {"我方": [], "敌方": []}
    uncertain = []

    for event in candidates:
        if event["side"] in picks:
            side_picks = picks[event["side"]]
            if len(side_picks) >= 5:
                uncertain.append(event)
                continue

            existing_names = {pick["display"] for pick in side_picks}
            if event["display"] in existing_names:
                uncertain.append(event)
                continue

            side_picks.append(event)
        else:
            uncertain.append(event)

    return bans, picks, onmyoji_events, uncertain


def build_lite_bp(events, segment_start):
    shikigami_events = [event for event in events if event["shikigami_id"]]
    onmyoji_events = [event for event in events if not event["shikigami_id"]]
    ban_window_end = segment_start + 18
    bans_by_side = {"我方": None, "敌方": None}
    for event in shikigami_events:
        if event["seconds"] > ban_window_end:
            break
        if event["side"] in bans_by_side and bans_by_side[event["side"]] is None:
            bans_by_side[event["side"]] = event

    ban_event_lines = {event["line_no"] for event in bans_by_side.values() if event}
    enemy_picks = []
    enemy_seen = set()
    unknown_side_events = []

    for event in shikigami_events:
        if event["line_no"] in ban_event_lines:
            continue
        if event["side"] == "敌方":
            if event["display"] in enemy_seen:
                continue
            enemy_picks.append(event)
            enemy_seen.add(event["display"])
            if len(enemy_picks) >= 5:
                break
        elif not event["side"]:
            unknown_side_events.append(event)

    return bans_by_side, enemy_picks, onmyoji_events, unknown_side_events


def format_event(event):
    side = f" {event['side']}" if event.get("side") else ""
    return f"{event['time']}{side} {event['display']} ({event['resource']})"


def print_bp_lite_report(path, mapping, shikigami_names):
    segments = extract_bp_segments(path, mapping, shikigami_names)
    if not segments:
        print("没有找到名士 BP 场景。")
        return

    for index, segment in enumerate(segments, start=1):
        events = dedupe_bp_events(segment["events"])
        bans_by_side, enemy_picks, onmyoji_events, unknown_side_events = build_lite_bp(events, segment["start"])

        print(f"## 名士 BP #{index}  {time_label(segment['start'])}")
        if segment.get("end"):
            print(f"结束标记: {time_label(segment['end'])}")
        print()

        our_ban = bans_by_side["我方"]
        enemy_ban = bans_by_side["敌方"]
        print(f"我方 ban: {our_ban['display'] if our_ban else '未识别'}")
        print(f"敌方 ban: {enemy_ban['display'] if enemy_ban else '未识别'}")

        if enemy_picks:
            enemy_line = " / ".join(f"{idx + 1}.{event['display']}" for idx, event in enumerate(enemy_picks))
        else:
            enemy_line = "未识别"
        print(f"敌方选人: {enemy_line}")

        enemy_onmyoji = [event for event in onmyoji_events if event["side"] == "敌方"]
        if enemy_onmyoji:
            print(f"敌方阴阳师: {enemy_onmyoji[0]['display']}")

        print()
        if len(enemy_picks) < 5:
            print("提示: 敌方选人不足 5 个，可能是资源映射未覆盖，或这局不是完整名士 BP。")
        if unknown_side_events:
            print("未归属候选:")
            for event in unknown_side_events[:8]:
                print(f"- {format_event(event)}")
            print()


def print_bp_report(path, mapping, shikigami_names):
    segments = extract_bp_segments(path, mapping, shikigami_names)
    if not segments:
        print("没有找到名士 BP 场景。")
        return

    for index, segment in enumerate(segments, start=1):
        events = dedupe_bp_events(segment["events"])
        bans, picks, onmyoji_events, uncertain = split_bp_events(events)

        print(f"## 名士 BP #{index}  {time_label(segment['start'])}")
        if segment.get("end"):
            print(f"结束标记: {time_label(segment['end'])}")
        print()

        print("疑似 ban:")
        if bans:
            for event in bans:
                print(f"- {format_event(event)}")
        else:
            print("- 未识别")
        print()

        print("候选选人（按模型首次上场；试选/拖上去也会出现）:")
        for side in ("我方", "敌方"):
            side_picks = picks[side]
            if side_picks:
                names = " / ".join(f"{i + 1}.{event['display']}" for i, event in enumerate(side_picks))
                print(f"- {side}: {names}")
            else:
                print(f"- {side}: 未识别")
        print()

        if onmyoji_events:
            print("阴阳师/皮肤:")
            for event in onmyoji_events:
                print(f"- {format_event(event)}")
            print()

        if uncertain:
            print("后续候选/重复/未归属:")
            for event in uncertain:
                print(f"- {format_event(event)}")
            print()

        print("原始 BP 模型时间线:")
        for event in events:
            print(f"- {format_event(event)}")
        print()


def main():
    parser = argparse.ArgumentParser(description="解析阴阳师客户端日志里的模型/技能资源。")
    parser.add_argument("log_path", help="log.txt 路径")
    parser.add_argument("--map", default=str(DATA_DIR / "log-resource-map.json"), help="资源映射 JSON")
    parser.add_argument("--bucket", type=int, default=60, help="按多少秒分组输出")
    parser.add_argument("--bp", action="store_true", help="输出名士 BP 时间线")
    parser.add_argument("--bp-lite", action="store_true", help="只输出双方 ban 和敌方选人")
    args = parser.parse_args()

    log_path = Path(args.log_path).expanduser()
    if not log_path.exists():
        raise SystemExit(f"找不到日志文件: {log_path}")

    mapping = load_json(Path(args.map))
    shikigami_names = load_shikigami_names()
    if args.bp_lite:
        print_bp_lite_report(log_path, mapping, shikigami_names)
    elif args.bp:
        print_bp_report(log_path, mapping, shikigami_names)
    else:
        buckets, unknown, _ = parse_log(log_path, mapping, shikigami_names, args.bucket)
        print_report(buckets, unknown, args.bucket)


if __name__ == "__main__":
    main()
