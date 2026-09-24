# 雀魂麻将助手 · 0.3 实验版

面向 Windows Steam 雀魂的本地 AI 全栈项目：桌面小窗口读取选定游戏窗口，视频回放走同一识别与事件管线；浏览器看板展示牌局事件、赛后问答和三麻／四麻模型实验。默认不调用云端服务。

**当前没有经过真实独立测试的听牌模型。**桌面端显示的听牌与风险仍是规则提示。合成数据训练只用于验证数据和模型流程，不代表实战准确率；看板会明确标出模型未达上线门槛。

## 在这台电脑上启动

- 双击 `启动助手.cmd` 打开桌面小窗口；选择“三麻”或“四麻”，再点击“开始实时监控”。
- 双击 `启动复盘看板.cmd` 打开本地 Web 看板；地址固定为 `http://127.0.0.1:8765/`。
- 桌面端可导入截图和视频。视频连续播放时与实时窗口使用同一会话、事件追踪和风险分析模块。

公开演示不需要个人视频：Web 看板内置合成三麻和四麻事件。真实窗口读取仍只针对明确选择的雀魂窗口；读取失败或识牌不完整时暂停模型推断。

## 在新电脑上开发

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,web,web-test,ml]"
cd web
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m mahjong_assistant.web
```

另开终端运行 `./.venv/Scripts/python.exe -m mahjong_assistant` 启动桌面端。Web 服务只监听 `127.0.0.1`。当前电脑的 PyTorch 安装为 CPU 版；演示数据训练可在 CPU 上完成，GPU 版可在确有真实数据和训练需求时单独安装。

要复现**合成样例**训练：

```powershell
.\.venv\Scripts\python.exe tools/generate_demo_data.py
.\.venv\Scripts\python.exe tools/train_models.py examples/synthetic_replays.jsonl --epochs 18
```

报告位于 `data/models/3p/report.json` 和 `data/models/4p/report.json`，并显示在 Web 看板。真实牌谱导入格式、来源校验和评估门槛见 [`docs/model-data.md`](docs/model-data.md)。

要复现**RiichiEnv 模拟对局**实验，先安装可选依赖，再生成三麻／四麻各 150 场东风战并训练：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[simulation,ml]"
.\.venv\Scripts\python.exe tools/generate_simulations.py --games-per-mode 150 --seed 20260925 --length east
.\.venv\Scripts\python.exe tools/train_models.py data/simulations/riichienv-greedy-v2.jsonl --epochs 18
```

完整 MJAI 模拟事件日志的压缩包和去路径清单公开在 `examples/simulated/`；本机原始输出、训练数据和权重位于被忽略的 `data/`。RiichiEnv 0.4.10 的东风战后续牌墙并不能仅凭 `reset(seed)` 精确重现，所以事件日志才是实验的可复现输入。克隆仓库后可直接重建**同一份模拟训练数据**：

```powershell
.\.venv\Scripts\python.exe tools/rebuild_simulations.py examples/simulated/riichienv-greedy-v2.events.jsonl.gz --output data/simulations/riichienv-greedy-v2.jsonl
.\.venv\Scripts\python.exe tools/train_models.py data/simulations/riichienv-greedy-v2.jsonl --epochs 18
```

训练报告单独列出未立直听牌指标；即使模拟测试表现好，模型也不会进入实时界面。此实验检验的是模拟分布下的训练流程，**不是雀魂真人对局准确率**。

本次实验的样本数、基线对比和失败场景见 [`docs/simulation-experiment.md`](docs/simulation-experiment.md)。

要从**自己录制的完整复盘**制作人工标注底稿，先在桌面端导入视频并连续播放，再从看板的 `/api/sessions` 查到对应会话 ID，运行 `./.venv/Scripts/python.exe tools/export_annotation_template.py 会话ID`。生成的 `data/annotations/*.jsonl` 在人工核对隐藏手牌、副露和公开牌后才能用于训练；未复核行会被程序拒绝。

## 系统边界

- 识牌使用本地模板；识不出的牌标记为 `?`。事件追踪只从连续稳定画面确认单次牌河增长；横置牌仅记为疑似立直。牌河跳变与牌数冲突会停止模型推断。
- 规则提示依据现物、筋、舍牌巡目和人工确认的立直／副露。规则分数不是概率。等待候选也不是对手真实等待牌。
- 模型从带真值的完整复盘训练，输入只使用当时公开信息与自己的手牌；对手隐藏手牌只用于标签。按整场牌局切分训练、验证、测试。模型必须在各模式的真实独立测试中超过规则基线，才可在桌面端显示概率。
- 本地赛后问答只引用已记录事件；纠错会单独存储，不会覆盖观察或自动训练。生成式云端对话是后续可选功能，目前没有配置密钥或收费调用。
- 私人截图、视频、牌面模板、训练牌谱、权重及本地 SQLite 位于被 Git 忽略的 `data/`；`examples/` 只含明确标记的合成演示资料。公开牌谱必须先核实可用于本项目的范围。

架构与简历展示说明见 [`docs/architecture.md`](docs/architecture.md) 和 [`docs/portfolio.md`](docs/portfolio.md)。
