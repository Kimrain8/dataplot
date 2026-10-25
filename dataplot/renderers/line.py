import numpy as np
import pandas as pd
import pyqtgraph as pg

from dataplot.core.encoding import SERIES_COLORS, make_sizes
from dataplot.core.spec import AxisSlot, SeriesSpec
from dataplot.renderers.base import RenderedSeries, SeriesRenderer, get_x_values
from dataplot.renderers.scatter import _normalize


class LineRenderer(SeriesRenderer):
    def render(self, plot_item, viewbox, df, x_col, series: SeriesSpec, context=None):
        if x_col is None or series.y is None:
            return None
            
        x_vals, labels = get_x_values(df, x_col)
        if labels is not None:
            plot_item.getAxis("bottom").setTicks([list(zip(range(len(labels)), labels))])
        else:
            plot_item.getAxis("bottom").setTicks(None)

        agg_name = series.agg.value if hasattr(series.agg, "value") else str(series.agg)
        is_y_numeric = pd.api.types.is_numeric_dtype(df[series.y])
        
        if not is_y_numeric and agg_name != "count":
            return None
            
        if agg_name == "count":
            y = np.ones(len(df), dtype=float)
            mask = np.isfinite(x_vals) & df[series.y].notna().to_numpy()
        else:
            y = pd.to_numeric(df[series.y], errors="coerce").to_numpy(dtype=float)
            mask = np.isfinite(x_vals) & np.isfinite(y)
            
        if not mask.any(): return None
        
        df_temp = df.loc[mask].copy()
        df_temp["x"] = x_vals[mask]
        df_temp["y"] = y[mask]
        
        if series.bin_width > 0 and labels is None:
            df_temp["x"] = (df_temp["x"] // series.bin_width) * series.bin_width
        
        if series.color:
            df_temp["c"] = df_temp[series.color].fillna("<缺失>").astype(str).values
        else:
            df_temp["c"] = "all"

        c_map = context.get("color_map") or {}
        default_idx = context.get("index", 0)
        base_rgb = c_map.get("base_rgb", SERIES_COLORS[default_idx % len(SERIES_COLORS)])
        
        results = []
        unique_colors = df_temp["c"].unique()
        
        for c_val in unique_colors:
            sub_df = df_temp[df_temp["c"] == c_val]
            if sub_df.empty: continue

            if agg_name != "none":
                agg_dict = {"y": agg_name}
                if series.size:
                    sz_agg = series.size_agg.value
                    agg_dict[series.size] = sz_agg if sz_agg != "none" else "first"
                    
                hover_fields = context.get("hover_fields", {})
                for hf, h_agg in hover_fields.items():
                    if hf in sub_df.columns:
                        h_agg_name = h_agg.value if hasattr(h_agg, "value") else str(h_agg)
                        if not pd.api.types.is_numeric_dtype(sub_df[hf]) and h_agg_name in ["mean", "sum", "var", "std"]:
                            h_agg_name = "first"
                        agg_dict[hf] = h_agg_name if h_agg_name != "none" else "first"
                
                extra_cols = [c for c in sub_df.columns if c not in ["x", "y", "c"] and c not in agg_dict]
                for col in extra_cols:
                    agg_dict[col] = "first"
                    
                if agg_name == "range":
                    agg_dict["y"] = lambda x: x.max() - x.min()
                    
                agg_df = sub_df.groupby("x", observed=True).agg(agg_dict).reset_index().sort_values("x").reset_index(drop=True)
            else:
                agg_df = sub_df.sort_values("x").reset_index(drop=True)
            
            x_v = agg_df["x"].to_numpy(dtype=float)
            y_v = agg_df["y"].to_numpy(dtype=float)
            
            if series.axis == AxisSlot.FLOATING:
                y_v = _normalize(y_v)

            if series.color:
                rgb = c_map.get("map", {}).get(c_val, base_rgb)
            else:
                rgb = base_rgb

            # 核心修复：加入 connect='finite' 保证含有 NaN 的数据也能跨越连接
            pen = pg.mkPen(rgb, width=2)
            item = pg.PlotCurveItem(x_v, y_v, pen=pen, connect='finite')
            viewbox.addItem(item)

            if series.size and series.size in agg_df:
                sizes = make_sizes(agg_df, series.size)
                scatter = pg.ScatterPlotItem(
                    x=x_v, y=y_v, size=sizes, brush=pg.mkBrush(*rgb, 200),
                    pen=pg.mkPen("w", width=1), pxMode=True
                )
                viewbox.addItem(scatter)

            results.append(RenderedSeries(series, x_v, y_v, None, x_v, y_v, agg_df))
            
        return results