from dataplot.core.spec import ChartType
from dataplot.renderers.bar import BarRenderer
from dataplot.renderers.histogram import HistogramRenderer
from dataplot.renderers.line import LineRenderer
from dataplot.renderers.scatter import ScatterRenderer


_RENDERERS = {
    ChartType.SCATTER: ScatterRenderer(),
    ChartType.BAR: BarRenderer(),
    ChartType.LINE: LineRenderer(),
    ChartType.HISTOGRAM: HistogramRenderer(),
}


def get_renderer(ct: ChartType):
    return _RENDERERS.get(ct)