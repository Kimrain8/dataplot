import numpy as np
import pandas as pd
import pyqtgraph as pg

from dataplot.core.encoding import series_default_brush
from dataplot.core.spec import HistogramMode, SeriesSpec
from dataplot.renderers.base import RenderedSeries, SeriesRenderer


class HistogramRenderer(SeriesRenderer):
    def render(self, plot_item, viewbox, df, x_col, series: SeriesSpec, context=None):
        col = series.y
        if col is None or not pd.api.types.is_numeric_dtype(df[col]):
            return None
        vals = pd.to_numeric(df[col], errors="coerce").dropna().to_numpy(dtype=float)
        if len(vals) == 0:
            return None

        counts, edges = np.histogram(vals, bins="auto")
        ctx = context or {}
        _, rgb = series_default_brush(ctx.get("index", 0))
        alpha = 200 if series.hist_mode == HistogramMode.GROUPED else 110
        bar = pg.BarGraphItem(
            x0=edges[:-1], x1=edges[1:], height=counts,
            brush=pg.mkBrush(*rgb, alpha), pen=pg.mkPen("w"),
        )
        viewbox.addItem(bar)
        
        plot_item.setLabel("bottom", col)
        plot_item.setLabel("left", "频数")
        
        return RenderedSeries(series, np.array([]), np.array([]), None, None, None)