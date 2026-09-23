# 模型数据与评估契约

## JSONL 输入

每行是一场完整对局，`game_id` 全文件唯一。`source.provenance` 必须是 `self_recorded`、`permission_granted`、`explicit_open_license` 或 `synthetic_demo`；许可数据还需 `license_url`，授权数据还需 `permission_ref`。来源仅作准入与审计标识，无法替代对真实使用权限的核实。下载到本机并不等于可用于本项目。

```json
{"game_id":"my-replay-001","mode":3,"source":{"provenance":"self_recorded","description":"我的雀魂复盘；仅本机保存"},"turns":[{"turn":7,"event_type":"discard","observer_hand":["1p","2p"],"rivers":{"self":["9s"],"top":["5p"],"right":["7z"]},"target_seat":"top","target_discard_history":["5p"],"target_concealed":["1p","2p","3p","4p","5p","6p","7p","8p","9p","1s","2s","3s","7z"],"target_meld_count":0,"target_riichi":true,"temporary_furiten":false}]}
```

示例只说明字段形状，不代表合法的完整物理牌局；真实导入须来自可复核的整场复盘。`turns` 中每条记录必须是**目标对手完成一次舍牌后的状态**。`observer_hand` 是当时自己的手牌；`rivers` 是自己与各对手当时仍在桌上的牌河；`target_discard_history` 包含该对手此前被副露移走的舍牌，末张必须是这次舍牌。`target_concealed` 是复盘揭示的目标对手手牌，仅用于产生真值。`target_meld_count` 包含已完成的面子；北拔不计入。`temporary_furiten` 未知时填 `null`，该样本不参与荣和标签训练。赤五在牌型判断中与普通五同种。

导入时检查来源声明、字段、三麻有效牌、牌数和真值手牌形状。标准型、七对子、国士的结构等待由确定性规则计算；立直荣和标签还排除永久振听及已明确记录的临时振听。副露后无役的荣和判定未完成，首版只训练有确定标签的立直荣和样本。

桌面端播放自己的完整复盘后，可运行 `tools/export_annotation_template.py 会话ID` 生成私有标注底稿。底稿的 `target_concealed` 留空、`target_riichi` 留空且 `needs_review=true`；训练器明确拒绝它。人工在原始复盘逐条核对公开状态、目标手牌和振听后再移除 `needs_review`。中途接入、识别跳变、被副露移走但未校验的片段不会自动生成可训练样本。

## 防止信息泄漏

训练特征只含：自己手牌、各家可见牌河、目标对手最近八张舍牌及其巡目、已确认的立直。目标对手手牌不进入特征向量。视频回放中若能看到对手手牌，那个区域也不得进入视觉模型输入。

分组键是 `game_id`，固定哈希划分 70% 训练、15% 验证、15% 测试。不能把一场牌局的相邻帧分到不同集合。三麻、四麻分别训练、评估、晋级。默认不会把人工纠错直接当成训练真值；修正需复核并写入受控数据集。

## 报告与上线门槛

每个模式报告来源数量、各集合的牌局数和样本数、听牌精确率／召回率／Brier 分数、等待牌 Recall@5、荣和风险 Brier，并与规则巡目基线或训练集先验比较。仅当数据全部来自非合成且已核实的来源、测试集至少有 20 场独立牌局，且听牌、等待、荣和三项都优于各自基线时，`promoted` 才为 `true`。任何缺失或不达标都保持“实验中”，实时窗口不会加载该概率。

当前 `examples/synthetic_replays.jsonl` 是确定性生成的合成数据，仅用于 CI／面试演示管线。它的分数不可用于宣称实战能力。
