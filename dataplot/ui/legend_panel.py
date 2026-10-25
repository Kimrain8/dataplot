from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from dataplot.core.encoding import ColorLegend


class ClickableLabel(QLabel):
    clicked = Signal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


class LegendPanel(QWidget):
    legendToggled = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(4)

    def clear(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

    def add_legend(self, series_name: str, legend: ColorLegend, hidden_categories: set[str]):
        block = QWidget()
        lay = QVBoxLayout(block)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)

        is_series_hidden = f"{series_name}||" in hidden_categories
        title = ClickableLabel(f"● {series_name}")
        title.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {'#aaa' if is_series_hidden else '#000'};")
        title.clicked.connect(lambda: self.legendToggled.emit(series_name, ""))
        lay.addWidget(title)

        if legend.kind == "categorical":
            for name, rgb in legend.entries[:40]:
                row = QHBoxLayout()
                row.setSpacing(4)
                
                is_cat_hidden = f"{series_name}||{name}" in hidden_categories or is_series_hidden
                # 核心修复：画布使用了 alpha=170 (约0.66)，图例也必须保持一致的透明度
                opacity = "0.2" if is_cat_hidden else "0.66"
                
                sw = QLabel()
                sw.setFixedSize(12, 12)
                sw.setStyleSheet(f"background: rgba({rgb[0]},{rgb[1]},{rgb[2]},{opacity}); border: 1px solid #333;")
                row.addWidget(sw)
                
                lbl = ClickableLabel(str(name))
                lbl.setStyleSheet(f"font-size: 11px; color: {'#aaa' if is_cat_hidden else '#000'};")
                lbl.clicked.connect(lambda n=name: self.legendToggled.emit(series_name, n))
                row.addWidget(lbl)
                
                row.addStretch()
                lay.addLayout(row)
        elif legend.kind == "continuous":
            grad = QLabel()
            grad.setFixedHeight(10)
            grad.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgb(60,130,220), stop:0.5 rgb(240,200,80), stop:1 rgb(220,70,70));")
            lay.addWidget(grad)
            
        self._layout.addWidget(block)

    def finalize(self):
        self._layout.addStretch()