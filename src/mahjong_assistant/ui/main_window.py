from datetime import datetime
from pathlib import Path
import time
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QFrame, QFileDialog, QMessageBox,
    QScrollArea, QDialog)
from ..application.session import Session
from ..application.prediction import predictions_for_session
from ..domain.analysis import assess
from ..domain.models import Opponent, Assessment, SEAT_NAMES, seat_name
from ..domain.tiles import label, normalize
from ..infrastructure.windows import game_windows, capture
from ..infrastructure.storage import History
from ..infrastructure.paths import data_root
from ..ml.model import ModelRegistry
from ..vision.recognizer import Recognizer
from .dialogs import BoardDialog, SamplesDialog, RegionsDialog, RiskDialog, pixmap


class ReadWorker(QThread):
    ready = Signal(object, float)
    failed = Signal(str)

    def __init__(self, recognizer, image=None, handle=None, source="截图", video=None, second=0):
        super().__init__()
        self.recognizer, self.image, self.handle, self.source = recognizer, image, handle, source
        self.video, self.second = video, second

    def run(self):
        try:
            started = time.perf_counter()
            image = self.image
            if self.video is not None:
                import cv2
                reader = cv2.VideoCapture(str(self.video))
                try:
                    reader.set(cv2.CAP_PROP_POS_MSEC, self.second * 1000)
                    ok, pixels = reader.read()
                    if not ok:
                        raise RuntimeError("视频已结束，或此位置没有可读取的画面。")
                    image = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
                finally:
                    reader.release()
            elif self.handle is not None:
                image = capture(self.handle)
            if image is None:
                raise RuntimeError("请先选择游戏窗口或导入截图。")
            observation = self.recognizer.read(image, self.source)
            self.ready.emit(observation, time.perf_counter() - started)
        except Exception as error:
            self.failed.emit(str(error))


