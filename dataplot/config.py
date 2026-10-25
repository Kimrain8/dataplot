# dataplot/config.py

# 鼠标悬停时，鼠标与图形点的最大允许物理像素距离。
# 数值越小越难触发悬停，越大越容易触发。
# 散点图因为点比较小，通常在 15~30 之间比较合适。
HOVER_TOLERANCE_PX = 10

# 鼠标悬停时，Tooltip 距离鼠标的横向和纵向像素偏移
TOOLTIP_OFFSET_X = 4
TOOLTIP_OFFSET_Y = 4