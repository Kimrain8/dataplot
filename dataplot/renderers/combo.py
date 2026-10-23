"""组合图：左轴散点 + 右轴折线（简化版，右轴与主 ViewBox 共享空间）。"""

import numpy as np
import pandas as pd
import pyqtgraph as pg

from dataplot.core.datastore import DataStore
from dataplot.core.mapping import Mapping
from dataplot.renderers.base import HoverSpec, Renderer
from dataplot.renderers.scatter import ScatterRenderer


class ComboRenderer(Renderer):
    name = "combo"

    def __init__(self):
        self._scatter = ScatterRenderer()

    def render(
        self,
        plot_item: pg.PlotItem,
        store: DataStore,
        mapping: Mapping,
    ) -> HoverSpec | None:
        hover = self._scatter.render(plot_item, store, mapping)

        y2_col = mapping.y2
        df = store.df
        if y2_col is None or df is None or mapping.x is None:
            return hover

        x_col = mapping.x
        tmp = pd.DataFrame(
            {
                x_col: df[x_col],
                y2_col: pd.to_numeric(df[y2_col], errors="coerce"),
            }
        ).dropna()
        if tmp.empty:
            return hover

        if pd.api.types.is_numeric_dtype(tmp[x_col]):
            sub = tmp.sort_values(x_col)
            x2 = sub[x_col].to_numpy(dtype=float)
            y2 = sub[y2_col].to_numpy(dtype=float)
        else:
            agg = tmp.groupby(x_col, observed=True)[y2_col].mean().dropna()
            x2 = np.arange(len(agg))
            y2 = agg.to_numpy(dtype=float)

        if len(x2) == 0:
            return hover

        curve = pg.PlotCurveItem(x2, y2, pen=pg.mkPen((220, 70, 70), width=2))
        plot_item.addItem(curve)
        plot_item.getAxis("right").setLabel(y2_col, color="#dc4646")
        return hover