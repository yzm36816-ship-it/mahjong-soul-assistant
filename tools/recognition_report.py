"""Generate reproducible observed counts, not claims of recognition accuracy."""
from pathlib import Path
import json
from PIL import Image, ImageDraw
from mahjong_assistant.infrastructure.paths import data_root, project_root
from mahjong_assistant.vision.recognizer import Recognizer

recognizer = Recognizer()
report = []
files = list((data_root()/"samples").glob("sample-*.png")) + list((data_root()/"video_samples").glob("*.png"))
for path in files:
    recognizer.use_profile("video" if path.parent.name == "video_samples" else "image")
    observation = recognizer.read(Image.open(path))
    records = [{"seat":d.seat,"tile":d.tile,"suggestion":d.suggestion,"similarity":round(d.similarity,3),"box":d.box} for d in observation.detections]
    report.append({"name":path.name,"counts":{s:len(observation.for_seat(s)) for s in recognizer.regions},"accepted":sum(d.tile!="?" for d in observation.detections),"detections":records})
    if path.name == "sample-2.png":
        sheet=Image.new("RGB",(1000,((len(records)+9)//10)*130),"#d9e0e6")
        draw=ImageDraw.Draw(sheet)
        for i,d in enumerate(observation.detections):
            x,y=i%10*100,i//10*130
            crop=d.crop.copy(); crop.thumbnail((88,94)); sheet.paste(crop,(x+6,y+22))
            draw.text((x+3,y+3),f"{i}:{d.seat}",fill="black")
            draw.text((x+3,y+113),f"{d.tile}/{d.suggestion} {d.similarity:.2f}",fill="black")
        sheet.save(project_root()/"artifacts"/"current-tiles.png")
target=project_root()/"artifacts"/"recognition-report.json"
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
for row in report:
    print(row['name'], row['counts'], 'accepted',row['accepted'])
