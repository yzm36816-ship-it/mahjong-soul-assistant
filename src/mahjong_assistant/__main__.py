import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from .infrastructure.paths import data_root


def main():
    parser = argparse.ArgumentParser(description="雀魂麻将助手")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--smoke-output", type=Path, help="Render UI and exit for local QA")
    args = parser.parse_args()
    logs = data_root() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(logs / "application.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFontDatabase, QFont
    from .ui.main_window import MainWindow
    from .ui.theme import STYLE
    app = QApplication(sys.argv[:1])
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
    app.setApplicationName("雀魂麻将助手")
    app.setStyleSheet(STYLE)

    def exception_hook(kind, value, traceback):
        logging.error("Unhandled error", exc_info=(kind, value, traceback))
        QMessageBox.critical(None, "操作未完成", f"{value}\n详细信息已写入 data/logs/application.log。")

    sys.excepthook = exception_hook
    window = MainWindow()
    window.show()
    if args.image:
        QTimer.singleShot(100, lambda: window.open_image(args.image))
    elif args.video:
        QTimer.singleShot(100, lambda: window.open_video(args.video))
    if args.smoke_output:
        attempts = [0]
        def finish():
            attempts[0] += 1
            if window.busy and attempts[0] < 30:
                QTimer.singleShot(500, finish)
                return
            args.smoke_output.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(args.smoke_output))
            window.close()
            app.quit()
        QTimer.singleShot(2500, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
