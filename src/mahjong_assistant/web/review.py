"""Evidence-bound local post-game review; no unsupported hidden-hand claims."""

KINDS = {"round_start": "开始新一局", "midround_join": "从牌局中途接入",
         "discard": "舍牌", "riichi_candidate": "出现疑似立直横置牌",
         "riichi_confirmed": "人工确认立直", "call_confirmed": "人工确认副露",
         "river_removed_candidate": "牌河减少，可能被副露取走",
         "tracking_gap": "出现识别或事件跟踪缺口"}


def describe(event: dict) -> str:
    action = KINDS.get(event["kind"], event["kind"])
    seat = event.get("seat") or "牌局"
    tile = f" {event['tile']}" if event.get("tile") else ""
    return f"事件 #{event['sequence']}：{seat}{action}{tile}。"


def answer(events: list[dict], question: str, sequence: int | None = None) -> dict:
    if not events:
        return {"answer": "还没有可复盘的事件。", "evidence": [], "limitations": "没有牌局数据。"}
    selected = next((event for event in events if event["sequence"] == sequence), events[-1])
    if any(word in question for word in ("听牌", "等什么", "等待", "放铳")):
        confirmed = [event for event in events if event["kind"] == "riichi_confirmed"]
        if confirmed:
            return {"answer": "记录中有人工确认的立直，因此该家已听牌；仅靠公开事件无法确定实际等待牌。",
                    "evidence": [event["sequence"] for event in confirmed],
                    "limitations": "此处没有对手完整手牌，也没有通过独立测试的等待预测。"}
        return {"answer": "这份事件记录不足以确认对手是否听牌，也无法确定等待牌。",
                "evidence": [selected["sequence"]], "limitations": "疑似横置牌不是立直确认；没有隐藏手牌真值。"}
    if "立直" in question:
        matches = [event for event in events if "riichi" in event["kind"]]
        return {"answer": "\n".join(describe(event) for event in matches[-5:]) if matches else "记录中没有识别到立直事件。",
                "evidence": [event["sequence"] for event in matches[-5:]],
                "limitations": "横置牌只代表疑似立直，除非有人工确认事件。"}
    if any(word in question for word in ("错", "漏", "可信", "问题")):
        matches = [event for event in events if event["kind"] in ("tracking_gap", "river_removed_candidate")]
        return {"answer": "\n".join(describe(event) for event in matches[-5:]) if matches else "当前记录没有标出的事件缺口。",
                "evidence": [event["sequence"] for event in matches[-5:]],
                "limitations": "未标出缺口不等于识别完全正确。"}
    return {"answer": describe(selected), "evidence": [selected["sequence"]],
            "limitations": "只描述已记录的公开事件；该事件的识别状态为「" + selected["confidence"] + "」。"}
