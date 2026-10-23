import numpy as np
import pandas as pd
import pyqtgraph as pg
from scipy.spatial import cKDTree

from dataplot.core.encoding import make_brushes, make_sizes
from dataplot.core.spec import AxisSlot, SeriesSpec
from dataplot.renderers.base import RenderedSeries, SeriesRenderer, get_x_values


def _normalize(v):
    vmin, vmax = float(np.nanmin(v)), float(np.nanmax(v))
    if vmax == vmin: return np.full_like(v, 0.5)
    return (v - vmin) / (vmax - vmin)


class ScatterRenderer(SeriesRenderer):
    def render(self, plot_item, viewbox, df, x_col, series: SeriesSpec, context=None):
        if x_col is None or series.y is None: return None
        
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
        df_temp["x_plot"] = x_vals[mask]
        df_temp["y_plot"] = y[mask]
        
        if series.bin_width > 0 and labels is None:
            df_temp["x_plot"] = (df_temp["x_plot"] // series.bin_width) * series.bin_width
        
        if series.color:
            df_temp["c"] = df_temp[series.color].fillna("<缺失>").astype(str).values
        else:
            df_temp["c"] = "all"

        if agg_name != "none":
            agg_dict = {"y_plot": agg_name}
            if series.size:
                sz_agg = series.size_agg.value
                agg_dict[series.size] = sz_agg if sz_agg != "none" else "first"
            
            hover_fields = context.get("hover_fields", {})
            for hf, h_agg in hover_fields.items():
                if hf in df_temp.columns:
                    h_agg_name = h_agg.value if hasattr(h_agg, "value") else str(h_agg)
                    if not pd.api.types.is_numeric_dtype(df_temp[hf]) and h_agg_name in ["mean", "sum", "var", "std"]:
                        h_agg_name = "first"
                    agg_dict[hf] = h_agg_name if h_agg_name != "none" else "first"

            extra_cols = [c for c in df_temp.columns if c not in ["x_plot", "y_plot", "c"] and c not in agg_dict]
            for col in extra_cols:
                agg_dict[col] = "first"
                
            if agg_name == "range":
                agg_dict["y_plot"] = lambda x: x.max() - x.min()
                
            df_agg = df_temp.groupby(["x_plot", "c"], observed=True).agg(agg_dict).reset_index()
        else:
            df_agg = df_temp.copy()

        df_agg = df_agg.reset_index(drop=True)
        plot_x = df_agg["x_plot"].to_numpy(dtype=float)
        plot_y = df_agg["y_plot"].to_numpy(dtype=float)
        
        if series.axis == AxisSlot.FLOATING:
            plot_y = _normalize(plot_y)

        c_map = context.get("color_map")
        brushes = make_brushes(df_agg, series.color, context.get("index", 0), c_map)
        sizes = make_sizes(df_agg, series.size)

        item = pg.ScatterPlotItem(
            x=plot_x, y=plot_y, size=sizes, brush=brushes, pen=pg.mkPen(None), pxMode=True,
        )
        viewbox.addItem(item)

        tree = cKDTree(np.column_stack((plot_x, plot_y)))
        
        order = np.argsort(plot_x)
        sorted_df = df_agg.iloc[order].reset_index(drop=True)
        
        return [RenderedSeries(series, plot_x, plot_y, None, plot_x[order], plot_y[order], sorted_df, tree)]