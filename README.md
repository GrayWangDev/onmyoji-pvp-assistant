# Onmyoji PVP Assistant

这是一个给公会用的阴阳师 PVP 助手雏形。

当前阶段先从 BP 推荐和御魂配置规则库开始，后续可以逐步扩展到阵容教学、版本策略管理、截图识别，以及战斗中操作建议。

## 目录

- `data/heroes.json`: 角色字典，记录角色正式名、简称、英文名。
- `data/builds.json`: 御魂配置库，记录同一个角色的不同配置。
- `data/versions/2026-05/meta.json`: 版本说明。
- `data/versions/2026-05/ban_magatsuhi/shijiamei/expert_a.json`: 某个版本、某个 ban 位、某个体系、某个高手的策略包。
- `scripts/validate_data.py`: 数据校验脚本。

## 第一步先填什么

先填 `data/heroes.json`。

目标不是一次填完所有角色，而是先把攻略里出现的角色放进去。重点是 `aliases`，也就是高手攻略里可能出现的简称。

示例：

```json
{
  "id": "sp_hoshiguma",
  "name": "SP星熊童子",
  "aliases": ["熊", "星熊", "SP熊", "sp熊"],
  "type": "SP"
}
```

## 填写原则

- `id` 用英文或拼音，创建后尽量不要改。
- `name` 用角色正式中文名。
- `aliases` 放所有常见简称。
- 暂时不确定的字段可以先留空，后面再补。
