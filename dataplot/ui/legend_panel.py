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

        for name, rgb in legend.entries:
            row = QHBoxLayout()
            row.setSpacing(4)
            
            is_cat_hidden = f"{series_name}||{name}" in hidden_categories or is_series_hidden
            
            sw = QLabel()
            sw.setFixedSize(12, 12)
            if is_cat_hidden:
                sw.setStyleSheet("background-color: #d1d5db; border: 1px solid #999;")
            else:
                r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
                sw.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #333;")
                
            row.addWidget(sw)
            
            lbl = ClickableLabel(str(name))
            lbl.setStyleSheet(f"font-size: 11px; color: {'#aaa' if is_cat_hidden else '#000'};")
            lbl.clicked.connect(lambda n=name: self.legendToggled.emit(series_name, n))
            row.addWidget(lbl)
            
            row.addStretch()
            lay.addLayout(row)
            
        self._layout.addWidget(block)

    def finalize(self):
        self._layout.addStretch()