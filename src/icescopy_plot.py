from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedLayout, QWidget
import numpy as np
import pyqtgraph as pg
from icescopy_freezfinder import compute_convolution_center_offset, compute_convolution_timeseries


class GrayscalePlotWidget(QWidget):
    """Pyqtgraph-backed grayscale timeseries viewer for selected circles."""

    LEGEND_CELL_LIMIT = 12

    PALETTES = {
        "bright": [
            (0, 122, 255),
            (52, 199, 89),
            (255, 149, 0),
            (175, 82, 222),
            (255, 45, 85),
            (90, 200, 250),
        ],
        "okabe_ito": [
            (0, 114, 178),
            (213, 94, 0),
            (0, 158, 115),
            (204, 121, 167),
            (230, 159, 0),
            (86, 180, 233),
        ],
        "muted": [
            (78, 121, 167),
            (242, 142, 43),
            (118, 183, 178),
            (225, 87, 89),
            (89, 161, 79),
            (176, 122, 161),
        ],
        "warm_cool": [
            (225, 87, 89),
            (238, 150, 75),
            (249, 213, 111),
            (130, 186, 106),
            (74, 123, 183),
            (155, 99, 182),
        ],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setMinimumHeight(0)
        self.grayscale_headers = []
        self.grayscale_rows = []
        self.freeze_rows = []
        self.cell_ids = []
        self.current_image_index = None
        self.current_image_name = None
        self.tail_extend_points = 0
        self.convolution_half_window_points = 0
        self.convolution_ramp_points = 0
        self.timeseries_palette = "bright"
        self.timeseries_line_width = 2.0
        self.convolution_line_width = 1.0
        self.freeze_line_color = (220, 20, 60, 180)
        self.freeze_line_width = 1.0
        self.current_frame_color = (255, 204, 0, 220)
        self.current_frame_width = 2.0
        self.current_frame_line = None
        self._data_signature = None
        self._render_signature = None
        self._column_map_cache = None
        self._file_name_column_index_cache = None
        self._row_indexes_by_file_name_cache = None
        self._freeze_map_cache = None
        self._series_cache_by_cell = {}
        self._convolution_cache = {}
        self._preserve_view_range_on_next_refresh = False

        self.message_label = QLabel(
            "Run analysis, then select one or more circles to plot grayscale timeseries."
        )
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.message_label.setMinimumHeight(0)

        pg.setConfigOptions(antialias=False)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.plot_widget.setMinimumHeight(0)
        self.plot_widget.setFocusPolicy(Qt.StrongFocus)
        self.plot_widget.setBackground(None)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setLabel("bottom", "Frame / Image Index")
        self.plot_widget.setLabel("left", "Mean Grayscale")
        self.plot_widget.setLabel("right", "Convolution Signal")
        self.plot_widget.setTitle("Grayscale Time Series")

        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.setClipToView(True)
        self.plot_item.setDownsampling(auto=True, mode="peak")
        self.plot_item.addLegend(offset=(8, 8))
        self.plot_item.showAxis("right")
        self.convolution_view_box = pg.ViewBox()
        self.plot_item.scene().addItem(self.convolution_view_box)
        self.plot_item.getAxis("right").linkToView(self.convolution_view_box)
        self.convolution_view_box.setXLink(self.plot_item.vb)
        self.plot_item.vb.sigResized.connect(self.update_convolution_view_geometry)
        self.update_convolution_view_geometry()

        self.stack = QStackedLayout(self)
        self.stack.addWidget(self.message_label)
        self.stack.addWidget(self.plot_widget)
        self.stack.setCurrentWidget(self.message_label)

    def sizeHint(self):
        return QSize(480, 180)

    def minimumSizeHint(self):
        return QSize(240, 120)

    def invalidate_render_cache(self):
        self._data_signature = None
        self._render_signature = None
        self._invalidate_data_caches()

    def update_plot_data(
        self,
        grayscale_headers,
        grayscale_rows,
        freeze_rows,
        cell_ids,
        current_image_index=None,
        tail_extend_points=0,
        convolution_half_window_points=0,
        convolution_ramp_points=0,
        timeseries_palette="bright",
        timeseries_line_width=2.0,
        convolution_line_width=1.0,
        freeze_line_color=(220, 20, 60, 180),
        freeze_line_width=1.0,
        current_frame_color=(255, 204, 0, 220),
        current_frame_width=2.0,
        current_image_name=None,
    ):
        normalized_headers = list(grayscale_headers or [])
        normalized_rows = list(grayscale_rows or [])
        normalized_freeze_rows = list(freeze_rows or [])
        normalized_cell_ids = tuple(sorted(set(cell_ids or [])))

        data_signature = self._build_data_signature(
            normalized_headers,
            normalized_rows,
            normalized_freeze_rows,
        )
        style_signature = (
            int(max(0, tail_extend_points)),
            int(max(0, convolution_half_window_points)),
            int(max(0, convolution_ramp_points)),
            timeseries_palette,
            float(timeseries_line_width),
            float(convolution_line_width),
            tuple(freeze_line_color),
            float(freeze_line_width),
            tuple(current_frame_color),
            float(current_frame_width),
        )
        render_signature = (
            data_signature,
            normalized_cell_ids,
            style_signature,
        )

        data_changed = data_signature != self._data_signature
        if data_changed:
            self._data_signature = data_signature
            self._invalidate_data_caches()

        self.grayscale_headers = normalized_headers
        self.grayscale_rows = normalized_rows
        self.freeze_rows = normalized_freeze_rows
        self.cell_ids = list(normalized_cell_ids)
        self.tail_extend_points = style_signature[0]
        self.convolution_half_window_points = style_signature[1]
        self.convolution_ramp_points = style_signature[2]
        self.timeseries_palette = style_signature[3]
        self.timeseries_line_width = style_signature[4]
        self.convolution_line_width = style_signature[5]
        self.freeze_line_color = style_signature[6]
        self.freeze_line_width = style_signature[7]
        self.current_frame_color = style_signature[8]
        self.current_frame_width = style_signature[9]

        # Fast path: if plot content/style/selected cells are unchanged, only move
        # the current-frame indicator instead of rebuilding all curves.
        if render_signature == self._render_signature:
            self.set_current_image_index(current_image_index, current_image_name)
            return

        self.current_image_index = current_image_index
        self.current_image_name = current_image_name
        self._preserve_view_range_on_next_refresh = (
            not data_changed
            and self.stack.currentWidget() is self.plot_widget
        )
        self._render_signature = render_signature
        self.refresh_plot()

    def set_current_image_index(self, current_image_index, current_image_name=None):
        self.current_image_index = current_image_index
        self.current_image_name = current_image_name
        frame_x = self._current_frame_x()
        if self.current_frame_line is None:
            if frame_x is not None and self.stack.currentWidget() is self.plot_widget:
                self._add_current_frame_line(frame_x, include_legend=False)
            return
        if frame_x is None:
            self.plot_item.removeItem(self.current_frame_line)
            self.current_frame_line = None
            return
        self.current_frame_line.setValue(frame_x)

    def _palette_colors(self):
        return self.PALETTES.get(self.timeseries_palette, self.PALETTES["bright"])

    def _timeseries_pen(self, series_index):
        palette = self._palette_colors()
        red, green, blue = palette[series_index % len(palette)]
        return pg.mkPen((red, green, blue), width=self.timeseries_line_width)

    def _convolution_pen(self, series_index):
        palette = self._palette_colors()
        red, green, blue = palette[series_index % len(palette)]
        return pg.mkPen((red, green, blue, 210), width=self.convolution_line_width, style=Qt.DashLine)

    def _freeze_pen(self):
        return pg.mkPen(self.freeze_line_color, width=self.freeze_line_width, style=Qt.DashLine)

    def _current_frame_pen(self):
        return pg.mkPen(self.current_frame_color, width=self.current_frame_width)

    def _show_message(self, message):
        self.message_label.setText(message)
        self.stack.setCurrentWidget(self.message_label)

    def _show_plot(self):
        self.stack.setCurrentWidget(self.plot_widget)

    def _clear_plot(self):
        # Clear plotted items while preserving the existing legend object.
        self.plot_item.clear()
        self.convolution_view_box.clear()
        self.current_frame_line = None
        self.plot_item.setTitle("Grayscale Time Series")
        self.plot_item.setLabel("bottom", "Frame / Image Index")
        self.plot_item.setLabel("left", "Mean Grayscale")
        self.plot_item.setLabel("right", "Convolution Signal")

    def _build_data_signature(self, headers, rows, freeze_rows):
        return (
            tuple(headers),
            tuple(tuple(row) for row in rows),
            tuple(tuple(row) for row in freeze_rows),
        )

    def _file_name_column_index(self):
        if self._file_name_column_index_cache is not None:
            if self._file_name_column_index_cache < 0:
                return None
            return self._file_name_column_index_cache
        for index, header in enumerate(self.grayscale_headers):
            if str(header).strip().casefold() == "file_name":
                self._file_name_column_index_cache = index
                return index
        self._file_name_column_index_cache = -1
        return None

    def _row_indexes_by_file_name(self):
        if self._row_indexes_by_file_name_cache is not None:
            return self._row_indexes_by_file_name_cache
        file_name_column = self._file_name_column_index()
        mapping = {}
        if file_name_column is not None:
            for row_index, row in enumerate(self.grayscale_rows):
                try:
                    file_name = str(row[file_name_column])
                except IndexError:
                    continue
                mapping.setdefault(file_name, []).append(row_index)
        self._row_indexes_by_file_name_cache = mapping
        return mapping

    def _current_frame_x(self):
        if not self.grayscale_rows:
            return None

        current_image_name = None
        if self.current_image_name is not None:
            current_image_name = str(self.current_image_name)

        file_name_column = self._file_name_column_index()
        if file_name_column is not None and current_image_name:
            try:
                current_image_index = int(self.current_image_index)
            except (TypeError, ValueError):
                current_image_index = None

            if (
                current_image_index is not None
                and 0 <= current_image_index < len(self.grayscale_rows)
            ):
                row = self.grayscale_rows[current_image_index]
                if (
                    file_name_column < len(row)
                    and str(row[file_name_column]) == current_image_name
                ):
                    return float(current_image_index)

            row_indexes = self._row_indexes_by_file_name().get(current_image_name, [])
            if row_indexes:
                return float(row_indexes[0])
            return None

        try:
            current_image_index = int(self.current_image_index)
        except (TypeError, ValueError):
            return None
        if not (0 <= current_image_index < len(self.grayscale_rows)):
            return None
        return float(current_image_index)

    def _finite_range(self, range_values):
        if not isinstance(range_values, (list, tuple)) or len(range_values) != 2:
            return None
        try:
            lower = float(range_values[0])
            upper = float(range_values[1])
        except (TypeError, ValueError):
            return None
        if not (np.isfinite(lower) and np.isfinite(upper)) or lower == upper:
            return None
        return (lower, upper)

    def _capture_view_ranges(self):
        primary_ranges = self.plot_item.vb.viewRange()
        convolution_ranges = self.convolution_view_box.viewRange()
        if len(primary_ranges) < 2 or len(convolution_ranges) < 2:
            return None
        x_range = self._finite_range(primary_ranges[0])
        y_range = self._finite_range(primary_ranges[1])
        convolution_y_range = self._finite_range(convolution_ranges[1])
        if x_range is None or y_range is None:
            return None
        return {
            "x_range": x_range,
            "y_range": y_range,
            "convolution_y_range": convolution_y_range,
        }

    def _restore_view_ranges(self, ranges):
        if not ranges:
            return False
        self.plot_item.setRange(
            xRange=ranges["x_range"],
            yRange=ranges["y_range"],
            padding=0,
        )
        if ranges.get("convolution_y_range") is not None:
            self.convolution_view_box.setYRange(
                ranges["convolution_y_range"][0],
                ranges["convolution_y_range"][1],
                padding=0,
            )
        return True

    def _invalidate_data_caches(self):
        self._column_map_cache = None
        self._file_name_column_index_cache = None
        self._row_indexes_by_file_name_cache = None
        self._freeze_map_cache = None
        self._series_cache_by_cell = {}
        self._convolution_cache = {}

    def _add_current_frame_line(self, frame_x, include_legend):
        self.current_frame_line = pg.InfiniteLine(
            pos=float(frame_x),
            angle=90,
            pen=self._current_frame_pen(),
            movable=False,
        )
        self.current_frame_line.setZValue(1000)
        self.plot_item.addItem(self.current_frame_line, ignoreBounds=True)
        if include_legend:
            self._configure_data_item(
                self.plot_item.plot(
                    np.empty(0, dtype=float),
                    np.empty(0, dtype=float),
                    pen=self._current_frame_pen(),
                    name="Current Frame",
                )
            )

    def update_convolution_view_geometry(self):
        self.convolution_view_box.setGeometry(self.plot_item.vb.sceneBoundingRect())
        self.convolution_view_box.linkedViewChanged(self.plot_item.vb, self.convolution_view_box.XAxis)

    def _grayscale_column_map(self):
        if self._column_map_cache is not None:
            return self._column_map_cache
        mapping = {}
        for index, header in enumerate(self.grayscale_headers):
            if (not header.endswith("_grayscale")) or ("_" not in header):
                continue
            parts = header.split("_")
            if len(parts) < 3:
                continue
            if parts[0] != "cell":
                continue
            try:
                cell_id = int(parts[1])
            except (TypeError, ValueError):
                continue
            mapping[cell_id] = index
        self._column_map_cache = mapping
        return mapping

    def _freeze_index_map(self):
        if self._freeze_map_cache is not None:
            return self._freeze_map_cache
        freeze_map = {}
        for row in self.freeze_rows:
            if len(row) < 2:
                continue
            label = str(row[0])
            parts = label.split("_")
            if len(parts) < 2 or parts[0] != "cell":
                continue
            try:
                cell_id = int(parts[1])
                image_index = int(float(row[1]))
            except (IndexError, ValueError):
                continue
            freeze_map.setdefault(cell_id, []).append(image_index)
        self._freeze_map_cache = freeze_map
        return freeze_map

    def _series_for_cell(self, cell_id):
        cached = self._series_cache_by_cell.get(cell_id)
        if cached is not None:
            return cached

        column_index = self._grayscale_column_map().get(cell_id)
        if column_index is None:
            return None

        y_values = []
        for row in self.grayscale_rows:
            try:
                value = float(row[column_index])
            except (IndexError, TypeError, ValueError):
                value = np.nan
            y_values.append(value)
        if not y_values:
            return None

        y_array = np.asarray(y_values, dtype=float)
        finite_mask = np.isfinite(y_array)
        if not np.any(finite_mask):
            return None

        x_array = np.arange(len(y_array), dtype=float)
        if not np.all(finite_mask):
            x_array = x_array[finite_mask]
            y_array = y_array[finite_mask]

        series = (x_array, y_array)
        self._series_cache_by_cell[cell_id] = series
        return series

    def _convolution_for_cell(self, cell_id, y_values):
        conv_key = (
            int(cell_id),
            len(y_values),
            int(max(0, self.tail_extend_points)),
            int(max(0, self.convolution_half_window_points)),
            int(max(0, self.convolution_ramp_points)),
        )
        cached = self._convolution_cache.get(conv_key)
        if cached is not None:
            return cached

        _, convolved_values = compute_convolution_timeseries(
            y_values,
            tail_extend_points=self.tail_extend_points,
            convolution_half_window_points=self.convolution_half_window_points,
            convolution_ramp_points=self.convolution_ramp_points,
        )
        if len(convolved_values):
            conv_offset = compute_convolution_center_offset(
                len(y_values) + int(max(0, self.tail_extend_points)),
                convolution_half_window_points=self.convolution_half_window_points,
                convolution_ramp_points=self.convolution_ramp_points,
            )
            conv_x_values = np.arange(len(convolved_values), dtype=float) + conv_offset
        else:
            conv_x_values = np.empty(0, dtype=float)
        conv_data = (conv_x_values, np.asarray(convolved_values, dtype=float))
        self._convolution_cache[conv_key] = conv_data
        return conv_data

    def _selected_series(self):
        series = []
        for cell_id in self.cell_ids:
            series_data = self._series_for_cell(cell_id)
            if series_data is None:
                continue
            x_values, y_values = series_data
            series.append((cell_id, x_values, y_values))
        return series

    def _configure_data_item(self, data_item):
        data_item.setClipToView(True)
        data_item.setDownsampling(auto=True, method="peak")
        data_item.setSkipFiniteCheck(True)
        return data_item

    def _freeze_segment_arrays(self, freeze_indices, y_min, y_max):
        segment_count = len(freeze_indices)
        x_values = np.repeat(np.asarray(sorted(freeze_indices), dtype=float), 2)
        y_values = np.empty(segment_count * 2, dtype=float)
        y_values[0::2] = float(y_min)
        y_values[1::2] = float(y_max)
        return x_values, y_values

    def refresh_plot(self):
        self.plot_widget.setUpdatesEnabled(False)
        try:
            preserved_view_ranges = (
                self._capture_view_ranges()
                if self._preserve_view_range_on_next_refresh
                else None
            )
            self._preserve_view_range_on_next_refresh = False

            if not self.grayscale_headers or not self.grayscale_rows:
                self._clear_plot()
                self._show_message("Run analysis to generate grayscale timeseries.")
                return

            if not self.cell_ids:
                self._clear_plot()
                self._show_message("Select one or more circles to plot grayscale timeseries.")
                return

            series = self._selected_series()
            if not series:
                self._clear_plot()
                self._show_message("No grayscale timeseries matched the currently selected cells.")
                return

            self._clear_plot()
            legend = getattr(self.plot_item, "legend", None)
            show_legend = len(series) <= self.LEGEND_CELL_LIMIT
            if legend is not None:
                legend.setVisible(show_legend)
            freeze_map = self._freeze_index_map()
            grayscale_y_min = None
            grayscale_y_max = None
            convolution_y_min = None
            convolution_y_max = None
            unique_freeze_indices = set()

            for series_index, (cell_id, x_values, y_values) in enumerate(series):
                pen = self._timeseries_pen(series_index)
                self._configure_data_item(
                    self.plot_item.plot(
                        x_values,
                        y_values,
                        pen=pen,
                        name=f"Cell {cell_id}" if show_legend else None,
                    )
                )
                series_y_min = float(np.min(y_values))
                series_y_max = float(np.max(y_values))
                grayscale_y_min = series_y_min if grayscale_y_min is None else min(grayscale_y_min, series_y_min)
                grayscale_y_max = series_y_max if grayscale_y_max is None else max(grayscale_y_max, series_y_max)

                conv_x_values, convolved_values = self._convolution_for_cell(cell_id, y_values)
                if len(convolved_values):
                    conv_pen = self._convolution_pen(series_index)
                    conv_curve_item = pg.PlotCurveItem(
                        conv_x_values,
                        convolved_values,
                        pen=conv_pen,
                    )
                    conv_curve_item.setSkipFiniteCheck(True)
                    self.convolution_view_box.addItem(conv_curve_item)
                    if show_legend:
                        self._configure_data_item(
                            self.plot_item.plot(
                                np.empty(0, dtype=float),
                                np.empty(0, dtype=float),
                                pen=conv_pen,
                                name=f"Cell {cell_id} Conv",
                            )
                        )
                    series_conv_min = float(np.min(convolved_values))
                    series_conv_max = float(np.max(convolved_values))
                    convolution_y_min = (
                        series_conv_min if convolution_y_min is None else min(convolution_y_min, series_conv_min)
                    )
                    convolution_y_max = (
                        series_conv_max if convolution_y_max is None else max(convolution_y_max, series_conv_max)
                    )

                unique_freeze_indices.update(freeze_map.get(cell_id, []))

            freeze_segments_item = None
            if (
                unique_freeze_indices
                and grayscale_y_min is not None
                and grayscale_y_max is not None
            ):
                freeze_x_values, freeze_y_values = self._freeze_segment_arrays(
                    unique_freeze_indices,
                    grayscale_y_min,
                    grayscale_y_max,
                )
                freeze_segments_item = self.plot_item.plot(
                    freeze_x_values,
                    freeze_y_values,
                    pen=self._freeze_pen(),
                    connect="pairs",
                )
                freeze_segments_item.setClipToView(False)
                freeze_segments_item.setDownsampling(auto=False)
                freeze_segments_item.setSkipFiniteCheck(True)
            if show_legend and unique_freeze_indices:
                self._configure_data_item(
                    self.plot_item.plot(
                        np.empty(0, dtype=float),
                        np.empty(0, dtype=float),
                        pen=self._freeze_pen(),
                        name="Freeze Event",
                    )
                )

            current_frame_x = self._current_frame_x()
            if current_frame_x is not None:
                self._add_current_frame_line(current_frame_x, include_legend=show_legend)

            if preserved_view_ranges and self._restore_view_ranges(preserved_view_ranges):
                pass
            elif grayscale_y_min is not None and grayscale_y_max is not None:
                padding = max((grayscale_y_max - grayscale_y_min) * 0.08, 1.0)
                self.plot_item.setYRange(grayscale_y_min - padding, grayscale_y_max + padding, padding=0)

            if (
                not preserved_view_ranges
                and convolution_y_min is not None
                and convolution_y_max is not None
            ):
                conv_padding = max((convolution_y_max - convolution_y_min) * 0.08, 1.0)
                self.convolution_view_box.setYRange(
                    convolution_y_min - conv_padding,
                    convolution_y_max + conv_padding,
                    padding=0,
                )

            if not preserved_view_ranges:
                self.plot_item.enableAutoRange(axis="x")
            self.update_convolution_view_geometry()
            self._show_plot()
        finally:
            self.plot_widget.setUpdatesEnabled(True)
