from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QToolButton, QWidget, QSizePolicy


class DropComboBox(QWidget):
    fieldDropped = Signal(str)

    def __init__(self, placeholder="拖入或选择", fields: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._field = None
        self.setAcceptDrops(True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.combo = QComboBox()
        # 核心修复：允许下拉框被无限压缩
        self.combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.combo.setMinimumWidth(0)
        self.combo.addItem("")
        if fields:
            self.combo.addItems(fields)
        self.combo.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo, 1)

        self.clear_btn = QToolButton()
        self.clear_btn.setText("×")
        self.clear_btn.setFixedSize(18, 18)
        self.clear_btn.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; font-size: 14px; color: #888; background: transparent; } "
            "QToolButton:hover { color: #ef4444; }"
        )
        self.clear_btn.clicked.connect(self._clear)
        layout.addWidget(self.clear_btn)
        
        self._update_ui()

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        field = e.mimeData().text()
        self.set_field(field)
        self.fieldDropped.emit(field)

    def _on_combo_changed(self, text):
        if text == "" and self._field is not None:
            self._field = None
            self._update_ui()
            self.fieldDropped.emit("")
            return
        if text != self._field:
            self._field = text
            self._update_ui()
            self.fieldDropped.emit(text)

    def set_field(self, field: str | None):
        self._field = field or None
        self.combo.blockSignals(True)
        if self._field:
            idx = self.combo.findText(self._field)
            if idx == -1:
                self.combo.addItem(self._field)
                idx = self.combo.findText(self._field)
            self.combo.setCurrentIndex(idx)
        else:
            self.combo.setCurrentIndex(0)
        self.combo.blockSignals(False)
        self._update_ui()

    def _clear(self):
        self.set_field(None)
        self.fieldDropped.emit("")

    def _update_ui(self):
        if self._field:
            self.combo.setStyleSheet("QComboBox { border: 1px solid #3b82f6; background: #eff6ff; font-weight: bold; }")
            self.clear_btn.show()
        else:
            self.combo.setStyleSheet("QComboBox { border: 1px solid #ccc; color: #888; }")
            self.clear_btn.hide()
            self.combo.setCurrentIndex(0)

    @property
    def field(self) -> str | None:
        return self._field