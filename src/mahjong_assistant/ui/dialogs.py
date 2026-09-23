from collections import Counter
from dataclasses import replace
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QCheckBox, QPushButton, QMessageBox, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea, QWidget, QFormLayout, QTabWidget)
from ..domain.models import Board, Opponent, SEAT_NAMES, seat_name
from ..domain.tiles import ALL_TILES, label, parse_tiles, normalize


def pixmap(image):
    return QPixmap.fromImage(ImageQt(image.convert("RGBA")))


class BoardDialog(QDialog):
    def __init__(self, board, parent=None):
        super().__init__(parent)
        self.setWindowTitle("牌局校对 · 当前这一局")
        self.resize(620, 510)
        self.original = board
        self.result_board = None
        layout = QVBoxLayout(self)
        tip = QLabel("对照游戏校对后再确认。立直和副露需要你填写。\n输入示例：123m456p789s东白；m=万，p=筒，s=索。\n未识别的牌未填入，必须补齐；新一局请点主界面的“新一局”。")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        form = QFormLayout()
        self.hand = QLineEdit(" ".join(board.hand))
        form.addRow("你的手牌", self.hand)
        self.fields = []
        opponents = board.opponents or [Opponent(s) for s in ("left", "top", "right") if board.mode != 3 or s != "left"]
        for opponent in opponents:
            river = QLineEdit(" ".join(opponent.discards))
            form.addRow(seat_name(opponent.seat, board.mode) + "舍牌", river)
            options = QHBoxLayout()
            melds = QSpinBox()
            melds.setRange(0, 4)
            melds.setValue(opponent.melds)
            riichi = QCheckBox("我已确认该家立直")
            riichi.setChecked(opponent.riichi)
            options.addWidget(QLabel("副露组数"))
            options.addWidget(melds)
            options.addWidget(riichi)
            options.addStretch()
            form.addRow("", options)
            self.fields.append((opponent.seat, river, melds, riichi))
        layout.addLayout(form)
        layout.addStretch()
        button = QPushButton("确认当前牌局并更新分析")
        button.setObjectName("primary")
        button.clicked.connect(self.commit)
        layout.addWidget(button)

    def commit(self):
        try:
            hand = parse_tiles(self.hand.text(), self.original.mode)
            if not 1 <= len(hand) <= 14:
                raise ValueError("手牌必须为 1–14 张；有副露时只填写未副露的手牌。")
            opponents = []
            for seat, river, melds, riichi in self.fields:
                discards = parse_tiles(river.text(), self.original.mode)
                if len(discards) > 30:
                    raise ValueError("牌河数量异常，请重新检查。")
                if riichi.isChecked() and melds.value():
                    raise ValueError("已副露的手牌不能立直。这里的副露组数不包含暗杠。")
                opponents.append(Opponent(seat, discards, melds.value(), riichi.isChecked(), True))
            known = hand + [t for o in opponents for t in o.discards]
            if any(n > 4 for n in Counter(normalize(t) for t in known).values()):
                raise ValueError("手牌与三家当前牌河中，同一种牌合计超过四张。")
            self.result_board = Board(self.original.mode, hand, opponents, self.original.source,
                                      True, True, ["人工确认的当前快照；画面变化后相关确认会失效。", "等待牌未知；风险等级为规则提示，不是概率。"])
            self.accept()
        except ValueError as error:
            QMessageBox.warning(self, "请检查牌局", str(error))