def text_label(text, name=None, wrap=False):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def panel():
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(7)
    return frame, layout


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("雀魂麻将助手 · 0.3 实验版")
        self.resize(438, 820)
        self.setMinimumSize(400, 620)
        self.recognizer = Recognizer()
        self.session = Session()
        self.model_registry = ModelRegistry(data_root() / "models")
        self.predictions = {}
        self.history = History()
        self.worker = None
        self.last_image = None
        self.busy = False
        self.video_path = None
        self.video_second = 0
        self.video_duration = 0
        self.active_handle = None
        self.source_kind = "window"
        self.preview_dialog = None
        self.preview_label = None
        self.failures = 0
        self.risk_dialogs = {}
        self.actions = []
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)
        self.build()
        self.refresh_windows()
        self.render()

    def button(self, text, callback, primary=False):
        button = QPushButton(text)
        if primary:
            button.setObjectName("primary")
        button.clicked.connect(callback)
        self.actions.append(button)
        return button

    def build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(12)
        header = QHBoxLayout()
        logo = text_label("雀", "logo")
        logo.setFixedSize(46, 46)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(text_label("雀魂助手", "title"))
        titles.addWidget(text_label("LIVE COMPANION  /  0.3", "eyebrow"))
        header.addLayout(titles)
        header.addStretch()
        self.pin = QCheckBox("置顶")
        self.pin.toggled.connect(self.toggle_pin)
        header.addWidget(self.pin)
        root.addLayout(header)
        self.status = text_label("● 本地运行 · 等待画面", "status")
        root.addWidget(self.status)

        connection, box = panel()
        row = QHBoxLayout()
        self.windows = QComboBox()
        self.windows.setMinimumWidth(140)
        row.addWidget(self.windows, 1)
        self.refresh = self.button("刷新", self.refresh_windows)
        row.addWidget(self.refresh)
        self.mode = QComboBox()
        self.mode.addItem("四麻", 4)
        self.mode.addItem("三麻", 3)
        self.mode.currentIndexChanged.connect(self.change_mode)
        row.addWidget(self.mode)
        box.addLayout(row)
        controls = QHBoxLayout()
        self.once = self.button("读取一次", self.read_window)
        controls.addWidget(self.once)
        self.live = self.button("开始实时监控", self.toggle_live, True)
        controls.addWidget(self.live)
        box.addLayout(controls)
        self.source_info = text_label("只读取所选游戏窗口 · 数据保存在本机", "muted", True)
        box.addWidget(self.source_info)
        self.capture_preview = QLabel("监控画面将在这里更新")
        self.capture_preview.setFixedHeight(90)
        self.capture_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.capture_preview.setVisible(False)
        box.addWidget(self.capture_preview)
        preview_button = self.button("查看实时监控画面 ↗", self.show_preview)
        preview_button.setObjectName("subtle")
        box.addWidget(preview_button)
        root.addWidget(connection)

        hand_panel, box = panel()
        hand_header = QHBoxLayout()
        hand_header.addWidget(text_label("我的手牌"))
        hand_header.addStretch()
        self.hand_status = text_label("等待识别", "muted")
        hand_header.addWidget(self.hand_status)
        box.addLayout(hand_header)
        self.hand_widget = QWidget()
        self.hand_grid = QGridLayout(self.hand_widget)
        self.hand_grid.setContentsMargins(0, 0, 0, 0)
        self.hand_grid.setSpacing(4)
        box.addWidget(self.hand_widget)
        root.addWidget(hand_panel)

        heading = QHBoxLayout()
        heading.addWidget(text_label("对手观察"))
        heading.addStretch()
        heading.addWidget(text_label("规则提示 · 非概率预测", "muted"))
        root.addLayout(heading)
        self.cards = {}
        for seat in ("left", "top", "right"):
            card, box = panel()
            row = QHBoxLayout()
            name = text_label(SEAT_NAMES[seat])
            name.setObjectName("seatName")
            name.setStyleSheet("font-weight: 700; font-size: 14px;")
            row.addWidget(name)
            row.addStretch()
            state = text_label("等待牌局", "status")
            row.addWidget(state)
            box.addLayout(row)
            detail = text_label("读取画面或导入截图后显示。", "muted", True)
            box.addWidget(detail)
            risk = text_label("", "warning", True)
            box.addWidget(risk)
            footer = QHBoxLayout()
            count = text_label("—", "muted")
            footer.addWidget(count)
            footer.addStretch()
            more = self.button("查看依据 →", lambda _=False, s=seat: self.show_risks(s))
            more.setObjectName("subtle")
            footer.addWidget(more)
            box.addLayout(footer)
            root.addWidget(card)
            self.cards[seat] = (card, state, detail, risk, count)

        tools = QGridLayout()
        for i, (title, handler) in enumerate([
            ("校对牌局", self.edit_board), ("牌面样本", self.edit_samples), ("校准区域", self.edit_regions),
            ("导入截图", self.import_image), ("导入视频", self.import_video), ("下一秒", self.next_video),
            ("截图示例", self.load_sample), ("导出记录", self.export_history), ("新一局", self.reset_session),
        ]):
            button = self.button(title, handler)
            tools.addWidget(button, i//3, i%3)
        root.addLayout(tools)
        self.warning = text_label("", "warning", True)
        root.addWidget(self.warning)
        self.metrics = text_label("", "muted", True)
        root.addWidget(self.metrics)
        root.addStretch()

    def toggle_pin(self, enabled):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()

    def refresh_windows(self):
        selected = self.windows.currentData()
        self.windows.clear()
        for window in game_windows():
            self.windows.addItem(window.title, window.handle)
        if self.windows.count() == 0:
            self.windows.addItem("未找到雀魂游戏窗口", None)
        elif self.windows.findData(selected) >= 0:
            self.windows.setCurrentIndex(self.windows.findData(selected))

    def change_mode(self):
        self.stop_live()
        self.session = Session(self.mode.currentData())
        self.predictions = {}
        if self.last_image is not None:
            self.begin(image=self.last_image, source="模式切换后的画面")
        else:
            self.render()

    def set_busy(self, busy):
        self.busy = busy
        for action in self.actions:
            action.setEnabled(not busy)
        self.mode.setEnabled(not busy)
        self.windows.setEnabled(not busy)
        # A long read must never disable the user's stop button.
        self.live.setEnabled(not busy or self.timer.isActive())

    def begin(self, **kwargs):
        if self.busy:
            return
        self.set_busy(True)
        if not self.timer.isActive():
            self.status.setText("● 正在读取与识别…")
        self.worker = ReadWorker(self.recognizer, **kwargs)
        self.worker.ready.connect(self.on_observation)
        self.worker.failed.connect(self.on_failure)
        self.worker.finished.connect(self.read_finished)
        self.worker.start()

    def read_finished(self):
        self.set_busy(False)
        if not self.timer.isActive() or self.failures:
            from ..infrastructure.gpu_capture import stop
            stop()

    def tick(self):
        if self.busy:
            return
        if self.source_kind == "video":
            if self.video_second + .5 >= self.video_duration:
                self.stop_live()
                self.status.setText("● 视频监控结束")
                return
            self.video_second += .5
            self.read_video_frame()
        else:
            self.read_window()

    def read_window(self):
        if self.busy:
            return
        handle = self.windows.currentData()
        if handle is None:
            if self.timer.isActive():
                self.refresh_windows()
                handle = self.windows.currentData()
            if handle is None:
                self.status.setText("● 等待雀魂窗口 · 自动重连" if self.timer.isActive() else "● 未连接 · 请打开游戏后刷新")
                return
        if self.active_handle != handle or self.video_path is not None or self.session.board.source != "Steam 游戏窗口":
            self.session.reset()
            self.predictions = {}
        self.active_handle = handle
        self.source_kind = "window"
        self.video_path = None
        self.recognizer.use_profile("window")
        self.begin(handle=handle, source="Steam 游戏窗口")

    def toggle_live(self):
        if self.timer.isActive():
            self.stop_live()
            self.status.setText("● 已暂停 · 显示最后一次快照")
        elif self.video_path is not None:
            self.source_kind = "video"
            self.timer.start()
            self.live.setText("暂停视频监控")
        elif self.windows.currentData() is None:
            self.source_kind = "window"
            self.timer.start()
            self.live.setText("停止等待窗口")
            self.status.setText("● 等待雀魂窗口 · 自动重连")
        else:
            self.timer.start()
            self.live.setText("暂停实时监控")
            self.read_window()

    def stop_live(self):
        self.timer.stop()
        self.live.setText("开始实时监控")
        if not self.busy:
            from ..infrastructure.gpu_capture import stop
            stop()

    def on_observation(self, observation, elapsed):
        self.last_image = observation.image
        self.failures = 0
        changed = self.session.update(observation, require_stability=self.source_kind != "image")
        self.predictions = predictions_for_session(self.session, self.model_registry)
        if self.session.recent_events:
            self.history.record_events(self.session.recent_events)
        if changed:
            self.history.record(self.session.board, self.session.tracker.session_id)
        self.status.setText(f"● {'实时监控' if self.timer.isActive() else '当前画面'} · {datetime.now():%H:%M:%S} · 第 {self.session.frames} 帧 · {elapsed:.1f}s")
        self.source_info.setText(observation.source)
        self.update_preview()
        self.render()

    def on_failure(self, message):
        self.failures += 1
        # Retain pixels for diagnosis but discard actionable analysis on capture failure.
        self.session.reset()
        self.predictions = {}
        self.render()
        self.status.setText("● 等待有效游戏画面 · 自动重试" if self.timer.isActive() else "● 读取失败 · 分析已清空")
        self.capture_preview.clear()
        self.capture_preview.setText("暂时没有有效画面")
        self.warning.setText(message)

    def update_preview(self):
        picture = pixmap(self.last_image)
        self.capture_preview.setPixmap(picture.scaled(350, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        if self.preview_label is not None and self.preview_dialog is not None and self.preview_dialog.isVisible():
            self.preview_label.setPixmap(picture.scaled(1000, 660, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def show_preview(self):
        # Modeless: inspecting the feed must not pause capture or analysis.
        if self.preview_dialog is None:
            self.preview_dialog = QDialog(self)
            self.preview_dialog.setWindowTitle("实时监控画面 · 与小窗口同步更新")
            layout = QVBoxLayout(self.preview_dialog)
            self.preview_label = QLabel("等待读取游戏画面")
            layout.addWidget(self.preview_label)
        self.preview_dialog.show()
        if self.last_image is not None:
            self.update_preview()

    def render(self):
        board = self.session.board
        while self.hand_grid.count():
            item = self.hand_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        tiles = board.hand
        if self.session.observation is not None and not board.hand_confirmed:
            tiles = [d.tile for d in self.session.observation.for_seat("hand")]
        if not tiles:
            self.hand_grid.addWidget(text_label("读取游戏画面，或先体验截图示例。", "muted", True), 0, 0, 1, 7)
        for index, tile in enumerate(tiles[:28]):
            chip = text_label(label(tile), "tile")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setMinimumSize(29, 34)
            self.hand_grid.addWidget(chip, index//10, index%10)
        self.hand_status.setText(f"{len(tiles)} 张 · {'人工确认' if board.hand_confirmed else '自动识别' if board.auto_hand_ready else '识别中'}")
        assessments = {a.seat: a for a in assess(board)}
        for seat, dialog in self.risk_dialogs.items():
            if seat in assessments:
                dialog.update_assessment(assessments[seat])
            else:
                dialog.update_assessment(Assessment(seat, "等待新画面", "旧分析已清空。"))
        for seat, (card, state, detail, risk, count) in self.cards.items():
            card.findChild(QLabel, "seatName").setText(seat_name(seat, board.mode))
            card.setVisible(not (board.mode == 3 and seat == "left"))
            assessment = assessments.get(seat)
            if assessment is None:
                state.setText("等待牌局")
                detail.setText("读取画面后，校对该家牌河与立直状态。")
                risk.setText("")
                count.setText("—")
                continue
            state.setText(assessment.status)
            state.setStyleSheet("color: #ffbd8b;" if "立直" in assessment.status else "color: #8ee1c8;")
            detail.setText(assessment.detail)
            prediction = self.predictions.get(seat)
            if prediction is not None:
                detail.setText(assessment.detail + f"\n独立验证模型：听牌估计 {prediction.tenpai_probability:.0%}（{prediction.model_version}）")
            opponent = next(o for o in board.opponents if o.seat == seat)
            count.setText(f"舍牌 {len(opponent.discards) + opponent.unknown_count} · 待认 {opponent.unknown_count} · 副露 {opponent.melds if opponent.confirmed else '?'}")
            if not board.hand_confirmed and not board.auto_hand_ready:
                risk.setText("等待稳定手牌画面，随后自动更新风险")
            elif not opponent.confirmed and not opponent.auto_observed:
                risk.setText("该家牌河识别中，等待稳定结果")
            else:
                danger = [label(r.tile) for r in assessment.risks if r.score >= 55][:5]
                safe = [label(r.tile) for r in assessment.risks if r.level in ("现物", "识别现物")][:5]
                risk.setText(("警戒：" + "  ".join(danger) if danger else "仍有未排除的等待") +
                             ("\n" + ("该家现物：" if opponent.confirmed else "识别现物：") + "  ".join(safe) if safe else "\n暂未找到该家现物"))
                if assessment.waits:
                    own_waits = [label(w.tile) for w in assessment.waits if w.tile in {normalize(t) for t in board.hand}]
                    risk.setText(risk.text() + "\n等待候选（手中）：" + (" ".join(own_waits) or "见详情"))
                if prediction is not None and prediction.waits:
                    top_waits = sorted(prediction.waits.items(), key=lambda item: -item[1])[:3]
                    risk.setText(risk.text() + "\n模型等待前列：" + "  ".join(f"{label(tile)} {probability:.0%}" for tile, probability in top_waits))
                    own_risk = [(tile, prediction.ron.get(normalize(tile), 0.0)) for tile in board.hand]
                    own_risk = sorted(own_risk, key=lambda item: -item[1])[:3]
                    risk.setText(risk.text() + "\n手中荣和风险：" + "  ".join(f"{label(tile)} {probability:.0%}" for tile, probability in own_risk))
        self.warning.setText("\n".join(board.warnings[:3]) if board.warnings else "先校对，再参考分析。实际等待牌无法由公开画面确定。")
        self.metrics.setText(f"事件追踪：{self.session.tracker.reason} · {self.session.frames} 帧 / {self.session.changes} 次变化\n规则提示不是模型概率；识别不完整时暂停预测。API 费用 ¥0")

    def import_image(self):
        self.stop_live()
        path, _ = QFileDialog.getOpenFileName(self, "选择雀魂截图", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.open_image(Path(path))

    def open_image(self, path):
        self.stop_live()
        self.session.reset()
        self.predictions = {}
        self.video_path = None
        self.source_kind = "image"
        self.recognizer.use_profile("image")
        try:
            with Image.open(path) as image:
                frame = image.convert("RGB")
            self.begin(image=frame, source=f"截图 · {path.name}")
        except OSError as error:
            self.on_failure(str(error))

    def load_sample(self):
        path = data_root() / "samples" / "sample-2.png"
        if path.exists():
            self.open_image(path)
        else:
            QMessageBox.information(self, "暂无示例", "请使用“导入截图”选择你自己的截图。")

    def import_video(self):
        self.stop_live()
        path, _ = QFileDialog.getOpenFileName(self, "选择本地雀魂视频", "", "视频 (*.mp4 *.mkv *.avi *.mov)")
        if path:
            self.open_video(Path(path))

    def open_video(self, path):
        self.stop_live()
        import cv2
        reader = cv2.VideoCapture(str(path))
        fps = reader.get(cv2.CAP_PROP_FPS)
        count = reader.get(cv2.CAP_PROP_FRAME_COUNT)
        reader.release()
        if fps <= 0 or count <= 0:
            self.on_failure("无法读取此视频。")
            return
        self.session.reset()
        self.predictions = {}
        self.source_kind = "video"
        self.recognizer.use_profile("video")
        self.video_path, self.video_duration, self.video_second = path, count/fps, 0
        self.read_video_frame()

    def read_video_frame(self):
        self.begin(video=self.video_path, second=self.video_second,
                   source=f"视频 · {self.video_path.name} · {self.video_second:.1f}/{self.video_duration:.1f}s")

    def next_video(self):
        if self.video_path is None:
            QMessageBox.information(self, "视频模式", "先导入视频，再逐秒检查牌面变化。")
            return
        if self.video_second + 1 >= self.video_duration:
            self.status.setText("● 视频已到结尾")
            return
        self.video_second += 1
        self.read_video_frame()

    def edit_board(self):
        self.stop_live()
        dialog = BoardDialog(self.session.board, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.confirm(dialog.result_board)
            self.predictions = {}
            self.history.record(self.session.board, self.session.tracker.session_id)
            self.history.record_events(self.session.recent_events)
            self.status.setText("● 人工校对完成 · 当前快照")
            self.render()

    def edit_samples(self):
        self.stop_live()
        if self.session.observation is None:
            QMessageBox.information(self, "需要画面", "请先读取窗口、导入截图或视频。")
            return
        dialog = SamplesDialog(self.session.observation, self.recognizer.bank, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.reset()
            self.predictions = {}
            self.begin(image=self.last_image, source="校正样本后的画面")

    def edit_regions(self):
        self.stop_live()
        if self.session.observation is None:
            QMessageBox.information(self, "需要画面", "请先读取窗口、导入截图或视频。")
            return
        dialog = RegionsDialog(self.session.observation, self.recognizer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.session.reset()
            self.predictions = {}
            self.begin(image=self.last_image, source="校准后的画面")

    def show_risks(self, seat):
        assessment = next((a for a in assess(self.session.board) if a.seat == seat), None)
        if assessment:
            if seat in self.risk_dialogs:
                self.risk_dialogs[seat].show()
                return
            dialog = RiskDialog(assessment, self)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.risk_dialogs[seat] = dialog
            dialog.destroyed.connect(lambda _=None, s=seat: self.risk_dialogs.pop(s, None))
            dialog.show()

    def export_history(self):
        self.stop_live()
        path, _ = QFileDialog.getSaveFileName(self, "导出本地记录", str(data_root() / "sessions" / "牌局记录.json"), "JSON (*.json)")
        if path:
            self.history.export(Path(path))
            self.status.setText("● 记录已导出")

    def reset_session(self):
        self.stop_live()
        self.session.reset()
        self.predictions = {}
        self.last_image = None
        self.video_path = None
        self.status.setText("● 新一局 · 上局确认已清空")
        self.render()

    def closeEvent(self, event):
        self.stop_live()
        if self.worker and self.worker.isRunning():
            self.status.setText("● 正在读取，请完成后关闭")
            event.ignore()
            return
        event.accept()
