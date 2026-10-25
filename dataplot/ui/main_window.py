import os
import json
import dataclasses
from dataclasses import asdict
import pandas as pd
import numpy as np
from PySide6.QtCore import Qt, QPoint, QMimeData
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QDrag
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidgetItem, QListWidget,
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QScrollArea, QMessageBox,
    QComboBox, QCompleter, QFrame, QDialog, QLineEdit, QMenu, QListWidgetItem
)

from dataplot.core.datastore import DataStore
from dataplot.core.spec import (
    ChartSpec, AggType, HierarchySpec, SeriesSpec, AxisSlot, ChartType, ColorTheme, HistogramMode
)
from dataplot.ui.collapsible import CollapsiblePanel, CollapsibleGroupBox
from dataplot.ui.field_list import FieldList, FieldItemWidget
from dataplot.ui.legend_panel import LegendPanel
from dataplot.ui.plot_canvas import PlotCanvas
from dataplot.ui.series_table import SeriesTable
from dataplot.ui.drop_combo import DropComboBox
from dataplot.ui.data_source_dialog import DataSourceDialog

DB_IMPORT_ERROR = None
try:
    from utils.dbManager import MySQLHelper
except Exception as e:
    import traceback
    MySQLHelper = None
    DB_IMPORT_ERROR = traceback.format_exc()


