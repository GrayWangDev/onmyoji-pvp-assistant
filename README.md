# Onmyoji PVP Assistant

给公会使用的阴阳师 PVP 助手雏形。

当前阶段聚焦 BP 推荐：根据双方 ban 位和敌方已选式神，预测对方可能体系，并展示我方推荐阵容、分支和理由。后续可以继续扩展到截图/OCR 识别、实时 BP 辅助、阵容教学和战斗中操作建议。

## 当前功能

- 式神字典：维护式神正式名、简称、英文名。
- 御魂配置库：维护同一式神的多套配置。
- 策略包：按版本、ban 位、体系、作者记录 BP 思路。
- 命令行推荐器：输入 ban 位和敌方已选，输出推荐阵容。
- 静态网页：手动点选 ban 位和敌方已选，实时显示推荐结果。
- 截图 OCR 实验：上传 BP 截图，尝试识别中间角色名字牌。
- 数据校验：检查式神和配置引用是否有效。

## 目录

- `data/shikigami.json`: 式神字典。
- `data/builds.json`: 御魂配置库。
- `data/versions/2026-05/meta.json`: 版本说明。
- `data/versions/2026-05/ban_magatsuhi/shijiamei/expert_a.json`: 策略包示例。
- `docs/strategy_package_format.md`: 策略包格式说明。
- `scripts/validate_data.py`: 数据校验脚本。
- `scripts/recommend.py`: 命令行推荐器。
- `web/`: 静态网页雏形。

## 运行网页

在项目根目录启动本地服务器：

```bash
python3 -m http.server 8000
```

然后打开：

```text
http://127.0.0.1:8000/web/
```

网页会读取 `data/` 里的 JSON 数据。

截图 OCR 功能目前是实验入口，会通过浏览器加载 Tesseract.js，并优先识别截图中间左右两侧的名字牌区域。识别结果会用 `data/shikigami.json` 的 `aliases` 映射到式神。

## GitHub Pages 部署

仓库包含 GitHub Pages workflow：

```text
.github/workflows/pages.yml
```

推送到 `main` 后，GitHub Actions 会发布静态页面。第一次使用时，需要在 GitHub 仓库里确认 Pages 设置：

```text
Settings -> Pages -> Build and deployment -> Source -> GitHub Actions
```

部署完成后访问：

```text
https://graywangdev.github.io/onmyoji-pvp-assistant/
```

根页面会自动跳转到 `web/`。

## 命令行推荐

示例：

```bash
python3 scripts/recommend.py --our-ban 祸 --enemy-ban 禅 --enemy-picks 离 封 骷髅 言
```

另一个示例：

```bash
python3 scripts/recommend.py --our-ban 祸 --enemy-ban 阎魔 --enemy-picks 因幡 面 龙珏
```

输入可以用式神 `id`、正式名或 `aliases` 里的简称。

## 数据校验

每次修改式神字典、御魂配置或策略包后，建议运行：

```bash
python3 scripts/validate_data.py
```

当前校验会检查：

- `shikigami.json` 的字段、重复 id/name/aliases。
- `builds.json` 的字段、重复 id。
- `builds.json` 里的 `shikigami_id` 是否存在于 `shikigami.json`。

## 填写规则

### 式神字典

```json
{
  "id": "sphoshiguma",
  "name": "SP星熊童子",
  "aliases": ["SP星熊童子", "SP熊", "sp熊"],
  "type": "SP"
}
```

- `id`: 稳定唯一编号，建议小写英文、数字、下划线。
- `name`: 式神正式名。
- `aliases`: 攻略里可能出现的简称，尽量避免不同式神重复。

### 御魂配置

```json
{
  "id": "sp_hoshiguma_jizo_hp_hit_hp",
  "shikigami_id": "sphoshiguma",
  "label": "地藏 生/命/生",
  "soul": "地藏像",
  "stats": ["生命", "效果命中", "生命"],
  "tags": ["抗速攻", "防爆发", "挖土对策"],
  "use_case": "专门应对一速加爆发输出的挖土阵容"
}
```

- `shikigami_id`: 必须对应 `data/shikigami.json` 里的式神 `id`。
- `stats`: 按 2/4/6 号位填写。
- `tags`: 可重复，用于分类和筛选。
- `use_case`: 给玩家看的使用场景。

## 下一步方向

- 补充更多 ban 位和高手策略包。
- 给网页增加我方已选、个人式神池和配置池。
- 增加策略包引用校验。
- 接入截图/OCR 识别，自动填充双方 ban 和敌方已选。

## 已知边界

- 当前只覆盖已经录入策略包的 ban 位和阵容体系。
- 如果对方选人不符合已有体系，网页会提示“没有找到匹配策略包”。
- 这种局面可以先手动判断，并记录下来作为后续补规则的素材。
- 截图 OCR 目前只验证名字牌识别，不保证能识别所有头像、皮肤或角色模型。
