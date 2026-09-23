"""Sequential replay with no confirmation calls; records behavior, not model accuracy."""
import json
from pathlib import Path
import sys
import time
import cv2
from PIL import Image
from mahjong_assistant.application.session import Session
from mahjong_assistant.vision.recognizer import Recognizer
from mahjong_assistant.domain.analysis import assess

reader = cv2.VideoCapture(sys.argv[1])
fps = reader.get(cv2.CAP_PROP_FPS)
duration = reader.get(cv2.CAP_PROP_FRAME_COUNT)/fps
recognizer = Recognizer()
recognizer.use_profile("video")
session = Session(3)
rows = []
started = time.perf_counter()
for i in range(int(duration * 2)):
    second = i / 2
    reader.set(cv2.CAP_PROP_POS_MSEC, second*1000)
    ok, pixels = reader.read()
    if not ok:
        break
    observation = recognizer.read(Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)))
    session.update(observation)
    results = assess(session.board)
    rows.append({"second":second,"hand":len(session.board.hand),"automatic":session.board.auto_hand_ready,
                 "statuses":{a.seat:a.status for a in results},"risk_rows":sum(len(a.risks) for a in results),
                 "riichi_candidates":sum(o.riichi_candidate for o in session.board.opponents),
                 "event_ready":session.tracker.ready,"events":[e.kind for e in session.recent_events]})
reader.release()
report={"frames":len(rows),"automatic_risk_frames":sum(r['risk_rows']>0 for r in rows),
        "tracked_events":len(session.tracker.events),
        "ready_frames":sum(r['event_ready'] for r in rows),
        "manual_confirmations":0,"seconds":round(time.perf_counter()-started,2),"rows":rows}
Path('artifacts/continuous-validation-v02.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print({k:v for k,v in report.items() if k!='rows'})
