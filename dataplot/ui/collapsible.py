from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class CollapsiblePanel(QWidget):
    def __init__(self, title: str, direction: str = "right", expanded_width: int = 320):
        super().__init__()
        self.direction = direction
        self._title = title
        self._expanded_width = expanded_width
        self._collapsed_width = 32
        self._collapsed = False

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.toggle_btn = QPushButton(self._label_expanded())
        self.toggle_btn.clicked.connect(self._toggle)
        outer.addWidget(self.toggle_btn)
        outer.addWidget(self._content, 1)

        self.setFixedWidth(expanded_width)

    def _label_expanded(self):
        return f"{self._title} ◀" if self.direction == "right" else f"▶ {self._title}"

    def _label_collapsed(self):
        return "◀" if self.direction == "right" else "▶"

    def content_layout(self):
        return self._content_layout

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        if self._collapsed:
            self.setFixedWidth(self._collapsed_width)
            self.toggle_btn.setText(self._label_collapsed())
        else:
            self.setFixedWidth(self._expanded_width)
            self.toggle_btn.setText(self._label_expanded())


class CollapsibleGroupBox(QWidget):
    """上下折叠的区块（手风琴效果）。"""
    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._title = title
        self._expanded = expanded
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.toggle_btn = QPushButton(f"▼ {self._title}" if expanded else f"▶ {self._title}")
        self.toggle_btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 5px; font-weight: bold; "
            "background: #f0f0f0; border: 1px solid #ccc; border-radius: 3px; }"
            "QPushButton:hover { background: #e8e8e8; }"
        )
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.content_widget)
        
        self.content_widget.setVisible(expanded)

    def _toggle(self):
        self._expanded = not self._expanded
        self.content_widget.setVisible(self._expanded)
        self.toggle_btn.setText(f"▼ {self._title}" if self._expanded else f"▶ {self._title}")

    def addWidget(self, widget: QWidget):
        self.content_layout.addWidget(widget)
        
    def addLayout(self, layout):
        self.content_layout.addLayout(layout)