"""散点悬停的最近邻索引。"""

import numpy as np
from scipy.spatial import cKDTree


class NearestPointIndex:
    """对有限点集建立 KDTree，支持按数据坐标查最近点。"""

    def __init__(self):
        self._tree: cKDTree | None = None
        self._x: np.ndarray | None = None
        self._y: np.ndarray | None = None

    def build(self, x, y) -> None:
        self._x = np.asarray(x, dtype=float)
        self._y = np.asarray(y, dtype=float)
        if len(self._x) == 0:
            self._tree = None
            return
        self._tree = cKDTree(np.column_stack([self._x, self._y]))

    @property
    def ready(self) -> bool:
        return self._tree is not None and len(self._x) > 0

    def query(self, x: float, y: float):
        """返回 (距离, 索引, 点x, 点y) 或 None。"""
        if not self.ready:
            return None
        dist, idx = self._tree.query([x, y], k=1)
        return dist, int(idx), float(self._x[idx]), float(self._y[idx])