import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel

class PandasModel(QAbstractTableModel):
    def __init__(self, data=pd.DataFrame(), max_rows=1000):
        super().__init__()
        # 性能核心：截断数据，只保留前 max_rows 行
        self._data = data.head(max_rows).copy()
        self._is_truncated = len(data) > max_rows
        self._total_rows = len(data)

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
            
        row, col = index.row(), index.column()
        val = self._data.iloc[row, col]

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return str(val)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if isinstance(val, (int, float)):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            row, col = index.row(), index.column()
            col_name = self._data.columns[col]
            old_val = self._data.iloc[row, col]
            
            # 尝试类型推断保持原格式
            new_val = value
            if isinstance(old_val, (int, float)):
                try:
                    new_val = float(value) if '.' in value else int(value)
                except ValueError:
                    pass # 用户输入非法数字，保持字符串
            
            self._data.iloc[row, col] = new_val
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
            return True
        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])
            else:
                return str(section)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        # 允许编辑
        return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def get_dataframe(self):
        """返回被用户修改后的 DataFrame（仅限前1000行）"""
        return self._data