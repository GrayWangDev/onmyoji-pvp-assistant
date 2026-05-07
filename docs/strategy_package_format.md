# Strategy Package Format

策略包用来记录某个版本、某个我方 ban 位、某个体系、某个高手的 BP 思路。

当前采用 `enemy_system_prediction_v1` 格式：先根据对方 ban 位预测可能体系，再根据对方已选式神缩小范围，并展示我方推荐阵容。

## 顶层字段

```json
{
  "id": "expert_a_ban_magatsuhi_shijiamei_2026_05",
  "schema": "enemy_system_prediction_v1",
  "version": "2026-05",
  "author": "高手A",
  "our_ban": "ssrmagetsuhi",
  "system": "shijiamei",
  "system_name": "ban祸津神 · 市加美版本",
  "enabled": true,
  "matchups": []
}
```

- `our_ban`: 我方 ban 的式神 id，来自 `data/shikigami.json`。
- `system`: 我方体系 id，自定义英文或拼音。
- `matchups`: 不同敌方 ban 位下的应对。

## matchup

```json
{
  "id": "vs_enemy_ban_kuzunoha",
  "title": "我方ban祸 vs 对方ban葛",
  "enemy_ban": "kuzunoha",
  "default_recommendation": {},
  "enemy_systems": [],
  "ambiguous_policy": {}
}
```

- `enemy_ban`: 对方 ban 的式神 id。
- `default_recommendation`: 只看到双方 ban 时，我方推荐起手。
- `enemy_systems`: 对方可能玩的体系。
- `ambiguous_policy`: 对方已选还不明确时怎么处理。

## default_recommendation

```json
{
  "id": "enma_oto_open",
  "name": "阎音起手",
  "first_picks": ["enma", "tsukuyomi"],
  "first_builds": [],
  "reason": "对方ban葛后常见是禅羊或火山，阎音起手能同时覆盖两个方向。"
}
```

- `first_picks`: 我方推荐先出的式神。
- `first_builds`: 起手阶段需要指定的配置 id，来自 `data/builds.json`；没有就留空数组。

## enemy_system

```json
{
  "id": "zen_yang",
  "name": "禅羊体系",
  "initial_score": 50,
  "core_picks": ["spungaikyo", "guijin"],
  "confirm_picks": ["spungaikyo"],
  "fuzzy_picks": [],
  "notes": "看到禅镜后基本确认对方走禅队。",
  "recommended_lineups": []
}
```

- `core_picks`: 这个体系常见核心。
- `confirm_picks`: 看到这些式神时，基本确认这个体系。
- `fuzzy_picks`: 看到这些式神仍然不确定，只提高可能性。
- `initial_score`: 只看 ban 位时的初始可能性，先用 0-100。

## recommended_lineup

```json
{
  "id": "enma_oto_spqian_odo_zen",
  "name": "阎音千骷禅",
  "picks": ["enma", "tsukuyomi", "spsenhime", "odokuro", "spungaikyo"],
  "builds": [],
  "style": ["针对禅队", "稳定"],
  "difficulty": 2,
  "risk_level": "低",
  "reason": "对方确认禅队后，按阎音千骷禅应对。"
}
```

- `picks`: 我方完整推荐阵容，式神 id 来自 `data/shikigami.json`。
- `builds`: 需要指定的御魂配置 id，来自 `data/builds.json`。
- `difficulty`: 1-5，数字越高越吃熟练度。
- `risk_level`: `低`、`中`、`高`。

## ambiguous_policy

```json
{
  "keep_all_systems": true,
  "message": "对方已选式神还不能确认体系时，继续保留所有可能体系和对应推荐。"
}
```

如果对方选择的是模糊式神，程序会继续展示多个可能体系。
