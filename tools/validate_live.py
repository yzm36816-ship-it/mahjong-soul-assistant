"""Read the single user-authorized Mahjong Soul window without game interaction."""
import json
import time
import sys
from pathlib import Path
from mahjong_assistant.infrastructure.windows import game_windows, capture
from mahjong_assistant.infrastructure.gpu_capture import stop
from mahjong_assistant.vision.recognizer import Recognizer
from mahjong_assistant.application.session import Session
from mahjong_assistant.domain.analysis import assess

windows = game_windows()
if len(windows) != 1:
    raise SystemExit("Expected exactly one user-authorized Mahjong Soul window")
recognizer = Recognizer()
recognizer.use_profile("window")
session = Session(3)
rows = []
frame_count = int(sys.argv[1]) if len(sys.argv) > 1 else 12
try:
    for index in range(frame_count):
        started=time.monotonic()
        image = capture(windows[0].handle)
        if index in (0, 5, frame_count-1):
            image.save(f"data/diagnostics/live-{index}.png")
        observation = recognizer.read(image, "Steam 游戏窗口")
        session.update(observation)
        results = assess(session.board)
        rows.append({"index":index,"size":image.size,"hand":[d.tile for d in observation.for_seat('hand')],
                     "automatic":session.board.auto_hand_ready,
                     "river_counts":{o.seat:len(o.discards) for o in session.board.opponents},
                     "statuses":{a.seat:a.status for a in results},
                     "risk_rows":sum(len(a.risks) for a in results),"warnings":session.board.warnings})
        time.sleep(max(0,.75-(time.monotonic()-started)))
finally:
    stop()
Path('artifacts/live-validation-v02.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print({"frames":len(rows),"auto_risk_frames":sum(r['risk_rows']>0 for r in rows),"last_hand":rows[-1]['hand'],"river_counts":rows[-1]['river_counts']})
