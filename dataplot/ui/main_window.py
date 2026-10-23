from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidgetItem, QListWidget,
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QScrollArea, QMessageBox,
    QComboBox, QCompleter, QFrame
)
from dataplot.core.datastore import DataStore
from dataplot.core.spec import ChartSpec, AggType
from dataplot.ui.collapsible import CollapsiblePanel, CollapsibleGroupBox
from dataplot.ui.field_list import FieldList, FieldItemWidget
from dataplot.ui.legend_panel import LegendPanel
from dataplot.ui.plot_canvas import PlotCanvas
from dataplot.ui.series_table import SeriesTable
from dataplot.ui.drop_combo import DropComboBox


def create_app_icon() -> QIcon:
    """用 QPainter 动态绘制一个带有柱状图和折线的科技感图标"""
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 1. 深色科技感圆角背景
    painter.setBrush(QColor(30, 41, 59))  # 深蓝灰
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(16, 16, 224, 224, 48, 48)
    
    # 2. 绘制底层彩色柱状图 (蓝, 绿, 黄, 红)
    colors = [QColor(59, 130, 246), QColor(16, 185, 129), QColor(245, 158, 11), QColor(239, 68, 68)]
    for i, color in enumerate(colors):
        painter.setBrush(color)
        x = 48 + i * 44
        height = (i * 17) % 80 + 60
        painter.drawRoundedRect(x, 224 - height - 24, 28, height, 8, 8)
        
    # 3. 绘制上层白色折线图
    pen = QPen(QColor(255, 255, 255))
    pen.setWidth(8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    
    # 向上的数据趋势折线
    points = [
        QPoint(48, 140),
        QPoint(88, 100),
        QPoint(128, 120),
        QPoint(168, 60),
        QPoint(208, 80)
    ]
    painter.drawPolyline(points)
    
    # 4. 绘制折线上的高亮数据点
    painter.setBrush(QColor(255, 255, 255))
    painter.setPen(Qt.PenStyle.NoPen)
    for pt in points:
        painter.drawEllipse(pt, 10, 10)
        
    painter.end()
    return QIcon(pixmap)


class HoverChip(QFrame):
    def __init__(self, field, agg, on_remove, on_agg_change, parent=None):
        super().__init__(parent)
        self.field = field
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)
        self.setStyleSheet("QFrame { background: #e0f2fe; border: 1px solid #7dd3fc; border-radius: 4px; }")
        
        lbl = QLabel(field)
        lbl.setStyleSheet("border: none; background: transparent; font-size: 11px;")
        layout.addWidget(lbl)
        
        self.agg_combo = QComboBox()
        for at in AggType:
            self.agg_combo.addItem(at.value, at)
        self.agg_combo.setCurrentText(agg.value)
        self.agg_combo.setFixedWidth(60)
        self.agg_combo.setStyleSheet("QComboBox { border: 1px solid #ccc; background: white; font-size: 10px; }")
        self.agg_combo.currentIndexChanged.connect(lambda: on_agg_change(self.field, self.agg_combo.currentData()))
        layout.addWidget(self.agg_combo)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(14, 14)
        close_btn.setStyleSheet("QPushButton { border: none; background: transparent; font-weight: bold; } QPushButton:hover { color: red; }")
        close_btn.clicked.connect(lambda: on_remove(self.field))
        layout.addWidget(close_btn)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DataPlot")
        # 设置动态生成的图标
        self.setWindowIcon(create_app_icon())
        
        self.resize(1500, 850)

        self.store = DataStore()
        self.spec = ChartSpec()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        # 左侧面板
        self.left_panel = CollapsiblePanel("数据源", direction="left", expanded_width=260)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setSpacing(10)
        
        self.sql_group = CollapsibleGroupBox("SQL 编辑器 (开发中)", expanded=False)
        self.sql_placeholder = QLabel("此处预留给 SQL 查询编辑器。\n当前请点击上方工具栏加载文件。")
        self.sql_placeholder.setStyleSheet("color: #888; font-size: 11px; padding: 10px;")
        self.sql_group.addWidget(self.sql_placeholder)
        left_lay.addWidget(self.sql_group)
        
        self.field_group = CollapsibleGroupBox("字段列表", expanded=True)
        self.field_list = FieldList()
        self.field_group.addWidget(self.field_list)
        left_lay.addWidget(self.field_group)
        
        left_lay.addStretch()
        left_scroll.setWidget(left_widget)
        self.left_panel.content_layout().addWidget(left_scroll)
        root.addWidget(self.left_panel)

        # 中央画布
        self.canvas = PlotCanvas(self.store, self.spec)
        root.addWidget(self.canvas, 1)

        # 右侧面板
        self.right_panel = CollapsiblePanel("配置", direction="right", expanded_width=380)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        right_widget = QWidget()
        right_lay = QVBoxLayout(right_widget)
        right_lay.setSpacing(10)
        
        tip = QLabel("提示：Ctrl+左键拖拽平移，Shift+滚轮缩放X轴，Ctrl+滚轮缩放Y轴，双击重置")
        tip.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
        tip.setWordWrap(True)
        right_lay.addWidget(tip)

        # 切片配置
        self.facet_group = CollapsibleGroupBox("切片 (Facet)", expanded=True)
        
        facet_row1 = QHBoxLayout()
        facet_row1.addWidget(QLabel("X 切片:"))
        self.facet_x_combo = DropComboBox("无")
        self.facet_x_combo.fieldDropped.connect(self._on_facet_x)
        facet_row1.addWidget(self.facet_x_combo, 1)
        self.facet_group.addLayout(facet_row1)
        
        facet_row2 = QHBoxLayout()
        facet_row2.addWidget(QLabel("Y 切片:"))
        self.facet_y_combo = DropComboBox("无")
        self.facet_y_combo.fieldDropped.connect(self._on_facet_y)
        facet_row2.addWidget(self.facet_y_combo, 1)
        self.facet_group.addLayout(facet_row2)
        
        size_lay = QHBoxLayout()
        size_lay.addWidget(QLabel("窗口尺寸:"))
        self.cell_size_combo = QComboBox()
        for size in [300, 400, 500, 600, 800, 1000]:
            self.cell_size_combo.addItem(f"{size} px", size)
        self.cell_size_combo.setCurrentIndex(1)
        self.cell_size_combo.currentIndexChanged.connect(self._on_cell_size_changed)
        size_lay.addWidget(self.cell_size_combo)
        size_lay.addStretch()
        self.facet_group.addLayout(size_lay)
        
        right_lay.addWidget(self.facet_group)

        self.x_group = CollapsibleGroupBox("X 轴（全局）", expanded=True)
        self.x_combo = DropComboBox("拖入或选择 X 字段")
        self.x_combo.fieldDropped.connect(self._on_x)
        self.x_group.addWidget(self.x_combo)
        right_lay.addWidget(self.x_group)

        self.y_group = CollapsibleGroupBox("Y 序列", expanded=True)
        self.series_table = SeriesTable()
        self.series_table.changed.connect(self._on_series_changed)
        self.y_group.addWidget(self.series_table)
        right_lay.addWidget(self.y_group)

        # 悬停字段
        self.hover_group = CollapsibleGroupBox("悬停额外字段", expanded=True)
        
        self.hover_combo = QComboBox()
        self.hover_combo.setEditable(True)
        self.hover_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.hover_combo.setPlaceholderText("输入或选择字段...")
        self.hover_combo.lineEdit().returnPressed.connect(self._add_hover_field)
        self.hover_combo.activated.connect(self._add_hover_field)
        
        self.hover_group.addWidget(self.hover_combo)
        
        self.hover_tags_widget = QWidget()
        self.hover_tags_layout = QHBoxLayout(self.hover_tags_widget)
        self.hover_tags_layout.setContentsMargins(0, 0, 0, 0)
        self.hover_tags_layout.setSpacing(4)
        self.hover_tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.hover_group.addWidget(self.hover_tags_widget)
        
        right_lay.addWidget(self.hover_group)

        self.legend_group = CollapsibleGroupBox("图例（点击隐藏/显示）", expanded=False)
        self.legend_panel = LegendPanel()
        self.legend_panel.legendToggled.connect(self._on_legend_toggled)
        self.legend_group.addWidget(self.legend_panel)
        right_lay.addWidget(self.legend_group)
        
        right_lay.addStretch()
        scroll.setWidget(right_widget)
        self.right_panel.content_layout().addWidget(scroll)
        root.addWidget(self.right_panel)

        toolbar = self.addToolBar("主")
        act_load = toolbar.addAction("加载文件")
        act_load.triggered.connect(self._load_file)

        self.statusBar().showMessage("就绪")
        
    def _on_cell_size_changed(self, index):
        val = self.cell_size_combo.itemData(index)
        if val:
            self.canvas.cell_size = val
            self._rerender()

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择数据文件", "", "数据文件 (*.csv *.xlsx *.xls *.pkl)")
        if not path: return
        try:
            df = self.store.load(path)
        except Exception as exc:
            self.statusBar().showMessage(f"加载失败: {exc}"); return
            
        self.field_list.clear()
        self.hover_combo.clear()
        self.spec.hidden_categories.clear()
        self._refresh_hover_tags()
        
        cols = df.columns.tolist()
        self.series_table.set_fields(cols)
        
        for combo in [self.x_combo, self.facet_x_combo, self.facet_y_combo]:
            combo.combo.blockSignals(True)
            combo.combo.clear()
            combo.combo.addItem("")
            combo.combo.addItems(cols)
            combo.combo.blockSignals(False)
        
        for col in cols:
            w = FieldItemWidget(col, str(df[col].dtype))
            w.typeChanged.connect(self._on_type_changed)
            item = QListWidgetItem()
            item.setSizeHint(w.sizeHint())
            self.field_list.addItem(item)
            self.field_list.setItemWidget(item, w)
            
            self.hover_combo.addItem(col)

        completer = self.hover_combo.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

    def _add_hover_field(self):
        field = self.hover_combo.currentText().strip()
        if field and field not in self.spec.hover_fields:
            self.spec.hover_fields[field] = AggType.MEAN
            self._refresh_hover_tags()
            self._rerender()
        self.hover_combo.setCurrentIndex(-1)
        self.hover_combo.clearEditText()

    def _remove_hover_field(self, field):
        if field in self.spec.hover_fields:
            del self.spec.hover_fields[field]
            self._refresh_hover_tags()
            self._rerender()
            
    def _on_hover_agg_changed(self, field, agg):
        if field in self.spec.hover_fields:
            self.spec.hover_fields[field] = agg
            self._rerender()

    def _refresh_hover_tags(self):
        while self.hover_tags_layout.count():
            item = self.hover_tags_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
            
        for f, agg in self.spec.hover_fields.items():
            chip = HoverChip(f, agg, self._remove_hover_field, self._on_hover_agg_changed)
            self.hover_tags_layout.addWidget(chip)
        self.hover_tags_layout.addStretch()

    def _on_type_changed(self, col: str, dtype: str):
        ok, err = self.store.convert_type(col, dtype)
        if not ok:
            QMessageBox.critical(self, "转换失败", f"字段 {col} 无法转换为 {dtype}：\n{err}")
        self._rerender()

    def _on_legend_toggled(self, series_name, category):
        key = f"{series_name}||{category}"
        if key in self.spec.hidden_categories:
            self.spec.hidden_categories.remove(key)
        else:
            self.spec.hidden_categories.add(key)
        self._rerender()

    def _on_x(self, field: str):
        self.spec.x = field or None
        self._rerender()
        
    def _on_facet_x(self, field: str):
        self.spec.facet_x = field or None
        self._rerender()
        
    def _on_facet_y(self, field: str):
        self.spec.facet_y = field or None
        self._rerender()

    def _on_series_changed(self):
        self.spec.series = self.series_table.specs()
        self._rerender()

    def _rerender(self):
        res = self.canvas.render() or ([], [])
        legends, warnings = res
        
        if warnings:
            self.statusBar().showMessage("提示: " + " | ".join(warnings))
        else:
            self.statusBar().showMessage("就绪")
            
        self.legend_panel.clear()
        for name, legend in legends:
            self.legend_panel.add_legend(name, legend, self.spec.hidden_categories)
        self.legend_panel.finalize()