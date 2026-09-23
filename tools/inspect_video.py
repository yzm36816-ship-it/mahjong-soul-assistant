"""Sample a user-supplied video; preserve original file and keep frames local."""
import argparse
import json
from pathlib import Path
import cv2
from PIL import Image, ImageDraw
from mahjong_assistant.infrastructure.paths import data_root, project_root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit("无法读取视频")
    fps, count = capture.get(cv2.CAP_PROP_FPS), capture.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = count / fps
    folder = data_root() / "video_samples"
    folder.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (1440, 3 * 285), "#13212b")
    draw = ImageDraw.Draw(sheet)
    records = []
    for index in range(9):
        second = min(duration - 0.2, 1 + index * (duration - 2) / 8)
        capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        target = folder / f"frame-{index:02d}-{second:.1f}s.png"
        image.save(target)
        image.thumbnail((480, 258))
        x, y = (index % 3)*480, (index // 3)*285
        sheet.paste(image, (x, y+24))
        draw.text((x+8, y+5), f"{index} / {second:.1f}s", fill="white")
        records.append({"second": second, "path": str(target)})
    capture.release()
    sheet.save(project_root() / "artifacts" / "video-contact-sheet.jpg")
    (folder / "manifest.json").write_text(json.dumps({"duration":duration,"fps":fps,"frames":records},ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"duration={duration:.2f}, samples={len(records)}")


if __name__ == "__main__":
    main()
