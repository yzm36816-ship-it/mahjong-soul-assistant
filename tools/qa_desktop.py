"""Exercise actual Windows HWND capture against a dedicated fixture window.

Does not capture the desktop or any existing user window.
"""
import json
from pathlib import Path
from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QLabel
from mahjong_assistant.infrastructure.paths import data_root, project_root
from mahjong_assistant.infrastructure.windows import capture, game_windows
from mahjong_assistant.vision.recognizer import Recognizer

app = QApplication([])
fixture = QLabel()
fixture.setWindowTitle("雀魂 Capture QA Fixture")
image = Image.open(data_root()/"samples"/"sample-2.png")
image.thumbnail((1280, 720))
fixture.setPixmap(QPixmap.fromImage(ImageQt(image)))
fixture.show()
result = {}


def check():
    try:
        handle = int(fixture.winId())
        result["enumerated_fixture"] = handle in {w.handle for w in game_windows()}
        captured = capture(handle)
        result["captured_size"] = captured.size
        result["detected_tiles"] = len(Recognizer().read(captured).detections)
        captured.save(project_root()/"artifacts"/"window-capture-qa.png")
        result["ok"] = result["enumerated_fixture"] and result["detected_tiles"] > 20
    except Exception as error:
        result["ok"] = False
        result["error"] = str(error)
    finally:
        (project_root()/"artifacts"/"window-capture-qa.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        fixture.close()
        app.quit()


QTimer.singleShot(700, check)
app.exec()
print(json.dumps(result))
raise SystemExit(0 if result.get("ok") else 1)
