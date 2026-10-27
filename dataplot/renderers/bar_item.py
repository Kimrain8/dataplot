import numpy as np
import pyqtgraph as pg

class MinWidthBarGraphItem(pg.BarGraphItem):
    """
    一个能在渲染时动态保护最小像素宽度的柱状图组件。
    当屏幕缩放导致柱子小于 3 像素时，强制撑到 3 像素；放大后恢复真实数据宽度。
    """
    def paint(self, p, *args):
        vb = self.getViewBox()
        if vb is None or vb.width() <= 0:
            return super().paint(p, *args)
        
        # 获取当前 X 轴的视图范围
        x_range = vb.viewRange()[0]
        span = x_range[1] - x_range[0]
        
        if span <= 0:
            return super().paint(p, *args)
            
        px_per_unit = vb.width() / span
        orig_widths = self.opts.get('width')
        
        if orig_widths is not None:
            xs = self.opts.get('x')
            n_bars = len(xs) if hasattr(xs, '__len__') else 1
            
            if isinstance(orig_widths, (int, float)):
                orig_widths = np.full(n_bars, orig_widths)
            else:
                orig_widths = np.array(orig_widths)
            
            if len(orig_widths) == n_bars:
                # 计算当前每个柱子在屏幕上的像素宽度
                widths_px = np.abs(orig_widths * px_per_unit)
                min_px = 3.0
                needs_scale = widths_px < min_px
                
                # 如果有柱子太细，临时用 3 像素的宽度替换
                if np.any(needs_scale):
                    new_widths = orig_widths.copy()
                    new_widths[needs_scale] = np.sign(new_widths[needs_scale]) * (min_px / px_per_unit)
                    new_widths[new_widths == 0] = min_px / px_per_unit
                    
                    self.opts['width'] = new_widths
                    super().paint(p, *args)
                    self.opts['width'] = orig_widths
                    return

        super().paint(p, *args)