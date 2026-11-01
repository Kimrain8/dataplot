import numpy as np
import pandas as pd
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph import Vector
from PySide6.QtCore import QTimer

def _add_axes_and_grid(gl_widget: gl.GLViewWidget):
    """核心新增：添加红绿蓝 XYZ 坐标轴以及底面网格"""
    # 1. 坐标轴线（范围设为 -6 到 6，覆盖数据归一化后的 [-5, 5] 空间）
    # X 轴（红色）
    x_axis = gl.GLLinePlotItem(pos=np.array([[-6, 0, 0], [6, 0, 0]]), color=(1, 0, 0, 1), width=2, antialias=True)
    # Y 轴（绿色）
    y_axis = gl.GLLinePlotItem(pos=np.array([[0, -6, 0], [0, 6, 0]]), color=(0, 1, 0, 1), width=2, antialias=True)
    # Z 轴（蓝色）
    z_axis = gl.GLLinePlotItem(pos=np.array([[0, 0, -6], [0, 0, 6]]), color=(0, 0, 1, 1), width=2, antialias=True)
    
    gl_widget.addItem(x_axis)
    gl_widget.addItem(y_axis)
    gl_widget.addItem(z_axis)
    
    # 2. 尝试添加文字标签 (视 pyqtgraph 版本而定)
    try:
        x_text = gl.GLTextItem(pos=(6.5, 0, 0), text="X", color=(255, 0, 0, 255))
        y_text = gl.GLTextItem(pos=(0, 6.5, 0), text="Y", color=(0, 255, 0, 255))
        z_text = gl.GLTextItem(pos=(0, 0, 6.5), text="Z", color=(0, 0, 255, 255))
        gl_widget.addItem(x_text)
        gl_widget.addItem(y_text)
        gl_widget.addItem(z_text)
    except Exception:
        pass # 如果该版本不支持 GLTextItem 则静默跳过

    # 3. 添加底部网格（放置在 Z = -5 的底面上，方便观察高度）
    grid = gl.GLGridItem()
    grid.setSize(x=12, y=12)
    grid.setSpacing(x=1, y=1)
    grid.translate(0, 0, -5) 
    gl_widget.addItem(grid)


def render_3d_surface(gl_widget: gl.GLViewWidget, df: pd.DataFrame, scatter_mode=False):
    gl_widget.clear()
    
    z = df.values
    n_rows, n_cols = z.shape
    
    x_vals = np.arange(n_cols)
    y_vals = np.arange(n_rows)
    
    z_valid = z[np.isfinite(z)]
    if len(z_valid) == 0: return
    
    # 各向独立归一化到 [-5, 5]
    span_x = max(1e-9, np.max(x_vals) - np.min(x_vals))
    span_y = max(1e-9, np.max(y_vals) - np.min(y_vals))
    span_z = max(1e-9, np.max(z_valid) - np.min(z_valid))
    
    x_norm = (x_vals - np.mean(x_vals)) * (10.0 / span_x)
    y_norm = (y_vals - np.mean(y_vals)) * (10.0 / span_y)
    z_norm = (z.T - np.mean(z_valid)) * (10.0 / span_z)

    # 统一颜色映射
    cmap = pg.ColorMap([0.0, 0.5, 1.0], [(60,130,220), (240,200,80), (220,70,70)])

    if not scatter_mode:
        # 曲面模式
        z_flat = z_norm.flatten()
        qcolors = cmap.map((z_flat - np.min(z_flat)) / (np.max(z_flat) - np.min(z_flat) + 1e-9), mode='qcolor')
        colors_arr = np.array([[c.redF(), c.greenF(), c.blueF(), 1.0] for c in qcolors], dtype=np.float32)
        colors_arr = colors_arr.reshape((n_cols, n_rows, 4))
        
        surf = gl.GLSurfacePlotItem(x=x_norm, y=y_norm, z=z_norm, colors=colors_arr, smooth=True)
        gl_widget.addItem(surf)
    else:
        # 散点模式
        xs, ys, zs = [], [], []
        for r in range(n_rows):
            for c in range(n_cols):
                if np.isfinite(z[r, c]):
                    xs.append(x_norm[c])
                    ys.append(y_norm[r])
                    zs.append(z_norm[c, r])
                    
        pts = np.vstack([xs, ys, zs]).transpose()
        z_arr = np.array(zs)
        colors = cmap.map((z_arr - np.min(z_arr)) / (np.max(z_arr) - np.min(z_arr) + 1e-9), mode='float').astype(np.float32)
        
        scatter = gl.GLScatterPlotItem(pos=pts, color=colors, size=3, pxMode=True)
        gl_widget.addItem(scatter)

    # 核心新增：加上坐标轴和网格
    _add_axes_and_grid(gl_widget)
    
    gl_widget.setCameraPosition(pos=Vector(0, 0, 0), distance=25)


