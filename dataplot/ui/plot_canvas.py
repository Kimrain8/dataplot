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
        
        self.btn_float_up = QToolButton(self.layout_widget)
        self.btn_float_up.setText("↑")
        self.btn_float_up.setToolTip("向上移动所有浮动图形")
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
                        msg = f"悬停字段 '{hf}' 为文本，不支持 '{h_agg_name}' 聚合，已忽略。"
                        if msg not in warnings:
                            warnings.append(msg)
                    else:
                        valid_hover_fields[hf] = h_agg

            for idx, s in enumerate(self.spec.series):
                if s.chart_type != ChartType.HISTOGRAM and s.y is None: continue
                
                if s.chart_type != ChartType.HISTOGRAM and s.y:
                    is_y_numeric = pd.api.types.is_numeric_dtype(sub_df[s.y])
                    agg_name = s.agg.value if hasattr(s.agg, "value") else str(s.agg)
                    if not is_y_numeric and agg_name != "count":
                        msg = f"Y序列 '{s.y}' 为文本，不支持 '{agg_name}' 聚合，该序列未绘制。"
                        if msg not in warnings:
                            warnings.append(msg)
                        continue

                series_name = s.y or s.color or f"series_{idx}"
                is_series_hidden = f"{series_name}||" in self.spec.hidden_categories

                if s.axis == AxisSlot.LEFT:
                    vb = pi.vb
                    if s.y: left_y = s.y
                elif s.axis == AxisSlot.RIGHT:
                    vb = rvb
                    if s.y: right_y = s.y
                else:
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
                    if isinstance(result, list): 
                        for r in result:
                            r.vb = vb  # 动态绑定对应的 ViewBox
                        cell["rendered"].extend(result)
                    else: 
                        result.vb = vb
                        cell["rendered"].append(result)

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

        best_rs = None
        best_idx = -1
        min_px_dist = float('inf')

        for rs in rendered:
            vb = getattr(rs, "vb", None)
            if vb is None: continue
            
            # 将鼠标位置映射到该系列所属的具体 ViewBox 坐标系中
            pt = vb.mapSceneToView(pos)
            cur_mx, cur_my = pt.x(), pt.y()
            px_size_x, px_size_y = vb.viewPixelSize()
            
            if rs.tree is not None:
                # 散点图：二维距离
                dist, idx = rs.tree.query([cur_mx, cur_my])
                dx_px = (rs.x[idx] - cur_mx) / px_size_x if px_size_x > 0 else 0
                dy_px = (rs.y[idx] - cur_my) / px_size_y if px_size_y > 0 else 0
                px_dist = np.hypot(dx_px, dy_px)
            elif rs.sorted_x is not None and len(rs.sorted_x) > 0:
                # 折线图/柱状图：找最近的 X 轴点
                idx = np.searchsorted(rs.sorted_x, cur_mx)
                idx = min(max(idx, 0), len(rs.sorted_x) - 1)
                if idx > 0 and abs(rs.sorted_x[idx-1] - cur_mx) < abs(rs.sorted_x[idx] - cur_mx):
                    idx -= 1
                
                rx, ry = rs.sorted_x[idx], rs.sorted_y[idx]
                dx_px = (rx - cur_mx) / px_size_x if px_size_x > 0 else 0
                dy_px = (ry - cur_my) / px_size_y if px_size_y > 0 else 0
                
                if rs.spec.chart_type == ChartType.BAR:
                    # 柱状图：只要水平在柱子范围附近即可
                    if abs(dx_px) < 20:
                        px_dist = abs(dx_px)
                    else:
                        px_dist = np.hypot(dx_px, dy_px)
                else:
                    # 折线图：靠近折线点
                    px_dist = np.hypot(dx_px, dy_px)
                    
            if px_dist < min_px_dist:
                min_px_dist = px_dist
                best_rs = rs
                best_idx = idx

        if best_rs is not None and min_px_dist < 25:
            row = best_rs.data.iloc[best_idx]
            
            # 提取真实的 X 轴显示值
            if "x" in row:
                x_val = row["x"]
            elif "x_plot" in row:
                x_val = row["x_plot"]
            else:
                x_val = best_rs.sorted_x[best_idx]

            if self.x_labels is not None:
                idx_x = int(round(x_val))
                display_x = self.x_labels[idx_x] if 0 <= idx_x < len(self.x_labels) else str(x_val)
            else:
                display_x = f"{x_val:.4g}"

            x_col_name = self.spec.x or "X"
            lines = [f"<b>{x_col_name} = {display_x}</b>"]
            
            name = best_rs.spec.y or best_rs.spec.chart_type.value
            if "y" in row:
                y_val = row["y"]
            elif "y_plot" in row:
                y_val = row["y_plot"]
            else:
                y_val = row.get(best_rs.spec.y, 0)
                
            if isinstance(y_val, (float, int, np.number)):
                y_val_str = f"{y_val:.4g}"
            else:
                y_val_str = str(y_val)

            label = name
            if best_rs.spec.color and "c" in row:
                label += f" ({row['c']})"
                
            lines.append(f"<b>{label}: {y_val_str}</b>")
            
            for hf in self.spec.hover_fields:
                if hf in row:
                    val = row[hf]
                    if isinstance(val, (float, int, np.number)):
                        val_str = f"{val:.4g}"
                    else:
                        val_str = str(val)
                    lines.append(f"{hf}: {val_str}")

            self.tooltip.setText("<br>".join(lines))
            self.tooltip.adjustSize()
            local = self.layout_widget.mapFromScene(pos)
            self.tooltip.move(local.x() + 14, local.y() + 14)
            self.tooltip.show()
        else:
            self.tooltip.hide()