import numpy as np
import pyqtgraph as pg


class Crosshair:
    def __init__(self):
        self.vline = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#999", width=1, style=pg.QtCore.Qt.PenStyle.DashLine),
        )
        self.vline.hide()

    def attach(self, plot_item):
        plot_item.addItem(self.vline, ignoreBounds=True)

    def update(self, x):
        self.vline.setPos(x)
        self.vline.show()

    def hide(self):
        self.vline.hide()


def nearest(sorted_x, sorted_y, target_x):
    if sorted_x is None or len(sorted_x) == 0:
        return None
    idx = int(np.searchsorted(sorted_x, target_x))
    idx = min(max(idx, 0), len(sorted_x) - 1)
    if idx > 0 and (idx == len(sorted_x) or
                    abs(sorted_x[idx - 1] - target_x) < abs(sorted_x[idx] - target_x)):
        idx -= 1
    return float(sorted_x[idx]), float(sorted_y[idx])