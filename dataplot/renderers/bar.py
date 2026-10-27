import numpy as np
import pandas as pd
import pyqtgraph as pg

from dataplot.core.encoding import series_default_brush, SERIES_COLORS, make_sizes
from dataplot.core.spec import SeriesSpec
from dataplot.renderers.base import RenderedSeries, SeriesRenderer, get_x_values


class BarRenderer(SeriesRenderer):
    def render(self, plot_item, viewbox, df, x_col, series: SeriesSpec, context=None):
        if x_col is None or series.y is None:
            return None
        ctx = context or {}
        n_series = max(ctx.get("bar_count", 1), 1)
        s_idx = ctx.get("bar_index", 0)

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

        if df_temp.empty:
            return None

        if agg_name != "none":
            def _get_agg(a):
                return (lambda x: x.max() - x.min()) if a == "range" else a
                
            agg_dict = {"y": _get_agg(agg_name)}
            if series.size and series.size in df_temp.columns:
                sz_agg = series.size_agg.value
                agg_dict[series.size] = _get_agg(sz_agg if sz_agg != "none" else "first")
            
            hover_fields = ctx.get("hover_fields", {})
            for hf, h_agg in hover_fields.items():
                if hf in df_temp.columns:
                    h_agg_name = h_agg.value if hasattr(h_agg, "value") else str(h_agg)
                    if not pd.api.types.is_numeric_dtype(df_temp[hf]) and h_agg_name in ["mean", "sum", "var", "std", "range"]:
                        h_agg_name = "first"
                    agg_dict[hf] = _get_agg(h_agg_name if h_agg_name != "none" else "first")
            
            extra_cols = [c for c in df_temp.columns if c not in ["x", "y", "c"] and c not in agg_dict]
            for col in extra_cols:
                agg_dict[col] = "first"
                
            agg_df = df_temp.groupby(["x", "c"], observed=True).agg(agg_dict).reset_index()
        else:
            agg_df = df_temp.copy()

        if agg_df.empty: return None

        # px_size_x, _ = viewbox.viewPixelSize()
        # min_w_data = 3.0 * abs(px_size_x) if px_size_x != 0 else 0.0

        if labels is not None:
            base_width = 1.0
        else:
            unique_x = np.sort(agg_df["x"].unique())
            if len(unique_x) > 1:
                diffs = np.diff(unique_x)
                base_width = np.min(diffs) if len(diffs) > 0 else 1.0
            else:
                base_width = 1.0

        unique_colors = agg_df["c"].unique()
        c_map = ctx.get("color_map") or {}
        default_idx = ctx.get("index", 0)
        
        base_rgb = c_map.get("base_rgb", SERIES_COLORS[default_idx % len(SERIES_COLORS)])

        if series.size and series.size in agg_df:
            sz_vals = agg_df[series.size].to_numpy(dtype=float)
            sz_min, sz_max = np.nanmin(sz_vals), np.nanmax(sz_vals)
            if sz_max > sz_min:
                width_ratios = 0.2 + 0.7 * (sz_vals - sz_min) / (sz_max - sz_min)
            else:
                width_ratios = np.full(len(sz_vals), 0.6)
        else:
            width_ratios = np.full(len(agg_df), 0.8)

        agg_df["x_draw"] = agg_df["x"]
        results = []
        
        if agg_name == "none":
            agg_df["idx"] = agg_df.groupby(["x", "c"]).cumcount()
            max_idx = agg_df["idx"].max() + 1 if not agg_df.empty else 1
            
            for i in range(len(agg_df)):
                row = agg_df.iloc[i]
                w = base_width * width_ratios[i] / (n_series * max(1, max_idx))
                # if w < min_w_data: w = min_w_data
                # 高度直接用真实数值，绝不篡改
                h = row["y"]
                
                offset = (s_idx - (n_series - 1) / 2) * w
                x_draw = row["x"] + offset + (row["idx"] - (max_idx - 1) / 2) * w
                agg_df.loc[agg_df.index[i], "x_draw"] = x_draw
                
                rgb = c_map.get("map", {}).get(row["c"], base_rgb) if series.color else base_rgb
                bar = pg.BarGraphItem(x=[x_draw], height=[h], width=w, brush=pg.mkBrush(*rgb, 200), pen=pg.mkPen("w", width=1))
                viewbox.addItem(bar)
        else:
            if series.color:
                for x_val in agg_df["x"].unique():
                    sub_x = agg_df[agg_df["x"] == x_val]
                    n_c = len(sub_x)
                    for j, (idx, row) in enumerate(sub_x.iterrows()):
                        w = base_width * width_ratios[idx] / (n_series * n_c)
                        # if w < min_w_data: w = min_w_data
                        h = row["y"]
                            
                        group_w = w * n_c
                        offset = (s_idx - (n_series - 1) / 2) * group_w
                        c_offset = (j - (n_c - 1) / 2) * w
                        
                        x_draw = row["x"] + offset + c_offset
                        agg_df.loc[idx, "x_draw"] = x_draw
                        
                        rgb = c_map.get("map", {}).get(row["c"], base_rgb)
                        bar = pg.BarGraphItem(x=[x_draw], height=[h], width=w, brush=pg.mkBrush(*rgb, 200), pen=pg.mkPen("w", width=1))
                        viewbox.addItem(bar)
            else:
                for i in range(len(agg_df)):
                    row = agg_df.iloc[i]
                    w = base_width * width_ratios[i] / n_series
                    # if w < min_w_data: w = min_w_data
                    h = row["y"]
                        
                    offset = (s_idx - (n_series - 1) / 2) * w
                    x_draw = row["x"] + offset
                    agg_df.loc[agg_df.index[i], "x_draw"] = x_draw
                    
                    bar = pg.BarGraphItem(x=[x_draw], height=[h], width=w, brush=pg.mkBrush(*base_rgb, 200), pen=pg.mkPen("w", width=1))
                    viewbox.addItem(bar)

        agg_df = agg_df.sort_values("x_draw").reset_index(drop=True)
        results.append(RenderedSeries(series, agg_df["x_draw"].values, agg_df["y"].values, None, agg_df["x_draw"].values, agg_df["y"].values, agg_df))
        return results