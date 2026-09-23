"""Manually reviewed video calibration frames. Not independent validation."""
from PIL import Image
from mahjong_assistant.infrastructure.paths import data_root
from mahjong_assistant.vision.recognizer import Recognizer

LABELS = {
    0: "9m 1p 1p 2p 2p 0p 5p 6p 6p 9p 9p 7s 5z 3z".split(),
    5: "1p 1p 1p 2p 2p 0p 5p 6p 6p 9p 9p 9p 9m 7s 7s 1s 9m 5z 5s 3z 1s 5z 7s 2s 1s 2z 8p 2s 2z 7z 6z 2z 2z".split(),
}

recognizer = Recognizer()
recognizer.use_profile("video")
for index, labels in LABELS.items():
    path = next((data_root()/"video_samples").glob(f"frame-{index:02d}-*.png"))
    observation = recognizer.read(Image.open(path))
    if len(labels) != len(observation.detections):
        raise ValueError(f"Frame {index}: recheck crop annotations before seeding")
    for n, (tile, detection) in enumerate(zip(labels, observation.detections)):
        destination = recognizer.bank.root / tile / f"video-{index}-{n}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        detection.crop.save(destination)
recognizer.bank.reload()
print(f"templates={len(recognizer.bank.entries)}, unique={recognizer.bank.coverage}/34")
