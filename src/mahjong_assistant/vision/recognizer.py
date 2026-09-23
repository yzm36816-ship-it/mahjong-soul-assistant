"""Local, editable tile templates. Unknowns must stay unknown."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import uuid
import cv2
import numpy as np
from PIL import Image
from ..infrastructure.paths import data_root
from ..infrastructure.storage import save_json
from ..domain.tiles import normalize

DEFAULT_REGIONS = {
    "hand": [0.13, 0.82, 0.84, 0.999],
    "self": [0.393, 0.492, 0.615, 0.651],
    "left": [0.285, 0.264, 0.415, 0.515],
    "top": [0.414, 0.145, 0.586, 0.297],
    "right": [0.585, 0.266, 0.686, 0.518],
}


@dataclass
class Detection:
    seat: str
    box: tuple[int, int, int, int]
    crop: Image.Image
    tile: str = "?"
    similarity: float = 0.0
    suggestion: str = "?"
    sideways: bool = False


@dataclass
class Observation:
    image: Image.Image
    detections: list[Detection] = field(default_factory=list)
    source: str = "截图"

    def for_seat(self, seat: str) -> list[Detection]:
        return [d for d in self.detections if d.seat == seat]


def feature(image: Image.Image) -> np.ndarray:
    pixels = np.asarray(image.convert("RGB"))
    # Remove frame and retain ink color, normalizing the extent of the glyph.
    h, w = pixels.shape[:2]
    pixels = pixels[max(1, h // 12):h - max(1, h // 12), max(1, w // 12):w - max(1, w // 12)]
    minimum = pixels.min(axis=2)
    spread = pixels.max(axis=2).astype(float) - minimum
    ink = (minimum < 125) | ((spread > 85) & (minimum < 165))
    coords = cv2.findNonZero(ink.astype(np.uint8))
    if coords is None:
        return np.zeros((48, 32, 3), np.float32)
    x, y, width, height = cv2.boundingRect(coords)
    # Color channels: dark, red, green. Ring/calligraphy geometry remains spatial.
    r, g, b = [pixels[:, :, c].astype(float) for c in range(3)]
    colored = np.stack([ink & (spread < 55), ink & (r > g * 1.25) & (r > b * 1.2),
                        ink & (g > r * 1.15) & (g > b * 0.9)], axis=2).astype(np.float32)
    return cv2.resize(colored[y:y + height, x:x + width], (32, 48), interpolation=cv2.INTER_AREA)


class TemplateBank:
    def __init__(self, root: Path | None = None):
        self.root = root or data_root() / "templates"
        self.root.mkdir(parents=True, exist_ok=True)
        self.entries: list[tuple[str, np.ndarray]] = []
        self.reload()

    def reload(self):
        self.entries = []
        for path in sorted(self.root.glob("*/*.png")):
            try:
                normalize(path.parent.name)
                with Image.open(path) as im:
                    self.entries.append((path.parent.name, feature(im)))
            except (ValueError, OSError):
                continue

    @property
    def coverage(self) -> int:
        return len({normalize(tile) for tile, _ in self.entries})

    def add(self, image: Image.Image, tile: str):
        normalize(tile)
        folder = self.root / tile
        folder.mkdir(parents=True, exist_ok=True)
        image.save(folder / f"{uuid.uuid4().hex[:12]}.png")
        self.entries.append((tile, feature(image)))

    def classify(self, image: Image.Image) -> tuple[str, float, str]:
        if not self.entries:
            return "?", 0.0, "?"
        features = [feature(image), feature(image.rotate(180))]
        best_by_tile = {}
        for tile, reference in self.entries:
            if normalize(tile) == "5z" and np.linalg.norm(reference) < .1:
                best_by_tile[tile] = 1.0 if np.linalg.norm(features[0]) < .1 else 0.0
                continue
            score = max(float((candidate * reference).sum() /
                              max(1e-6, np.linalg.norm(candidate) * np.linalg.norm(reference)))
                        for candidate in features)
            best_by_tile[tile] = max(best_by_tile.get(tile, 0.0), score)
        ranking = sorted(best_by_tile.items(), key=lambda item: -item[1])
        best, score = ranking[0]
        alternative = next((s for t, s in ranking[1:] if normalize(t) != normalize(best)), 0.0)
        accepted = score >= 0.83 and score - alternative >= 0.055
        return (best if accepted else "?"), score, best


class Recognizer:
    def __init__(self, bank: TemplateBank | None = None):
        self.bank = bank or TemplateBank()
        self.profiles = {"window": {k: list(v) for k,v in DEFAULT_REGIONS.items()},
                         "image": {k: list(v) for k,v in DEFAULT_REGIONS.items()},
                         "video": {k: list(v) for k,v in DEFAULT_REGIONS.items()}}
        self.profiles["video"]["hand"] = [.13, .82, .76, .999]
        self.profile = "image"
        self.regions = self.profiles[self.profile]
        path = data_root() / "config" / "regions.json"
        if path.exists():
            try:
                profiles = json.loads(path.read_text(encoding="utf-8"))
                for name, regions in profiles.items():
                    if name not in self.profiles or not isinstance(regions, dict):
                        continue
                    for key, value in regions.items():
                        if key in self.regions and len(value) == 4 and all(0 <= n <= 1 for n in value) and value[0] < value[2] and value[1] < value[3]:
                            self.profiles[name][key] = value
            except (ValueError, TypeError, AttributeError):
                pass

    def save_regions(self):
        self.profiles[self.profile] = self.regions
        save_json(data_root() / "config" / "regions.json", self.profiles)

    def use_profile(self, profile):
        self.profile = profile
        self.regions = self.profiles[profile]

    def read(self, image: Image.Image, source: str = "截图") -> Observation:
        # A bounded image size keeps continuous processing inexpensive.
        frame = image.convert("RGB")
        if frame.width > 1920:
            frame = frame.resize((1920, round(frame.height * 1920 / frame.width)), Image.Resampling.LANCZOS)
        pixels = np.asarray(frame)
        height, width = pixels.shape[:2]
        detections = []
        for seat, region in self.regions.items():
            x1, y1, x2, y2 = [round(v * (width if i % 2 == 0 else height)) for i, v in enumerate(region)]
            roi = pixels[y1:y2, x1:x2]
            if not roi.size:
                continue
            lo = roi.min(axis=2)
            diff = roi.max(axis=2).astype(np.int16) - lo
            mask = ((lo > 145) & (diff < 55)).astype(np.uint8) * 255
            # Do not close gaps: neighboring white faces have only thin dark seams.
            mask = cv2.erode(mask, np.ones((2, 2), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            found = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if not (width * .014 < w < width * .095 and height * .022 < h < height * .17):
                    continue
                if seat == "hand" and (w < width * .033 or h < height * .095):
                    continue
                if cv2.contourArea(cv2.convexHull(contour)) / (w * h) < .70 or not .3 < w / h < 3:
                    continue
                crop = frame.crop((x + x1, y + y1, x + x1 + w, y + y1 + h))
                if seat == "top":
                    crop = crop.rotate(180)
                elif seat == "left":
                    crop = crop.rotate(90, expand=True)
                elif seat == "right":
                    crop = crop.rotate(-90, expand=True)
                sideways = seat != "hand" and crop.width / crop.height > (1.5 if seat in ("self", "top") else 1.15)
                if sideways:
                    crop = crop.rotate(90, expand=True)
                tile, confidence, suggestion = self.bank.classify(crop)
                found.append(Detection(seat, (x+x1, y+y1, w, h), crop, tile, confidence, suggestion, sideways))
            # Table-relative order, approximate until event tracking is validated.
            if seat in ("hand", "self"):
                found.sort(key=lambda d: (round(d.box[1] / (height * .049)), d.box[0]))
            elif seat == "top":
                found.sort(key=lambda d: (-round(d.box[1] / (height * .037)), -d.box[0]))
            elif seat == "left":
                found.sort(key=lambda d: (-round(d.box[0] / (width * .033)), d.box[1]))
            else:
                found.sort(key=lambda d: (round(d.box[0] / (width * .033)), -d.box[1]))
            detections.extend(found)
        return Observation(frame, detections, source)
