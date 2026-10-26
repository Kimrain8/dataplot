import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QToolButton, QScrollArea, QMenu

from dataplot.core.spec import AxisSlot, ChartType, ChartSpec, AggType
from dataplot.renderers.registry import get_renderer
from dataplot.core.encoding import get_color_mapping, ColorLegend, THEME_CMAPS
from dataplot.config import HOVER_TOLERANCE_PX, TOOLTIP_OFFSET_X, TOOLTIP_OFFSET_Y

class AngledAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle(tickTextOffset=10)

    def drawPicture(self, p, axisSpec, tickSpecs, textSpecs):
        # 核心修复：兼容新版 pyqtgraph 的元组解包结构 (pen, p1, p2)
        p.setRenderHint(p.RenderHint.Antialiasing, False)
        p.setRenderHint(p.RenderHint.TextAntialiasing, True)
        
        # 绘制轴线
        pen, p1, p2 = axisSpec
        p.setPen(pen)
        p.drawLine(p1, p2)
        
        # 绘制刻度
        for tick in tickSpecs:
            pen, p1, p2 = tick
            p.setPen(pen)
            p.drawLine(p1, p2)
            
        # 绘制倾斜文本
        p.setPen(self.textPen())
        p.setFont(self.font())
        for rect, flags, text in textSpecs:
            p.save()
            # 将原点移动至刻度的正下方
            p.translate(rect.center().x(), rect.top())
            p.rotate(-45) 
            # 在原点处右对齐、顶对齐绘制文本（确保文本往左下角延伸，不覆盖轴线）
            p.drawText(QRectF(-200, 0, 200, 50), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, text)
            p.restore()

