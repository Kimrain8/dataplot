from PySide6.QtGui import QFont
from PySide6.QtCore import Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget, QLabel, QSizePolicy, QLineEdit
)

from dataplot.core.spec import AxisSlot, ChartType, SeriesSpec, AggType, ColorTheme
from dataplot.ui.drop_combo import DropComboBox


class SeriesRow(QWidget):
    changed = Signal()
    removed = Signal(object)

    def __init__(self, spec: SeriesSpec, fields: list[str], parent=None):
        super().__init__(parent)
        self.spec = spec

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        
        # 第一行：Y字段(2)，类型(1)，轴(1)
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        
        self.y_combo = DropComboBox("Y", fields)
        if spec.y: self.y_combo.set_field(spec.y)
        self.y_combo.fieldDropped.connect(self._on_y)
        row1.addWidget(self.y_combo, 2)

        self.type_combo = QComboBox()
        for ct in ChartType:
            self.type_combo.addItem(ct.value, ct)
        self.type_combo.setCurrentText(spec.chart_type.value)
        self.type_combo.currentIndexChanged.connect(self._on_type)
        row1.addWidget(self.type_combo, 1)

        self.axis_combo = QComboBox()
        for ax in AxisSlot:
            self.axis_combo.addItem(ax.value, ax)
        self.axis_combo.setCurrentText(spec.axis.value)
        self.axis_combo.currentIndexChanged.connect(self._on_axis)
        row1.addWidget(self.axis_combo, 1)
        
        main_layout.addLayout(row1)
        
        # 第二行：桶(1)，聚合(1)，颜色(2)，色系(1)
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        row2.addWidget(QLabel("桶:"))
        
        # 核心修复：用 QLineEdit 替代 QDoubleSpinBox，彻底杜绝白底白字和乱码
        self.bin_input = QLineEdit()
        self.bin_input.setPlaceholderText("0")
        self.bin_input.setText(str(spec.bin_width))
        self.bin_input.setValidator(QDoubleValidator(0.0, 999999.0, 2, self.bin_input))
        self.bin_input.setToolTip("X轴分桶大小，0为不分桶")
        self.bin_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.bin_input.editingFinished.connect(self._on_bin_changed)
        row2.addWidget(self.bin_input, 1)

        self.agg_combo = QComboBox()
        for at in AggType:
            self.agg_combo.addItem(at.value, at)
        self.agg_combo.setCurrentText(spec.agg.value)
        self.agg_combo.currentIndexChanged.connect(self._on_agg)
        row2.addWidget(self.agg_combo, 1)

        self.color_combo = DropComboBox("颜色", fields)
        if spec.color: self.color_combo.set_field(spec.color)
        self.color_combo.fieldDropped.connect(self._on_color)
        row2.addWidget(self.color_combo, 2)

        self.theme_combo = QComboBox()
        for ct in ColorTheme:
            self.theme_combo.addItem(ct.value, ct)
        self.theme_combo.setCurrentText(spec.color_theme.value)
        self.theme_combo.currentIndexChanged.connect(self._on_theme)
        row2.addWidget(self.theme_combo, 1)
        
        main_layout.addLayout(row2)
        
        # 第三行：大小(2)，大小聚合(1)，删除按钮
        row3 = QHBoxLayout()
        row3.setSpacing(4)

        self.size_combo = DropComboBox("大小", fields)
        if spec.size: self.size_combo.set_field(spec.size)
        self.size_combo.fieldDropped.connect(self._on_size)
        row3.addWidget(self.size_combo, 2)
        
        self.size_agg_combo = QComboBox()
        for at in AggType:
            self.size_agg_combo.addItem(at.value, at)
        self.size_agg_combo.setCurrentText(spec.size_agg.value)
        self.size_agg_combo.currentIndexChanged.connect(self._on_size_agg)
        row3.addWidget(self.size_agg_combo, 1)

        row3.addStretch()
        self.del_btn = QPushButton("× 删除")
        self.del_btn.setFixedWidth(60)
        self.del_btn.setStyleSheet("color: red;")
        self.del_btn.clicked.connect(lambda: self.removed.emit(self))
        row3.addWidget(self.del_btn)

        main_layout.addLayout(row3)
        
        self._sync()

    def _on_y(self, f):
        self.spec.y = f or None
        self.changed.emit()

    def _on_color(self, f):
        self.spec.color = f or None
        self.changed.emit()

    def _on_size(self, f):
        self.spec.size = f or None
        self.changed.emit()
        
    def _on_size_agg(self):
        val = self.size_agg_combo.currentData()
        self.spec.size_agg = val if isinstance(val, AggType) else AggType(val)
        self.changed.emit()

    def _on_bin_changed(self):
        text = self.bin_input.text().strip()
        try:
            val = float(text) if text else 0.0
        except ValueError:
            val = 0.0
            
        if self.spec.bin_width != val:
            self.spec.bin_width = val
            self.changed.emit()

    def _on_type(self):
        val = self.type_combo.currentData()
        self.spec.chart_type = val if isinstance(val, ChartType) else ChartType(val)
        self._sync()
        self.changed.emit()

    def _on_axis(self):
        val = self.axis_combo.currentData()
        self.spec.axis = val if isinstance(val, AxisSlot) else AxisSlot(val)
        self.changed.emit()

    def _on_agg(self):
        val = self.agg_combo.currentData()
        self.spec.agg = val if isinstance(val, AggType) else AggType(val)
        self.changed.emit()

    def _on_theme(self):
        val = self.theme_combo.currentData()
        self.spec.color_theme = val if isinstance(val, ColorTheme) else ColorTheme(val)
        self.changed.emit()

    def _sync(self):
        pass


class SeriesTable(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._rows: list[SeriesRow] = []
        self._fields: list[str] = []
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self._rows_container = QVBoxLayout()
        self._rows_container.setSpacing(6)
        self._layout.addLayout(self._rows_container)

        self.add_btn = QPushButton("+ 添加 series（或从左侧拖入）")
        self.add_btn.clicked.connect(self.add_series)
        self._layout.addWidget(self.add_btn)
        self._layout.addStretch()

    def set_fields(self, fields: list[str]):
        self._fields = fields

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not event.mimeData().hasText(): return
        field = event.mimeData().text()
        self.add_series(SeriesSpec(y=field))
        event.acceptProposedAction()

    def add_series(self, spec: SeriesSpec | None = None) -> SeriesRow:
        row = SeriesRow(spec or SeriesSpec(), self._fields)
        row.changed.connect(self.changed)
        row.removed.connect(self._remove_row)
        self._rows.append(row)
        self._rows_container.addWidget(row)
        self.changed.emit()
        return row

    def _remove_row(self, row: SeriesRow):
        if row in self._rows:
            self._rows.remove(row)
            self._rows_container.removeWidget(row)
            row.deleteLater()
            self.changed.emit()

    def specs(self) -> list[SeriesSpec]:
        return [r.spec for r in self._rows]