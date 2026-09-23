"""Seed reviewed crops from the two user screenshots; local-only private assets.

These images are calibration examples, NOT held-out accuracy test data.
"""
from PIL import Image
from mahjong_assistant.infrastructure.paths import data_root
from mahjong_assistant.vision.recognizer import Recognizer

LABELS = {
    1: "4m 5m 4p 5p 3s 3s 4s 4s 6s 6s 6s 4z 6z 3z".split(),
    2: ("2m 3m 1p 1p 3p 4p 6p 7p 8p 9p 0s 6s 8s 4m "
        "3z 6z 4p 1z 5m 9m 5s 6m 3p 1s 9s "
        "9m 6m 3m 3s 8m 5s 8s 9s 8m 3s 3m 1z 1m 2z "
        "3z 2z 1p 1m 1z 8p 6m 5p 5m 4m 2m 6z 7z 5m "
        "9m 3m 3s 1z 4m 2m 1m 7s 2z 6z 8m").split(),
}


def main():
    recognizer = Recognizer()
    for sample, labels in LABELS.items():
        image = Image.open(data_root() / "samples" / f"sample-{sample}.png")
        observation = recognizer.read(image)
        if len(labels) != len(observation.detections):
            raise ValueError(f"Sample {sample}: expected {len(labels)} tiles; got {len(observation.detections)}. Review segmentation before reseeding.")
        for tile, detection in zip(labels, observation.detections):
            destination = recognizer.bank.root / tile / f"seed-{sample}-{observation.detections.index(detection)}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            detection.crop.save(destination)
    recognizer.bank.reload()
    print(f"templates={len(recognizer.bank.entries)}, unique={recognizer.bank.coverage}/34")


if __name__ == "__main__":
    main()