def render_3d_scatter(gl_widget: gl.GLViewWidget, df: pd.DataFrame, x_col: str, y_col: str, z_col: str, c_col: str = None):
    gl_widget.clear()
    try:
        x = pd.to_numeric(df[x_col], errors='coerce').values
        y = pd.to_numeric(df[y_col], errors='coerce').values
        z = pd.to_numeric(df[z_col], errors='coerce').values
        mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        x, y, z = x[mask], y[mask], z[mask]
        
        if len(x) == 0: return
        
        # 各向独立归一化
        span_x = max(1e-9, np.max(x) - np.min(x))
        span_y = max(1e-9, np.max(y) - np.min(y))
        span_z = max(1e-9, np.max(z) - np.min(z))
        x_norm = (x - np.mean(x)) * (10.0 / span_x)
        y_norm = (y - np.mean(y)) * (10.0 / span_y)
        z_norm = (z - np.mean(z)) * (10.0 / span_z)
        
        colors = np.ones((len(x), 4), dtype=np.float32)
        colors[:, :3] = 0.2
        
        if c_col and c_col in df.columns:
            c_vals = df[c_col].values[mask]
            if pd.api.types.is_numeric_dtype(df[c_col]):
                c_vals = pd.to_numeric(c_vals, errors='coerce')
                vmin, vmax = np.nanmin(c_vals), np.nanmax(c_vals)
                if vmax == vmin: vmax += 1e-9
                cmap = pg.ColorMap([0, 1], [(0, 0, 255, 255), (255, 0, 0, 255)])
                colors = cmap.map((c_vals - vmin) / (vmax - vmin), mode='float').astype(np.float32)
            else:
                cats, codes = np.unique(c_vals.astype(str), return_inverse=True)
                palette = [
                    (0.12, 0.47, 0.71, 1.0), (1.0, 0.5, 0.05, 1.0),
                    (0.17, 0.63, 0.17, 1.0), (0.84, 0.15, 0.16, 1.0),
                    (0.58, 0.40, 0.74, 1.0), (0.55, 0.34, 0.29, 1.0),
                    (0.89, 0.47, 0.76, 1.0), (0.50, 0.50, 0.50, 1.0)
                ]
                colors = np.array([palette[c % len(palette)] for c in codes], dtype=np.float32)
                
        pts = np.vstack([x_norm, y_norm, z_norm]).transpose()
        scatter = gl.GLScatterPlotItem(pos=pts, color=colors, size=3, pxMode=True)
        gl_widget.addItem(scatter)
        
        # 核心新增：加上坐标轴和网格
        _add_axes_and_grid(gl_widget)
        
        gl_widget.setCameraPosition(pos=Vector(0, 0, 0), distance=25)
    except Exception as e:
        print(f"❌ 3D 渲染发生异常: {e}")

class PairsAnimator:
    def __init__(self, plot_item, df: pd.DataFrame, idx_dict: dict, interval_ms=800):
        self.plot_item = plot_item
        self.idx_dict = idx_dict
        self.anim_frames = sorted(list(idx_dict.keys()))
        self.anim_idx = 0
        
        self.x = pd.to_numeric(df.iloc[:, 0], errors='coerce').values
        self.y = pd.to_numeric(df.iloc[:, 1], errors='coerce').values
        mask = np.isfinite(self.x) & np.isfinite(self.y)
        self.x, self.y = self.x[mask], self.y[mask]
        
        self.base_colors = np.zeros((len(self.x), 4), dtype=float)
        self.base_colors[:, 3] = 1.0
        self.base_colors[:, :3] = 0.1  # 深灰色
        
        self.scatter = pg.ScatterPlotItem(x=self.x, y=self.y, size=10, brush=[pg.mkBrush(*c) for c in self.base_colors])
        self.plot_item.addItem(self.scatter)
        self.plot_item.autoRange()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        
    def start(self):
        if self.anim_frames:
            self.timer.start(800)
            
    def stop(self):
        self.timer.stop()
        
    def _tick(self):
        if not self.anim_frames: return
        
        colors = np.zeros((len(self.x), 4), dtype=float)
        colors[:, 3] = 1.0
        colors[:, :3] = 0.1
        
        if self.anim_idx < len(self.anim_frames):
            key = self.anim_frames[self.anim_idx]
            pt_indices = self.idx_dict[key]
            for i in pt_indices:
                if i < len(colors): colors[i] = [1, 0, 0, 1]
            self.anim_idx += 1
        else:
            self.anim_idx = 0
            
        self.scatter.setBrush([pg.mkBrush(*c) for c in colors])