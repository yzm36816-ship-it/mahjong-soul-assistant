# 使用与维护

## 数据目录

- `data/templates/<牌编码>/*.png`：本地牌面样本，仅私用。
- `data/samples/`：用户授权的原始截图副本与开发标注。
- `data/video_samples/`：参考视频提取的静帧与时间位置。
- `data/config/regions.json`：窗口、截图、视频各自的归一化区域。
- `data/sessions/history.sqlite3`：变化快照与人工确认结果。
- `data/logs/application.log`：程序错误；轮转保留，避免无限增长。
- `artifacts/`：开发验证报告和可视检查图。

模板只用于本地适配，未授予第三方游戏素材的公开分发许可。独立包包含本机已有模板，面向这次私人使用。

## 常见情况

**找不到窗口**：打开 Steam 雀魂客户端并恢复为可见窗口，点击刷新。浏览器窗口会被排除。

**黑屏 / 最小化**：恢复游戏，尝试窗口模式。程序会暂停，不会自动截全桌面作为替代。

**牌面识别不全**：等待动画结束；校准区域；在“牌面样本”确认正确裁剪。不要把多张牌或遮挡片段训练成单张牌。也可以直接在“校对牌局”输入完整当前状态。

**同一种牌超过四张**：可能识别错误、区域包含副露，或模式选错。修正后再确认。赤五与普通五合计不得超过四张。

**怎么输入牌**：例如 `123m 456p 789s 东南白`，也可用 `1234567z` 表示东南西北白发中；`0m / 0p / 0s` 表示赤五。三麻拒绝二至八万。

**确认后又变成待校对**：当前版本确认只对应同一观察快照。变化后重新核对，这是已知限制。

**视频快结束误识别**：结算页不属于牌桌，请停止分析。界面不会自动确认这些结果。

**重置识别区域**：关闭程序后备份或重命名 `data/config/regions.json`，再次启动即使用默认区域。

**删除误标样本**：关闭程序，在 `data/templates/` 对应牌编码目录删除那张错误裁剪，再启动。

## 开发验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/recognition_report.py
.\.venv\Scripts\python.exe tools/qa_desktop.py
.\.venv\Scripts\python.exe -m mahjong_assistant --image data/samples/sample-2.png --smoke-output artifacts/desktop-preview.png
```

`qa_desktop.py` 只截取它自己创建的测试窗口，不截取其他打开的窗口。原始素材尚未提交 Git，CI 只运行不依赖私有素材的规则 / 状态测试。

