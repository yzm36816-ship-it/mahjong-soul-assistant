"""Generate private tile contact sheets from explicitly supplied screenshots."""
from pathlib import Path
import json
import sys
from PIL import Image, ImageDraw
from mahjong_assistant.vision.recognizer import Recognizer
from mahjong_assistant.infrastructure.paths import data_root, project_root


def main():
    destination = data_root() / "samples"
    destination.mkdir(parents=True, exist_ok=True)
    recognizer = Recognizer()
    report = []
    for sample, filename in enumerate(sys.argv[1:], 1):
        with Image.open(filename) as image:
            image.convert("RGB").save(destination / f"sample-{sample}.png")
            observation = recognizer.read(image)
        cells = observation.detections
        sheet = Image.new("RGB", (1000, ((len(cells) + 9) // 10) * 130), "#d9e0e6")
        draw = ImageDraw.Draw(sheet)
        records = []
        for i, detection in enumerate(cells):
            x, y = (i % 10)*100, (i // 10)*130
            crop = detection.crop.copy()
            crop.thumbnail((88, 94))
            sheet.paste(crop, (x+6, y+22))
            draw.text((x+4, y+3), f"{i}: {detection.seat}", fill="black")
            draw.text((x+4, y+113), f"{detection.tile} {detection.similarity:.2f}", fill="black")
            records.append({"index": i, "seat": detection.seat, "box": detection.box})
        target = project_root() / "artifacts" / f"sample-{sample}-tiles.png"
        sheet.save(target)
        report.append({"sample": sample, "count": len(cells), "tiles": records})
        print(target, len(cells))
    (destination / "detections.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
