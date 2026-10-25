from dataclasses import dataclass, field
from enum import Enum

class AxisSlot(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    FLOATING = "floating"

class ChartType(str, Enum):
    SCATTER = "scatter"
    BAR = "bar"
    LINE = "line"
    HISTOGRAM = "histogram"

class HistogramMode(str, Enum):
    OVERLAY = "overlay"
    GROUPED = "grouped"

class AggType(str, Enum):
    NONE = "none"
    COUNT = "count"
    SUM = "sum"
    MEAN = "mean"
    STD = "std"
    VAR = "var"
    MAX = "max"
    MIN = "min"
    RANGE = "range"

class ColorTheme(str, Enum):
    DEFAULT = "default"
    VIRIDIS = "viridis"
    PLASMA = "plasma"
    COOLWARM = "coolwarm"
    MAGMA = "magma"
    INFERNO = "inferno"
    CIVIDIS = "cividis"

@dataclass
class SeriesSpec:
    y: str | None = None
    chart_type: ChartType = ChartType.SCATTER
    axis: AxisSlot = AxisSlot.LEFT
    color: str | None = None
    color_theme: ColorTheme = ColorTheme.DEFAULT
    size: str | None = None
    size_agg: AggType = AggType.MEAN
    hist_mode: HistogramMode = HistogramMode.OVERLAY
    agg: AggType = AggType.SUM
    bin_width: float = 0.0  # 保留字段防止报错，但 UI 中已移除

@dataclass
class HierarchySpec:
    name: str
    fields: list[str]

@dataclass
class ChartSpec:
    x: str | None = None
    x_hierarchy: list[str] | None = None
    series: list[SeriesSpec] = field(default_factory=list)
    hover_fields: dict[str, AggType] = field(default_factory=dict)
    hidden_categories: set[str] = field(default_factory=set)
    facet_x: str | None = None
    facet_y: str | None = None
    bucket_settings: dict[str, str] = field(default_factory=dict) # 值改为字符串（如 "10", "1D", "3H"）
    hierarchies: list[HierarchySpec] = field(default_factory=list)