"""Display limits for INP plots; calculations remain in the external toolkit."""
import math
import pyqtgraph as pg


class ConcentrationAxis(pg.AxisItem):
    """Use readable decade ticks; add 2 and 5 only when there is room."""

    def logTickValues(self, minVal, maxVal, size, stdTicks):
        span = maxVal - minVal
        if span < .5:
            return super().logTickValues(minVal, maxVal, size, stdTicks)
        step = max(1, math.ceil(span / max(1, size / 70)))
        major = list(range(math.ceil(minVal / step) * step, math.floor(maxVal) + 1, step))
        minor = []
        if step == 1 and size / span >= 110:
            minor = [power + math.log10(m) for power in range(math.floor(minVal), math.ceil(maxVal))
                     for m in (2, 5) if minVal < power + math.log10(m) < maxVal]
        return [(float(step), major), (None, minor)]


class TemperatureRangeItem(pg.LinearRegionItem):
    """Boundary handles only: the transparent interior must allow plot panning."""

    def mouseDragEvent(self, event):
        event.ignore()

    def mouseClickEvent(self, event):
        event.ignore()

    def hoverEvent(self, event):
        pass


def axis_limits(quantity, x_values, y_values, totals=(), *, logarithmic=False):
    """Return padded plot coordinates, including finite uncertainty endpoints.

    Log coordinates belong to the view only: observations and exports stay in
    their original units. No arbitrary epsilon is substituted for zero data.
    """
    xs = [v for v in x_values if math.isfinite(v)]
    ys = [v for v in y_values if math.isfinite(v)]
    xmin, xmax = (min(xs), max(xs)) if xs else (-30., 0.)
    pad = max((xmax - xmin) * .04, .1)
    xlim = (xmin - pad, xmax + pad)
    if logarithmic:
        positive = [math.log10(v) for v in ys if v > 0]
        if not positive:
            return xlim, (-1., 1.)
        low, high = min(positive), max(positive)
        pad = max((high - low) * .06, .15)
        return xlim, (low - pad, high + pad)
    if quantity == "Fraction frozen":
        return xlim, (-.03, 1.03)
    if quantity == "Number frozen":
        ys += [v for v in totals if math.isfinite(v)]
    maximum = max([v for v in ys if v >= 0], default=1.)
    if maximum == 0:
        maximum = 1.
    # A small margin keeps zero and fully frozen endpoint symbols visible.
    return xlim, (-.03 * maximum, 1.07 * maximum)