def create_app_icon() -> QIcon:
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(30, 41, 59))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(16, 16, 224, 224, 48, 48)
    colors = [QColor(59, 130, 246), QColor(16, 185, 129), QColor(245, 158, 11), QColor(239, 68, 68)]
    for i, color in enumerate(colors):
        painter.setBrush(color)
        x = 48 + i * 44
        height = (i * 17) % 80 + 60
        painter.drawRoundedRect(x, 224 - height - 24, 28, height, 8, 8)
    pen = QPen(QColor(255, 255, 255))
    pen.setWidth(8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    points = [QPoint(48, 140), QPoint(88, 100), QPoint(128, 120), QPoint(168, 60), QPoint(208, 80)]
    painter.drawPolyline(points)
    painter.setBrush(QColor(255, 255, 255))
    painter.setPen(Qt.PenStyle.NoPen)
    for pt in points:
        painter.drawEllipse(pt, 10, 10)
    painter.end()
    return QIcon(pixmap)


class HierarchyList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None: return
        mime = QMimeData()
        mime.setText(item.text())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class HierarchyDialog(QDialog):
    def __init__(self, fields, current_fields=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑层级")
        self.resize(450, 500)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("双击左侧字段加入右侧，或选中右侧字段拖拽上下移动来改变层级顺序："))
        
        hbox = QHBoxLayout()
        
        # 左侧：可选字段
        left_lay = QVBoxLayout()
        left_lay.addWidget(QLabel("可选字段"))
        self.left_list = QListWidget()
        self.left_list.addItems(fields)
        self.left_list.itemDoubleClicked.connect(self._add_to_right)
        left_lay.addWidget(self.left_list)
        hbox.addLayout(left_lay)
        
        # 中间：操作按钮
        mid_lay = QVBoxLayout()
        mid_lay.addStretch()
        btn_add = QPushButton(" > ")
        btn_add.clicked.connect(self._add_to_right)
        mid_lay.addWidget(btn_add)
        btn_remove = QPushButton(" < ")
        btn_remove.clicked.connect(self._remove_from_right)
        mid_lay.addWidget(btn_remove)
        mid_lay.addStretch()
        hbox.addLayout(mid_lay)
        
        # 右侧：已选层级
        right_lay = QVBoxLayout()
        right_lay.addWidget(QLabel("已选层级 (拖拽排序)"))
        self.right_list = QListWidget()
        self.right_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        right_lay.addWidget(self.right_list)
        hbox.addLayout(right_lay)
        
        layout.addLayout(hbox)
        
        # 预填当前层级
        if current_fields:
            for f in current_fields:
                self.right_list.addItem(f)
            for i in reversed(range(self.left_list.count())):
                if self.left_list.item(i).text() in current_fields:
                    self.left_list.takeItem(i)
        
        btn = QPushButton("确定")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def _add_to_right(self):
        item = self.left_list.currentItem()
        if item:
            self.right_list.addItem(item.text())
            self.left_list.takeItem(self.left_list.row(item))

    def _remove_from_right(self):
        item = self.right_list.currentItem()
        if item:
            self.left_list.addItem(item.text())
            self.right_list.takeItem(self.right_list.row(item))
            
    def get_fields(self):
        return [self.right_list.item(i).text() for i in range(self.right_list.count())]


class HoverChip(QFrame):
    def __init__(self, field, agg, on_remove, on_agg_change, parent=None):
        super().__init__(parent)
        self.field = field
        self.setStyleSheet("QFrame { background: #e0f2fe; border: 1px solid #7dd3fc; border-radius: 4px; }")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)
        
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
        self.setWindowIcon(create_app_icon())
        self.resize(1500, 850)

        self.store = DataStore()
        self.spec = ChartSpec()
        self._last_series_count = 0
        self._current_project_path = None
        self._is_loading_from_project = False
        self._is_rebuilding_ui = False  # <-- 新增这句

        self.data_source_dialog = None
        if MySQLHelper:
            self.data_source_dialog = DataSourceDialog(MySQLHelper, self)
            self.data_source_dialog.data_applied.connect(self._on_data_applied)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        self.left_panel = CollapsiblePanel("数据源", direction="left", expanded_width=260)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setSpacing(10)
        
        self.sql_group = CollapsibleGroupBox("数据获取", expanded=True)
        self.btn_open_source = QPushButton("打开数据源编辑器 (SQL/Python)")
        self.btn_open_source.setStyleSheet("padding: 8px; font-weight: bold; background: #e0f2fe; border: 1px solid #7dd3fc;")
        self.btn_open_source.clicked.connect(self._open_data_source)
        self.sql_group.addWidget(self.btn_open_source)
        left_lay.addWidget(self.sql_group)
        
        self.hierarchy_group = CollapsibleGroupBox("层级 (Hierarchy)", expanded=True)
        self.btn_add_hier = QPushButton("+ 新建层级")
        self.btn_add_hier.clicked.connect(self._create_hierarchy)
        self.hierarchy_group.addWidget(self.btn_add_hier)
        self.hierarchy_list = HierarchyList()
        self.hierarchy_list.itemDoubleClicked.connect(self._edit_hierarchy)
        self.hierarchy_list.customContextMenuRequested.connect(self._show_hierarchy_menu)
        self.hierarchy_group.addWidget(self.hierarchy_list)
        left_lay.addWidget(self.hierarchy_group)

        self.field_group = CollapsibleGroupBox("字段列表", expanded=True)
        self.field_list = FieldList()
        self.field_group.addWidget(self.field_list)
        left_lay.addWidget(self.field_group)
        
        left_lay.addStretch()
        left_scroll.setWidget(left_widget)
        self.left_panel.content_layout().addWidget(left_scroll)
        root.addWidget(self.left_panel)

        self.canvas = PlotCanvas(self.store, self.spec)
        root.addWidget(self.canvas, 1)

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

        self.bucket_group = CollapsibleGroupBox("分桶 (Bucketing)", expanded=True)
        self.bucket_layout = QVBoxLayout()
        self.bucket_group.addLayout(self.bucket_layout)
        right_lay.addWidget(self.bucket_group)

        self.y_group = CollapsibleGroupBox("Y 序列", expanded=True)
        self.series_table = SeriesTable()
        self.series_table.changed.connect(self._on_series_changed)
        self.y_group.addWidget(self.series_table)
        right_lay.addWidget(self.y_group)

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
        
        # 文件菜单增强
        file_menu = QMenu(self)
        act_new = file_menu.addAction("新建项目...")
        act_new.triggered.connect(self._new_project)
        act_open = file_menu.addAction("打开项目...")
        act_open.triggered.connect(self._load_project)
        act_save = file_menu.addAction("保存项目...")
        act_save.triggered.connect(self._save_project)
        
        btn_file = QPushButton("文件")
        btn_file.setMenu(file_menu)
        toolbar.addWidget(btn_file)
        
        act_load = toolbar.addAction("加载本地文件")
        act_load.triggered.connect(self._load_file)
        
        act_source = toolbar.addAction("打开数据源")
        act_source.triggered.connect(self._open_data_source)

        self.statusBar().showMessage("就绪")
    def _new_project(self):
        if self.store.is_loaded or self.spec.series:
            reply = QMessageBox.question(
                self, '确认', '当前工作区有数据或配置，是否先保存当前项目？',
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        # 清空所有状态
        self.store.df = None
        self.store.source_type = "none"
        self.store.source_path = ""
        self.spec = ChartSpec()
        self.canvas.spec = self.spec
        self._current_project_path = None
        self._last_series_count = 0

        # 重置 UI
        self.field_list.clear()
        self.hover_combo.clear()
        self.hierarchy_list.clear()
        self._refresh_hover_tags()
        self._last_series_count = 0
        
        self.x_combo.combo.blockSignals(True)
        self.facet_x_combo.combo.blockSignals(True)
        self.facet_y_combo.combo.blockSignals(True)
        
        for combo in [self.x_combo, self.facet_x_combo, self.facet_y_combo]:
            combo.combo.clear()
            combo.combo.addItem("")
            
        self.x_combo.combo.blockSignals(False)
        self.facet_x_combo.combo.blockSignals(False)
        self.facet_y_combo.combo.blockSignals(False)

        self.series_table.clear_all()
        self.legend_panel.clear()
        self.legend_panel.finalize()
        self._update_bucket_ui()
        
        self.canvas.render()
        self.statusBar().showMessage("已新建项目")
    def _open_data_source(self):
        if not MySQLHelper:
            QMessageBox.critical(self, "模块加载失败", f"无法加载 utils.dbManager。\n错误详情:\n{DB_IMPORT_ERROR}")
            return
        self.data_source_dialog.show()
        self.data_source_dialog.raise_()
        self.data_source_dialog.activateWindow()

    def _on_data_applied(self, df):
        # print(f"DEBUG: \n========== 主窗口接收到数据 ==========")
        # print(f"DEBUG: 接收到的数据形状: {df.shape if df is not None else 'None'}")
        
        if df is None or df.empty: return
        
        df = DataStore.infer_types(df)
        self.store.df = df
        self.store.source_type = "db"
        self.store._refresh_columns()
        
        if self._is_loading_from_project:
            self._is_loading_from_project = False
            self._refresh_all_ui_from_spec()
        else:
            self._refresh_fields_and_cols()
        self.statusBar().showMessage(f"成功应用数据源: {len(df)} 行 × {len(df.columns)} 列")

    def _refresh_fields_and_cols(self):
        # 核心修复：先备份当前配置，防止刷新下拉框时被信号清空
        old_x = self.spec.x
        old_hier = self.spec.x_hierarchy
        old_fx = self.spec.facet_x
        old_fy = self.spec.facet_y

        self.field_list.clear()
        self.hover_combo.clear()
        self.spec.hidden_categories.clear()
        self._refresh_hover_tags()
        
        cols = self.store.df.columns.tolist()
        self.series_table.set_fields(cols)
        
        self.x_combo.combo.blockSignals(True)
        self.facet_x_combo.combo.blockSignals(True)
        self.facet_y_combo.combo.blockSignals(True)
        
        for combo in [self.x_combo, self.facet_x_combo, self.facet_y_combo]:
            combo.combo.clear()
            combo.combo.addItem("")
            combo.combo.addItems(cols)
            
        self.x_combo.combo.blockSignals(False)
        self.facet_x_combo.combo.blockSignals(False)
        self.facet_y_combo.combo.blockSignals(False)

        # 核心修复：立刻将备份的配置贴回去
        self.spec.x = old_x
        self.spec.x_hierarchy = old_hier
        self.spec.facet_x = old_fx
        self.spec.facet_y = old_fy
        
        # 恢复下拉框的显示状态
        if self.spec.x_hierarchy:
            self.x_combo.set_field(" > ".join(self.spec.x_hierarchy))
        else:
            self.x_combo.set_field(self.spec.x)
        self.facet_x_combo.set_field(self.spec.facet_x)
        self.facet_y_combo.set_field(self.spec.facet_y)
        
        for col in cols:
            w = FieldItemWidget(col, str(self.store.df[col].dtype))
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
            
        self._last_series_count = len(self.spec.series)
        self._update_bucket_ui()
        self._rerender(reset_view=True)

    def _refresh_all_ui_from_spec(self):
        self._is_rebuilding_ui = True 
        try:
            if self.store.is_loaded:
                self._refresh_fields_and_cols()
                
            self.hierarchy_list.clear()
            for h in self.spec.hierarchies:
                if len(h.fields) > 2:
                    for i in range(2, len(h.fields) + 1):
                        self.hierarchy_list.addItem(" > ".join(h.fields[:i]))
                else:
                    self.hierarchy_list.addItem(h.name)
                    
            if self.spec.x_hierarchy:
                self.x_combo.set_field(" > ".join(self.spec.x_hierarchy))
            else:
                self.x_combo.set_field(self.spec.x)
                
            self._update_bucket_ui()
            
            self.series_table.clear_all()
            for s in self.spec.series:
                self.series_table.add_series(s)
                
        finally:
            self._is_rebuilding_ui = False

        if self.store.is_loaded:
            self._last_series_count = len(self.spec.series)
            self._rerender(reset_view=True)

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择数据文件", "", "数据文件 (*.csv *.xlsx *.xls *.pkl)")
        if not path: return
        try:
            df = self.store.load(path)
            self.store.source_type = "local"
            self.store.source_path = path
        except Exception as exc:
            self.statusBar().showMessage(f"加载失败: {exc}"); return
            
        self._refresh_fields_and_cols()
        self.statusBar().showMessage(f"已加载本地文件 {len(df)} 行")

    def _on_cell_size_changed(self, index):
        val = self.cell_size_combo.itemData(index)
        if val:
            self.canvas.cell_size = val
            self._rerender(reset_view=False)

    def _create_hierarchy(self):
        cols = self.store.df.columns.tolist() if self.store.is_loaded else []
        if not cols:
            QMessageBox.warning(self, "提示", "请先加载数据。")
            return
            
        dialog = HierarchyDialog(cols, parent=self)
        if dialog.exec():
            selected = dialog.get_fields()
            if len(selected) >= 2:
                name = " > ".join(selected)
                spec = HierarchySpec(name=name, fields=selected)
                self.spec.hierarchies.append(spec)
                
                self.hierarchy_list.clear()
                for h in self.spec.hierarchies:
                    if len(h.fields) > 2:
                        for i in range(2, len(h.fields) + 1):
                            sub_name = " > ".join(h.fields[:i])
                            self.hierarchy_list.addItem(sub_name)
                    else:
                        self.hierarchy_list.addItem(h.name)
            else:
                QMessageBox.warning(self, "提示", "请至少选择两个字段建立层级。")

    def _edit_hierarchy(self, item):
        old_name = item.text()
        target_fields = old_name.split(" > ")
        old_spec = None
        for h in self.spec.hierarchies:
            if h.fields[:len(target_fields)] == target_fields:
                old_spec = h
                break
                
        if not old_spec: return
        
        cols = self.store.df.columns.tolist()
        dialog = HierarchyDialog(cols, current_fields=old_spec.fields, parent=self)
        if dialog.exec():
            selected = dialog.get_fields()
            if len(selected) >= 2:
                old_spec.fields = selected
                old_spec.name = " > ".join(selected)
                
                self.hierarchy_list.clear()
                for h in self.spec.hierarchies:
                    if len(h.fields) > 2:
                        for i in range(2, len(h.fields) + 1):
                            self.hierarchy_list.addItem(" > ".join(h.fields[:i]))
                    else:
                        self.hierarchy_list.addItem(h.name)
                        
                if self.spec.x_hierarchy and self.spec.x_hierarchy[:len(target_fields)] == target_fields:
                    self.spec.x_hierarchy = selected
                    self.x_combo.set_field(old_spec.name)
                self._rerender(reset_view=True)
            else:
                QMessageBox.warning(self, "提示", "请至少选择两个字段建立层级。")

    def _show_hierarchy_menu(self, pos):
        item = self.hierarchy_list.itemAt(pos)
        if not item: return
        
        menu = QMenu(self)
        act_del = menu.addAction("删除该层级")
        act = menu.exec(self.hierarchy_list.mapToGlobal(pos))
        
        if act == act_del:
            name = item.text()
            self.spec.hierarchies = [h for h in self.spec.hierarchies if h.name != name]
            self.hierarchy_list.takeItem(self.hierarchy_list.row(item))
            if self.spec.x_hierarchy and " > ".join(self.spec.x_hierarchy) == name:
                self.spec.x_hierarchy = None
                self.spec.x = None
                self.x_combo.set_field(None)
            self._rerender(reset_view=True)

    def _update_bucket_ui(self):
        while self.bucket_layout.count():
            item = self.bucket_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            if item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget(): sub.widget().deleteLater()

        if not self.store.is_loaded:
            return

        target_cols = []
        if self.spec.x_hierarchy: target_cols.extend(self.spec.x_hierarchy)
        elif self.spec.x: target_cols.append(self.spec.x)

        has_bucket = False
        for col in target_cols:
            if col in self.store.df.columns:
                is_dt = pd.api.types.is_datetime64_any_dtype(self.store.df[col])
                is_num = pd.api.types.is_numeric_dtype(self.store.df[col])
                
                if is_dt or is_num:
                    has_bucket = True
                    h = QHBoxLayout()
                    lbl = QLabel(f"{col}:")
                    lbl.setFixedWidth(80)
                    h.addWidget(lbl)
                    
                    if is_dt:
                        inp = QComboBox()
                        inp.addItems(["不分组", "1H", "1D", "W", "M", "Y"])
                        current_val = self.spec.bucket_settings.get(col, "不分组")
                        inp.setCurrentText(current_val if current_val in ["不分组", "1H", "1D", "W", "M", "Y"] else "不分组")
                        inp.currentTextChanged.connect(lambda text, c=col: self._set_bucket(c, "" if text == "不分组" else text))
                        h.addWidget(inp)
                    else:
                        inp = QLineEdit()
                        inp.setPlaceholderText("0 (不分桶)")
                        inp.setText(self.spec.bucket_settings.get(col, "0"))
                        inp.editingFinished.connect(lambda c=col, i=inp: self._set_bucket(c, i.text()))
                        h.addWidget(inp)
                        
                    self.bucket_layout.addLayout(h)
                    
        if not has_bucket:
            self.bucket_layout.addWidget(QLabel("当前 X 轴（或层级）没有可用的数值/时间字段。"))

    def _set_bucket(self, col, text):
        if self.spec.bucket_settings.get(col) != text:
            self.spec.bucket_settings[col] = text
            self._rerender(reset_view=True)

    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存项目", "", "DataPlot 项目 (*.dpj)")
        if not path: return
        
        spec_dict = asdict(self.spec)
        spec_dict["hidden_categories"] = list(self.spec.hidden_categories)
        
        py_script = self.data_source_dialog.saved_py_code if self.data_source_dialog else ""
        sql_script = self.data_source_dialog.saved_sql_code if self.data_source_dialog else ""
        
        # 核心修复：只要代码区有脚本，强制将来源标记为 db
        src_type = self.store.source_type
        if py_script.strip() or sql_script.strip():
            src_type = "db"

        data_source = {
            "type": src_type,
            "path": getattr(self.store, 'source_path', ''),
            "py_script": py_script,
            "sql_script": sql_script
        }
        
        project = {
            "version": "1.0",
            "spec": spec_dict,
            "data_source": data_source
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(project, f, ensure_ascii=False, indent=2)
            
        self._current_project_path = path
        self.statusBar().showMessage(f"项目已保存至: {path}")

    def _parse_spec_from_dict(self, data: dict) -> ChartSpec:
        series_list = []
        for s_dict in data.get("series", []):
            s_dict['chart_type'] = ChartType(s_dict.get('chart_type', 'scatter'))
            s_dict['axis'] = AxisSlot(s_dict.get('axis', 'left'))
            s_dict['agg'] = AggType(s_dict.get('agg', 'sum'))
            s_dict['size_agg'] = AggType(s_dict.get('size_agg', 'mean'))
            s_dict['color_theme'] = ColorTheme(s_dict.get('color_theme', 'default'))
            s_dict['hist_mode'] = HistogramMode(s_dict.get('hist_mode', 'overlay'))
            series_list.append(SeriesSpec(**s_dict))
            
        hier_list = []
        for h_dict in data.get("hierarchies", []):
            hier_list.append(HierarchySpec(**h_dict))
            
        hover_dict = {}
        for k, v in data.get("hover_fields", {}).items():
            hover_dict[k] = AggType(v)
            
        hidden_set = set(data.get("hidden_categories", []))
        buckets = data.get("bucket_settings", {})
        
        spec = ChartSpec(
            x=data.get("x"),
            x_hierarchy=data.get("x_hierarchy"),
            series=series_list,
            hover_fields=hover_dict,
            hidden_categories=hidden_set,
            facet_x=data.get("facet_x"),
            facet_y=data.get("facet_y"),
            bucket_settings=buckets,
            hierarchies=hier_list
        )
        return spec

    def _load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "", "DataPlot 项目 (*.dpj)")
        if not path: return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                project = json.load(f)
                
            data_source = project.get("data_source", {})
            spec_dict = project.get("spec", {})
            
            self.spec = self._parse_spec_from_dict(spec_dict)
            
            py_s = data_source.get("py_script", "")
            sql_s = data_source.get("sql_script", "")
            
            # 核心修复：只要脚本非空，绝对优先走异步加载
            if py_s.strip() or sql_s.strip():
                if self.data_source_dialog:
                    self.data_source_dialog.saved_py_code = py_s
                    self.data_source_dialog.saved_sql_code = sql_s
                    
                    # 核心修复：根据非空的脚本来决定使用哪种模式
                    if sql_s.strip() and not py_s.strip():
                        # 切换到 SQL 模式（会自动将 sql_s 填入编辑器）
                        self.data_source_dialog.mode_combo.setCurrentText("SQL")
                    else:
                        # 切换到 Python 模式（会自动将 py_s 填入编辑器）
                        self.data_source_dialog.mode_combo.setCurrentText("Python")
                        
                    self._is_loading_from_project = True
                    # 开启自动应用，这样 SQL 异步跑完就会自动传给主窗口
                    self.data_source_dialog.auto_apply = True
                    self.data_source_dialog._execute()
            elif data_source.get("type") == "local":
                file_path = data_source.get("path", "")
                if os.path.exists(file_path):
                    self.store.load(file_path)
                    self.store.source_type = "local"
                    self.store.source_path = file_path
                    self._refresh_all_ui_from_spec()
                else:
                    QMessageBox.warning(self, "提示", f"找不到本地数据文件:\n{file_path}")
            else:
                self._refresh_all_ui_from_spec()
            
            self.statusBar().showMessage(f"项目已加载: {path}")
            self._current_project_path = path
            
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            QMessageBox.critical(self, "错误", f"加载项目失败:\n{err}")

    def _on_x(self, field: str):
        if getattr(self, '_is_rebuilding_ui', False):
            return  # 核心修复：重建界面时忽略这个信号
        is_hier = False
        for h in self.spec.hierarchies:
            if h.name == field:
                is_hier = True
                self.spec.x_hierarchy = h.fields
                self.spec.x = None
                break
                
        if not is_hier:
            self.spec.x = field or None
            self.spec.x_hierarchy = None
            
        self._update_bucket_ui()
        self._rerender(reset_view=True)

    def _on_facet_x(self, field: str):
        if getattr(self, '_is_rebuilding_ui', False):
            return
        self.spec.facet_x = field or None
        self._rerender(reset_view=True)
        
    def _on_facet_y(self, field: str):
        if getattr(self, '_is_rebuilding_ui', False):
            return
        self.spec.facet_y = field or None
        self._rerender(reset_view=True)

    def _on_series_changed(self):
        if getattr(self, '_is_rebuilding_ui', False):
            return  # <-- 核心修复：在重建界面时，忽略信号
        self.spec.series = self.series_table.specs()
        current_count = len(self.spec.series)
        
        if current_count > self._last_series_count:
            self._last_series_count = current_count
            self._rerender(reset_view=False)
        else:
            self._last_series_count = current_count
            self._rerender(reset_view=False)

    def _on_legend_toggled(self, series_name, category):
        key = f"{series_name}||{category}"
        if key in self.spec.hidden_categories:
            self.spec.hidden_categories.remove(key)
        else:
            self.spec.hidden_categories.add(key)
        self._rerender(reset_view=False)

    def _on_type_changed(self, col: str, dtype: str):
        ok, err = self.store.convert_type(col, dtype)
        if not ok:
            QMessageBox.critical(self, "转换失败", f"字段 {col} 无法转换为 {dtype}：\n{err}")
        self._update_bucket_ui()
        self._rerender(reset_view=False)

    def _add_hover_field(self):
        field = self.hover_combo.currentText().strip()
        if field and field not in self.spec.hover_fields:
            self.spec.hover_fields[field] = AggType.MEAN
            self._refresh_hover_tags()
            self._rerender(reset_view=False)
        self.hover_combo.setCurrentIndex(-1)
        self.hover_combo.clearEditText()

    def _remove_hover_field(self, field):
        if field in self.spec.hover_fields:
            del self.spec.hover_fields[field]
            self._refresh_hover_tags()
            self._rerender(reset_view=False)
            
    def _on_hover_agg_changed(self, field, agg):
        if field in self.spec.hover_fields:
            self.spec.hover_fields[field] = agg
            self._rerender(reset_view=False)

    def _refresh_hover_tags(self):
        while self.hover_tags_layout.count():
            item = self.hover_tags_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
            
        for f, agg in self.spec.hover_fields.items():
            chip = HoverChip(f, agg, self._remove_hover_field, self._on_hover_agg_changed)
            self.hover_tags_layout.addWidget(chip)
        self.hover_tags_layout.addStretch()

    def _rerender(self, reset_view=False):
        # 核心修复：每次重绘前，强制把最新的 spec 同步给画布，防止对象脱钩
        self.canvas.spec = self.spec
        
        warnings = []
        
        if self.spec.x_hierarchy:
            for row in self.series_table._rows:
                if row.spec.agg == AggType.NONE:
                    row.spec.agg = AggType.COUNT
                    row.agg_combo.blockSignals(True)
                    row.agg_combo.setCurrentText("count")
                    row.agg_combo.blockSignals(False)
                    warnings.append(f"Y序列 '{row.spec.y}' 在层级模式下不支持不聚合，已自动改为 count。")
                if row.spec.size_agg == AggType.NONE:
                    row.spec.size_agg = AggType.MEAN
                    row.size_agg_combo.blockSignals(True)
                    row.size_agg_combo.setCurrentText("mean")
                    row.size_agg_combo.blockSignals(False)
                    warnings.append(f"大小字段在层级模式下不支持不聚合，已自动改为 mean。")
                    
            for hf, ha in self.spec.hover_fields.items():
                if ha == AggType.NONE:
                    self.spec.hover_fields[hf] = AggType.COUNT
                    for i in range(self.hover_tags_layout.count()):
                        w = self.hover_tags_layout.itemAt(i).widget()
                        if isinstance(w, HoverChip) and w.field == hf:
                            w.agg_combo.blockSignals(True)
                            w.agg_combo.setCurrentText("count")
                            w.agg_combo.blockSignals(False)
                    warnings.append(f"悬停字段 '{hf}' 在层级模式下不支持不聚合，已自动改为 count。")

        res = self.canvas.render(reset_view=reset_view) or ([], [])
        legends, canvas_warnings = res
        
        warnings.extend(canvas_warnings)
        
        if warnings:
            self.statusBar().showMessage("提示: " + " | ".join(list(set(warnings))))
        else:
            self.statusBar().showMessage("就绪")
            
        self.legend_panel.clear()
        for name, legend in legends:
            self.legend_panel.add_legend(name, legend, self.spec.hidden_categories)
        self.legend_panel.finalize()