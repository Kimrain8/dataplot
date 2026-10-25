from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import pyqtgraph as pg


SIZE_MIN = 4.0
SIZE_MAX = 20.0
DEFAULT_SIZE = 8

THEME_CMAPS = {
    "default": [(60, 130, 220), (240, 200, 80), (220, 70, 70)],
    "viridis": [(68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98), (253, 231, 37)],
    "plasma": [(13, 8, 135), (126, 3, 168), (204, 71, 120), (248, 149, 64), (240, 249, 33)],
    "coolwarm": [(59, 76, 192), (144, 160, 236), (221, 221, 221), (244, 154, 123), (180, 4, 38)],
    "magma": [(0, 0, 4), (81, 18, 124), (183, 55, 121), (252, 137, 97), (252, 253, 191)],
    "inferno": [(0, 0, 4), (87, 15, 109), (188, 55, 84), (249, 142, 8), (252, 255, 164)],
    "cividis": [(0, 32, 76), (42, 84, 117), (88, 129, 128), (156, 174, 105), (255, 234, 70)],
}

SERIES_COLORS = [
    (60, 130, 220), (220, 70, 70), (70, 180, 100), (240, 180, 60),
    (150, 90, 200), (80, 200, 200), (200, 120, 60), (120, 120, 220),
]


@dataclass
class ColorLegend:
    title: str
    kind: str  # "categorical" | "continuous"
    entries: list[tuple[str, tuple[int, int, int]]] = field(default_factory=list)
    vmin: float = 0.0
    vmax: float = 0.0


def series_default_brush(index: int):
    rgb = SERIES_COLORS[index % len(SERIES_COLORS)]
    return pg.mkBrush(*rgb, 170), rgb


def _interpolate_color(theme_colors: list[tuple[int,int,int]], t: float) -> tuple[int, int, int]:
    n = len(theme_colors)
    if n == 1: return theme_colors[0]
    pos = t * (n - 1)
    idx = int(pos)
    if idx >= n - 1: return theme_colors[-1]
    frac = pos - idx
    c1, c2 = theme_colors[idx], theme_colors[idx+1]
    return (
        int(c1[0] + (c2[0] - c1[0]) * frac),
        int(c1[1] + (c2[1] - c1[1]) * frac),
        int(c1[2] + (c2[2] - c1[2]) * frac)
    )


def get_color_mapping(df: pd.DataFrame, color_col: str | None, theme_name: str = "default"):
    if not color_col or color_col not in df.columns:
        return None, None
        
    theme_colors = THEME_CMAPS.get(theme_name, THEME_CMAPS["default"])
    cmap = pg.ColorMap(np.linspace(0, 1, len(theme_colors)), theme_colors)
    
    series = df[color_col]
    if pd.api.types.is_numeric_dtype(series):
        vals = _fill_median(series.to_numpy(dtype=float))
        vmin, vmax = float(vals.min()), float(vals.max())
        c_map = {"type": "continuous", "vmin": vmin, "vmax": vmax, "cmap": cmap}
        
        # 数值型生成 20 个区间的图例
        entries = []
        for i in range(20):
            v0 = vmin + (vmax - vmin) * (i / 20)
            v1 = vmin + (vmax - vmin) * ((i + 1) / 20)
            mid_t = (i + 0.5) / 20
            rgb = _interpolate_color(theme_colors, mid_t)
            entries.append((f"{v0:.4g} ~ {v1:.4g}", rgb))
            
        return c_map, ColorLegend(color_col, "categorical", entries=entries)
    else:
        filled = series.astype("object").where(series.notna(), "<缺失>").astype(str)
        uniques = filled.unique()
        n = len(uniques)
        if n == 0: return None, None
        
        color_dict = {}
        for i, u in enumerate(uniques):
            t = i / max(1, n - 1) if n > 1 else 0.5
            rgb = _interpolate_color(theme_colors, t)
            color_dict[u] = rgb
            
        entries = []
        if n <= 20:
            for i, u in enumerate(uniques):
                entries.append((str(u), color_dict[u]))
        else:
            # 类别型合并为 20 个区间
            for i in range(20):
                start_idx = int(i * n / 20)
                end_idx = int((i + 1) * n / 20) - 1
                if end_idx >= n: end_idx = n - 1
                mid_idx = (start_idx + end_idx) // 2
                rgb = color_dict[uniques[mid_idx]]
                entries.append((f"{uniques[start_idx]} ~ {uniques[end_idx]}", rgb))
                
        c_map = {"type": "categorical", "map": color_dict}
        return c_map, ColorLegend(color_col, "categorical", entries=entries)


def make_brushes(df: pd.DataFrame, color_col: str | None, default_index: int, color_map: dict | None):
    if color_col is None or color_col not in df.columns:
        if color_map and "base_rgb" in color_map:
            rgb = color_map["base_rgb"]
        else:
            rgb = SERIES_COLORS[default_index % len(SERIES_COLORS)]
        return pg.mkBrush(*rgb, 170)

    series = df[color_col]
    if pd.api.types.is_numeric_dtype(series):
        vals = _fill_median(series.to_numpy(dtype=float))
        vmin = color_map.get("vmin", 0)
        vmax = color_map.get("vmax", 1)
        cmap = color_map.get("cmap")
        t = np.zeros_like(vals) if vmax == vmin else (vals - vmin) / (vmax - vmin)
        rgb = cmap.map(t, mode="byte")[:, :3]
        return [pg.mkBrush(*c, 170) for c in rgb]

    brushes = []
    for val in series.astype("object").where(series.notna(), "<缺失>").astype(str):
        rgb = color_map["map"].get(val, (100, 100, 100))
        brushes.append(pg.mkBrush(*rgb, 170))
    return brushes


def make_sizes(df: pd.DataFrame, size_col: str | None):
    if size_col is None or not pd.api.types.is_numeric_dtype(df[size_col]):
        return DEFAULT_SIZE
    vals = _fill_median(df[size_col].to_numpy(dtype=float))
    vmin, vmax = float(vals.min()), float(vals.max())
    if vmax == vmin:
        return DEFAULT_SIZE
    t = (vals - vmin) / (vmax - vmin)
    return SIZE_MIN + t * (SIZE_MAX - SIZE_MIN)


def _fill_median(vals):
    m = np.nanmedian(vals)
    if not np.isfinite(m):
        m = 0.0
    return np.where(np.isfinite(vals), vals, m)