class SamplesDialog(QDialog):
    def __init__(self, observation, bank, parent=None):
        super().__init__(parent)
        self.setWindowTitle("牌面校对与样本库")
        self.resize(760, 630)
        self.observation, self.bank = observation, bank
        layout = QVBoxLayout(self)
        info = QLabel("逐张检查裁剪牌面。勾选你能确认的牌并选择正确名称，再保存为本地样本。\n合并了多张牌、被截断或遮挡的裁剪不要保存。匹配值不是正确率。")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.table = QTableWidget(len(observation.detections), 5)
        self.table.setHorizontalHeaderLabels(["确认", "位置", "裁剪牌面", "正确牌名", "匹配值"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fields = []
        for row, detection in enumerate(observation.detections):
            check = QCheckBox()
            self.table.setCellWidget(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem({"hand": "手牌", "self": "自己牌河", **SEAT_NAMES}[detection.seat]))
            picture = QLabel()
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            picture.setPixmap(pixmap(detection.crop).scaled(60, 76, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.table.setCellWidget(row, 2, picture)
            choice = QComboBox()
            choice.addItem("请选择", "?")
            for tile in (*ALL_TILES, "0m", "0p", "0s"):
                choice.addItem(label(tile), tile)
            choice.setCurrentIndex(max(0, choice.findData(detection.tile)))
            self.table.setCellWidget(row, 3, choice)
            self.table.setItem(row, 4, QTableWidgetItem(f"{detection.similarity:.2f}"))
            self.table.setRowHeight(row, 88)
            self.fields.append((check, choice, detection))
        layout.addWidget(self.table)
        save = QPushButton("保存勾选的正确样本")
        save.setObjectName("primary")
        save.clicked.connect(self.commit)
        layout.addWidget(save)

    def commit(self):
        selected = [(choice, detection) for check, choice, detection in self.fields if check.isChecked()]
        if not selected or any(choice.currentData() == "?" for choice, _ in selected):
            QMessageBox.warning(self, "请选择", "请勾选要保存的牌，并为每张选择正确名称。")
            return
        for choice, detection in selected:
            tile = choice.currentData()
            self.bank.add(detection.crop, tile)
            detection.tile = tile
            detection.similarity = 1.0
        self.accept()


class RegionCanvas(QLabel):
    def __init__(self, image, regions, parent=None):
        super().__init__(parent)
        self.regions = {k: list(v) for k, v in regions.items()}
        self.current = "hand"
        self.start = None
        self.drag = None
        self.setPixmap(pixmap(image).scaled(1000, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.setFixedSize(self.pixmap().size())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.start is not None:
            self.drag = QRect(self.start, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start is not None:
            rect = QRect(self.start, event.position().toPoint()).normalized().intersected(self.rect())
            if rect.width() > 15 and rect.height() > 15:
                self.regions[self.current] = [rect.left()/self.width(), rect.top()/self.height(), rect.right()/self.width(), rect.bottom()/self.height()]
            self.start = self.drag = None
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        for key, values in self.regions.items():
            painter.setPen(QPen(QColor("#65efc3" if key == self.current else "#ffcd78"), 2))
            x1, y1, x2, y2 = values
            rectangle = QRect(round(x1*self.width()), round(y1*self.height()), round((x2-x1)*self.width()), round((y2-y1)*self.height()))
            painter.drawRect(rectangle)
            painter.drawText(rectangle.topLeft()+QPoint(3, 16), {"hand": "手牌", "self": "自己牌河", **SEAT_NAMES}[key])
        if self.drag:
            painter.setPen(QPen(QColor("white"), 2))
            painter.drawRect(self.drag)


class RegionsDialog(QDialog):
    def __init__(self, observation, recognizer, parent=None):
        super().__init__(parent)
        self.setWindowTitle("识别区域校准")
        self.recognizer = recognizer
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("选择区域，再在图上拖出矩形。框住完整牌河，避开头像、中央计分板和副露。"))
        choice = QComboBox()
        for key, name in {"hand": "我的手牌", "self": "我的牌河", **SEAT_NAMES}.items():
            choice.addItem(name, key)
        layout.addWidget(choice)
        self.canvas = RegionCanvas(observation.image, recognizer.regions)
        layout.addWidget(self.canvas)
        choice.currentIndexChanged.connect(lambda: self.select(choice.currentData()))
        save = QPushButton("保存区域并重新识别")
        save.setObjectName("primary")
        save.clicked.connect(self.commit)
        layout.addWidget(save)

    def select(self, key):
        self.canvas.current = key
        self.canvas.update()

    def commit(self):
        self.recognizer.regions = self.canvas.regions
        self.recognizer.save_regions()
        self.accept()


class RiskDialog(QDialog):
    def __init__(self, assessment, parent=None):
        super().__init__(parent)
        mode = parent.session.mode if parent is not None else 4
        self.setWindowTitle(seat_name(assessment.seat, mode) + " · 风险依据")
        self.resize(710, 500)
        layout = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        tabs = QTabWidget()
        self.risks = QTableWidget(0, 3)
        self.risks.setHorizontalHeaderLabels(["你的牌", "风险类别", "判断依据"])
        self.risks.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.risks, "手中牌风险")
        self.waits = QTableWidget(0, 2)
        self.waits.setHorizontalHeaderLabels(["候选牌", "尚未排除的等待形状"])
        self.waits.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self.waits, "立直等待候选")
        layout.addWidget(tabs)
        note = QLabel("等待候选在立直或疑似立直时列出，仅检查局部牌型与可见牌约束，不是完整手牌还原或概率排名。自动识别可能出错；现物仅针对该家的荣和。")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.update_assessment(assessment)

    def update_assessment(self, assessment):
        self.title.setText(assessment.status + "\n" + assessment.detail)
        self.risks.setRowCount(len(assessment.risks))
        for row, risk in enumerate(assessment.risks):
            for col, text in enumerate((label(risk.tile), risk.level, risk.reason)):
                self.risks.setItem(row, col, QTableWidgetItem(text))
            self.risks.setRowHeight(row, 64)
        self.waits.setRowCount(len(assessment.waits))
        for row, candidate in enumerate(assessment.waits):
            self.waits.setItem(row, 0, QTableWidgetItem(label(candidate.tile)))
            self.waits.setItem(row, 1, QTableWidgetItem("；".join(candidate.shapes)))
            self.waits.setRowHeight(row, 58)
