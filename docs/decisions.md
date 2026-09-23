# 技术决策记录

## ADR-001：先采用 Python + PySide6

理由：本机已有可用运行时，能较快完成 Windows 窗口读取、本地计算和小窗口。领域层与 Qt 分离，后续可更换 UI。代价：运行包比原生 Win32 程序大。

## ADR-002：模板识别与可纠正的未知结果

理由：当前只有两张截图和约 70 秒回放，不足以声称通用识别性能。预览版先完成检测、拒识、标注和校准闭环。代价：主题、缩放、动画和皮肤差异需要更多样本。

模板相似度 0.83 与候选差值 0.055 为初始工程阈值，未经独立数据校准，不是置信概率。自动结果仍需确认。

## ADR-003：风险排序与等待预测分开

现物和筋可根据已确认信息给出受规则约束的说明，但不能据此还原真实等待牌。v0.1 仅提供手中牌的防守风险等级。真实等待候选预测进入后续模型评估阶段，不使用假百分比充数。

## ADR-004：人工确认立直与副露

立直标记、横置牌和动画的完整状态尚未验证。预览版将这两项作为人工输入，禁止未经验证的视觉判断直接标记“已听牌”。

## ADR-005：保守失效

当前仅处理观察快照，不能可靠识别所有新局或叫牌事件。为避免跨局复用状态，观察变化、来源切换和读取错误都会使相关确认失效。这降低了连续使用便利性，但保持输出可解释，后续用事件回放测试逐步改善。

## 技术与规则依据

- [Qt for Python / QTimer](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QTimer.html)
- [Pillow / ImageGrab](https://pillow.readthedocs.io/en/stable/reference/ImageGrab.html)
- [OpenCV / contours](https://docs.opencv.org/4.x/d4/d73/tutorial_py_contours_begin.html)
- [EMA Riichi rules 2025](https://mahjong-europe.org/portal/images/docs/Riichi-rules-2025-EN.pdf)：振听与立直的基础规则；雀魂具体规则差异需单独验证。

