import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEROES_PATH = ROOT / "data" / "heroes.json"
BUILDS_PATH = ROOT / "data" / "builds.json"
ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def collect_duplicates(items):
    return {key: values for key, values in items.items() if len(values) > 1}


def validate_heroes():
    heroes = load_json(HEROES_PATH)
    issues = []
    ids = defaultdict(list)
    names = defaultdict(list)
    aliases = defaultdict(list)

    for index, hero in enumerate(heroes):
        label = hero.get("name") or f"index {index}"

        for field in ("id", "name", "aliases", "type"):
            if field not in hero:
                issues.append(f"{label}: 缺少字段 {field}")

        hero_id = hero.get("id", "")
        name = hero.get("name", "")
        hero_aliases = hero.get("aliases", [])

        if not isinstance(hero_id, str) or not hero_id.strip():
            issues.append(f"{label}: id 不能为空")
        elif not ID_PATTERN.match(hero_id):
            issues.append(f"{label}: id 建议只用小写英文、数字、下划线，目前是 {hero_id}")

        if not isinstance(name, str) or not name.strip():
            issues.append(f"{label}: name 不能为空")

        if not isinstance(hero_aliases, list):
            issues.append(f"{label}: aliases 必须是数组")
            hero_aliases = []

        ids[hero_id].append(label)
        names[name].append(hero_id)

        for alias in hero_aliases:
            aliases[alias].append(f"{hero_id}:{name}")

    duplicate_ids = collect_duplicates(ids)
    duplicate_names = collect_duplicates(names)
    duplicate_aliases = collect_duplicates(aliases)

    print(f"角色数量: {len(heroes)}")

    if duplicate_ids:
        print("\n重复 id:")
        for key, values in duplicate_ids.items():
            print(f"- {key}: {', '.join(values)}")

    if duplicate_names:
        print("\n重复 name:")
        for key, values in duplicate_names.items():
            print(f"- {key}: {', '.join(values)}")

    if duplicate_aliases:
        print("\n重复 aliases:")
        for key, values in duplicate_aliases.items():
            print(f"- {key}: {', '.join(values)}")

    return heroes, issues


def validate_builds(hero_ids):
    builds = load_json(BUILDS_PATH)
    issues = []
    ids = defaultdict(list)

    for index, build in enumerate(builds):
        label = build.get("id") or f"index {index}"

        for field in ("id", "hero_id", "label", "soul", "stats", "tags", "use_case"):
            if field not in build:
                issues.append(f"{label}: 缺少字段 {field}")

        build_id = build.get("id", "")
        hero_id = build.get("hero_id", "")

        if not isinstance(build_id, str) or not build_id.strip():
            issues.append(f"{label}: id 不能为空")
        elif not ID_PATTERN.match(build_id):
            issues.append(f"{label}: id 建议只用小写英文、数字、下划线，目前是 {build_id}")

        if hero_id not in hero_ids:
            issues.append(f"{label}: hero_id 不存在于 heroes.json: {hero_id}")

        if not isinstance(build.get("stats", []), list):
            issues.append(f"{label}: stats 必须是数组")

        if not isinstance(build.get("tags", []), list):
            issues.append(f"{label}: tags 必须是数组")

        ids[build_id].append(label)

    duplicate_ids = collect_duplicates(ids)
    if duplicate_ids:
        for key, values in duplicate_ids.items():
            issues.append(f"重复 build id {key}: {', '.join(values)}")

    print(f"配置数量: {len(builds)}")
    return builds, issues


def main():
    heroes, hero_issues = validate_heroes()
    hero_ids = {hero["id"] for hero in heroes}
    _, build_issues = validate_builds(hero_ids)
    issues = hero_issues + build_issues

    if issues:
        print("\n需要处理:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
