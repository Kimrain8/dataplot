from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QWidget, QMessageBox
)


class FieldItemWidget(QWidget):
    typeChanged = Signal(str, str)  # col_name, new_type

    def __init__(self, col_name: str, dtype: str):
        super().__init__()
        self.col_name = col_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        
        self.label = QLabel(col_name)
        layout.addWidget(self.label, 1)
        
        self.combo = QComboBox()
        self.combo.addItems(["float", "str", "datetime"])
        if "int" in dtype or "float" in dtype:
            self.combo.setCurrentText("float")
        elif "datetime" in dtype:
            self.combo.setCurrentText("datetime")
        else:
            self.combo.setCurrentText("str")
            
        self.combo.currentTextChanged.connect(self._on_changed)
        layout.addWidget(self.combo)

    def _on_changed(self, text):
        # 恢复原状，等 MainWindow 确认转换成功后由外部强制设置
        self.typeChanged.emit(self.col_name, text)


class FieldList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None: return
        # 拖拽项本身
        w = self.itemWidget(item)
        if not w: return
        
        from PySide6.QtCore import QMimeData
        mime = QMimeData()
        mime.setText(w.col_name)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)