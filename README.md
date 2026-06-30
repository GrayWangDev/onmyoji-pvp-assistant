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
- 实时日志监听实验：读取 Steam 版阴阳师 `log.txt`，实时显示双方选人。
- 数据校验：检查式神和配置引用是否有效。

## 目录

- `data/shikigami.json`: 式神字典。
- `data/builds.json`: 御魂配置库。
- `data/versions/2026-05/meta.json`: 版本说明。
- `data/versions/2026-05/ban_magatsuhi/shijiamei/expert_a.json`: 策略包示例。
- `docs/strategy_package_format.md`: 策略包格式说明。
- `scripts/validate_data.py`: 数据校验脚本。
- `scripts/recommend.py`: 命令行推荐器。
- `scripts/bp_live_monitor.py`: 实时日志监听窗口。
- `scripts/start_bp_monitor.bat`: Windows 一键启动脚本。
- `data/log-resource-map.json`: 游戏日志资源名到式神的映射表。
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

截图 OCR 功能目前是实验入口，会通过浏览器加载 Tesseract.js，并优先识别截图中间左右两侧的名字牌区域。识别会尝试英文和简体中文，并对中文竖排名字牌尝试旋转识别。识别结果会用 `data/shikigami.json` 的 `aliases` 映射到式神。

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

## 实时日志监听

这是给 Windows Steam 版阴阳师准备的实验功能，用来测试“只读游戏日志，不做图像识别”的 BP 识别路线。

### Windows 使用

1. 下载仓库 ZIP 并解压，或用 Git 拉取仓库。
2. 打开 `scripts` 文件夹。
3. 双击 `start_bp_monitor.bat`。
4. 窗口打开后，确认日志路径是阴阳师目录下的 `log.txt`。
5. 点“开始监听”。
6. 回到游戏进入斗技选人，窗口会显示双方 ban 和选人。

常见 Steam 路径：

```text
C:\Program Files (x86)\Steam\steamapps\common\Onmyoji\log.txt
```

如果自动寻找失败，可以在窗口里手动选择 `log.txt`。

### 目前能做什么

- 支持名士局：双方先 ban，再选 5 个式神。
- 支持无 ban 对局：例如 3000 分以下直接选人。
- 会尝试区分我方和敌方选人。
- 我方一轮内来回拖多个式神时，会取这一轮最后出现的式神作为当前推测结果。
- 对方选人通常更稳定，因为对方来回拖动不会提前暴露给本地日志。

### 注意事项

- 需要 Windows 上安装 Python。安装时建议勾选 `Add Python to PATH`。
- 这个功能现在还是实验版，核心目标是先验证日志识别准确率。
- 游戏日志记录的是资源名，不是中文式神名，所以依赖 `data/log-resource-map.json`。
- 如果遇到未识别的式神，需要补充日志资源名映射。
- 阴阳师、御灵、皮肤和战斗技能也会出现在日志里，目前 BP 窗口主要关注式神选人。

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
- 继续完善日志监听，稳定识别双方 ban 位、敌方选人和无 ban 对局。
- 保留截图/OCR 作为备用方案，用于日志无法覆盖的场景。

## 已知边界

- 当前只覆盖已经录入策略包的 ban 位和阵容体系。
- 如果对方选人不符合已有体系，网页会提示“没有找到匹配策略包”。
- 这种局面可以先手动判断，并记录下来作为后续补规则的素材。
- 截图 OCR 目前只验证名字牌识别，不保证能识别所有头像、皮肤或角色模型。中文 OCR 模型较大，第一次加载会慢一些。
- 实时日志监听依赖游戏本地日志格式。如果游戏更新改变资源名或加载顺序，可能需要重新补映射或调整解析规则。
