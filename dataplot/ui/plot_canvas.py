import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QToolButton, QScrollArea

from dataplot.core.spec import AxisSlot, ChartType, ChartSpec
from dataplot.renderers.registry import get_renderer
from dataplot.core.encoding import get_color_mapping, ColorLegend, THEME_CMAPS


class CustomGraphicsLayoutWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctrl_panning = False
        self._last_pos = None

    def mousePressEvent(self, ev):
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier and ev.button() == Qt.MouseButton.LeftButton:
            self._ctrl_panning = True
            self._last_pos = ev.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._ctrl_panning:
            delta = ev.pos() - self._last_pos
            self._last_pos = ev.pos()
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
                
            if isinstance(scroll_area, QScrollArea):
                h_bar = scroll_area.horizontalScrollBar()
                v_bar = scroll_area.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
            ev.accept()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._ctrl_panning:
            self._ctrl_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            ev.accept()
        else:
            super().mouseReleaseEvent(ev)


class PlotCanvas(QWidget):
    def __init__(self, store, spec: ChartSpec, parent=None):
        super().__init__(parent)
        self.store = store
        self.spec = spec
        self.x_labels = None
        self.cells = []
        self.cell_size = 400

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.layout_widget = CustomGraphicsLayoutWidget()
        self.layout_widget.setBackground("w")
        self.scroll_area.setWidget(self.layout_widget)
        
        self.tooltip = QLabel(self.layout_widget)
        self.tooltip.setStyleSheet("background: rgba(255,255,255,235); border: 1px solid #888; padding: 4px; font-size: 11px;")
        self.tooltip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.tooltip.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

        btn_style = (
            "QToolButton { background: rgba(255,255,255,0.85); border: 1px solid #aaa; "
            "border-radius: 4px; padding: 4px; font-size: 14px; font-weight: bold; }"
            "QToolButton:hover { background: #e0e0e0; }"
        )
        btn_active_style = (
            "QToolButton { background: #bfdbfe; border: 1px solid #3b82f6; "
            "border-radius: 4px; padding: 4px; font-size: 14px; font-weight: bold; }"
        )
        
        self.btn_reset = QToolButton(self.layout_widget)
        self.btn_reset.setText("↺")
        self.btn_reset.setToolTip("适应窗口")
        self.btn_reset.setStyleSheet(btn_style)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self._reset_view)
        
        self.btn_rect = QToolButton(self.layout_widget)
        self.btn_rect.setText("⬚")
        self.btn_rect.setToolTip("框选放大")
        self.btn_rect.setStyleSheet(btn_style)
        self.btn_rect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rect.clicked.connect(self._toggle_rect_mode)
        
        # 浮动图上下平移控制按钮
        self.btn_float_up = QToolButton(self.layout_widget)
        self.btn_float_up.setText("↑")
        self.btn_float_up.setToolTip("向上移动所有浮动图形（也可以直接在图上左键拖拽浮动图形）")
        self.btn_float_up.setStyleSheet(btn_style)
        self.btn_float_up.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_float_up.clicked.connect(lambda: self._shift_float_y(0.1))
        
        self.btn_float_down = QToolButton(self.layout_widget)
        self.btn_float_down.setText("↓")
        self.btn_float_down.setToolTip("向下移动所有浮动图形")
        self.btn_float_down.setStyleSheet(btn_style)
        self.btn_float_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_float_down.clicked.connect(lambda: self._shift_float_y(-0.1))
        
        self._btn_style = btn_style
        self._btn_active_style = btn_active_style
        self._rect_mode = False
        
        self.btn_reset.show()
        self.btn_rect.show()
        self.btn_float_up.hide()
        self.btn_float_down.hide()

        self.layout_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)
        
        # 启动时渲染欢迎图表
        self._render_welcome()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "btn_reset"):
            w = self.layout_widget.width()
            self.btn_reset.move(w - 105, 10)
            self.btn_rect.move(w - 70, 10)
            self.btn_float_up.move(w - 35, 10)
            self.btn_float_down.move(w - 35, 45)

    def _cleanup_cells(self):
        for cell in self.cells:
            rvb = cell.get("right_vb")
            if rvb:
                rvb.clear()
                if rvb.scene():
                    rvb.scene().removeItem(rvb)
            for vb in cell.get("floating_vbs", []):
                vb.clear()
                if vb.scene():
                    vb.scene().removeItem(vb)
        self.cells.clear()
        self.layout_widget.clear()

    def _render_welcome(self):
        """渲染酷炫的洛伦兹吸引子欢迎背景"""
        self._cleanup_cells()
        self.layout_widget.setMinimumSize(0, 0)
        self.layout_widget.setMaximumSize(16777215, 16777215)
        
        pi = self.layout_widget.addPlot(row=0, col=0)
        pi.hideAxis('left')
        pi.hideAxis('bottom')
        pi.setAspectLocked(True)
        pi.setMouseEnabled(x=False, y=False)
        
        # 计算洛伦兹吸引子
        dt = 0.005
        sigma, rho, beta = 10.0, 28.0, 8.0/3.0
        x, y, z = 1.0, 1.0, 1.0
        xs, ys = [], []
        for i in range(15000):
            dx = sigma * (y - x)
            dy = x * (rho - z) - y
            dz = x * y - beta * z
            x += dx * dt
            y += dy * dt
            z += dz * dt
            if i > 1000:
                xs.append(x)
                ys.append(z)  # 取 X-Z 投影
                
        cmap = pg.ColorMap([0, 0.5, 1], [(60, 130, 220), (240, 200, 80), (220, 70, 70)])
        t = np.linspace(0, 1, len(xs))
        colors = cmap.map(t, mode='byte')
        brushes = [pg.mkBrush(*c[:3], 180) for c in colors]
        
        scatter = pg.ScatterPlotItem(x=xs, y=ys, size=2, brush=brushes, pen=None)
        pi.addItem(scatter)
        
        text = pg.TextItem(
            "DataPlot\n\n请在上方工具栏点击「加载文件」\n支持 CSV / XLSX / PKL",
            color=(80, 80, 80), anchor=(0.5, 0.5)
        )
        font = text.textItem.font()
        font.setPointSize(16)
        font.setBold(True)
        text.setFont(font)
        text.setPos(np.mean(xs), np.mean(ys))
        pi.addItem(text)
        
        self.btn_float_up.hide()
        self.btn_float_down.hide()

    def _reset_view(self):
        for cell in self.cells:
            cell["plot_item"].vb.autoRange()
            if cell["right_vb"]: cell["right_vb"].autoRange()
            for vb in cell["floating_vbs"]: vb.autoRange()

    def _toggle_rect_mode(self):
        self._rect_mode = not self._rect_mode
        mode = pg.ViewBox.RectMode if self._rect_mode else pg.ViewBox.PanMode
        for cell in self.cells:
            cell["plot_item"].vb.setMouseMode(mode)
        self.btn_rect.setStyleSheet(self._btn_active_style if self._rect_mode else self._btn_style)

    def _shift_float_y(self, ratio):
        for cell in self.cells:
            for vb in cell.get("floating_vbs", []):
                y_range = vb.viewRange()[1]
                y_center = (y_range[0] + y_range[1]) / 2
                y_span = y_range[1] - y_range[0]
                new_center = y_center + y_span * ratio
                vb.setYRange(new_center - y_span/2, new_center + y_span/2, padding=0)

    def _sync_cell_vb(self, cell):
        pi = cell["plot_item"]
        rvb = cell["right_vb"]
        rect = pi.vb.sceneBoundingRect()
        if rvb is not None:
            rvb.setGeometry(rect)
            rvb.linkedViewChanged(pi.vb, rvb.XAxis)
        for vb in cell["floating_vbs"]:
            vb.setGeometry(rect)
            vb.linkedViewChanged(pi.vb, vb.XAxis)

    def render(self):
        if not self.store.is_loaded:
            self._render_welcome()
            return [], []

        self._cleanup_cells()
        self.tooltip.hide()

        x_col = self.spec.x
        self.x_labels = None
        if x_col:
            from dataplot.renderers.base import get_x_values
            _, labels = get_x_values(self.store.df, x_col)
            self.x_labels = labels

        if x_col is None: return [], []

        df = self.store.df
        facets = [(None, None)]
        if self.spec.facet_x or self.spec.facet_y:
            df_f = df.copy()
            fx = self.spec.facet_x
            fy = self.spec.facet_y
            if fx: df_f[fx] = df_f[fx].fillna("<缺失>").astype(str)
            if fy: df_f[fy] = df_f[fy].fillna("<缺失>").astype(str)
            
            if fx and fy:
                facets = df_f.groupby([fy, fx], sort=False).size().index.tolist()
            elif fx:
                facets = [(None, v) for v in df_f[fx].unique()]
            else:
                facets = [(v, None) for v in df_f[fy].unique()]
                
        n_cols = len(set(c[1] for c in facets)) if self.spec.facet_x else 1
        n_rows = (len(facets) + n_cols - 1) // n_cols
        
        has_facet_x = bool(self.spec.facet_x)
        has_facet_y = bool(self.spec.facet_y)
        
        if has_facet_x and has_facet_y:
            self.layout_widget.setFixedSize(n_cols * self.cell_size, n_rows * self.cell_size)
        elif has_facet_x:
            self.layout_widget.setFixedWidth(n_cols * self.cell_size)
            self.layout_widget.setMinimumHeight(0)
            self.layout_widget.setMaximumHeight(16777215)
        elif has_facet_y:
            self.layout_widget.setFixedHeight(n_rows * self.cell_size)
            self.layout_widget.setMinimumWidth(0)
            self.layout_widget.setMaximumWidth(16777215)
        else:
            self.layout_widget.setMinimumSize(0, 0)
            self.layout_widget.setMaximumSize(16777215, 16777215)
        
        w = self.layout_widget.width()
        self.btn_reset.move(w - 105, 10)
        self.btn_rect.move(w - 70, 10)
        self.btn_float_up.move(w - 35, 10)
        self.btn_float_down.move(w - 35, 45)

        global_legends = {}
        warnings = []
        has_float = False
        
        for i, (fy_val, fx_val) in enumerate(facets):
            row = i // n_cols
            col = i % n_cols
            
            pi = self.layout_widget.addPlot(row=row, col=col)
            pi.showGrid(x=True, y=True, alpha=0.3)
            
            has_left = any(s.axis == AxisSlot.LEFT for s in self.spec.series)
            has_right = any(s.axis == AxisSlot.RIGHT for s in self.spec.series)

            if row > 0: pi.getAxis("bottom").setStyle(showValues=False)
            if col > 0: pi.getAxis("left").setStyle(showValues=False)
            
            pi.showAxis("left", has_left and col == 0)
            pi.showAxis("right", has_right and col == n_cols - 1)
            
            if self.spec.facet_x or self.spec.facet_y:
                title = []
                if fx_val is not None: title.append(f"{self.spec.facet_x}: {fx_val}")
                if fy_val is not None: title.append(f"{self.spec.facet_y}: {fy_val}")
                pi.setTitle(" | ".join(title))

            rvb = pg.ViewBox()
            pi.scene().addItem(rvb)
            pi.getAxis("right").linkToView(rvb)
            rvb.setXLink(pi.vb)
            rvb.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            
            cell = {"plot_item": pi, "right_vb": rvb, "floating_vbs": [], "rendered": []}
            self.cells.append(cell)
            
            pi.vb.sigResized.connect(lambda *args, c=cell: self._sync_cell_vb(c))
            
            if i > 0: pi.setXLink(self.cells[0]["plot_item"])

            sub_df = df
            if fx_val is not None: sub_df = sub_df[sub_df[self.spec.facet_x].fillna("<缺失>").astype(str) == fx_val]
            if fy_val is not None: sub_df = sub_df[sub_df[self.spec.facet_y].fillna("<缺失>").astype(str) == fy_val]
            if sub_df.empty: continue

            bar_counts = {}
            for s in self.spec.series:
                if s.chart_type == ChartType.BAR: bar_counts[s.axis] = bar_counts.get(s.axis, 0) + 1

            bar_seen = {AxisSlot.LEFT: 0, AxisSlot.RIGHT: 0, AxisSlot.FLOATING: 0}
            left_y, right_y = None, None

            valid_hover_fields = {}
            for hf, h_agg in self.spec.hover_fields.items():
                if hf in sub_df.columns:
                    h_agg_name = h_agg.value if hasattr(h_agg, "value") else str(h_agg)
                    if not pd.api.types.is_numeric_dtype(sub_df[hf]) and h_agg_name in ["mean", "sum", "var", "std"]:
                        msg = f"字段 '{hf}' 为文本，不支持 '{h_agg_name}' 聚合，已忽略。"
                        if msg not in warnings:
                            warnings.append(msg)
                    else:
                        valid_hover_fields[hf] = h_agg

            for idx, s in enumerate(self.spec.series):
                if s.chart_type != ChartType.HISTOGRAM and s.y is None: continue

                series_name = s.y or s.color or f"series_{idx}"
                is_series_hidden = f"{series_name}||" in self.spec.hidden_categories

                if s.axis == AxisSlot.LEFT:
                    vb = pi.vb
                    if s.y: left_y = s.y
                elif s.axis == AxisSlot.RIGHT:
                    vb = rvb
                    if s.y: right_y = s.y
                else:
                    # 核心修改：浮动轴允许鼠标左键上下拖动，关闭 X 轴移动
                    vb = pg.ViewBox()
                    pi.scene().addItem(vb)
                    vb.setXLink(pi.vb)
                    vb.setMouseEnabled(x=False, y=True)
                    vb.setMouseMode(pg.ViewBox.PanMode)
                    vb.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
                    cell["floating_vbs"].append(vb)
                    has_float = True

                context = {"index": idx, "bar_index": 0, "bar_count": 1, "hover_fields": valid_hover_fields}
                if s.chart_type == ChartType.BAR:
                    context["bar_index"] = bar_seen[s.axis]
                    context["bar_count"] = bar_counts.get(s.axis, 1)
                    bar_seen[s.axis] += 1

                c_map, c_legend = get_color_mapping(df, s.color, s.color_theme.value)
                if not c_legend:
                    theme_colors = THEME_CMAPS.get(s.color_theme.value, THEME_CMAPS["default"])
                    base_rgb = theme_colors[len(theme_colors)//2]
                    c_map = {"base_rgb": base_rgb}
                    c_legend = ColorLegend(series_name, "solid", entries=[("", base_rgb)])
                
                context["color_map"] = c_map
                if series_name not in global_legends: global_legends[series_name] = c_legend

                renderer = get_renderer(s.chart_type)
                if renderer is None: continue

                s_df = sub_df
                if s.color:
                    hidden_cats = [k.split("||")[1] for k in self.spec.hidden_categories if k.startswith(f"{series_name}||") and k != f"{series_name}||"]
                    if hidden_cats:
                        s_col = s_df[s.color].fillna("<缺失>").astype(str)
                        s_df = s_df[~s_col.isin(hidden_cats)].copy()

                if is_series_hidden or s_df.empty: continue

                result = renderer.render(pi, vb, s_df, x_col, s, context)
                if result:
                    if isinstance(result, list): cell["rendered"].extend(result)
                    else: cell["rendered"].append(result)

            if col == 0 and left_y: pi.setLabel("left", left_y)
            if col == n_cols - 1 and has_right and right_y: pi.getAxis("right").setLabel(right_y)
                
            pi.vb.autoRange(padding=0.05)
            rvb.autoRange(padding=0.05)
            for vb in cell["floating_vbs"]: vb.autoRange(padding=0.05)
            self._sync_cell_vb(cell)

        if has_float:
            self.btn_float_up.show()
            self.btn_float_down.show()
        else:
            self.btn_float_up.hide()
            self.btn_float_down.hide()

        return [(name, leg) for name, leg in global_legends.items()], warnings

    def _on_mouse_moved(self, pos):
        active_cell = None
        for cell in self.cells:
            if cell["plot_item"].sceneBoundingRect().contains(pos):
                active_cell = cell
                break
        if active_cell is None:
            self.tooltip.hide(); return

        pi = active_cell["plot_item"]
        rendered = active_cell["rendered"]
        if not rendered:
            self.tooltip.hide(); return

        mouse_pt = pi.vb.mapSceneToView(pos)
        mx, my = mouse_pt.x(), mouse_pt.y()
        px_size_x, px_size_y = pi.vb.viewPixelSize()
        
        snapped_x = None
        for rs in rendered:
            if rs.spec.chart_type == ChartType.SCATTER and rs.tree is not None:
                dist, idx = rs.tree.query([mx, my])
                dx_px = (rs.x[idx] - mx) / px_size_x if px_size_x > 0 else 0
                dy_px = (rs.y[idx] - my) / px_size_y if px_size_y > 0 else 0
                if np.sqrt(dx_px**2 + dy_px**2) < 15:
                    snapped_x = rs.x[idx]
                    break
        
        x_data = snapped_x if snapped_x is not None else mx
        if self.x_labels is not None:
            idx = int(round(x_data))
            if 0 <= idx < len(self.x_labels):
                display_x = self.x_labels[idx]
                x_data = float(idx)
            else:
                display_x = str(x_data)
        else:
            display_x = f"{x_data:.4g}"

        x_col_name = self.spec.x or "X"
        lines = [f"<b>{x_col_name} = {display_x}</b>"]
        
        for rs in rendered:
            hit = False
            row = None
            
            if rs.spec.chart_type == ChartType.SCATTER and rs.tree is not None:
                dist, idx = rs.tree.query([x_data, my])
                dx_px = (rs.x[idx] - x_data) / px_size_x if px_size_x > 0 else 0
                dy_px = (rs.y[idx] - my) / px_size_y if px_size_y > 0 else 0
                if np.sqrt(dx_px**2 + dy_px**2) < 15:
                    hit = True
                    row = rs.data.iloc[idx]
            else:
                if rs.sorted_x is not None and len(rs.sorted_x) > 0:
                    idx = np.searchsorted(rs.sorted_x, x_data)
                    idx = min(max(idx, 0), len(rs.sorted_x) - 1)
                    if idx > 0 and abs(rs.sorted_x[idx-1] - x_data) < abs(rs.sorted_x[idx] - x_data):
                        idx -= 1
                    
                    x_near = rs.sorted_x[idx]
                    view_range = pi.vb.viewRange()
                    x_span = view_range[0][1] - view_range[0][0]
                    
                    if self.x_labels is not None:
                        if round(x_near) == round(x_data): hit = True
                    else:
                        if x_span > 0 and abs(x_near - x_data) <= x_span * 0.02: hit = True
                            
                    if hit and rs.data is not None and idx < len(rs.data):
                        row = rs.data.iloc[idx]
            
            if hit and row is not None:
                name = rs.spec.y or rs.spec.chart_type.value
                y_val = row.get(rs.spec.y, row.get("y", 0))
                label = name
                if rs.spec.color and "c" in row:
                    label += f" ({row['c']})"
                lines.append(f"<b>{label}: {y_val:.4g}</b>")
                
                for hf in self.spec.hover_fields:
                    if hf in row:
                        val = row[hf]
                        if isinstance(val, float): val = f"{val:.4g}"
                        lines.append(f"{hf}: {val}")

        if len(lines) == 1:
            self.tooltip.hide(); return

        self.tooltip.setText("<br>".join(lines))
        self.tooltip.adjustSize()
        local = self.layout_widget.mapFromScene(pos)
        self.tooltip.move(local.x() + 14, local.y() + 14)
        self.tooltip.show()