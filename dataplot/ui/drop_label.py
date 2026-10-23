from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton


class DropLabel(QFrame):
    fieldDropped = Signal(str)

    def __init__(self, placeholder="拖入", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._field = None
        self.setAcceptDrops(True)
        self.setObjectName("DropFrame")
        
        self.normal_style = "#DropFrame { border: 1px dashed #aaa; border-radius: 3px; background: #fafafa; }"
        self.hover_style = "#DropFrame { border: 1px dashed #3b82f6; border-radius: 3px; background: #eff6ff; }"
        self.setStyleSheet(self.normal_style)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 2, 2)
        layout.setSpacing(2)
        
        self.label = QLabel(placeholder)
        self.label.setStyleSheet("color: #888; border: none; background: transparent;")
        layout.addWidget(self.label, 1)
        
        self.clear_btn = QToolButton()
        self.clear_btn.setText("×")
        self.clear_btn.setFixedSize(18, 18)
        self.clear_btn.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; font-size: 14px; color: #888; background: transparent; } "
            "QToolButton:hover { color: #ef4444; }"
        )
        self.clear_btn.hide()
        self.clear_btn.clicked.connect(self._clear)
        layout.addWidget(self.clear_btn)
        
    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()
            self.setStyleSheet(self.hover_style)
            
    def dragLeaveEvent(self, e):
        self.setStyleSheet(self.normal_style)
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        self.setStyleSheet(self.normal_style)
        field = e.mimeData().text()
        self.set_field(field)
        self.fieldDropped.emit(field)

    def set_field(self, field: str | None):
        self._field = field or None
        if field:
            self.label.setText(field)
            self.label.setStyleSheet("color: #000; font-weight: bold; border: none; background: transparent;")
            self.clear_btn.show()
        else:
            self.label.setText(self._placeholder)
            self.label.setStyleSheet("color: #888; border: none; background: transparent;")
            self.clear_btn.hide()

    def _clear(self):
        self.set_field(None)
        self.fieldDropped.emit("")

    @property
    def field(self) -> str | None:
        return self._field