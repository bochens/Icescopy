"""Display limits for INP plots; calculations remain in the external toolkit."""
import math


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
