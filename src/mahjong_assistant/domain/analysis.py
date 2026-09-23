"""Transparent, uncalibrated defensive heuristics. Scores are NOT probabilities.

Human confirmation and repeated visual observations remain separate.
Automatic genbutsu is conditional on correct recognition, never an absolute guarantee.
"""
from .models import Assessment, Board, Opponent, TileRisk
from .tiles import normalize
from .waits import possible_ron_waits


def tile_risk(tile: str, opponent: Opponent) -> TileRisk:
    t = normalize(tile)
    discards = {normalize(x) for x in opponent.discards}
    if t in discards and opponent.confirmed:
        return TileRisk(tile, "现物", 0, "已确认该家舍过同种牌；仅对该家的荣和安全，不表示不在其自摸等待中。")
    if not opponent.confirmed and not opponent.auto_observed:
        return TileRisk(tile, "待核对", 50, "该家牌河未确认，暂不生成安全结论。")
    if t in discards and opponent.auto_observed:
        return TileRisk(tile, "识别现物", 10, "画面识别到该家舍过同种牌；若识别正确则对该家荣和安全，仍可能误认或漏检。")
    n, suit = int(t[0]), t[1]
    if suit == "z":
        return TileRisk(tile, "未排除", 45, "字牌仍可能是单骑或双碰；未统计完整可见牌数量。")
    counterparts = ([n + 3] if n <= 3 else [n - 3] if n >= 7 else [n - 3, n + 3])
    if all(f"{v}{suit}" in discards for v in counterparts):
        return TileRisk(tile, "筋·仍有险", 30, "筋只排除对应两面荣和；仍可能有嵌张、边张、单骑或双碰。")
    return TileRisk(tile, "优先警戒", 65 if 3 <= n <= 7 else 55,
                    "尚无现物或完整筋依据；属于规则警戒排序，不是对手等待牌预测。")


def assess(board: Board) -> list[Assessment]:
    result = []
    for opponent in board.opponents:
        discard_count = len(opponent.discards) + opponent.unknown_count
        if opponent.riichi and opponent.confirmed:
            status, detail = "已确认立直", "已听牌；实际等待未知。下方仅比较你手中牌的荣和风险。"
        elif opponent.riichi_candidate:
            status, detail = "疑似立直 · 高警戒", "连续画面检测到横置舍牌；可能是立直牌，请结合游戏立直提示。"
        elif not opponent.confirmed and not opponent.auto_observed:
            status, detail = "证据待确认", "正在自动观察稳定画面；牌面变化后会继续分析，无需逐轮点击校对。"
        elif opponent.melds >= 3 or (opponent.melds >= 2 and discard_count >= 10):
            status, detail = "听牌倾向较高", "多次副露且手牌推进较深；启发式判断，可能仍未听牌。"
        elif discard_count >= 12:
            status, detail = "需要警戒", f"检测到 {discard_count} 张舍牌，后段默听不能排除；巡目不能证明听牌。"
        elif discard_count >= 6:
            status, detail = "默听需留意", f"检测到 {discard_count} 张舍牌；进入中盘观察，尚无确切听牌证据。"
        else:
            status, detail = "听牌证据不足", "公开信息不足以确认听牌，也不能据此认定没有听牌。"
        risks = []
        if (board.hand_confirmed or board.auto_hand_ready) and (opponent.confirmed or opponent.auto_observed):
            unique = dict.fromkeys(board.hand)
            risks = sorted((tile_risk(t, opponent) for t in unique), key=lambda r: (-r.score, r.tile))
        if opponent.unknown_count:
            detail += f" 其中 {opponent.unknown_count} 张牌名未确定。"
        result.append(Assessment(opponent.seat, status, detail, risks, possible_ron_waits(board, opponent)))
    return result
