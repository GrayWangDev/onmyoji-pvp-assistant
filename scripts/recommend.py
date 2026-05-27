import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_shikigami():
    items = load_json(DATA_DIR / "shikigami.json")
    by_id = {item["id"]: item for item in items}
    alias_to_id = {}

    for item in items:
        names = [item["id"], item["name"], *item.get("aliases", [])]
        for name in names:
            alias_to_id[name.lower()] = item["id"]
            alias_to_id[name] = item["id"]

    return by_id, alias_to_id


def load_builds():
    items = load_json(DATA_DIR / "builds.json")
    return {item["id"]: item for item in items}


def load_strategy_packages(version):
    version_dir = DATA_DIR / "versions" / version
    return [load_json(path) for path in sorted(version_dir.rglob("*.json")) if path.name != "meta.json"]


def resolve_one(value, alias_to_id):
    if not value:
        return ""

    if value in alias_to_id:
        return alias_to_id[value]

    lowered = value.lower()
    if lowered in alias_to_id:
        return alias_to_id[lowered]

    return value


def resolve_many(values, alias_to_id):
    if not values:
        return []

    result = []
    for value in values:
        if not value:
            continue
        result.append(resolve_one(value, alias_to_id))
    return result


def display_shikigami(shikigami_id, by_id):
    item = by_id.get(shikigami_id)
    if not item:
        return shikigami_id
    return item["name"]


def display_build(build_id, builds_by_id, shikigami_by_id):
    build = builds_by_id.get(build_id)
    if not build:
        return build_id

    shikigami_name = display_shikigami(build["shikigami_id"], shikigami_by_id)
    return f'{shikigami_name} · {build["label"]}'


def format_ids(ids, by_id):
    return " / ".join(display_shikigami(item, by_id) for item in ids) if ids else "无"


def matchup_enemy_bans(matchup):
    if "enemy_bans" in matchup:
        return set(matchup["enemy_bans"])
    if "enemy_ban" in matchup:
        return {matchup["enemy_ban"]}
    return set()


def includes_all(selected, required):
    return set(required).issubset(selected)


def intersects(selected, candidates):
    return bool(set(candidates) & selected)


def system_score(system, enemy_picks, enemy_pick_order):
    score = int(system.get("initial_score", 0))

    confirm_hits = set(system.get("confirm_picks", [])) & enemy_picks
    first_n_rule = system.get("confirm_picks_first_n")
    if first_n_rule:
        first_n = int(first_n_rule.get("n", 0))
        first_n_picks = set(enemy_pick_order[:first_n])
        confirm_hits |= set(first_n_rule.get("picks", [])) & first_n_picks

    fuzzy_hits = set(system.get("fuzzy_picks", [])) & enemy_picks
    excluded_hits = set(system.get("excluded_picks", [])) & enemy_picks

    score += len(confirm_hits) * 50
    score += len(fuzzy_hits) * 15
    score -= len(excluded_hits) * 80
    return score, confirm_hits, fuzzy_hits, excluded_hits


def lineup_matches(lineup, enemy_picks):
    reasons = []

    if "enemy_opening" in lineup:
        if not includes_all(enemy_picks, lineup["enemy_opening"]):
            return False, []
        reasons.append("命中对方开局")

    if "enemy_opening_contains" in lineup:
        if not includes_all(enemy_picks, lineup["enemy_opening_contains"]):
            return False, []
        reasons.append("命中对方关键式神")

    return True, reasons


def matching_branches(lineup, enemy_picks, enemy_pick_order):
    branches = []

    for branch in lineup.get("fifth_pick_branches", []):
        if "enemy_picks_contains" in branch and not includes_all(enemy_picks, branch["enemy_picks_contains"]):
            continue
        if "enemy_picks_excludes" in branch and intersects(enemy_picks, branch["enemy_picks_excludes"]):
            continue
        if "enemy_pick_at" in branch:
            matched = True
            for slot, expected in branch["enemy_pick_at"].items():
                index = int(slot) - 1
                if index >= len(enemy_pick_order) or enemy_pick_order[index] != expected:
                    matched = False
                    break
            if not matched:
                continue
        branches.append(branch)

    return branches


