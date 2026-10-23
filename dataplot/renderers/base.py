from dataclasses import dataclass
import numpy as np
import pandas as pd
from dataplot.core.encoding import ColorLegend
from dataplot.core.spec import SeriesSpec


@dataclass
class RenderedSeries:
    spec: SeriesSpec
    x: np.ndarray
    y: np.ndarray
    legend: ColorLegend | None = None
    sorted_x: np.ndarray | None = None
    sorted_y: np.ndarray | None = None
    data: pd.DataFrame | None = None
    tree: any = None  # 用于散点图的二维空间索引


def get_x_values(df: pd.DataFrame, x_col: str) -> tuple[np.ndarray, list[str] | None]:
    if x_col is None or x_col not in df.columns:
        return np.array([]), None
    if pd.api.types.is_numeric_dtype(df[x_col]):
        x = pd.to_numeric(df[x_col], errors="coerce").to_numpy(dtype=float)
        return x, None
    else:
        s = df[x_col].astype("object").where(df[x_col].notna(), "<缺失>").astype(str)
        codes, uniques = pd.factorize(s, use_na_sentinel=False)
        return codes.astype(float), [str(u) for u in uniques]


class SeriesRenderer:
    def render(self, plot_item, viewbox, df, x_col, series: SeriesSpec, context=None) -> list[RenderedSeries] | None:
        raise NotImplementedError