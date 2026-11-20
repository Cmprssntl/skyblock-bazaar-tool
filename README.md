# SkyBlock Bazaar Tool 4.0

Hypixel SkyBlock 市场分析工具（Qt 版）：Bazaar、Craft、Forge、Enchant 四个行情表，外加本地 K 线图。

4.0 用 PySide6 重写了原 Tk 界面：单窗口标签页、一个进程、后台刷新不阻塞界面，并新增行情录制与 K 线。
旧版 3.5 的四个独立窗口和子进程同步机制已移除。

> **来源与维护**
>
> 本项目 fork 自 [wuyingxiaomo/skyblock-bazaar-tool](https://github.com/wuyingxiaomo/skyblock-bazaar-tool)（上游最后版本为 3.5）。
> 4.0 起由 [Cmprssntl](https://github.com/Cmprssntl) 维护，在上游基础上做了界面重写与功能扩展。
> 原始代码版权归原作者所有，本项目继续按 MIT 许可发布。

## 4.0 相对上游的主要改动

- **界面**：用 PySide6 重写为单窗口标签页（Bazaar / Craft / Forge / Enchant / K 线），后台刷新不再卡界面，支持 Linux 与 Windows。
- **K 线与录制**：新增 SQLite 本地行情记录、15m / 1h / 1d K 线（蜡烛、MA5/10/20、成交量、十字光标、缩放平移）以及无头 `record` CLI。
- **价格语义修正**：明确收购价/出售价的 API 字段；区分挂单深度与 7 日成交量；价格为 0 视为该方向无挂单，缺材料价时成本、利润、产能统一显示 `-`，不再出现虚高利润。
- **交互**：参数面板（列显隐/顺序/数值上下限/单位/数据源）、列宽与排序记忆、行内搜索、右键菜单、标签页恢复、快捷键设置与 X11 全局热键。
- **稳定性**：修复 AH 分页重试、断网时缓存价格回写、设置迁移、PyInstaller 路径等问题；历史数据默认保留 90 天并自动清理。
- **测试与打包**：42 项测试（含 3.5 golden 对照与 Qt 冒烟测试）、ruff 配置、PyInstaller spec、Linux 桌面安装脚本和图标。

## 功能

- **Bazaar**：收购价、出售价、中间价、单件差价、利润率、订单数、挂单件数、7 日成交量
- **Craft / Forge / Enchant**：材料成本、四种买卖组合利润、利润率、可制作数量、锻造时间与小时利润
- **K 线**：蜡烛 + MA5/10/20 + 成交量柱 + 十字光标，周期 15m / 1h / 1d（默认 15 分钟，适合游戏内的交易频率）
- **本地录制**：每次成功刷新 Bazaar 后，把自选物品写入 SQLite，重启后历史仍在
- **表格**：数值列正确排序（未知值永远在最后）、行内搜索、右键复制 ID / 查看 K 线 / 加入自选
- **参数面板**：列显隐、列顺序、数值上下限（支持 `10k` / `2.5m` / `1b`）、单位切换、数据源筛选
- **设置**：单一 `settings.json`、原子写入、自动迁移 3.5 的旧配置、窗口几何与列宽记忆
- **快捷键**：任意按钮可绑定单键、修饰键组合或 `V+B` 这类普通按键组合；X11 下支持窗口外全局热键

## 安装与运行

需要 Python 3.10+。

### Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m skyblock_bazaar
```

安装桌面图标（写入 `~/.local/share/applications`，不需要 root）：

```bash
bash deploy/install-desktop.sh
```

全局热键依赖 `python-xlib`（`requirements.txt` 已在 Linux 上自动安装）。
Wayland 会话无法注册全局热键，快捷键只在窗口内生效，程序会在状态栏提示。

### Windows

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m skyblock_bazaar
```

打包（PyInstaller）：

```powershell
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller deploy\skyblock-bazaar.spec
```

产物在 `dist\SkyBlockBazaar\`，配方目录与 `bazaar.ico` 会一并打包。

## 数据目录

默认使用项目根目录（打包后是 exe 旁边）的 `bazaar_config/`：

| 文件 | 内容 |
|---|---|
| `settings.json` | 全部设置，权限 600 |
| `bazaar_data.json` | 最近一次 Bazaar 快照缓存 |
| `auction_data.json` | Auction House BIN 最低价索引 |
| `history.db` | 本地 K 线历史（SQLite，WAL） |
| `logs/` | 滚动日志 |

可以用环境变量 `SBZ_DATA_DIR=/path/to/data` 改到别的位置。

首次启动会自动读取 3.5 的 `bazaar_config.json` / `craft_config.json` / `forge_config.json` / `enchant_config.json` 并合并迁移，旧文件保持不动。

## 价格与数量口径

| 名称 | Hypixel 字段 | 含义 |
|---|---|---|
| 收购价 | `quick_status.sellPrice` | 立即买入价（卖一价 / ask） |
| 出售价 | `quick_status.buyPrice` | 立即卖出价（买一价 / bid） |
| 中间价 | 两者平均 | K 线默认口径 |

**4.0 更正**：API 的 `buyVolume` / `sellVolume` 是订单簿两侧的**挂单件数（深度）**，不是成交量。
真正成交量使用 `*MovingWeek`（近 7 天滚动成交）：

- 页面上的“卖单件数 / 买单件数”是挂单深度；
- “7 日买入量 / 7 日卖出量”才是成交量；
- K 线量柱取相邻快照 `Δ sellMovingWeek + Δ buyMovingWeek`（间隔 ≤ 30 分钟，负值归零），UI 标注“近似”。

价格为 0 表示该方向没有挂单（没有卖一价或买一价），显示为 `-`，不会被当成“免费”。
配方中只要有一种材料拿不到 Bazaar 价格，成本、利润和可制作数量也显示为 `-`，避免用部分成本算出虚高利润。

## K 线与本地录制

- 开启“录制”（默认开启）后，每次 Bazaar 刷新都会记录自选列表中的物品。
- 在任意表格行右键 → **加入/移出自选**，或双击行进入 K 线页后点“记录此物品”。
- 自动刷新间隔默认 60 秒，右键工具栏上的“自动刷新”按钮可在 30 秒 / 1 分钟 / 2 分钟 / 5 分钟 / 关闭之间切换。
- K 线页可切换价格口径（中间价 / 收购价 / 出售价）和周期；滚轮缩放、拖拽平移、双击回到最新。
- 历史默认保留 90 天，启动时清理过期行；可在 `settings.json` 的 `history.retention_days` 调整。
- 无头录制（适合长期挂机，不打开界面）：

```bash
.venv/bin/python -m skyblock_bazaar record --items ENCHANTED_DIAMOND,BOOSTER_COOKIE --interval 60
# 只采一次
.venv/bin/python -m skyblock_bazaar record --items ENCHANTED_DIAMOND --once
```

不传 `--items` 时使用界面里保存的自选列表。`Ctrl+C` 会先写完队列再退出。

## 快捷键与筛选

- 默认 `Ctrl+F` 打开当前页搜索；`Esc` 关闭。
- “快捷键设置”里点击“设置”，直接按想要的键：支持单键、`Ctrl+Alt+X`，以及按住 `V` 再按 `B` 的普通组合键。
- 勾选“全局”后窗口失去焦点仍生效（仅修饰键组合；Windows 用 `RegisterHotKey`，X11 用 `XGrabKey`）。
- 参数面板里数值下限/上限支持 `10k`、`2.5m`、`1b`，也可以配合单位下拉使用；两者不会重复换算。
- 公式错误（例如输入 `abc`）会标红并提示，不再静默忽略。

## 开发与测试

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/ruff check skyblock_bazaar tests
```

测试包含：

- 3.5 golden 数据对照（Craft / Forge / Enchant 的价格、成本、利润、产能）
- 配置迁移、单位解析、排序（未知值最后）、OHLC 聚合、SQLite 写入/清理
- 四个页面与 K 线页的 offscreen Qt 冒烟测试

`tests/fixtures/bazaar_snapshot.json` 是真实 Bazaar 快照；`tests/golden/` 由 3.5 代码生成。
有意差异只有“未知价格”规则，测试会逐字段断言。

## 配方库维护

`craft_recipe/`、`forge_recipe/`、`enchanted_book_recipe/` 是运行时读取的配方数据。
`generate_enchanted_book_recipes.py` 是附魔书配方生成脚本（需要 NEU 仓库和一份 `bazaar_data.json`），仅维护配方时使用。
本次配方更新的核对结果见 [recipe_update_report.md](recipe_update_report.md)。

## 许可

MIT，见 [LICENSE](LICENSE)。

原始项目 [wuyingxiaomo/skyblock-bazaar-tool](https://github.com/wuyingxiaomo/skyblock-bazaar-tool) 的版权归原作者所有；
4.0 起的修改由 [Cmprssntl](https://github.com/Cmprssntl) 维护。