def print_recommendations(args):
    shikigami_by_id, alias_to_id = load_shikigami()
    builds_by_id = load_builds()
    packages = load_strategy_packages(args.version)

    our_ban = resolve_one(args.our_ban, alias_to_id)
    enemy_ban = resolve_one(args.enemy_ban, alias_to_id)
    enemy_pick_order = resolve_many(args.enemy_picks, alias_to_id)
    enemy_picks = set(enemy_pick_order)

    print(f"版本: {args.version}")
    print(f"我方ban: {display_shikigami(our_ban, shikigami_by_id)}")
    print(f"敌方ban: {display_shikigami(enemy_ban, shikigami_by_id)}")
    print(f"敌方已选: {format_ids(enemy_pick_order, shikigami_by_id)}")
    print()

    matched_any = False

    for package in packages:
        if package.get("enabled") is False:
            continue
        if package.get("our_ban") != our_ban:
            continue

        for matchup in package.get("matchups", []):
            if enemy_ban not in matchup_enemy_bans(matchup):
                continue

            matched_any = True
            print(f"## {matchup['title']}")

            default = matchup.get("default_recommendation")
            if default:
                print(f"默认起手: {default['name']}")
                print(f"先选: {format_ids(default.get('first_picks', []), shikigami_by_id)}")
                if default.get("first_builds"):
                    builds = [display_build(item, builds_by_id, shikigami_by_id) for item in default["first_builds"]]
                    print(f"配置: {' / '.join(builds)}")
                print(f"理由: {default.get('reason', '')}")
                print()

            systems = []
            for system in matchup.get("enemy_systems", []):
                if enemy_picks and "required_picks" in system and not includes_all(enemy_picks, system["required_picks"]):
                    continue
                score, confirm_hits, fuzzy_hits, excluded_hits = system_score(system, enemy_picks, enemy_pick_order)
                if excluded_hits:
                    continue
                if enemy_picks and not confirm_hits and not fuzzy_hits and not intersects(enemy_picks, system.get("core_picks", [])):
                    continue
                if score <= 0:
                    continue
                systems.append((score, confirm_hits, fuzzy_hits, excluded_hits, system))

            systems.sort(key=lambda item: item[0], reverse=True)

            for score, confirm_hits, fuzzy_hits, excluded_hits, system in systems:
                print(f"可能体系: {system['name']}  score={score}")
                if confirm_hits:
                    print(f"确认信号: {format_ids(sorted(confirm_hits), shikigami_by_id)}")
                elif fuzzy_hits:
                    print(f"模糊信号: {format_ids(sorted(fuzzy_hits), shikigami_by_id)}")
                elif not enemy_picks:
                    print("状态: 只根据ban位预测")
                else:
                    print("状态: 还未命中明确信号")

                if system.get("notes"):
                    print(f"备注: {system['notes']}")

                printed_lineup = False
                for lineup in system.get("recommended_lineups", []):
                    ok, _ = lineup_matches(lineup, enemy_picks)
                    if enemy_picks and not ok:
                        continue

                    printed_lineup = True
                    print(f"- 推荐阵容: {lineup['name']}")
                    print(f"  式神: {format_ids(lineup.get('picks', []), shikigami_by_id)}")
                    if lineup.get("builds"):
                        builds = [display_build(item, builds_by_id, shikigami_by_id) for item in lineup["builds"]]
                        print(f"  配置: {' / '.join(builds)}")
                    print(f"  理由: {lineup.get('reason', '')}")

                    for branch in matching_branches(lineup, enemy_picks, enemy_pick_order):
                        print(f"  分支: {branch.get('id')}")
                        print(f"    下一手: {format_ids(branch.get('next_picks', []), shikigami_by_id)}")
                        print(f"    理由: {branch.get('reason', '')}")

                    if lineup.get("fifth_options"):
                        print(f"  5手可选: {format_ids(lineup['fifth_options'], shikigami_by_id)}")

                    for slot in lineup.get("lineup_slots", []):
                        print(f"  {slot['slot']}手可选: {format_ids(slot.get('options', []), shikigami_by_id)}")
                        if slot.get("note"):
                            print(f"    {slot['note']}")

                if not printed_lineup:
                    print("- 暂无完全命中的推荐阵容，继续观察对方后续选择。")
                print()

            if not systems and matchup.get("ambiguous_policy"):
                print(matchup["ambiguous_policy"].get("message", "继续观察。"))
                print()

    if not matched_any:
        print("没有找到匹配策略包。")


def main():
    parser = argparse.ArgumentParser(description="读取策略包并输出PVP推荐。")
    parser.add_argument("--version", default="2026-05")
    parser.add_argument("--our-ban", required=True)
    parser.add_argument("--enemy-ban", required=True)
    parser.add_argument("--enemy-picks", nargs="*", default=[])
    args = parser.parse_args()

    print_recommendations(args)


if __name__ == "__main__":
    main()