class PlotCanvas(QWidget):
    def __init__(self, store, spec: ChartSpec, parent=None):
        super().__init__(parent)
        self.store = store
        self.spec = spec
        self.cells = []
        self.cell_size = 400
        self._saved_ranges = None
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.layout_widget = pg.GraphicsLayoutWidget()
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
            "QToolButton::menu-indicator { image: none; }"
        )
        btn_active_style = (
            "QToolButton { background: #bfdbfe; border: 1px solid #3b82f6; "
            "border-radius: 4px; padding: 4px; font-size: 14px; font-weight: bold; }"
        )
        
        self.btn_reset = QToolButton(self.layout_widget)
        self.btn_reset.setText("↺")
        self.btn_reset.setToolTip("适应窗口")
        self.btn_reset.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_reset.setStyleSheet(btn_style)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.reset_menu = QMenu(self.btn_reset)
        self.btn_reset.setMenu(self.reset_menu)
        self.reset_menu.aboutToShow.connect(self._build_reset_menu)
        
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

    def _build_reset_menu(self):
        self.reset_menu.clear()
        act_all = self.reset_menu.addAction("适应全部")
        act_all.triggered.connect(self._reset_view)
        if not self.spec.series: return
        self.reset_menu.addSeparator()
        seen_y = set()
        for s in self.spec.series:
            if not s.y or s.y in seen_y: continue
            seen_y.add(s.y)
            label = f"{s.y} ({s.axis.value})"
            act = self.reset_menu.addAction(label)
            act.triggered.connect(lambda checked=False, spec=s: self._reset_view_specific(spec))

    def _cleanup_cells(self):
        for cell in self.cells:
            rvb = cell.get("right_vb")
            if rvb:
                rvb.clear()
                if rvb.scene(): rvb.scene().removeItem(rvb)
            for vb in cell.get("floating_vbs", []):
                vb.clear()
                if vb.scene(): vb.scene().removeItem(vb)
        self.cells.clear()
        self.layout_widget.clear()

    def _save_current_ranges(self):
        if not self.cells: return
        saved = []
        for c in self.cells:
            s = {
                "main": c["plot_item"].vb.viewRange(),
                "right": c["right_vb"].viewRange() if c["right_vb"] else None,
                "floats": [vb.viewRange() for vb in c["floating_vbs"]]
            }
            saved.append(s)
        self._saved_ranges = saved

    def _reset_view(self):
        self._saved_ranges = None
        for cell in self.cells:
            cell["plot_item"].vb.autoRange()
            if cell["right_vb"]: cell["right_vb"].autoRange()
            for vb in cell["floating_vbs"]: vb.autoRange()
        self._save_current_ranges()

    def _reset_view_specific(self, target_spec):
        all_matching_rs = []
        for cell in self.cells:
            for rs in cell["rendered"]:
                if rs.spec == target_spec: all_matching_rs.append(rs)
        if not all_matching_rs: return
        x_vals = []
        for rs in all_matching_rs: x_vals.extend(rs.x[np.isfinite(rs.x)])
        if not x_vals: return
        x_min, x_max = min(x_vals), max(x_vals)
        if x_min == x_max: x_min -= 1; x_max += 1
            
        for cell in self.cells:
            cell_rs = [rs for rs in cell["rendered"] if rs.spec == target_spec]
            if not cell_rs: continue
            y_vals = []
            for rs in cell_rs: y_vals.extend(rs.y[np.isfinite(rs.y)])
            if not y_vals: continue
            y_min, y_max = min(y_vals), max(y_vals)
            if y_min == y_max: y_min -= 1; y_max += 1
                
            pi = cell["plot_item"]
            cur_y = pi.vb.viewRange()[1]  # 暂存当前的左轴Y范围
            
            #下面备注部分是原来的代码
            if target_spec.axis == AxisSlot.RIGHT:
                # 核心修复：仅改变 X 轴和右轴，强行锁定左轴 Y 范围
                pi.vb.setRange(xRange=(x_min, x_max), yRange=cur_y, padding=0.05)
                if cell["right_vb"]: 
                    cell["right_vb"].setYRange(y_min, y_max, padding=0.05)
            elif target_spec.axis == AxisSlot.LEFT:
                # 改变 X 轴和左轴
                pi.vb.setRange(xRange=(x_min, x_max), yRange=(y_min, y_max), padding=0.05)
            else:
                # 仅改变 X 轴和浮动轴，强行锁定左轴 Y 范围
                pi.vb.setRange(xRange=(x_min, x_max), yRange=cur_y, padding=0.05)
                for fvb in cell["floating_vbs"]: 
                    fvb.setYRange(y_min, y_max, padding=0.05)
            # pi.vb.setXRange(x_min, x_max, padding=0.05)
            # if target_spec.axis == AxisSlot.LEFT:
            #     pi.vb.setYRange(y_min, y_max, padding=0.05)
            # elif target_spec.axis == AxisSlot.RIGHT:
            #     if cell["right_vb"]: cell["right_vb"].setYRange(y_min, y_max, padding=0.05)
            # else:
            #     for fvb in cell["floating_vbs"]: fvb.setYRange(y_min, y_max, padding=0.05)
        self._save_current_ranges()

    def _toggle_rect_mode(self):
        self._rect_mode = not self._rect_mode
        mode = pg.ViewBox.RectMode if self._rect_mode else pg.ViewBox.PanMode
        for cell in self.cells: cell["plot_item"].vb.setMouseMode(mode)
        self.btn_rect.setStyleSheet(self._btn_active_style if self._rect_mode else self._btn_style)

    def _shift_float_y(self, ratio):
        for cell in self.cells:
            for vb in cell.get("floating_vbs", []):
                y_range = vb.viewRange()[1]
                y_center = (y_range[0] + y_range[1]) / 2
                y_span = y_range[1] - y_range[0]
                new_center = y_center + y_span * ratio
                vb.setYRange(new_center - y_span/2, new_center + y_span/2, padding=0)
        self._save_current_ranges()

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

    def _process_data(self, df):
        is_hierarchy = bool(self.spec.x_hierarchy)
        
        if is_hierarchy:
            for s in self.spec.series:
                if s.agg == AggType.NONE: s.agg = AggType.COUNT
                if s.size_agg == AggType.NONE: s.size_agg = AggType.MEAN
            for hf, ha in self.spec.hover_fields.items():
                if ha == AggType.NONE: self.spec.hover_fields[hf] = AggType.COUNT

        # 时间与数值分桶
        for col, bucket in self.spec.bucket_settings.items():
            if col in df.columns and bucket and bucket != "不分组":
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    try:
                        # 核心修复：直接格式化为字符串，供 get_x_values 识别为类别
                        if bucket == "1H": df[col] = df[col].dt.strftime("%Y-%m-%d %H:00")
                        elif bucket == "1D": df[col] = df[col].dt.strftime("%Y-%m-%d")
                        elif bucket == "W": df[col] = df[col].dt.to_period('W').dt.start_time.dt.strftime("%Y-%m-%d")
                        elif bucket == "M": df[col] = df[col].dt.strftime("%Y-%m")
                        elif bucket == "Y": df[col] = df[col].dt.strftime("%Y")
                    except Exception:
                        pass
                elif pd.api.types.is_numeric_dtype(df[col]):
                    try:
                        w = float(bucket)
                        if w > 0: df[col] = (df[col] // w) * w
                    except:
                        pass
                    
        if is_hierarchy:
            valid_cols = [c for c in self.spec.x_hierarchy if c in df.columns]
            if valid_cols:
                df["__x_layer__"] = df[valid_cols].astype(str).agg(" > ".join, axis=1)
                self.spec.x = "__x_layer__"
            else:
                self.spec.x = None
        else:
            if "__x_layer__" in df.columns:
                df.drop(columns=["__x_layer__"], inplace=True)
        return df

    def render(self, reset_view=False):
        # print("\n>>> DEBUG: 进入 PlotCanvas.render")
        if not self.store.is_loaded:
            # print(">>> DEBUG: store 未加载，直接返回")
            return [], []
        # if not self.store.is_loaded: return [], []

        if not reset_view: self._save_current_ranges()
        else: self._saved_ranges = None

        self._cleanup_cells()
        self.tooltip.hide()

        df = self._process_data(self.store.df.copy())
        x_col = self.spec.x
        self.x_labels = None
        # print(f">>> DEBUG: 画布 X 字段: {x_col}")
        # print(f">>> DEBUG: 画布数据列: {df.columns.tolist()[:10]}")
        if x_col and x_col in df.columns:
            from dataplot.renderers.base import get_x_values
            _, labels = get_x_values(df, x_col)
            self.x_labels = labels
        elif not x_col:
            return [], []

        facets = [(None, None)]
        if self.spec.facet_x or self.spec.facet_y:
            df_f = df.copy()
            fx = self.spec.facet_x
            fy = self.spec.facet_y
            if fx: df_f[fx] = df_f[fx].fillna("<缺失>").astype(str)
            if fy: df_f[fy] = df_f[fy].fillna("<缺失>").astype(str)
            
            if fx and fy: facets = df_f.groupby([fy, fx], sort=False).size().index.tolist()
            elif fx: facets = [(None, v) for v in df_f[fx].unique()]
            else: facets = [(v, None) for v in df_f[fy].unique()]
                
        n_cols = len(set(c[1] for c in facets)) if self.spec.facet_x else 1
        n_rows = (len(facets) + n_cols - 1) // n_cols
        has_facet_x, has_facet_y = bool(self.spec.facet_x), bool(self.spec.facet_y)
        
        if has_facet_x and has_facet_y:
            self.layout_widget.setFixedSize(n_cols * self.cell_size, n_rows * self.cell_size)
        elif has_facet_x:
            self.layout_widget.setFixedWidth(n_cols * self.cell_size)
            self.layout_widget.setMinimumHeight(0); self.layout_widget.setMaximumHeight(16777215)
        elif has_facet_y:
            self.layout_widget.setFixedHeight(n_rows * self.cell_size)
            self.layout_widget.setMinimumWidth(0); self.layout_widget.setMaximumWidth(16777215)
        else:
            self.layout_widget.setMinimumSize(0, 0); self.layout_widget.setMaximumSize(16777215, 16777215)
        
        w = self.layout_widget.width()
        self.btn_reset.move(w - 105, 10); self.btn_rect.move(w - 70, 10)
        self.btn_float_up.move(w - 35, 10); self.btn_float_down.move(w - 35, 45)

        global_legends, warnings, has_float = {}, [], False
        
        for i, (fy_val, fx_val) in enumerate(facets):
            row, col = i // n_cols, i % n_cols
            pi = self.layout_widget.addPlot(row=row, col=col)
            pi.showGrid(x=True, y=True, alpha=0.3)
            
            # 注入自定义倾斜 X 轴
            axis = AngledAxisItem(orientation='bottom')
            pi.setAxisItems({'bottom': axis})
            
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
                        if msg not in warnings: warnings.append(msg)
                    else:
                        valid_hover_fields[hf] = h_agg

            for idx, s in enumerate(self.spec.series):
                if s.chart_type != ChartType.HISTOGRAM and s.y is None: 
                    continue
                
                if s.chart_type != ChartType.HISTOGRAM and s.y:
                    is_y_numeric = pd.api.types.is_numeric_dtype(sub_df[s.y])
                    agg_name = s.agg.value if hasattr(s.agg, "value") else str(s.agg)
                    if not is_y_numeric and agg_name != "count":
                        msg = f"Y序列 '{s.y}' 为文本，不支持 '{agg_name}' 聚合，该序列未绘制。"
                        if msg not in warnings: warnings.append(msg)
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
                        for r in result: r.vb = vb
                        cell["rendered"].extend(result)
                    else: 
                        result.vb = vb
                        cell["rendered"].append(result)

            if col == 0 and left_y: pi.setLabel("left", left_y)
            if col == n_cols - 1 and has_right and right_y: pi.getAxis("right").setLabel(right_y)

            if self._saved_ranges and i < len(self._saved_ranges):
                sr = self._saved_ranges[i]
                # 核心修复：使用 setRange 同时锁定 X 和 Y，防止 pyqtgraph 内部触发联动适应
                if sr["main"]:
                    pi.vb.setRange(
                        xRange=(sr["main"][0][0], sr["main"][0][1]), 
                        yRange=(sr["main"][1][0], sr["main"][1][1]), 
                        padding=0
                    )
                
                if rvb and sr.get("right"):
                    rvb.setYRange(sr["right"][1][0], sr["right"][1][1], padding=0)
                elif rvb and has_right and not sr.get("right"):
                    rvb.autoRange(padding=0.05)  # 新加的右轴自动适应
                
                for j, fvb in enumerate(cell["floating_vbs"]):
                    if sr.get("floats") and j < len(sr["floats"]):
                        fr = sr["floats"][j]
                        fvb.setYRange(fr[1][0], fr[1][1], padding=0)
                    elif not sr.get("floats") or j >= len(sr["floats"]):
                        fvb.autoRange(padding=0.05)  # 新加的浮动轴自动适应
                        
            else:
                has_drawn_left, has_drawn_right, has_drawn_float = False, False, False
                for rs in cell["rendered"]:
                    ax = rs.spec.axis
                    if ax == AxisSlot.LEFT and not has_drawn_left:
                        pi.vb.autoRange(padding=0.05); has_drawn_left = True
                    elif ax == AxisSlot.RIGHT and not has_drawn_right and rvb:
                        rvb.autoRange(padding=0.05); has_drawn_right = True
                    elif ax == AxisSlot.FLOATING and not has_drawn_float:
                        for fvb in cell["floating_vbs"]: fvb.autoRange(padding=0.05)
                        has_drawn_float = True
                if not has_drawn_left and not has_drawn_right and not has_drawn_float:
                    pi.vb.autoRange(padding=0.05)

            self._sync_cell_vb(cell)

        self._save_current_ranges()
        if has_float: self.btn_float_up.show(); self.btn_float_down.show()
        else: self.btn_float_up.hide(); self.btn_float_down.hide()

        return [(name, leg) for name, leg in global_legends.items()], warnings

    def _on_mouse_moved(self, pos):
        active_cell = None
        for cell in self.cells:
            if cell["plot_item"].sceneBoundingRect().contains(pos):
                active_cell = cell
                break
        if active_cell is None:
            self.tooltip.hide(); return

        rendered = active_cell["rendered"]
        if not rendered:
            self.tooltip.hide(); return

        best_rs, best_idx, min_dist = None, -1, float('inf')

        for rs in rendered:
            vb = getattr(rs, "vb", None)
            if vb is None: continue
            
            if rs.tree is not None:
                pt = vb.mapSceneToView(pos)
                k = min(50, len(rs.x))
                dists, idxs = rs.tree.query([pt.x(), pt.y()], k=k)
                if k == 1: idxs = [idxs]
                
                for idx in idxs:
                    scene_pt = vb.mapViewToScene(QPointF(rs.x[idx], rs.y[idx]))
                    dx = scene_pt.x() - pos.x()
                    dy = scene_pt.y() - pos.y()
                    px_dist = np.hypot(dx, dy)
                    
                    if px_dist < min_dist:
                        min_dist = px_dist
                        best_rs = rs
                        best_idx = idx
            elif rs.sorted_x is not None and len(rs.sorted_x) > 0:
                pt = vb.mapSceneToView(pos)
                idx = np.searchsorted(rs.sorted_x, pt.x())
                idx = min(max(idx, 0), len(rs.sorted_x) - 1)
                if idx > 0 and abs(rs.sorted_x[idx-1] - pt.x()) < abs(rs.sorted_x[idx] - pt.x()):
                    idx -= 1
                
                scene_pt = vb.mapViewToScene(QPointF(rs.sorted_x[idx], rs.sorted_y[idx]))
                dx = scene_pt.x() - pos.x()
                dy = scene_pt.y() - pos.y()
                px_dist = np.hypot(dx, dy)
                
                if rs.spec.chart_type == ChartType.BAR:
                    if abs(dx) < 30: px_dist = abs(dx) if abs(dx) > 0 else 0
                    
                if px_dist < min_dist:
                    min_dist = px_dist
                    best_rs = rs
                    best_idx = idx

        # 阈值 15，贴近鼠标
        if best_rs is not None and min_dist < HOVER_TOLERANCE_PX:
            row = best_rs.data.iloc[best_idx]
            
            if "x" in row: x_val = row["x"]
            elif "x_plot" in row: x_val = row["x_plot"]
            else: x_val = best_rs.sorted_x[best_idx]

            if self.x_labels is not None:
                idx_x = int(round(x_val))
                display_x = self.x_labels[idx_x] if 0 <= idx_x < len(self.x_labels) else str(x_val)
            else:
                if isinstance(x_val, pd.Timestamp):
                    bucket = self.spec.bucket_settings.get(self.spec.x, "不分组")
                    if bucket == "Y": display_x = x_val.strftime("%Y")
                    elif bucket == "M": display_x = x_val.strftime("%Y-%m")
                    elif bucket in ("W", "D"): display_x = x_val.strftime("%Y-%m-%d")
                    elif bucket == "1H": display_x = x_val.strftime("%Y-%m-%d %H:00")
                    else: display_x = x_val.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    display_x = f"{x_val:.4g}"

            x_col_name = self.spec.x or "X"
            lines = [f"<b>{x_col_name} = {display_x}</b>"]
            
            name = best_rs.spec.y or best_rs.spec.chart_type.value
            if "y" in row: y_val = row["y"]
            elif "y_plot" in row: y_val = row["y_plot"]
            else: y_val = row.get(best_rs.spec.y, 0)
                
            if isinstance(y_val, (float, int, np.number)): y_val_str = f"{y_val:.4g}"
            else: y_val_str = str(y_val)

            label = name
            if best_rs.spec.color and "c" in row: label += f" ({row['c']})"
            lines.append(f"<b>{label}: {y_val_str}</b>")
            
            for hf in self.spec.hover_fields:
                if hf in row:
                    val = row[hf]
                    if isinstance(val, (float, int, np.number)): val_str = f"{val:.4g}"
                    else: val_str = str(val)
                    lines.append(f"{hf}: {val_str}")

            self.tooltip.setText("<br>".join(lines))
            self.tooltip.adjustSize()
            local = self.layout_widget.mapFromScene(pos)
            # 偏移量改为 7，贴近鼠标
            self.tooltip.move(local.x() + TOOLTIP_OFFSET_X, local.y() + TOOLTIP_OFFSET_Y)
            self.tooltip.show()
        else:
            self.tooltip.hide()