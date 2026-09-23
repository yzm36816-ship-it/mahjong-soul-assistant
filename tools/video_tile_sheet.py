from pathlib import Path
from PIL import Image, ImageDraw
from mahjong_assistant.infrastructure.paths import data_root, project_root
from mahjong_assistant.vision.recognizer import Recognizer

recognizer = Recognizer()
for index in (0, 5):
    path = next((data_root() / "video_samples").glob(f"frame-{index:02d}-*.png"))
    image = Image.open(path)
    # Video captures the entire client with no taskbar. Keep the full tile faces.
    recognizer.regions["hand"] = [.13, .82, .76, .999]
    observation = recognizer.read(image)
    sheet = Image.new("RGB", (1000, ((len(observation.detections)+9)//10)*130), "#d9e0e6")
    draw = ImageDraw.Draw(sheet)
    for i, d in enumerate(observation.detections):
        x, y = i%10*100, i//10*130
        crop = d.crop.copy()
        crop.thumbnail((88, 94))
        sheet.paste(crop, (x+6,y+22))
        draw.text((x+3,y+3), f"{i}: {d.seat}", fill="black")
        draw.text((x+3,y+113), f"{d.tile}/{d.suggestion} {d.similarity:.2f}", fill="black")
    sheet.save(project_root()/"artifacts"/f"video-{index}-tiles.png")
