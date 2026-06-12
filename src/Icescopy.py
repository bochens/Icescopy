from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QFileDialog, QVBoxLayout,
                               QWidget, QGraphicsScene, QLineEdit, QLabel,
                               QTextEdit, QSizePolicy, QHBoxLayout, QGraphicsView, QSplitter, QSlider,
                               QStatusBar, QDialog, QDoubleSpinBox, QAbstractSpinBox,
                               QListView, QGridLayout, QTreeWidget, QTreeWidgetItem, QTableWidget, QHeaderView, QStackedWidget, QSpinBox, QComboBox,
                               QTableWidgetItem, QAbstractItemView, QMessageBox, QFrame, QDockWidget, QTabWidget, QStyle, QStyleOptionSlider, QStyleFactory,
                               QCheckBox)
from PySide6.QtGui import QPixmap, QPen, QBrush, QColor, QPainter, Qt, QCursor, QTransform, QFont, QAction, QIcon, QGuiApplication, QUndoStack, QShortcut, QKeySequence, QPolygonF
from PySide6.QtCore import QRectF, QSize, QTimer, QEvent, QModelIndex, QItemSelectionModel, QSignalBlocker, QPointF
import xml.etree.ElementTree as ET
import csv
import os
import sys
import math
import tempfile
import traceback
import darkdetect
import platform
import ctypes
import time
from functools import partial
import copy
from collections import OrderedDict
from datetime import datetime, timedelta
import numpy as np
import shiboken6
import re
from PIL import Image

# Custom Python Files
from icescopy_aux import CustomGraphicsView, AboutDialog, Image_analysis_thread, PreferencesDialog, SortImagesDialog
import icescopy_stylesheet
from icescopy_cell import CellStateManager
from icescopy_cell_items import CellCircle, CellSnapshot
from icescopy_dialogs import (
    CSUTemperatureImportDialog,
    NewSessionMetadataDialog,
    OutputResultsDialog,
    PKUTemperatureImportDialog,
    StandardTemperatureImportDialog,
    TAMUTemperatureImportDialog,
    UTKTemperatureImportDialog,
)
from icescopy_dock import DockTitleBar
from icescopy_frameslider import FrameSlider, SliderZoom_Slider
from icescopy_frame_source import (
    DEFAULT_VIDEO_GRAYSCALE_MODE,
    ImageSequenceFrameSource,
    SOURCE_KIND_IMAGE_SEQUENCE,
    SOURCE_KIND_VIDEO,
    VideoFrameSource,
    VideoSequenceFrameSource,
    frame_source_from_session_payload,
    normalize_video_grayscale_mode,
)
from icescopy_freeze_count_timeseries import FreezeCountTimeseriesMixin
from icescopy_sample_catalog import SampleCatalogPanelMixin
from icescopy_video_preview import VideoPreviewDecodeController
from icescopy_image_edit import (
    IMAGE_EDIT_HISTOGRAM_BIN_COUNT,
    ImageCropOverlayItem,
    ImageHistogramWidget,
    ImageRectOverlayItem,
    apply_affine_to_point,
    apply_image_adjustments_to_uint8,
    apply_image_adjustments_to_qimage,
    build_rotated_crop_affine,
    compute_histogram_bins,
    crop_state_is_identity,
    invert_affine_matrix,
    normalize_rect_area_state,
    normalize_rotated_crop_state,
    qimage_to_grayscale_array,
)
from icescopy_plot import GrayscalePlotWidget
from icescopy_cell_controller import CellEditController
from icescopy_temperature_import import (
    IMAGE_TIMESTAMP_SOURCE_FILENAME,
    IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS,
    TEMPERATURE_UNIT_CELSIUS,
    TIMESTAMP_STYLE_AUTO,
    TemperatureImportError,
    normalize_sample_name,
    parse_ice_array_calibration_csv,
    parse_csu_is_dat,
    parse_linksys32_iml,
    parse_standard_temperature_csv,
    parse_tamu_linkam_xlsx,
    parse_utk_temperature_csv,
    parse_utk_video_start_timestamp,
)
from icescopy_session import (
    FrameNavigationCommand,
    ImageListModel,
    SessionAnalysisMarkerCommand,
    SessionDataCommand,
    SessionFreezeAnnotationCommand,
    SessionImageEditCommand,
    SessionImageListCommand,
    SessionLoadedImagesCommand,
    SessionCellCommand,
    SessionSnapshotCommand,
    SessionTimelineMarkersCommand,
)
from icescopy_session_io import (
    build_restore_state,
    build_session_payload,
    build_freeze_count_timeseries_csv_text,
    deserialize_sample_catalog_payload,
    load_session_bundle,
    normalize_sample_catalog_record,
    save_session_bundle,
    serialize_sample_catalog_payload,
)
from icescopy_sample_metadata import (
    default_sample_metadata_schema,
    dropped_sample_metadata_keys,
    export_sample_metadata_field_keys,
    migrate_sample_catalog_for_schema,
    same_for_all_sample_metadata_values,
    sample_metadata_schema_from_payload,
    sample_metadata_schema_from_xml,
    sample_metadata_schema_to_payload,
)
from icescopy_tool_options import (
    TOOL_OPTIONS_BUTTON_SPACING,
    TOOL_OPTIONS_CONTENT_WIDTH,
    TOOL_OPTIONS_CONTROL_QSS,
    TOOL_OPTIONS_FIELD_WIDTH,
    TOOL_OPTIONS_LABEL_WIDTH,
    TOOL_OPTIONS_PANEL_DEFAULT_WIDTH,
    TOOL_OPTIONS_SHORTCUT_WIDTH,
    TOOL_OPTIONS_SPINBOX_SLOT_HEIGHT,
    ToolOptionsFormPage,
    ToolOptionsInfoPage,
)
from icescopy_analysis_windows import (
    frame_count_from_ranges,
    normalize_analysis_marker_ranges,
)


module_dir = os.path.dirname(__file__)
resources_dir = os.path.join(module_dir, 'resources')
if not os.path.isdir(resources_dir):
    resources_dir = os.path.join(os.path.dirname(module_dir), 'resources')
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
ui_images_dir = os.path.join(resources_dir, 'ui_images')
SIDE_PANEL_DEFAULT_WIDTH = 280


class IcescopyApplication(QApplication):
    """QApplication that opens .icescopy documents sent by the operating system."""

    def __init__(self, args):
        super().__init__(args)
        self.main_window = None
        self.pending_session_paths = []
        self.opened_session_paths = set()

    def set_main_window(self, main_window):
        self.main_window = main_window
        self.open_pending_session_paths()

    def event(self, event):
        if event.type() == QEvent.FileOpen:
            file_path = self.file_path_from_file_open_event(event)
            if file_path:
                self.open_session_path(file_path)
                return True
        return super().event(event)

    def file_path_from_file_open_event(self, event):
        file_path = event.file()
        if file_path:
            return file_path

        url = event.url()
        if url.isLocalFile():
            return url.toLocalFile()
        return ""

    def open_session_path(self, file_path):
        normalized_path = os.path.abspath(os.path.expanduser(str(file_path)))
        if normalized_path in self.opened_session_paths:
            return

        if self.main_window is None:
            if normalized_path not in self.pending_session_paths:
                self.pending_session_paths.append(normalized_path)
            return

        opened = self.main_window.open_session_file_path(
            normalized_path,
            next_action_label="opening a session file",
        )
        if opened:
            self.opened_session_paths.add(normalized_path)

    def open_pending_session_paths(self):
        pending_paths = list(self.pending_session_paths)
        self.pending_session_paths = []
        for file_path in pending_paths:
            self.open_session_path(file_path)


DEFAULT_VISUAL_COLORS = {
    "CircleDefaultColor": "255,0,0,255",
    "CircleHoverColor": "0,0,255,255",
    "CircleSelectedColor": "64,156,255,255",
    "CircleEditColor": "240,168,168,255",
    "CirclePressedColor": "255,255,0,255",
    "GridPreviewOutlineColor": "0,122,255,200",
    "GridPreviewFillColor": "0,122,255,25",
}

SAMPLE_VISUAL_PALETTE = (
    (52, 199, 89),
    (255, 149, 0),
    (175, 82, 222),
    (48, 176, 199),
    (162, 132, 94),
    (106, 90, 205),
    (153, 153, 0),
    (199, 97, 20),
)



class IceScopy(QMainWindow, FreezeCountTimeseriesMixin, SampleCatalogPanelMixin):
    def __init__(self):

        # SETTINGS
        self.circle_radius = 22 #default value
        self.pen_width = 1
        self.maximum_zoom = 10
        self.dot_size = 1
        self.slider_maxzoom_pixel_interval = 10
        self.slider_tick_pixel_interval = 20
        self.undo_limit = 20
        self.viewer_image_count = 1
        self.viewer_split_orientation = "horizontal"
        self.sort_mode = "natural_filename"
        self.grid_rows = 4
        self.grid_columns = 4
        self.grid_horizontal_pitch = 60
        self.grid_vertical_pitch = 60
        self.grid_rotation_degrees = 0
        self.grid_cell_id_direction = "left_to_right"
        self.radius_wheel_step = 1.0
        self.grid_pitch_wheel_step = 1.0
        self.grid_tilt_wheel_step = 1.0
        self.freeze_finder_width = 10.0
        self.freeze_finder_prominence = 100.0
        self.freeze_finder_head_extend_points = 0
        self.freeze_finder_tail_extend_points = 5
        self.convolution_half_window_points = 0
        self.convolution_ramp_points = 0
        self.freeze_finder_detect_brightening = False
        self.video_grayscale_mode = DEFAULT_VIDEO_GRAYSCALE_MODE
        self.temperature_cycle_warmup_hysteresis_c = 0.02
        self.timeseries_palette = "bright"
        self.timeseries_line_width = 2.0
        self.timeseries_convolution_line_width = 1.0
        self.timeseries_freeze_line_color = "220,20,60,180"
        self.timeseries_freeze_line_width = 1.0
        self.timeseries_current_frame_color = "255,204,0,170"
        self.timeseries_current_frame_line_width = 1.5
        self.circle_default_color = DEFAULT_VISUAL_COLORS["CircleDefaultColor"]
        self.circle_hover_color = DEFAULT_VISUAL_COLORS["CircleHoverColor"]
        self.circle_selected_color = DEFAULT_VISUAL_COLORS["CircleSelectedColor"]
        self.circle_edit_color = DEFAULT_VISUAL_COLORS["CircleEditColor"]
        self.circle_pressed_color = DEFAULT_VISUAL_COLORS["CirclePressedColor"]
        self.grid_preview_outline_color = DEFAULT_VISUAL_COLORS["GridPreviewOutlineColor"]
        self.grid_preview_fill_color = DEFAULT_VISUAL_COLORS["GridPreviewFillColor"]
        self.preview_handle_size = 12.0
        self.circle_label_font_size = 12.0
        self.circle_label_offset_x = 6.0
        self.circle_label_offset_y = 6.0
        self.default_sample_metadata_schema = default_sample_metadata_schema()
        self.default_circle_radius = self.circle_radius
        self.default_grid_rows = self.grid_rows
        self.default_grid_columns = self.grid_columns
        self.default_grid_horizontal_pitch = self.grid_horizontal_pitch
        self.default_grid_vertical_pitch = self.grid_vertical_pitch
        self.default_grid_rotation_degrees = self.grid_rotation_degrees
        self.default_grid_cell_id_direction = self.grid_cell_id_direction
        self.edit_single_base_radius = None
        self.edit_single_radius_delta = 0.0
        self.edit_group_base_radius = None
        self.edit_group_base_radii_by_number = {}
        self.edit_group_base_positions_by_number = {}
        self.edit_group_base_origin_pixels = None
        self.edit_group_base_primary_axis = (1.0, 0.0)
        self.edit_group_base_secondary_axis = (0.0, 1.0)
        self.edit_group_radius_delta = 0.0
        self.edit_group_base_horizontal_pitch = None
        self.edit_group_base_vertical_pitch = None
        self.edit_group_base_rotation_degrees = None
        self.edit_group_horizontal_pitch_delta = 0.0
        self.edit_group_vertical_pitch_delta = 0.0
        self.edit_group_rotation_delta = 0.0
        
        super().__init__()
        self.cell_state = CellStateManager(self)
        self.cell_controller = CellEditController(self)
        self.undo_stack = QUndoStack(self)
        self.undo_redo_enabled = True
        self.image_list_enabled = True
        self.frame_list_frozen_only = False
        self.frame_list_visible_indices = []
        self.history_restoring = False
        # Tool actions can fire during initUI, so temporary key/mode state has
        # to exist before any default tool is triggered.
        self.temporary_event_data = {}
        self.space_held = False             # important for using space to activate an and zoom
        self.default_dock_state = None
        self.initData()
        self.initUI()
        self.set_preferences()

    def set_preferences(self, preserve_session_tool_state=False):
        preferences = {}
        # use .get() method on a dictionary to specify a default value if a key is not found.
        try:
            preferences = self.load_preferences_from_xml()
        except FileNotFoundError:
            print('No preference file set')
            # If the preferences.xml file is not found, you might want to save the default preferences
            pass

        current_tool_state = None
        if preserve_session_tool_state:
            current_tool_state = {
                "circle_radius": self.circle_radius,
                "grid_rows": self.grid_rows,
                "grid_columns": self.grid_columns,
                "grid_horizontal_pitch": self.grid_horizontal_pitch,
                "grid_vertical_pitch": self.grid_vertical_pitch,
                "grid_rotation_degrees": self.grid_rotation_degrees,
            }

        self.default_circle_radius = preferences.get('DefaultCircleRadius', self.default_circle_radius)
        self.circle_radius = self.default_circle_radius
        self.maximum_zoom = preferences.get('MaximumZoom', self.maximum_zoom)
        self.pen_width = max(1, preferences.get('PenWidth', self.pen_width))
        self.dot_size = preferences.get('DotSize', self.dot_size)
        self.slider_maxzoom_pixel_interval = preferences.get('SliderMaxZoomPixelInterval', self.slider_maxzoom_pixel_interval)
        self.slider_tick_pixel_interval = preferences.get('SliderTickPixelInterval', self.slider_tick_pixel_interval)
        self.undo_limit = int(preferences.get('UndoLimit', self.undo_limit))
        self.sample_name_pattern = str(
            preferences.get('SampleNamePattern', getattr(self, "sample_name_pattern", "Sample_#"))
        )
        self.default_sample_metadata_schema = sample_metadata_schema_from_payload(
            preferences.get("SampleMetadataSchema", default_sample_metadata_schema())
        )
        if not preserve_session_tool_state and not getattr(self, "session_active", False):
            self.sample_metadata_schema = sample_metadata_schema_from_payload(
                self.default_sample_metadata_schema
            )
        self.viewer_image_count = int(preferences.get('ViewerImageCount', self.viewer_image_count))
        self.sort_mode = preferences.get('SortMode', self.sort_mode)
        self.default_grid_rows = int(preferences.get('GridRows', self.default_grid_rows))
        self.default_grid_columns = int(preferences.get('GridColumns', self.default_grid_columns))
        self.default_grid_horizontal_pitch = preferences.get('GridHorizontalPitch', self.default_grid_horizontal_pitch)
        self.default_grid_vertical_pitch = preferences.get('GridVerticalPitch', self.default_grid_vertical_pitch)
        self.default_grid_rotation_degrees = preferences.get('GridRotationDegrees', self.default_grid_rotation_degrees)
        self.default_grid_cell_id_direction = preferences.get('GridCellIdDirection', self.default_grid_cell_id_direction)
        self.grid_rows = self.default_grid_rows
        self.grid_columns = self.default_grid_columns
        self.grid_horizontal_pitch = self.default_grid_horizontal_pitch
        self.grid_vertical_pitch = self.default_grid_vertical_pitch
        self.grid_rotation_degrees = self.default_grid_rotation_degrees
        self.grid_cell_id_direction = self.default_grid_cell_id_direction
        self.radius_wheel_step = preferences.get('RadiusWheelStep', self.radius_wheel_step)
        self.grid_pitch_wheel_step = preferences.get('GridPitchWheelStep', self.grid_pitch_wheel_step)
        self.grid_tilt_wheel_step = preferences.get('GridTiltWheelStep', self.grid_tilt_wheel_step)
        self.freeze_finder_width = preferences.get('FreezeFinderWidth', self.freeze_finder_width)
        self.freeze_finder_prominence = preferences.get('FreezeFinderProminence', self.freeze_finder_prominence)
        self.freeze_finder_head_extend_points = int(
            preferences.get('FreezeFinderHeadExtendPoints', self.freeze_finder_head_extend_points)
        )
        self.freeze_finder_tail_extend_points = int(
            preferences.get('FreezeFinderTailExtendPoints', self.freeze_finder_tail_extend_points)
        )
        self.convolution_half_window_points = int(
            preferences.get('ConvolutionHalfWindowPoints', self.convolution_half_window_points)
        )
        self.convolution_ramp_points = int(
            preferences.get('ConvolutionRampPoints', self.convolution_ramp_points)
        )
        self.freeze_finder_detect_brightening = bool(
            preferences.get('FreezeFinderDetectBrightening', self.freeze_finder_detect_brightening)
        )
        self.video_grayscale_mode = normalize_video_grayscale_mode(
            preferences.get('VideoGrayscaleMode', self.video_grayscale_mode)
        )
        self.temperature_cycle_warmup_hysteresis_c = float(
            preferences.get(
                'TemperatureCycleWarmupHysteresisC',
                self.temperature_cycle_warmup_hysteresis_c,
            )
        )
        self.timeseries_palette = preferences.get('TimeseriesPalette', self.timeseries_palette)
        self.timeseries_line_width = float(
            preferences.get('TimeseriesLineWidth', self.timeseries_line_width)
        )
        self.timeseries_convolution_line_width = float(
            preferences.get('TimeseriesConvolutionLineWidth', self.timeseries_convolution_line_width)
        )
        self.timeseries_freeze_line_color = preferences.get(
            'TimeseriesFreezeLineColor',
            self.timeseries_freeze_line_color,
        )
        self.timeseries_freeze_line_width = float(
            preferences.get('TimeseriesFreezeLineWidth', self.timeseries_freeze_line_width)
        )
        self.timeseries_current_frame_color = preferences.get(
            'TimeseriesCurrentFrameColor',
            self.timeseries_current_frame_color,
        )
        self.timeseries_current_frame_line_width = float(
            preferences.get('TimeseriesCurrentFrameLineWidth', self.timeseries_current_frame_line_width)
        )
        self.circle_default_color = preferences.get('CircleDefaultColor', self.circle_default_color)
        self.circle_hover_color = preferences.get('CircleHoverColor', self.circle_hover_color)
        self.circle_selected_color = preferences.get('CircleSelectedColor', self.circle_selected_color)
        self.circle_edit_color = preferences.get('CircleEditColor', self.circle_edit_color)
        self.circle_pressed_color = preferences.get('CirclePressedColor', self.circle_pressed_color)
        self.grid_preview_outline_color = preferences.get('GridPreviewOutlineColor', self.grid_preview_outline_color)
        self.grid_preview_fill_color = preferences.get('GridPreviewFillColor', self.grid_preview_fill_color)
        self.preview_handle_size = float(preferences.get('PreviewHandleSize', self.preview_handle_size))
        self.circle_label_font_size = float(preferences.get('CircleLabelFontSize', self.circle_label_font_size))
        self.circle_label_offset_x = float(preferences.get('CircleLabelOffsetX', self.circle_label_offset_x))
        self.circle_label_offset_y = float(preferences.get('CircleLabelOffsetY', self.circle_label_offset_y))

        if current_tool_state is not None:
            self.circle_radius = current_tool_state["circle_radius"]
            self.grid_rows = current_tool_state["grid_rows"]
            self.grid_columns = current_tool_state["grid_columns"]
            self.grid_horizontal_pitch = current_tool_state["grid_horizontal_pitch"]
            self.grid_vertical_pitch = current_tool_state["grid_vertical_pitch"]
            self.grid_rotation_degrees = current_tool_state["grid_rotation_degrees"]

        if self.undo_stack.count() == 0:
            self.undo_stack.setUndoLimit(self.undo_limit)
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()
        if hasattr(self, "tool_options_stack"):
            self.sync_tool_options_panel()
        if hasattr(self, "radius_textbox"):
            self.updateRadiusTextbox()
        if hasattr(self, "viewer_single_action"):
            self.update_viewer_mode_actions()
        if self.has_frames() and hasattr(self, "view"):
            self.updateImage(self.image_index)
        elif hasattr(self, "view"):
            self.view.viewport().update()
        if hasattr(self, "cell_controller") and self.cell_controller.uses_grid_preview():
            self.update_grid_preview()
        if hasattr(self, "grayscale_plot_widget"):
            self.refresh_grayscale_plot()
        self.scene.update()

    def default_tool_settings(self):
        return {
            "circle_radius": float(self.default_circle_radius),
            "grid_rows": int(self.default_grid_rows),
            "grid_columns": int(self.default_grid_columns),
            "grid_horizontal_pitch": float(self.default_grid_horizontal_pitch),
            "grid_vertical_pitch": float(self.default_grid_vertical_pitch),
            "grid_rotation_degrees": float(self.default_grid_rotation_degrees),
        }

    def serialize_tool_settings(self):
        return self.normalize_tool_settings(
            {
                "circle_radius": self.circle_radius,
                "grid_rows": self.grid_rows,
                "grid_columns": self.grid_columns,
                "grid_horizontal_pitch": self.grid_horizontal_pitch,
                "grid_vertical_pitch": self.grid_vertical_pitch,
                "grid_rotation_degrees": self.grid_rotation_degrees,
            }
        )

    def normalize_tool_settings(self, tool_settings):
        defaults = self.default_tool_settings()
        if not isinstance(tool_settings, dict):
            return defaults

        normalized = dict(defaults)
        numeric_fields = (
            ("circle_radius", float),
            ("grid_rows", int),
            ("grid_columns", int),
            ("grid_horizontal_pitch", float),
            ("grid_vertical_pitch", float),
            ("grid_rotation_degrees", float),
        )
        for field_name, converter in numeric_fields:
            if field_name not in tool_settings:
                continue
            try:
                normalized[field_name] = converter(tool_settings[field_name])
            except (TypeError, ValueError):
                normalized[field_name] = defaults[field_name]

        normalized["circle_radius"] = max(0.1, float(normalized["circle_radius"]))
        normalized["grid_rows"] = max(1, int(normalized["grid_rows"]))
        normalized["grid_columns"] = max(1, int(normalized["grid_columns"]))
        normalized["grid_horizontal_pitch"] = max(0.1, float(normalized["grid_horizontal_pitch"]))
        normalized["grid_vertical_pitch"] = max(0.1, float(normalized["grid_vertical_pitch"]))
        normalized["grid_rotation_degrees"] = max(
            -180.0,
            min(180.0, float(normalized["grid_rotation_degrees"])),
        )
        return normalized

    def apply_tool_settings(self, tool_settings=None, *, sync_ui=False):
        normalized = self.normalize_tool_settings(tool_settings)
        self.circle_radius = normalized["circle_radius"]
        self.grid_rows = normalized["grid_rows"]
        self.grid_columns = normalized["grid_columns"]
        self.grid_horizontal_pitch = normalized["grid_horizontal_pitch"]
        self.grid_vertical_pitch = normalized["grid_vertical_pitch"]
        self.grid_rotation_degrees = normalized["grid_rotation_degrees"]

        if sync_ui:
            if hasattr(self, "radius_textbox"):
                self.updateRadiusTextbox()
            if hasattr(self, "tool_options_stack"):
                self.sync_tool_options_panel()
            if hasattr(self, "cell_controller") and self.cell_controller.uses_grid_preview():
                self.update_grid_preview()

    def get_qcolor(self, color_value):
        if isinstance(color_value, QColor):
            return QColor(color_value)
        try:
            red, green, blue, alpha = [int(part.strip()) for part in str(color_value).split(",")]
            return QColor(red, green, blue, alpha)
        except Exception:
            return QColor(255, 0, 0, 255)

    def sample_visual_color(self, sample_id, alpha=255):
        if sample_id in (None, ""):
            return None
        try:
            palette_index = max(0, int(sample_id))
        except (TypeError, ValueError):
            return None
        red, green, blue = SAMPLE_VISUAL_PALETTE[palette_index % len(SAMPLE_VISUAL_PALETTE)]
        return QColor(red, green, blue, alpha)

    def sample_visual_color_for_cell(self, cell_id, alpha=255):
        record = self.ensure_cell_record(cell_id)
        if record is None:
            return None
        return self.sample_visual_color(getattr(record, "sample_id", ""), alpha=alpha)

    def refresh_cell_sample_visuals(self):
        for item in getattr(self, "cell_items", []):
            item.update()
        if hasattr(self, "scene"):
            self.scene.update()

    def extract_cell_id_from_analysis_header(self, header_text):
        return self.cell_state.extract_cell_id_from_analysis_header(header_text)

    def extract_cell_id_from_label(self, label_text):
        return self.cell_state.extract_cell_id_from_label(label_text)

    def serialize_cell_records(self):
        return self.cell_state.serialize_cell_records()

    def deserialize_cell_records(self, payload):
        return self.cell_state.deserialize_cell_records(payload)

    def ensure_cell_record(self, cell_id):
        return self.cell_state.ensure_cell_record(cell_id)

    def ensure_cell_registry_matches_scene_cells(self):
        self.cell_state.ensure_cell_registry_matches_scene_cells()

    def recompute_next_cell_id(self, preserve_if_larger=True):
        return self.cell_state.recompute_next_cell_id(preserve_if_larger=preserve_if_larger)

    def allocate_cell_id(self):
        return self.cell_state.allocate_cell_id()

    def cell_id_exists(self, cell_id, exclude_cell_id=None):
        return self.cell_state.cell_id_exists(cell_id, exclude_cell_id=exclude_cell_id)

    def rename_cell_id(self, old_cell_id, new_cell_id):
        return self.cell_state.rename_cell_id(old_cell_id, new_cell_id)

    def clear_cell_analysis(self):
        self.cell_state.clear_cell_analysis()

    def sync_cell_analysis_from_results(self):
        self.cell_state.sync_cell_analysis_from_results()

    def prune_analysis_results_for_deleted_cells(self, deleted_cell_ids):
        return self.cell_state.prune_analysis_results_for_deleted_cells(deleted_cell_ids)

    def serialize_sample_catalog(self):
        return serialize_sample_catalog_payload(
            getattr(self, "sample_catalog", {}),
            self.active_sample_metadata_schema(),
        )

    def deserialize_sample_catalog(self, payload):
        return deserialize_sample_catalog_payload(payload, self.active_sample_metadata_schema())

    def active_sample_metadata_schema(self):
        return sample_metadata_schema_from_payload(
            getattr(self, "sample_metadata_schema", None)
        )

    def serialize_sample_metadata_schema(self):
        return sample_metadata_schema_to_payload(self.active_sample_metadata_schema())

    def sample_metadata_field_names(self):
        return tuple(field["key"] for field in self.active_sample_metadata_schema())

    def freeze_count_timeseries_sample_metadata_field_names(self):
        return export_sample_metadata_field_keys(self.active_sample_metadata_schema())

    def apply_sample_metadata_schema(self, new_schema, rename_map=None, *, record_history=True):
        old_schema = self.active_sample_metadata_schema()
        normalized_new_schema = sample_metadata_schema_from_payload(new_schema)
        before_state = self.capture_data_state() if record_history else None
        self.sample_catalog = migrate_sample_catalog_for_schema(
            getattr(self, "sample_catalog", {}),
            old_schema,
            normalized_new_schema,
            rename_map=rename_map,
        )
        self.sample_metadata_schema = normalized_new_schema
        self.refresh_freeze_count_timeseries_metadata_from_sample_catalog(relabel_headers=True)
        self.refresh_sample_catalog_tree(preserve_selection=True)
        self.update_cursor_sample_controls()
        self.refresh_cells_panel()
        if record_history and before_state is not None:
            self.push_data_history("Update Sample Metadata Fields", before_state)

    def used_sample_ids(self):
        used_ids = set()
        for sample_id in getattr(self, "sample_catalog", {}).keys():
            try:
                used_ids.add(int(sample_id))
            except (TypeError, ValueError):
                continue
        for record in getattr(self, "cell_records_by_id", {}).values():
            sample_value = str(getattr(record, "sample_id", "")).strip()
            if not sample_value:
                continue
            try:
                sample_id = int(sample_value)
            except (TypeError, ValueError):
                continue
            if sample_id >= 0:
                used_ids.add(sample_id)
        return used_ids

    def lowest_available_sample_id(self):
        used_ids = self.used_sample_ids()
        next_id = 0
        while next_id in used_ids:
            next_id += 1
        return next_id

    def recompute_next_sample_id(self, preserve_if_larger=True):
        derived_next = self.lowest_available_sample_id()
        if preserve_if_larger:
            self.next_sample_id = max(int(getattr(self, "next_sample_id", 0)), derived_next)
        else:
            self.next_sample_id = derived_next
        if self.next_sample_id < 0:
            self.next_sample_id = 0
        return self.next_sample_id

    def allocate_sample_id(self):
        sample_id = int(self.recompute_next_sample_id(preserve_if_larger=False))
        return sample_id

    def default_sample_name(self, sample_id):
        try:
            sample_id = int(sample_id)
        except (TypeError, ValueError):
            sample_id = 0
        pattern = str(getattr(self, "sample_name_pattern", "Sample_#") or "Sample_#")
        sample_id_text = str(sample_id)
        output = []
        index = 0
        while index < len(pattern):
            char = pattern[index]
            if char == "\\":
                if index + 1 < len(pattern) and pattern[index + 1] in ("#", "\\"):
                    output.append(pattern[index + 1])
                    index += 2
                    continue
                output.append("\\")
                index += 1
                continue
            if char == "#":
                output.append(sample_id_text)
            else:
                output.append(char)
            index += 1
        return "".join(output)

    def sample_name_for_id(self, sample_id):
        return str(self.sample_record_for_id(sample_id).get("sample_name", ""))

    def sample_record_for_id(self, sample_id):
        if sample_id in (None, ""):
            return normalize_sample_catalog_record({}, self.active_sample_metadata_schema())
        try:
            sample_key = int(sample_id)
        except (TypeError, ValueError):
            return normalize_sample_catalog_record({}, self.active_sample_metadata_schema())
        return normalize_sample_catalog_record(
            self.sample_catalog.get(sample_key, {}),
            self.active_sample_metadata_schema(),
        )

    def default_sample_record(self, sample_id):
        active_schema = self.active_sample_metadata_schema()
        record = normalize_sample_catalog_record({}, active_schema)
        record["sample_name"] = self.default_sample_name(sample_id)
        for field_key, value in same_for_all_sample_metadata_values(
            getattr(self, "sample_catalog", {}),
            active_schema,
        ).items():
            record[field_key] = value
        return record

    def build_freeze_count_timeseries_sample_column_metadata(self, sample):
        active_schema = (
            self.active_sample_metadata_schema()
            if hasattr(self, "active_sample_metadata_schema")
            else sample_metadata_schema_from_payload(getattr(self, "sample_metadata_schema", None))
        )
        sample_id = str(sample.get("sample_id", "") or "").strip()
        if sample_id:
            record = self.sample_record_for_id(sample_id)
        else:
            record = normalize_sample_catalog_record({}, active_schema)
            record["sample_name"] = str(sample.get("sample_name", "") or "")
        sample_cell_count = None
        if sample.get("total_cells", "") not in (None, ""):
            sample_cell_count = max(0, int(sample.get("total_cells", 0)))
        elif sample.get("cell_ids"):
            sample_cell_count = len({int(cell_id) for cell_id in sample.get("cell_ids", [])})
        elif sample_id:
            sample_cell_count = sum(
                1
                for cell_record in getattr(self, "cell_records_by_id", {}).values()
                if str(getattr(cell_record, "sample_id", "")).strip() == sample_id
            )
        cell_number = "" if sample_cell_count is None else str(int(sample_cell_count))

        return {
            "sample_id": sample_id,
            "cell_number": cell_number,
            **{
                field_name: str(record.get(field_name, "") or "")
                for field_name in export_sample_metadata_field_keys(
                    active_schema
                )
            },
        }

    def freeze_count_timeseries_sample_column_metadata(self):
        return list(
            getattr(self, "freeze_count_timeseries_summary", {}).get("sample_column_metadata", [])
            or []
        )

    def build_freeze_count_timeseries_missing_metadata_report(self):
        missing_session_fields = []
        for field_name in (
            "project_name",
            "user_name",
            "institution",
            "date",
        ):
            if not str(self.serialize_session_metadata().get(field_name, "") or "").strip():
                missing_session_fields.append(field_name)

        missing_sample_lines = []
        seen_sample_ids = set()
        for sample_metadata in self.freeze_count_timeseries_sample_column_metadata():
            sample_id = str(sample_metadata.get("sample_id", "") or "").strip()
            if not sample_id or sample_id in seen_sample_ids:
                continue
            seen_sample_ids.add(sample_id)
            missing_fields = [
                field_name
                for field_name in export_sample_metadata_field_keys(
                    getattr(self, "sample_metadata_schema", None)
                )
                if field_name != "sample_name"
                and not str(sample_metadata.get(field_name, "") or "").strip()
            ]
            if not missing_fields:
                continue
            sample_name = str(sample_metadata.get("sample_name", "") or "").strip()
            if sample_name:
                missing_sample_lines.append(
                    f"Sample {sample_id} ({sample_name}): " + ", ".join(missing_fields)
                )
            else:
                missing_sample_lines.append(
                    f"Sample {sample_id}: " + ", ".join(missing_fields)
                )

        if not missing_session_fields and not missing_sample_lines:
            return []

        report_lines = [
            "Missing metadata values were written as nan in the exported Freeze Count Timeseries CSV.",
        ]
        if missing_session_fields:
            report_lines.append("")
            report_lines.append("Session metadata:")
            report_lines.extend(f"- {field_name}" for field_name in missing_session_fields)
        if missing_sample_lines:
            report_lines.append("")
            report_lines.append("Sample metadata:")
            report_lines.extend(f"- {line}" for line in missing_sample_lines)
        return report_lines

    def show_freeze_count_timeseries_export_notice(self, exported_paths):
        report_lines = self.build_freeze_count_timeseries_missing_metadata_report()
        if not report_lines:
            return

        paths = [str(path) for path in exported_paths if str(path).strip()]
        if len(paths) == 1:
            summary_text = (
                "Freeze Count Timeseries CSV export completed.\n\n"
                "Some metadata values were missing and were written as nan."
            )
        else:
            summary_text = (
                "Freeze Count Timeseries CSV export completed.\n\n"
                f"{len(paths)} files were exported. Some metadata values were missing and were written as nan."
            )
        self.show_detailed_information_dialog(
            "Freeze Count Timeseries CSV export",
            summary_text,
            "\n".join(report_lines),
        )

    def ensure_sample_catalog_matches_cell_records(self):
        if not hasattr(self, "sample_catalog") or not isinstance(self.sample_catalog, dict):
            self.sample_catalog = {}
        for record in getattr(self, "cell_records_by_id", {}).values():
            sample_value = str(getattr(record, "sample_id", "")).strip()
            if not sample_value:
                continue
            try:
                sample_id = int(sample_value)
            except (TypeError, ValueError):
                continue
            if sample_id < 0:
                continue
            if sample_id not in self.sample_catalog:
                self.sample_catalog[sample_id] = self.default_sample_record(sample_id)
        self.recompute_next_sample_id(preserve_if_larger=False)

    def cursor_sample_catalog_signature(self):
        return tuple(
            (
                str(int(sample_id)),
                str(
                    normalize_sample_catalog_record(
                        sample_record,
                        self.active_sample_metadata_schema(),
                    ).get("sample_name", "")
                ),
            )
            for sample_id, sample_record in sorted(self.sample_catalog.items(), key=lambda pair: int(pair[0]))
        )

    def ordered_sample_catalog_records(self):
        return [
            (
                int(sample_id),
                normalize_sample_catalog_record(
                    sample_record,
                    self.active_sample_metadata_schema(),
                ),
            )
            for sample_id, sample_record in sorted(
                getattr(self, "sample_catalog", {}).items(),
                key=lambda pair: int(pair[0]),
            )
        ]

    def available_sample_names(self):
        return [
            str(sample_record.get("sample_name", "") or "")
            for _, sample_record in self.ordered_sample_catalog_records()
            if str(sample_record.get("sample_name", "") or "").strip()
        ]

    def available_sample_choices(self):
        records = [
            (sample_id, str(sample_record.get("sample_name", "") or "").strip())
            for sample_id, sample_record in self.ordered_sample_catalog_records()
            if str(sample_record.get("sample_name", "") or "").strip()
        ]
        name_counts = {}
        for _sample_id, sample_name in records:
            normalized_name = normalize_sample_name(sample_name)
            name_counts[normalized_name] = name_counts.get(normalized_name, 0) + 1

        choices = []
        for sample_id, sample_name in records:
            label = sample_name
            if name_counts.get(normalize_sample_name(sample_name), 0) > 1:
                label = f"{sample_name} (sample {int(sample_id)})"
            choices.append(
                {
                    "sample_id": str(int(sample_id)),
                    "sample_name": sample_name,
                    "label": label,
                }
            )
        return choices

    def invalidate_cursor_sample_combo_cache(self):
        self.cursor_sample_combo_catalog_signature = None
        self.cursor_sample_combo_has_mixed_item = False

    def set_cursor_sample_combo_mixed_item_visible(self, visible):
        if not hasattr(self, "cursor_sample_combo"):
            return

        mixed_index = self.cursor_sample_combo.findData("__mixed__")
        currently_visible = mixed_index >= 0
        if visible == currently_visible:
            self.cursor_sample_combo_has_mixed_item = visible
            return

        blocker = QSignalBlocker(self.cursor_sample_combo)
        if visible:
            self.cursor_sample_combo.insertItem(0, "Mixed Selection", "__mixed__")
        elif mixed_index >= 0:
            self.cursor_sample_combo.removeItem(mixed_index)
        self.cursor_sample_combo_has_mixed_item = visible

    def refresh_cursor_sample_combo_catalog(self, include_mixed_item=False, force=False):
        if not hasattr(self, "cursor_sample_combo"):
            return

        catalog_signature = self.cursor_sample_catalog_signature()
        cached_signature = getattr(self, "cursor_sample_combo_catalog_signature", None)
        needs_rebuild = force or (catalog_signature != cached_signature) or (self.cursor_sample_combo.count() == 0)

        if needs_rebuild:
            blocker = QSignalBlocker(self.cursor_sample_combo)
            self.cursor_sample_combo.clear()
            self.cursor_sample_combo.addItem("None", "")
            for sample_id_text, sample_name in catalog_signature:
                self.cursor_sample_combo.addItem(sample_id_text, sample_id_text)
            self.cursor_sample_combo_catalog_signature = catalog_signature
            self.cursor_sample_combo_has_mixed_item = False

        self.set_cursor_sample_combo_mixed_item_visible(include_mixed_item)

    def summarize_integer_list(self, values, limit=8):
        normalized_values = []
        for value in values:
            try:
                normalized_values.append(int(value))
            except (TypeError, ValueError):
                continue
        if not normalized_values:
            return "-"

        unique_values = sorted(set(normalized_values))
        preview = ", ".join(str(value) for value in unique_values[:limit])
        if len(unique_values) > limit:
            preview += f", +{len(unique_values) - limit} more"
        return preview

    def format_numeric_display(self, value, decimals=1):
        if value in (None, ""):
            return "-"
        try:
            return f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            return "-"

    def set_cursor_display_field_locked(self, field, locked):
        if field is None:
            return
        field.setEnabled(True)
        field.setReadOnly(bool(locked))
        field.setFocusPolicy(Qt.NoFocus if locked else Qt.StrongFocus)

    def format_integer_list_csv(self, values):
        normalized_values = []
        seen_values = set()
        for value in values:
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                continue
            if normalized in seen_values:
                continue
            seen_values.add(normalized)
            normalized_values.append(normalized)
        if not normalized_values:
            return "-"
        return ", ".join(str(value) for value in normalized_values)

    def parse_integer_csv_text(self, text, *, allow_empty=True, minimum=None, maximum=None):
        raw_text = str(text or "").strip()
        if not raw_text:
            return [] if allow_empty else None

        values = []
        seen_values = set()
        for token in raw_text.split(","):
            piece = token.strip()
            if not piece:
                continue
            try:
                value = int(piece)
            except (TypeError, ValueError):
                return None
            if minimum is not None and value < minimum:
                return None
            if maximum is not None and value > maximum:
                return None
            if value in seen_values:
                continue
            seen_values.add(value)
            values.append(value)
        return values

    def parse_freeze_frame_text(self, text):
        raw_text = str(text or "").strip()
        if raw_text.lower() in {"", "none", "-", "clear"}:
            return []
        return self.parse_integer_csv_text(raw_text, allow_empty=True, minimum=0, maximum=100000)

    def rebuild_freeze_rows_for_cell(self, cell_id, freeze_event_indices):
        rebuilt_rows = []
        label = f"cell_{int(cell_id)}"
        for frame_index in freeze_event_indices:
            image_name = ""
            if 0 <= int(frame_index) < len(self.grayscale_results_rows):
                row = self.grayscale_results_rows[int(frame_index)]
                if len(row) > 0:
                    image_name = str(row[0])
            elif 0 <= int(frame_index) < self.frame_count():
                image_name = str(self.frame_name(int(frame_index)))
            rebuilt_rows.append([
                label,
                str(int(frame_index)),
                image_name,
            ])
        return rebuilt_rows

    def apply_manual_freeze_event_indices(
        self,
        cell_id,
        freeze_event_indices,
        refresh_tables=True,
        refresh_freeze_markers=True,
        refresh_freeze_count_table=True,
    ):
        return self.apply_manual_freeze_event_indices_batch(
            {int(cell_id): freeze_event_indices},
            refresh_tables=refresh_tables,
            refresh_freeze_markers=refresh_freeze_markers,
            refresh_freeze_count_table=refresh_freeze_count_table,
        )

    def apply_manual_freeze_event_indices_batch(
        self,
        freeze_event_indices_by_cell_id,
        refresh_tables=True,
        refresh_freeze_markers=True,
        refresh_freeze_count_table=True,
    ):
        normalized_by_cell_id = {}
        rebuilt_rows_by_cell_id = {}
        for cell_id, freeze_event_indices in (freeze_event_indices_by_cell_id or {}).items():
            try:
                normalized_cell_id = int(cell_id)
            except (TypeError, ValueError):
                continue
            record = self.ensure_cell_record(normalized_cell_id)
            if record is None:
                continue

            normalized_indices = sorted({int(value) for value in freeze_event_indices})
            record.freeze_event_indices = list(normalized_indices)
            rebuilt_rows = self.rebuild_freeze_rows_for_cell(normalized_cell_id, normalized_indices)
            record.freeze_rows = [list(row) for row in rebuilt_rows]
            normalized_by_cell_id[normalized_cell_id] = normalized_indices
            rebuilt_rows_by_cell_id[normalized_cell_id] = rebuilt_rows

        if not normalized_by_cell_id:
            return []

        target_labels = {
            f"cell_{int(cell_id)}"
            for cell_id in normalized_by_cell_id
        }
        kept_rows = [
            list(row)
            for row in self.freeze_results_rows
            if not row or str(row[0]) not in target_labels
        ]
        for cell_id in sorted(rebuilt_rows_by_cell_id):
            kept_rows.extend(rebuilt_rows_by_cell_id[cell_id])
        kept_rows.sort(
            key=lambda row: (
                self.extract_cell_id_from_label(row[0] if row else None) or -1,
                int(row[1]) if len(row) > 1 and str(row[1]).strip().isdigit() else -1,
            )
        )
        self.freeze_results_rows = kept_rows
        if any(rebuilt_rows_by_cell_id.values()) and not self.freeze_results_headers:
            self.freeze_results_headers = ["cell", "image_index", "image_name"]
        self.last_freeze_output_path = None
        if hasattr(self, "grayscale_plot_widget"):
            self.grayscale_plot_widget.invalidate_render_cache()
        self.invalidate_freeze_count_timeseries_results(
            "freeze frame annotations changed",
            refresh_table=refresh_freeze_count_table,
        )
        if refresh_tables:
            self.refresh_freeze_annotation_views()
        elif refresh_freeze_markers:
            self.refresh_freeze_flag_markers()
        return sorted(normalized_by_cell_id)

    def selected_cell_freeze_frames(self, selected_items=None):
        if selected_items is None:
            if not hasattr(self, "cell_controller") or not hasattr(self, "scene"):
                return []
            selected_items = self.get_selected_cell_items()
        if not self.has_frames():
            return []

        selected_freeze_frames = set()
        frame_count = self.frame_count()
        if selected_items:
            records = [
                self.ensure_cell_record(getattr(item, "cell_id", None))
                for item in selected_items
            ]
        else:
            records = list(getattr(self, "cell_records_by_id", {}).values())
        for record in records:
            if record is None:
                continue
            for frame_value in getattr(record, "freeze_event_indices", []):
                try:
                    frame_index = int(frame_value)
                except (TypeError, ValueError):
                    continue
                if 0 <= frame_index < frame_count:
                    selected_freeze_frames.add(frame_index)
        return sorted(selected_freeze_frames)

    def refresh_freeze_flag_markers(self, selected_items=None):
        if not hasattr(self, "image_slider"):
            return

        previous_frames = set(getattr(self, "flagframe_list", []))
        self.flagframe_list = self.selected_cell_freeze_frames(selected_items=selected_items)
        current_frames = set(self.flagframe_list)
        self.image_slider.sync_marker_state(
            self.keyframe_list,
            self.flagframe_list,
            self.analysis_start_frame_list,
            self.analysis_end_frame_list,
        )
        changed_frames = previous_frames | current_frames
        if changed_frames:
            self.update_image_list_annotations(sorted(changed_frames))
        self.update_toggle_flagging_button_icon()

    def selected_cells_freeze_state_at_current_frame(self, selected_items=None):
        if selected_items is None:
            if not hasattr(self, "cell_controller") or not hasattr(self, "scene"):
                return False, False
            selected_items = self.get_selected_cell_items()
        if not self.has_frames():
            return False, False

        frame_index = int(self.image_index)
        has_any = False
        has_all = True
        if selected_items:
            records = [
                self.ensure_cell_record(getattr(item, "cell_id", None))
                for item in selected_items
            ]
        else:
            records = list(getattr(self, "cell_records_by_id", {}).values())
        records = [record for record in records if record is not None]
        if not records:
            return False, False
        for record in records:
            freeze_values = set()
            for value in getattr(record, "freeze_event_indices", []):
                try:
                    freeze_values.add(int(value))
                except (TypeError, ValueError):
                    continue
            cell_has_frame = frame_index in freeze_values
            has_any = has_any or cell_has_frame
            has_all = has_all and cell_has_frame
        return has_any, has_all

    def toggle_selected_cells_freeze_at_current_frame(self):
        selected_items = sorted(
            self.get_selected_cell_items(),
            key=lambda item: int(getattr(item, "cell_id", 0)),
        )
        if not selected_items or not self.has_frames():
            return False

        frame_index = int(self.image_index)
        if not (0 <= frame_index < self.frame_count()):
            return False

        _has_any, has_all = self.selected_cells_freeze_state_at_current_frame(selected_items)
        should_add = not has_all
        before_state = self.capture_freeze_annotation_state()
        updated_values_by_cell_id = {}
        for item in selected_items:
            cell_id = int(item.cell_id)
            record = self.ensure_cell_record(cell_id)
            current_values_set = set()
            for value in getattr(record, "freeze_event_indices", []):
                try:
                    current_values_set.add(int(value))
                except (TypeError, ValueError):
                    continue
            current_values = sorted(current_values_set)
            if should_add:
                if frame_index in current_values:
                    continue
                updated_values = sorted(current_values + [frame_index])
            else:
                if frame_index not in current_values:
                    continue
                updated_values = [value for value in current_values if value != frame_index]
            updated_values_by_cell_id[cell_id] = updated_values

        if not updated_values_by_cell_id:
            return False

        changed_cell_ids = self.apply_manual_freeze_event_indices_batch(
            updated_values_by_cell_id,
            refresh_tables=False,
            refresh_freeze_markers=False,
            refresh_freeze_count_table=False,
        )
        self.refresh_freeze_annotation_views_fast(
            changed_cell_ids,
            selected_items=selected_items,
            marker_updates={frame_index: should_add},
        )
        self.refresh_cursor_selection_info(selected_items=selected_items)
        action_text = "Mark Freeze Frame" if should_add else "Clear Freeze Frame"
        self.push_freeze_annotation_history(action_text, before_state)
        cell_text = self.summarize_integer_list(changed_cell_ids)
        if should_add:
            self.log(f"Mark frame {frame_index} as frozen for cell(s) {cell_text}")
        else:
            self.log(f"Clear frame {frame_index} as frozen for cell(s) {cell_text}")
        return True

    def build_cells_panel_records(self):
        self.ensure_cell_registry_matches_scene_cells()
        records = []
        for cell_id in sorted(self.cell_records_by_id.keys()):
            record = self.ensure_cell_record(cell_id)
            sample_id = str(getattr(record, "sample_id", ""))
            sample_name = self.sample_name_for_id(sample_id)
            freeze_frames = list(getattr(record, "freeze_event_indices", []))
            freeze_rows = list(getattr(record, "freeze_rows", []))
            records.append({
                "cell_id": int(cell_id),
                "sample_id": sample_id,
                "sample_name": sample_name,
                "freeze_frames": self.summarize_integer_list(freeze_frames),
            })
        return records

    def refresh_cells_panel(self, changed_columns=None, preserve_selection=False):
        if not hasattr(self, "cells_tree_widget"):
            return
        if (not self.should_refresh_cells_panel_from_redraw()) and not bool(getattr(self, "cells_panel_force_refresh", False)):
            self.cells_panel_dirty = True
            return

        expanded_cell_ids = set()
        for index in range(self.cells_tree_widget.topLevelItemCount()):
            item = self.cells_tree_widget.topLevelItem(index)
            if item.isExpanded():
                cell_id = item.data(0, Qt.UserRole)
                if cell_id is not None:
                    expanded_cell_ids.add(int(cell_id))
        selected_cell_ids = {
            int(item.cell_id)
            for item in self.get_selected_cell_items()
        }

        records = self.build_cells_panel_records()
        tree_snapshot = tuple(
            (
                record["cell_id"],
                record["sample_id"],
                record["sample_name"],
                record["freeze_frames"],
            )
            for record in records
        )
        if tree_snapshot == getattr(self, "cells_panel_last_snapshot", None) and not bool(getattr(self, "cells_panel_force_refresh", False)):
            self.cells_panel_dirty = False
            return

        tree_blocker = QSignalBlocker(self.cells_tree_widget)
        try:
            self.cells_tree_widget.clear()
            for record in records:
                cell_id = int(record["cell_id"])
                sample_id = str(record["sample_id"] or "-")
                sample_name = str(record["sample_name"] or "-")
                freeze_frames = str(record["freeze_frames"] or "-")
                top_item = QTreeWidgetItem([f"Cell {cell_id}", ""])
                top_item.setData(0, Qt.UserRole, cell_id)

                detail_rows = (
                    ("Cell ID", str(cell_id)),
                    ("Sample ID", sample_id),
                    ("Sample Name", sample_name),
                    ("Freeze Frame(s)", freeze_frames),
                )
                for field_name, value_text in detail_rows:
                    child_item = QTreeWidgetItem([field_name, value_text])
                    child_item.setFlags(child_item.flags() & ~Qt.ItemIsSelectable)
                    top_item.addChild(child_item)

                self.cells_tree_widget.addTopLevelItem(top_item)
                if cell_id in expanded_cell_ids:
                    top_item.setExpanded(True)
                if cell_id in selected_cell_ids:
                    top_item.setSelected(True)
        finally:
            del tree_blocker

        self.cells_panel_last_snapshot = tree_snapshot
        self.cells_panel_dirty = False
        self.cells_panel_force_refresh = False

    def sync_cells_panel_selection(self):
        if not hasattr(self, "cells_tree_widget"):
            return
        selected_cell_ids = {
            int(item.cell_id)
            for item in self.get_selected_cell_items()
        }
        blocker = QSignalBlocker(self.cells_tree_widget)
        try:
            for index in range(self.cells_tree_widget.topLevelItemCount()):
                item = self.cells_tree_widget.topLevelItem(index)
                cell_id = item.data(0, Qt.UserRole)
                if cell_id is None:
                    continue
                item.setSelected(int(cell_id) in selected_cell_ids)
        finally:
            del blocker

    def handle_cells_panel_selection_changed(self):
        if not hasattr(self, "cells_tree_widget"):
            return
        selected_cell_ids = []
        for item in self.cells_tree_widget.selectedItems():
            if item.parent() is not None:
                continue
            cell_id = item.data(0, Qt.UserRole)
            if cell_id is None:
                continue
            selected_cell_ids.append(int(cell_id))
        self.reselect_cell_ids(selected_cell_ids, sync_tool_panel=True)

    def should_refresh_cells_panel_from_redraw(self):
        if bool(getattr(self, "preview_frame_update_in_progress", False)):
            return False
        dock = getattr(self, "cells_dock", None)
        if dock is None or (not shiboken6.isValid(dock)):
            return False
        toggle_action = dock.toggleViewAction()
        if toggle_action is None:
            return True
        return bool(toggle_action.isChecked())

    def handle_cells_panel_visibility_changed(self, visible):
        if not visible:
            return
        self.cells_panel_force_refresh = True
        self.refresh_cells_panel()

    def handle_grayscale_plot_visibility_changed(self, visible):
        if not visible:
            return
        self.refresh_grayscale_plot()
        self.update_grayscale_plot_current_frame(force=True)

    def refresh_cursor_selection_info(self, selected_items=None):
        if not hasattr(self, "cursor_info_value_labels"):
            return 0

        if selected_items is None:
            selected_items = sorted(
                self.get_selected_cell_items(),
                key=lambda item: int(getattr(item, "cell_id", 0)),
            )

        selected_ids = []
        selected_sample_names = set()
        for item in selected_items:
            selected_ids.append(int(item.cell_id))
            record = self.ensure_cell_record(item.cell_id)
            sample_id = str(getattr(record, "sample_id", ""))
            selected_sample_names.add(self.sample_name_for_id(sample_id))

        info_values = {
            "cell_id": "-",
            "sample_name": "-",
            "x": "-",
            "y": "-",
            "radius": "-",
            "selected": "0",
        }
        if len(selected_items) == 1:
            item = selected_items[0]
            record = self.ensure_cell_record(item.cell_id)
            pixel_x = None
            pixel_y = None
            radius = None
            try:
                pixel_x = float(item.circle_pixel_positions[0])
                pixel_y = float(item.circle_pixel_positions[1])
                radius = float(item.circle_sizes)
            except (AttributeError, IndexError, TypeError, ValueError):
                pass
            info_values.update({
                "cell_id": str(int(item.cell_id)),
                "sample_name": self.sample_name_for_id(getattr(record, "sample_id", "")) or "-",
                "x": self.format_numeric_display(pixel_x),
                "y": self.format_numeric_display(pixel_y),
                "radius": self.format_numeric_display(radius),
            })
        elif len(selected_items) > 1:
            selected_sample_name_values = {value for value in selected_sample_names}
            if len(selected_sample_name_values) == 1:
                only_sample_name = next(iter(selected_sample_name_values))
                sample_name_text = only_sample_name or "-"
            else:
                sample_name_text = "Mixed"
            info_values.update({
                "selected": str(len(selected_items)),
                "cell_id": self.summarize_integer_list(selected_ids),
                "sample_name": sample_name_text,
                "x": "Multiple",
                "y": "Multiple",
                "radius": "Multiple",
            })

        for field_name, value_label in self.cursor_info_value_labels.items():
            value_label.setText(str(info_values.get(field_name, "-")))

        has_selection = bool(selected_items)
        single_selected = len(selected_items) == 1
        self.cursor_info_section_label.setVisible(has_selection)
        self.cursor_info_row_widgets["selected"].setVisible(len(selected_items) > 1)
        self.cursor_info_row_widgets["cell_id"].setVisible(has_selection)
        self.cursor_info_row_widgets["sample_name"].setVisible(has_selection)
        self.cursor_info_row_widgets["x"].setVisible(single_selected)
        self.cursor_info_row_widgets["y"].setVisible(single_selected)
        self.cursor_info_row_widgets["radius"].setVisible(single_selected)
        self.cursor_info_label_widgets["cell_id"].setText("Cell IDs:" if len(selected_items) > 1 else "Cell ID:")

        return len(selected_ids)

    def update_cursor_record_edit_state(self, selected_items=None):
        if not hasattr(self, "cursor_sample_combo"):
            return

        if selected_items is None:
            selected_items = sorted(
                self.get_selected_cell_items(),
                key=lambda item: int(getattr(item, "cell_id", 0)),
            )

        has_selection = bool(selected_items)
        single_selected = len(selected_items) == 1
        self.cursor_edit_section_label.setVisible(has_selection)
        if hasattr(self, "cursor_info_edit_separator"):
            self.cursor_info_edit_separator.setVisible(has_selection)
        self.cursor_sample_row.setVisible(has_selection)
        self.cursor_sample_button_row.setVisible(has_selection)
        self.cursor_freeze_row.setVisible(single_selected)
        if hasattr(self, "cursor_freeze_lineedit"):
            self.cursor_freeze_lineedit.setEnabled(single_selected)
            if hasattr(self, "cursor_freeze_apply_button"):
                self.cursor_freeze_apply_button.setEnabled(single_selected)
            blocker = QSignalBlocker(self.cursor_freeze_lineedit)
            if single_selected:
                record = self.ensure_cell_record(selected_items[0].cell_id)
                freeze_values = [int(value) for value in getattr(record, "freeze_event_indices", [])]
                self.cursor_freeze_lineedit.setText(
                    "None" if not freeze_values else self.format_integer_list_csv(freeze_values)
                )
                self.cursor_freeze_lineedit.setPlaceholderText("None")
            else:
                self.cursor_freeze_lineedit.clear()
                self.cursor_freeze_lineedit.setPlaceholderText("")

    def apply_cursor_freeze_frames_edit(self):
        selected_items = sorted(
            self.get_selected_cell_items(),
            key=lambda item: int(getattr(item, "cell_id", 0)),
        )
        if len(selected_items) != 1:
            return False

        if not hasattr(self, "cursor_freeze_lineedit"):
            return False

        parsed_values = self.parse_freeze_frame_text(self.cursor_freeze_lineedit.text())
        if parsed_values is None:
            QMessageBox.warning(
                self,
                "Freeze Frame",
                "Enter freeze frames as comma-separated non-negative integers, or use None to clear them.",
            )
            return False

        target_cell_id = int(selected_items[0].cell_id)
        current_values = [
            int(value)
            for value in getattr(self.ensure_cell_record(target_cell_id), "freeze_event_indices", [])
        ]
        if current_values == parsed_values:
            self.cursor_freeze_lineedit.clearFocus()
            if hasattr(self, "view"):
                self.view.setFocus()
                self.view.viewport().setFocus()
            return True

        before_state = self.capture_freeze_annotation_state()
        changed_cell_ids = self.apply_manual_freeze_event_indices(
            target_cell_id,
            parsed_values,
            refresh_tables=False,
            refresh_freeze_markers=False,
            refresh_freeze_count_table=False,
        )
        self.refresh_freeze_annotation_views_fast(
            changed_cell_ids,
            selected_items=selected_items,
            refresh_plot=True,
        )
        self.refresh_cursor_selection_info(selected_items=selected_items)
        self.push_freeze_annotation_history("Edit Freeze Frames", before_state)
        self.log(
            f"Update freeze frames for cell {target_cell_id} to "
            f"{self.format_integer_list_csv(parsed_values)}"
        )
        self.cursor_freeze_lineedit.clearFocus()
        if hasattr(self, "view"):
            self.view.setFocus()
            self.view.viewport().setFocus()
        return True

    def current_single_edit_target_item(self):
        target_items = self.cell_controller.get_edit_chosen_items()
        if len(target_items) == 1:
            return target_items[0]
        target_items = self.get_edit_target_items()
        if len(target_items) == 1:
            return target_items[0]
        return None

    def apply_edit_circle_cell_id_edit(self):
        if self.tool_mode != "edit-new" or not hasattr(self, "edit_circle_cell_id_spinbox"):
            return

        target_item = self.current_single_edit_target_item()
        if target_item is None:
            return

        old_cell_id = int(target_item.cell_id)
        new_cell_id = int(self.edit_circle_cell_id_spinbox.value())
        if new_cell_id == old_cell_id:
            return

        before_state = self.capture_cell_state(include_analysis=True)
        renamed, message = self.rename_cell_id(old_cell_id, new_cell_id)
        if not renamed:
            QMessageBox.warning(self, "Rename Cell ID", message or "Unable to rename the selected cell.")
            self.sync_tool_options_panel()
            return

        self.cell_controller.redraw_current_cells(preserve_selection=False, force_scene_scan=True)
        self.reset_cell_items_edit_chosen()
        for item in self.cell_items:
            if int(getattr(item, "cell_id", -1)) == new_cell_id:
                item.edit_chosen = True
                item.update()
                break
        self.reselect_cell_ids([new_cell_id], sync_tool_panel=False)
        self.refresh_grayscale_plot()
        self.push_cell_history("Rename Cell ID", before_state, include_analysis=True)
        self.log(f"Rename cell {old_cell_id} to {new_cell_id}")
        self.sync_tool_options_panel()

    def initData(self):
        # Gets called so wiped at loading images
        # All Attributes related to data
        if hasattr(self, 'image_cache'):
            self.image_cache.clear()
        if hasattr(self, 'pixmap_cache'):
            self.pixmap_cache.clear()
        self.cell_items = [] # current displayed cell items
        self.rendered_cell_items = [] # currently drawn QGraphics items for cells
        self.next_cell_id = 0
        self.cell_records_by_id = {}
        self.sample_metadata_schema = sample_metadata_schema_from_payload(
            getattr(self, "default_sample_metadata_schema", default_sample_metadata_schema())
        )
        self.sample_catalog = {}
        self.invalidate_cursor_sample_combo_cache()
        self.next_sample_id = 0
        self.image_edit_exposure = 0.0
        self.image_edit_contrast = 0.0
        self.image_edit_uniform_exposure_area_x = None
        self.image_edit_uniform_exposure_area_y = None
        self.image_edit_uniform_exposure_area_width = None
        self.image_edit_uniform_exposure_area_height = None
        self.image_edit_uniform_exposure_offsets = {}
        self.image_edit_crop_center_x = None
        self.image_edit_crop_center_y = None
        self.image_edit_crop_width = None
        self.image_edit_crop_height = None
        self.image_edit_crop_angle = 0.0

        self.keyframe_list = []
        self.flagframe_list = []
        self.analysis_start_frame_list = []
        self.analysis_end_frame_list = []
        self.keyframe_cell_items_dict = {} # a dictionary. {frame number: cell_items}
        
        
        self.image_width = None  # Add image_width attribute
        self.imagePaths = []
        self.imageNames = []
        self.frame_source = ImageSequenceFrameSource([])
        self.image_index = 0  # Index of the currently displayed image
        self.last_committed_image_index = 0
        self.pending_preview_image_index = None
        self.preview_frame_update_in_progress = False
        self.video_preview_decoder = None
        self.video_preview_decode_in_flight = False
        self.video_preview_target_index = None
        self.pending_image_edit_preview_state = None
        self.image_edit_preview_in_progress = False
        self.pending_image_edit_histogram_qimage = None
        self.pending_image_edit_histogram_apply_crop = None
        if hasattr(self, "image_edit_preview_timer"):
            self.image_edit_preview_timer.stop()
        if hasattr(self, "image_edit_histogram_timer"):
            self.image_edit_histogram_timer.stop()
        self.last_grayscale_output_path = None
        self.last_freeze_output_path = None
        self.grayscale_results_headers = []
        self.grayscale_results_rows = []
        self.freeze_results_headers = []
        self.freeze_results_rows = []
        self.freeze_count_timeseries_headers = []
        self.freeze_count_timeseries_rows = []
        self.freeze_count_timeseries_summary = {}
        self.last_temperature_import_path = None
        self.last_temperature_calibration_path = None
        self.last_temperature_reset_temperature = None
        self.last_temperature_blank_sample_names = []
        self.last_standard_temperature_image_timestamp_source = IMAGE_TIMESTAMP_SOURCE_FILENAME
        self.last_standard_temperature_image_timestamp_style = TIMESTAMP_STYLE_AUTO
        self.last_standard_temperature_temperature_timestamp_style = TIMESTAMP_STYLE_AUTO
        self.last_standard_temperature_use_image_timestamp_style = True
        self.last_standard_temperature_generated_start_text = ""
        self.last_standard_temperature_frame_interval_seconds = 1.0
        self.last_standard_temperature_temperature_unit = TEMPERATURE_UNIT_CELSIUS
        self.pending_navigation_before_index = None
        self.pending_navigation_history_text = "Change Frame"
        self.slider_drag_start_index = None
        self.analysis_progress_navigation_suppressed = False
        self.analysis_progress_start_index = None
        self.pending_analysis_progress_index = None
        self.pending_analysis_before_state = None
        self.sort_mode = getattr(self, "sort_mode", "natural_filename")
        self.session_project_name = ""
        self.session_user_name = ""
        self.session_institution = ""
        self.session_date = ""

        # miscellaneous
        self.timer = None
        self.output_state = False
        self.raw_image_cache = OrderedDict()
        self.raw_image_cache_size = 8
        self.preview_raw_frame_keys = set()
        self.image_cache = OrderedDict()
        self.image_cache_size = 12
        self.pixmap_cache = OrderedDict()
        self.pixmap_cache_size = 12
        self.raw_image_size_cache = {}
        self.image_edit_histogram_scale_cache = {}
        self.image_edit_uniform_exposure_overlay = None
        self.image_edit_crop_overlay = None
        self.displayed_image_edit_crop_applied = None
        self.context_pixmap_items = []
        self.placeholder_items = []
        self.grid_preview_items = []
        self.grid_preview_handle_item = None
        self.grid_preview_origin_pixels = None
        self.grid_preview_floating = True
        self.preview_offset_x = 0.0
        self.preview_offset_y = 0.0
        self.cell_controller.reset()
        self.image_list_entry_ids = []
        self.next_image_list_entry_id = 0
        self.syncing_image_list_selection = False
        self.active_image_panel = "viewer"
        self.tool_mode = "cursor"
        self.session_active = False
        self.current_session_file_path = None
        self.update_session_metadata_status_label()

    def active_frame_source(self):
        if not hasattr(self, "frame_source") or self.frame_source is None:
            self.frame_source = ImageSequenceFrameSource(getattr(self, "imagePaths", []))
        return self.frame_source

    def frame_count(self):
        try:
            return int(self.active_frame_source().frame_count())
        except Exception:
            return len(getattr(self, "imagePaths", []))

    def has_frames(self):
        return self.frame_count() > 0

    def source_kind(self):
        try:
            return str(self.active_frame_source().source_kind())
        except Exception:
            return SOURCE_KIND_IMAGE_SEQUENCE

    def is_video_source(self):
        return self.source_kind() == SOURCE_KIND_VIDEO

    def start_video_preview_decoder(self):
        self.stop_video_preview_decoder()
        if not self.is_video_source():
            return

        frame_source = self.active_frame_source()
        preview_cache_dir = getattr(frame_source, "preview_cache_dir", lambda: "")()
        if not preview_cache_dir:
            return

        self.video_preview_decoder = VideoPreviewDecodeController(
            frame_source.preview_payload(),
            preview_cache_dir,
            frame_source.source_token(),
            parent=self,
        )
        self.video_preview_decoder.decoded.connect(self.handle_video_preview_decoded)
        self.video_preview_decoder.failed.connect(self.handle_video_preview_failed)
        self.video_preview_decoder.start()

    def stop_video_preview_decoder(self):
        self.video_preview_decode_in_flight = False
        self.video_preview_target_index = None
        decoder = getattr(self, "video_preview_decoder", None)
        if decoder is not None:
            decoder.close(timeout_ms=1000)
        self.video_preview_decoder = None

    def supports_image_file_operations(self):
        try:
            return bool(self.active_frame_source().supports_image_file_operations())
        except Exception:
            return False

    def supports_video_clip_sorting(self):
        if not self.is_video_source():
            return False
        try:
            return len(self.active_frame_source().source_paths()) > 1
        except Exception:
            return False

    def frame_name(self, index):
        try:
            index = int(index)
        except (TypeError, ValueError):
            return ""
        try:
            return self.active_frame_source().frame_name(index)
        except Exception:
            if self.imageNames and 0 <= index < len(self.imageNames):
                return self.imageNames[index]
        return ""

    def frame_tooltip(self, index):
        try:
            index = int(index)
        except (TypeError, ValueError):
            return ""
        try:
            return self.active_frame_source().frame_tooltip(index)
        except Exception:
            if self.imagePaths and 0 <= index < len(self.imagePaths):
                return self.imagePaths[index]
        return ""

    def frame_key(self, index):
        try:
            index = int(index)
        except (TypeError, ValueError):
            return str(index)
        try:
            return self.active_frame_source().frame_key(index)
        except Exception:
            if self.imagePaths and 0 <= index < len(self.imagePaths):
                return os.path.normcase(os.path.normpath(self.imagePaths[index]))
        return str(index)

    def rebuild_image_sequence_frame_source(self):
        old_frame_source = getattr(self, "frame_source", None)
        self.stop_video_preview_decoder()
        self.frame_source = ImageSequenceFrameSource(getattr(self, "imagePaths", []))
        if old_frame_source is not None and old_frame_source is not self.frame_source:
            close_source = getattr(old_frame_source, "close", None)
            if callable(close_source):
                close_source()
        self.imageNames = self.frame_source.names()

    def set_frame_source(self, frame_source, *, reset_frame_ids=True):
        old_frame_source = getattr(self, "frame_source", None)
        self.stop_video_preview_decoder()
        self.frame_source = frame_source or ImageSequenceFrameSource([])
        if old_frame_source is not None and old_frame_source is not self.frame_source:
            close_source = getattr(old_frame_source, "close", None)
            if callable(close_source):
                close_source()
        if self.source_kind() == SOURCE_KIND_IMAGE_SEQUENCE:
            self.imagePaths = self.frame_source.paths()
            self.imageNames = self.frame_source.names()
        else:
            self.imagePaths = []
            self.imageNames = []
        if reset_frame_ids:
            self.image_list_entry_ids = (
                list(range(self.frame_count()))
                if self.source_kind() == SOURCE_KIND_IMAGE_SEQUENCE
                else []
            )
            self.next_image_list_entry_id = self.frame_count()
        if self.source_kind() == SOURCE_KIND_VIDEO:
            self.start_video_preview_decoder()

    def frame_source_session_payload(self):
        return self.active_frame_source().to_session_payload()

    def serialize_session_metadata(self):
        return {
            "project_name": str(getattr(self, "session_project_name", "")).strip(),
            "user_name": str(getattr(self, "session_user_name", "")).strip(),
            "institution": str(getattr(self, "session_institution", "")).strip(),
            "date": str(getattr(self, "session_date", "")).strip(),
        }

    def serialize_image_edit_state(self):
        valid_frame_keys = {
            self.frame_key(index)
            for index in range(self.frame_count())
        }
        return {
            "exposure": float(getattr(self, "image_edit_exposure", 0.0)),
            "contrast": float(getattr(self, "image_edit_contrast", 0.0)),
            "uniform_exposure": {
                "area": {
                    "x": getattr(self, "image_edit_uniform_exposure_area_x", None),
                    "y": getattr(self, "image_edit_uniform_exposure_area_y", None),
                    "width": getattr(self, "image_edit_uniform_exposure_area_width", None),
                    "height": getattr(self, "image_edit_uniform_exposure_area_height", None),
                },
                "offsets": {
                    str(frame_key): float(value)
                    for frame_key, value in dict(getattr(self, "image_edit_uniform_exposure_offsets", {})).items()
                    if str(frame_key) in valid_frame_keys and abs(float(value)) > 1e-9
                },
            },
            "crop": {
                "center_x": getattr(self, "image_edit_crop_center_x", None),
                "center_y": getattr(self, "image_edit_crop_center_y", None),
                "width": getattr(self, "image_edit_crop_width", None),
                "height": getattr(self, "image_edit_crop_height", None),
                "angle": float(getattr(self, "image_edit_crop_angle", 0.0)),
            },
        }

    def apply_image_edit_state(self, state, *, invalidate_results=False, refresh_display=True, sync_controls=True):
        try:
            exposure_value = float((state or {}).get("exposure", 0.0))
        except (AttributeError, TypeError, ValueError):
            exposure_value = 0.0
        try:
            contrast_value = float((state or {}).get("contrast", 0.0))
        except (AttributeError, TypeError, ValueError):
            contrast_value = 0.0
        uniform_exposure_state = (state or {}).get("uniform_exposure", {})
        raw_uniform_area = (uniform_exposure_state or {}).get("area", {})
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        has_uniform_area = any(
            raw_uniform_area.get(key) is not None
            for key in ("x", "y", "width", "height")
        )
        if has_uniform_area and raw_width > 0 and raw_height > 0:
            uniform_area = self.normalize_image_edit_uniform_exposure_area_state(raw_uniform_area)
        elif has_uniform_area:
            try:
                uniform_area = {
                    "x": float(raw_uniform_area.get("x", 0.0)),
                    "y": float(raw_uniform_area.get("y", 0.0)),
                    "width": float(raw_uniform_area.get("width", 16.0)),
                    "height": float(raw_uniform_area.get("height", 16.0)),
                }
            except (AttributeError, TypeError, ValueError):
                uniform_area = None
        else:
            uniform_area = None
        uniform_offsets = {}
        for image_path, offset_value in dict((uniform_exposure_state or {}).get("offsets", {})).items():
            try:
                offset_float = float(offset_value)
            except (TypeError, ValueError):
                continue
            if abs(offset_float) > 1e-9:
                uniform_offsets[str(image_path)] = offset_float
        raw_crop_state = (state or {}).get("crop", {})
        has_crop_state = any(
            raw_crop_state.get(key) is not None
            for key in ("center_x", "center_y", "width", "height", "angle")
        ) if isinstance(raw_crop_state, dict) else False
        if has_crop_state and raw_width > 0 and raw_height > 0:
            crop_value = self.normalize_image_edit_crop_state(raw_crop_state)
        elif has_crop_state:
            try:
                crop_value = {
                    "center_x": float(raw_crop_state.get("center_x", 0.0)),
                    "center_y": float(raw_crop_state.get("center_y", 0.0)),
                    "width": float(raw_crop_state.get("width", 1.0)),
                    "height": float(raw_crop_state.get("height", 1.0)),
                    "angle": float(raw_crop_state.get("angle", 0.0)),
                }
            except (AttributeError, TypeError, ValueError):
                crop_value = self.normalize_image_edit_crop_state({})
        else:
            crop_value = self.normalize_image_edit_crop_state({})

        previous_value = float(getattr(self, "image_edit_exposure", 0.0))
        previous_contrast = float(getattr(self, "image_edit_contrast", 0.0))
        previous_uniform_area = self.current_image_edit_uniform_exposure_area_state()
        previous_uniform_offsets = {
            str(path): float(value)
            for path, value in dict(getattr(self, "image_edit_uniform_exposure_offsets", {})).items()
            if abs(float(value)) > 1e-9
        }
        previous_crop = self.current_image_edit_crop_state()
        state_changed = abs(previous_value - exposure_value) > 1e-9
        state_changed = state_changed or abs(previous_contrast - contrast_value) > 1e-9
        state_changed = state_changed or previous_uniform_area != uniform_area
        state_changed = state_changed or previous_uniform_offsets != uniform_offsets
        state_changed = state_changed or previous_crop != crop_value
        visual_changed = abs(previous_value - exposure_value) > 1e-9
        visual_changed = visual_changed or abs(previous_contrast - contrast_value) > 1e-9
        visual_changed = visual_changed or previous_uniform_offsets != uniform_offsets
        visual_changed = visual_changed or previous_crop != crop_value
        geometry_changed = previous_crop != crop_value
        self.image_edit_exposure = exposure_value
        self.image_edit_contrast = contrast_value
        if uniform_area is None:
            self.image_edit_uniform_exposure_area_x = None
            self.image_edit_uniform_exposure_area_y = None
            self.image_edit_uniform_exposure_area_width = None
            self.image_edit_uniform_exposure_area_height = None
        else:
            self.image_edit_uniform_exposure_area_x = float(uniform_area["x"])
            self.image_edit_uniform_exposure_area_y = float(uniform_area["y"])
            self.image_edit_uniform_exposure_area_width = float(uniform_area["width"])
            self.image_edit_uniform_exposure_area_height = float(uniform_area["height"])
        self.image_edit_uniform_exposure_offsets = uniform_offsets
        self.image_edit_crop_center_x = float(crop_value["center_x"])
        self.image_edit_crop_center_y = float(crop_value["center_y"])
        self.image_edit_crop_width = float(crop_value["width"])
        self.image_edit_crop_height = float(crop_value["height"])
        self.image_edit_crop_angle = float(crop_value["angle"])

        if visual_changed:
            self.clear_image_caches()

        if sync_controls:
            self.sync_image_edit_controls()

        if refresh_display and visual_changed and self.has_frames():
            if geometry_changed:
                self.updateImage(self.image_index)
            else:
                self.refresh_current_image_edit_visuals()
        else:
            self.request_image_edit_histogram_refresh()

    def refresh_current_image_edit_visuals(self):
        if not self.has_frames():
            return
        if not hasattr(self, "pixmap_item"):
            self.updateImage(self.image_index)
            return

        current_transform = self.view.transform()
        current_hscroll = self.view.horizontalScrollBar().value()
        current_vscroll = self.view.verticalScrollBar().value()

        self.view.setUpdatesEnabled(False)
        try:
            q_image = self.update_display_pixmaps(self.image_index)
            self.view.setTransform(current_transform)
            self.view.horizontalScrollBar().setValue(current_hscroll)
            self.view.verticalScrollBar().setValue(current_vscroll)
            self.request_image_edit_histogram_refresh(q_image)
        finally:
            self.view.setUpdatesEnabled(True)

    def prewarm_current_image_edit_render_cache(self):
        if not self.has_frames():
            return
        if not (0 <= int(self.image_index) < self.frame_count()):
            return
        self.get_cached_raw_image(self.image_index)
        self.get_cached_image(self.image_index)
        self.get_cached_pixmap(self.image_index)

    def get_image_edit_histogram_interval_ms(self):
        return 15

    def request_image_edit_histogram_refresh(self, q_image=None, *, immediate=False, apply_crop=None):
        if not hasattr(self, "image_edit_histogram_widget"):
            return
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        self.pending_image_edit_histogram_qimage = q_image
        self.pending_image_edit_histogram_apply_crop = bool(apply_crop)
        if immediate:
            if hasattr(self, "image_edit_histogram_timer"):
                self.image_edit_histogram_timer.stop()
            self.flush_pending_image_edit_histogram()
            return
        self.image_edit_histogram_timer.start(self.get_image_edit_histogram_interval_ms())

    def flush_pending_image_edit_histogram(self):
        q_image = self.pending_image_edit_histogram_qimage
        self.pending_image_edit_histogram_qimage = None
        apply_crop = self.pending_image_edit_histogram_apply_crop
        self.pending_image_edit_histogram_apply_crop = None
        self.refresh_image_edit_histogram(q_image, apply_crop=apply_crop)

    def normalize_image_edit_uniform_exposure_area_state(self, area_state=None, *, raw_width=None, raw_height=None):
        if raw_width is None or raw_height is None:
            raw_width, raw_height = self.get_current_raw_image_dimensions()
        return normalize_rect_area_state(raw_width, raw_height, area_state or {})

    def current_image_edit_uniform_exposure_area_state(self, *, index=None):
        if not self.has_image_edit_uniform_exposure_area():
            return None
        if index is None:
            raw_width, raw_height = self.get_current_raw_image_dimensions()
        else:
            raw_width, raw_height = self.get_raw_image_dimensions(index)
        return self.normalize_image_edit_uniform_exposure_area_state(
            {
                "x": getattr(self, "image_edit_uniform_exposure_area_x", None),
                "y": getattr(self, "image_edit_uniform_exposure_area_y", None),
                "width": getattr(self, "image_edit_uniform_exposure_area_width", None),
                "height": getattr(self, "image_edit_uniform_exposure_area_height", None),
            },
            raw_width=raw_width,
            raw_height=raw_height,
        )

    def current_image_edit_uniform_exposure_state(self):
        area_state = self.current_image_edit_uniform_exposure_area_state()
        return {
            "area": copy.deepcopy(area_state) if area_state is not None else {},
            "offsets": {
                str(path): float(value)
                for path, value in dict(getattr(self, "image_edit_uniform_exposure_offsets", {})).items()
                if abs(float(value)) > 1e-9
            },
        }

    def compose_image_edit_state(self, *, exposure=None, contrast=None, uniform_exposure=None, crop=None):
        return {
            "exposure": float(getattr(self, "image_edit_exposure", 0.0) if exposure is None else exposure),
            "contrast": float(getattr(self, "image_edit_contrast", 0.0) if contrast is None else contrast),
            "uniform_exposure": self.current_image_edit_uniform_exposure_state() if uniform_exposure is None else copy.deepcopy(uniform_exposure),
            "crop": self.current_image_edit_crop_state() if crop is None else copy.deepcopy(crop),
        }

    def has_image_edit_uniform_exposure_area(self):
        return all(
            getattr(self, attribute_name, None) is not None
            for attribute_name in (
                "image_edit_uniform_exposure_area_x",
                "image_edit_uniform_exposure_area_y",
                "image_edit_uniform_exposure_area_width",
                "image_edit_uniform_exposure_area_height",
            )
        )

    def has_image_edit_uniform_exposure(self):
        return bool(getattr(self, "image_edit_uniform_exposure_offsets", {}))

    def get_image_edit_uniform_exposure_offset(self, *, index=None, image_path=None):
        offsets = getattr(self, "image_edit_uniform_exposure_offsets", {}) or {}
        if image_path is None:
            if index is None:
                index = self.image_index
            if not self.has_frames() or not (0 <= int(index) < self.frame_count()):
                return 0.0
            image_path = self.frame_key(int(index))
        try:
            return float(offsets.get(str(image_path), 0.0))
        except (TypeError, ValueError):
            return 0.0

    def current_image_edit_total_exposure(self, *, index=None, image_path=None):
        return float(getattr(self, "image_edit_exposure", 0.0)) + self.get_image_edit_uniform_exposure_offset(
            index=index,
            image_path=image_path,
        )

    def current_image_edit_crop_state(self, *, index=None):
        if index is None:
            raw_width, raw_height = self.get_current_raw_image_dimensions()
        else:
            raw_width, raw_height = self.get_raw_image_dimensions(index)
        return self.normalize_image_edit_crop_state({
            "center_x": getattr(self, "image_edit_crop_center_x", raw_width * 0.5),
            "center_y": getattr(self, "image_edit_crop_center_y", raw_height * 0.5),
            "width": getattr(self, "image_edit_crop_width", raw_width),
            "height": getattr(self, "image_edit_crop_height", raw_height),
            "angle": float(getattr(self, "image_edit_crop_angle", 0.0)),
        }, raw_width=raw_width, raw_height=raw_height)

    def get_raw_image_dimensions(self, index):
        if not self.has_frames():
            return 0, 0
        try:
            index = int(index)
        except (TypeError, ValueError):
            return 0, 0
        if index < 0 or index >= self.frame_count():
            return 0, 0

        frame_key = self.frame_key(index)
        cached_size = getattr(self, "raw_image_size_cache", {}).get(frame_key)
        if cached_size is not None:
            return int(cached_size[0]), int(cached_size[1])

        raw_q_image = self.get_cached_raw_image(index)
        width = int(raw_q_image.width())
        height = int(raw_q_image.height())
        if hasattr(self, "raw_image_size_cache"):
            self.raw_image_size_cache[frame_key] = (width, height)
        return width, height

    def get_current_raw_image_dimensions(self):
        if not self.has_frames():
            return 0, 0
        return self.get_raw_image_dimensions(self.image_index)

    def normalize_image_edit_crop_state(self, crop_state=None, *, raw_width=None, raw_height=None):
        if raw_width is None or raw_height is None:
            raw_width, raw_height = self.get_current_raw_image_dimensions()
        return normalize_rotated_crop_state(raw_width, raw_height, crop_state or {})

    def should_apply_crop_in_display(self):
        return not self.is_image_edit_crop_active() and not self.is_image_edit_uniform_exposure_area_active()

    def current_image_edit_crop_transform(self, index=None, *, apply_crop=None):
        if index is None:
            index = self.image_index
        raw_width, raw_height = self.get_raw_image_dimensions(index)
        crop_state = self.current_image_edit_crop_state(index=index)
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        if (not apply_crop) or crop_state_is_identity(raw_width, raw_height, crop_state):
            return crop_state, None, None, (max(1, int(raw_width)), max(1, int(raw_height)))
        state, matrix, output_size = build_rotated_crop_affine(
            raw_width,
            raw_height,
            crop_state,
        )
        inverse_matrix = invert_affine_matrix(matrix)
        return state, matrix, inverse_matrix, output_size

    def image_pixel_to_scene_coordinates(self, pixel_x, pixel_y, image_rect=None, *, index=None, apply_crop=None):
        if image_rect is None:
            pixmap_item = getattr(self, "pixmap_item", None)
            if pixmap_item is None:
                return float(pixel_x), float(pixel_y)
            image_rect = pixmap_item.sceneBoundingRect()
        _crop_state, matrix, _inverse_matrix, _output_size = self.current_image_edit_crop_transform(
            index=index,
            apply_crop=apply_crop,
        )
        display_x = float(pixel_x)
        display_y = float(pixel_y)
        if matrix is not None:
            display_x, display_y = apply_affine_to_point(matrix, display_x, display_y)
        return (
            float(image_rect.left()) + display_x,
            float(image_rect.top()) + display_y,
        )

    def scene_to_image_pixel_coordinates(self, scene_pos, image_rect=None, *, index=None, apply_crop=None):
        if image_rect is None:
            pixmap_item = getattr(self, "pixmap_item", None)
            if pixmap_item is None:
                return float(scene_pos.x()), float(scene_pos.y())
            image_rect = pixmap_item.sceneBoundingRect()
        display_x = float(scene_pos.x()) - float(image_rect.left())
        display_y = float(scene_pos.y()) - float(image_rect.top())
        _crop_state, _matrix, inverse_matrix, _output_size = self.current_image_edit_crop_transform(
            index=index,
            apply_crop=apply_crop,
        )
        if inverse_matrix is not None:
            display_x, display_y = apply_affine_to_point(inverse_matrix, display_x, display_y)
        return (float(display_x), float(display_y))

    def sync_image_edit_controls(self):
        if hasattr(self, "image_edit_exposure_slider"):
            slider_value = int(round(float(getattr(self, "image_edit_exposure", 0.0)) * 10.0))
            with QSignalBlocker(self.image_edit_exposure_slider):
                self.image_edit_exposure_slider.setValue(slider_value)
        if hasattr(self, "image_edit_exposure_spinbox"):
            with QSignalBlocker(self.image_edit_exposure_spinbox):
                self.image_edit_exposure_spinbox.setValue(float(getattr(self, "image_edit_exposure", 0.0)))
        if hasattr(self, "image_edit_contrast_slider"):
            slider_value = int(round(float(getattr(self, "image_edit_contrast", 0.0))))
            with QSignalBlocker(self.image_edit_contrast_slider):
                self.image_edit_contrast_slider.setValue(slider_value)
        if hasattr(self, "image_edit_contrast_spinbox"):
            with QSignalBlocker(self.image_edit_contrast_spinbox):
                self.image_edit_contrast_spinbox.setValue(int(round(float(getattr(self, "image_edit_contrast", 0.0)))))
        if hasattr(self, "image_edit_uniform_exposure_area_button"):
            area_active = self.is_image_edit_uniform_exposure_area_active()
            has_area = self.has_image_edit_uniform_exposure_area()
            self.image_edit_uniform_exposure_area_button.setText("Done" if area_active else "Set Area")
            self.image_edit_uniform_exposure_run_button.setEnabled(bool(has_area))
            self.image_edit_uniform_exposure_reset_button.setEnabled(bool(has_area or self.has_image_edit_uniform_exposure()))
        if hasattr(self, "image_edit_crop_start_button"):
            crop_active = self.is_image_edit_crop_active()
            raw_width, raw_height = self.get_current_raw_image_dimensions()
            has_committed_crop = bool(
                raw_width > 0
                and raw_height > 0
                and (not crop_state_is_identity(raw_width, raw_height, self.current_image_edit_crop_state()))
            )
            self.image_edit_crop_start_button.setText("Cancel" if crop_active else "Crop")
            self.image_edit_crop_start_button.setEnabled(True)
            self.image_edit_crop_apply_button.setEnabled(crop_active)
            self.image_edit_crop_reset_button.setEnabled((not crop_active) and has_committed_crop)
        self.sync_image_edit_uniform_exposure_overlay()
        self.sync_image_edit_crop_overlay()

    def refresh_image_edit_histogram(self, q_image=None, *, apply_crop=None):
        if not hasattr(self, "image_edit_histogram_widget"):
            return
        if getattr(self, "tool_mode", "") != "image-edit":
            return
        if not self.has_frames() or not (0 <= self.image_index < self.frame_count()):
            self.image_edit_histogram_widget.clear_histogram()
            return

        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        if q_image is None:
            q_image = self.get_cached_image(self.image_index, apply_crop=apply_crop)
        gray_array = qimage_to_grayscale_array(q_image)
        histogram = compute_histogram_bins(gray_array, IMAGE_EDIT_HISTOGRAM_BIN_COUNT)
        overlay_histogram = None
        overlay_scale_max = None
        selected_items = list(self.cell_controller.selected_scene_items()) if hasattr(self, "cell_controller") else []
        if selected_items and gray_array is not None and gray_array.size > 0:
            selected_values = []
            image_height, image_width = gray_array.shape[:2]
            crop_matrix = None
            crop_is_identity = True
            if apply_crop:
                raw_width, raw_height = self.get_raw_image_dimensions(self.image_index)
                crop_state = self.current_image_edit_crop_state(index=self.image_index)
                crop_is_identity = crop_state_is_identity(raw_width, raw_height, crop_state)
                _crop_state, crop_matrix, _output_size = build_rotated_crop_affine(
                    raw_width,
                    raw_height,
                    crop_state,
                )
            for item in selected_items:
                try:
                    center_x = float(item.circle_pixel_positions[0])
                    center_y = float(item.circle_pixel_positions[1])
                    radius = float(item.circle_sizes)
                except (AttributeError, TypeError, ValueError, IndexError):
                    continue
                if radius <= 0:
                    continue
                if apply_crop and (not crop_is_identity):
                    center_x, center_y = apply_affine_to_point(crop_matrix, center_x, center_y)
                left = max(0, int(math.floor(center_x - radius)))
                top = max(0, int(math.floor(center_y - radius)))
                right = min(image_width, int(math.ceil(center_x + radius)) + 1)
                bottom = min(image_height, int(math.ceil(center_y + radius)) + 1)
                if right <= left or bottom <= top:
                    continue
                region = gray_array[top:bottom, left:right]
                yy, xx = np.ogrid[top:bottom, left:right]
                mask = ((xx - center_x) ** 2 + (yy - center_y) ** 2) <= (radius ** 2)
                if np.any(mask):
                    selected_values.append(region[mask])
            if selected_values:
                overlay_histogram = compute_histogram_bins(
                    np.concatenate(selected_values),
                    IMAGE_EDIT_HISTOGRAM_BIN_COUNT,
                )
                overlay_scale_max = max(float(np.max(overlay_histogram)) if overlay_histogram.size else 0.0, 1.0)
        scale_max = max(float(np.max(histogram)) if histogram.size else 0.0, 1.0)
        self.image_edit_histogram_widget.set_histogram(
            histogram,
            overlay_histogram=overlay_histogram,
            scale_max=scale_max,
            overlay_scale_max=overlay_scale_max,
        )

    def begin_image_edit_history(self, text):
        if self.history_restoring:
            return
        if "image_edit_before_state" in self.temporary_event_data:
            return
        self.temporary_event_data["image_edit_before_state"] = self.capture_image_edit_history_state()
        self.temporary_event_data["image_edit_history_text"] = str(text or "Edit Image")

    def commit_image_edit_history(self, text=None):
        before_state = self.temporary_event_data.pop("image_edit_before_state", None)
        history_text = str(text or self.temporary_event_data.pop("image_edit_history_text", "Edit Image"))
        if before_state is None:
            return
        after_state = self.capture_image_edit_history_state()
        if before_state == after_state:
            return
        self.push_image_edit_history(history_text, before_state)
        self.log_image_edit_change(history_text)

    def log_image_edit_change(self, history_text):
        history_text = str(history_text or "Edit Image")
        if history_text == "Adjust Exposure":
            self.log(f"Adjust Exposure: {float(getattr(self, 'image_edit_exposure', 0.0)):.1f}")
            return
        if history_text == "Adjust Contrast":
            self.log(f"Adjust Contrast: {int(round(float(getattr(self, 'image_edit_contrast', 0.0))))}")
            return
        if history_text == "Apply Crop":
            crop_state = self.current_image_edit_crop_state()
            self.log(
                "Apply Crop: "
                f"center=({float(crop_state['center_x']):.1f}, {float(crop_state['center_y']):.1f}), "
                f"size=({float(crop_state['width']):.1f} x {float(crop_state['height']):.1f}), "
                f"angle={float(crop_state['angle']):.1f}"
            )
            return
        if history_text == "Reset Crop":
            self.log("Reset Crop")
            return
        if history_text == "Reset Uniform Exposure":
            self.log("Reset Uniform Exposure")
            return
        self.log(history_text)

    def get_image_edit_preview_interval_ms(self):
        return 15

    def reset_pending_image_edit_preview_state(self, stop_timer=False):
        self.pending_image_edit_preview_state = None
        self.image_edit_preview_in_progress = False
        if stop_timer and hasattr(self, "image_edit_preview_timer"):
            self.image_edit_preview_timer.stop()

    def compose_pending_image_edit_preview_state(self, *, exposure=None, contrast=None):
        base_state = self.pending_image_edit_preview_state
        if base_state is None:
            base_state = self.compose_image_edit_state()
        else:
            base_state = copy.deepcopy(base_state)
        if exposure is not None:
            base_state["exposure"] = float(exposure)
        if contrast is not None:
            base_state["contrast"] = float(contrast)
        return base_state

    def queue_image_edit_preview_state(self, state):
        self.pending_image_edit_preview_state = copy.deepcopy(state)
        if self.image_edit_preview_in_progress:
            return
        self.image_edit_preview_timer.start(self.get_image_edit_preview_interval_ms())

    def flush_pending_image_edit_preview(self):
        if self.pending_image_edit_preview_state is None or self.image_edit_preview_in_progress:
            return
        pending_state = copy.deepcopy(self.pending_image_edit_preview_state)
        self.pending_image_edit_preview_state = None
        self.image_edit_preview_in_progress = True
        try:
            self.apply_image_edit_state(
                pending_state,
                invalidate_results=True,
                refresh_display=True,
                sync_controls=True,
            )
        finally:
            self.image_edit_preview_in_progress = False

        if self.pending_image_edit_preview_state is not None:
            self.image_edit_preview_timer.start(self.get_image_edit_preview_interval_ms())

    def handle_image_edit_exposure_slider_changed(self, slider_value):
        self.begin_image_edit_history("Adjust Exposure")
        exposure_value = float(slider_value) / 10.0
        if getattr(self, "image_edit_exposure_slider", None).isSliderDown():
            self.queue_image_edit_preview_state(
                self.compose_pending_image_edit_preview_state(exposure=exposure_value)
            )
            return
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                exposure=exposure_value,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Exposure")

    def handle_image_edit_exposure_spinbox_changed(self, exposure_value):
        self.begin_image_edit_history("Adjust Exposure")
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                exposure=float(exposure_value),
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Exposure")

    def handle_image_edit_exposure_slider_released(self):
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                exposure=float(self.image_edit_exposure_slider.value()) / 10.0,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Exposure")

    def handle_image_edit_contrast_slider_changed(self, contrast_value):
        self.begin_image_edit_history("Adjust Contrast")
        contrast_value = float(contrast_value)
        if getattr(self, "image_edit_contrast_slider", None).isSliderDown():
            self.queue_image_edit_preview_state(
                self.compose_pending_image_edit_preview_state(contrast=contrast_value)
            )
            return
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                contrast=contrast_value,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Contrast")

    def handle_image_edit_contrast_spinbox_changed(self, contrast_value):
        self.begin_image_edit_history("Adjust Contrast")
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                contrast=float(contrast_value),
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Contrast")

    def handle_image_edit_contrast_slider_released(self):
        self.reset_pending_image_edit_preview_state(stop_timer=True)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                contrast=float(self.image_edit_contrast_slider.value()),
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.commit_image_edit_history("Adjust Contrast")

    def is_image_edit_uniform_exposure_area_active(self):
        return bool(self.temporary_event_data.get("image_edit_uniform_exposure_area_active", False))

    def begin_image_edit_uniform_exposure_area(self):
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        if raw_width <= 0 or raw_height <= 0:
            return
        if self.is_image_edit_crop_active():
            self.cancel_image_edit_crop()
        if self.is_image_edit_uniform_exposure_area_active():
            self.sync_image_edit_controls()
            return
        if getattr(self, "image_edit_uniform_exposure_area_x", None) is None:
            area_state = self.normalize_image_edit_uniform_exposure_area_state({})
            self.image_edit_uniform_exposure_area_x = float(area_state["x"])
            self.image_edit_uniform_exposure_area_y = float(area_state["y"])
            self.image_edit_uniform_exposure_area_width = float(area_state["width"])
            self.image_edit_uniform_exposure_area_height = float(area_state["height"])
        self.temporary_event_data["image_edit_uniform_exposure_area_active"] = True
        if self.has_frames():
            self.updateImage(self.image_index)
        else:
            self.sync_image_edit_controls()

    def end_image_edit_uniform_exposure_area(self):
        if not self.is_image_edit_uniform_exposure_area_active():
            return
        self.temporary_event_data.pop("image_edit_uniform_exposure_area_active", None)
        if self.has_frames():
            self.updateImage(self.image_index)
        else:
            self.sync_image_edit_controls()

    def handle_image_edit_uniform_exposure_area_button(self):
        if self.is_image_edit_uniform_exposure_area_active():
            self.end_image_edit_uniform_exposure_area()
        else:
            self.begin_image_edit_uniform_exposure_area()

    def handle_image_edit_uniform_exposure_overlay_changed(self, area_state, finalize=False):
        pixmap_item = getattr(self, "pixmap_item", None)
        if pixmap_item is None:
            return
        image_rect = pixmap_item.sceneBoundingRect()
        top_left_scene = QPointF(float(image_rect.left()) + float(area_state["x"]), float(image_rect.top()) + float(area_state["y"]))
        bottom_right_scene = QPointF(
            float(image_rect.left()) + float(area_state["x"]) + float(area_state["width"]),
            float(image_rect.top()) + float(area_state["y"]) + float(area_state["height"]),
        )
        top_left = self.scene_to_image_pixel_coordinates(top_left_scene, image_rect=image_rect, apply_crop=False)
        bottom_right = self.scene_to_image_pixel_coordinates(bottom_right_scene, image_rect=image_rect, apply_crop=False)
        normalized = self.normalize_image_edit_uniform_exposure_area_state(
            {
                "x": min(float(top_left[0]), float(bottom_right[0])),
                "y": min(float(top_left[1]), float(bottom_right[1])),
                "width": abs(float(bottom_right[0]) - float(top_left[0])),
                "height": abs(float(bottom_right[1]) - float(top_left[1])),
            }
        )
        current = self.current_image_edit_uniform_exposure_area_state()
        if normalized == current:
            return
        self.image_edit_uniform_exposure_area_x = float(normalized["x"])
        self.image_edit_uniform_exposure_area_y = float(normalized["y"])
        self.image_edit_uniform_exposure_area_width = float(normalized["width"])
        self.image_edit_uniform_exposure_area_height = float(normalized["height"])
        self.request_image_edit_histogram_refresh()
        if finalize:
            self.sync_image_edit_controls()

    def ensure_image_edit_uniform_exposure_overlay(self):
        overlay = getattr(self, "image_edit_uniform_exposure_overlay", None)
        if overlay is not None and overlay.scene() is self.scene:
            return overlay
        overlay = ImageRectOverlayItem()
        overlay.areaChanged.connect(self.handle_image_edit_uniform_exposure_overlay_changed)
        overlay.areaChangeFinished.connect(lambda state: self.handle_image_edit_uniform_exposure_overlay_changed(state, finalize=True))
        self.scene.addItem(overlay)
        self.image_edit_uniform_exposure_overlay = overlay
        return overlay

    def sync_image_edit_uniform_exposure_overlay(self):
        overlay = getattr(self, "image_edit_uniform_exposure_overlay", None)
        should_show = (
            getattr(self, "tool_mode", "") == "image-edit"
            and self.has_frames()
            and getattr(self, "pixmap_item", None) is not None
            and self.is_image_edit_uniform_exposure_area_active()
            and not self.is_image_edit_crop_active()
        )
        if not should_show:
            if overlay is not None:
                overlay.hide()
            return
        overlay = self.ensure_image_edit_uniform_exposure_overlay()
        overlay.set_interactive(True)
        image_rect = self.pixmap_item.sceneBoundingRect()
        area_state = self.current_image_edit_uniform_exposure_area_state()
        if area_state is None:
            overlay.hide()
            return
        top_left = self.image_pixel_to_scene_coordinates(area_state["x"], area_state["y"], image_rect=image_rect, apply_crop=False)
        bottom_right = self.image_pixel_to_scene_coordinates(
            area_state["x"] + area_state["width"],
            area_state["y"] + area_state["height"],
            image_rect=image_rect,
            apply_crop=False,
        )
        scene_rect = QRectF(QPointF(*top_left), QPointF(*bottom_right)).normalized()
        overlay.sync_from_rect(
            image_rect,
            {
                "x": float(scene_rect.left() - image_rect.left()),
                "y": float(scene_rect.top() - image_rect.top()),
                "width": float(scene_rect.width()),
                "height": float(scene_rect.height()),
            },
        )
        overlay.show()

    def show_image_edit_progress_frame(self, index):
        if not self.has_frames():
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= self.frame_count():
            return
        self.image_slider.blockSignals(True)
        try:
            self.ensure_slider_window_contains_index(index)
            self.image_slider.setValue(index)
        finally:
            self.image_slider.blockSignals(False)
        self.updateImage(index, preview=False)
        QApplication.processEvents()

    def show_analysis_progress_frame(self, index):
        if not self.has_frames():
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= self.frame_count():
            return
        self.image_slider.blockSignals(True)
        try:
            self.ensure_slider_window_contains_index(index)
            self.image_slider.setValue(index)
        finally:
            self.image_slider.blockSignals(False)
        self.updateImage(index, preview=False)

    def get_analysis_progress_interval_ms(self):
        return 16

    def enqueue_analysis_progress_frame(self, index):
        if not self.has_frames():
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= self.frame_count():
            return
        self.pending_analysis_progress_index = index
        if not self.analysis_progress_timer.isActive():
            self.analysis_progress_timer.start(self.get_analysis_progress_interval_ms())

    def flush_pending_analysis_progress(self):
        pending_index = self.pending_analysis_progress_index
        self.pending_analysis_progress_index = None
        if pending_index is None:
            return
        self.show_analysis_progress_frame(pending_index)
        if self.pending_analysis_progress_index is not None:
            self.analysis_progress_timer.start(self.get_analysis_progress_interval_ms())

    def compute_image_edit_uniform_exposure_solution(self, area_state, reference_index, progress_callback=None):
        if not self.has_frames():
            return {}, {}
        try:
            reference_index = max(0, min(int(reference_index), self.frame_count() - 1))
        except (TypeError, ValueError):
            reference_index = self.image_index

        def load_gray(index):
            image_gray = self.active_frame_source().get_gray_array(index)
            if image_gray is None:
                raise ValueError(f"Unable to read frame: {index}")
            image_gray = apply_image_adjustments_to_uint8(
                image_gray,
                self.image_edit_exposure,
                self.image_edit_contrast,
                crop_state=None,
                apply_crop=False,
            )
            return image_gray

        def area_mean(image_gray, raw_area_state):
            image_height, image_width = image_gray.shape[:2]
            normalized_area = self.normalize_image_edit_uniform_exposure_area_state(
                raw_area_state,
                raw_width=image_width,
                raw_height=image_height,
            )
            left = int(round(float(normalized_area["x"])))
            top = int(round(float(normalized_area["y"])))
            width = int(round(float(normalized_area["width"])))
            height = int(round(float(normalized_area["height"])))
            right = min(image_width, left + width)
            bottom = min(image_height, top + height)
            if left >= right or top >= bottom:
                raise ValueError("Uniform exposure area is empty.")
            roi = image_gray[top:bottom, left:right]
            if roi.size == 0:
                raise ValueError("Uniform exposure area is empty.")
            return float(np.mean(roi, dtype=np.float64))

        reference_image = load_gray(reference_index)
        reference_mean = area_mean(reference_image, area_state)
        if reference_mean <= 1e-6:
            raise ValueError("Uniform exposure reference area is too dark.")

        offsets = {}
        for index in range(self.frame_count()):
            if progress_callback is not None:
                progress_callback(index)
            image_gray = reference_image if index == reference_index else load_gray(index)
            current_mean = area_mean(image_gray, area_state)
            if current_mean <= 1e-6:
                raise ValueError(f"Uniform exposure area is too dark on frame {index}.")
            offset = float(np.clip(np.log2(reference_mean / current_mean), -4.0, 4.0))
            if abs(offset) > 1e-9:
                offsets[self.frame_key(index)] = offset
        normalized_area = self.normalize_image_edit_uniform_exposure_area_state(area_state)
        return offsets, normalized_area

    def run_image_edit_uniform_exposure(self):
        if not self.has_frames():
            return
        if not self.has_image_edit_uniform_exposure_area():
            QMessageBox.information(self, "Uniform Exposure", "Set a control area first.")
            return
        reference_index = int(self.image_index)
        progress_restore_index = int(self.image_index)
        area_state = self.current_image_edit_uniform_exposure_area_state()
        try:
            offsets, normalized_area = self.compute_image_edit_uniform_exposure_solution(
                area_state,
                reference_index,
                progress_callback=self.show_image_edit_progress_frame,
            )
        except Exception as err:
            if self.has_frames() and 0 <= progress_restore_index < self.frame_count():
                self.show_image_edit_progress_frame(progress_restore_index)
            QMessageBox.warning(self, "Uniform Exposure", str(err))
            return
        before_state = self.capture_data_state()
        self.temporary_event_data.pop("image_edit_uniform_exposure_area_active", None)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                uniform_exposure={
                    "area": copy.deepcopy(normalized_area),
                    "offsets": offsets,
                },
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        if self.has_frames() and 0 <= progress_restore_index < self.frame_count() and progress_restore_index != self.image_index:
            self.show_image_edit_progress_frame(progress_restore_index)
        self.log(f"Applied uniform exposure to {self.frame_count()} frames")
        self.push_data_history("Run Uniform Exposure", before_state)

    def reset_image_edit_uniform_exposure(self):
        if not self.has_image_edit_uniform_exposure_area() and not self.has_image_edit_uniform_exposure():
            return
        before_state = self.capture_data_state()
        self.temporary_event_data.pop("image_edit_uniform_exposure_area_active", None)
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                uniform_exposure={
                    "area": {},
                    "offsets": {},
                },
            ),
            invalidate_results=bool(self.has_image_edit_uniform_exposure()),
            refresh_display=True,
            sync_controls=True,
        )
        self.push_data_history("Reset Uniform Exposure", before_state)
        self.log_image_edit_change("Reset Uniform Exposure")

    def is_image_edit_crop_active(self):
        return bool(self.temporary_event_data.get("image_edit_crop_active", False))

    def get_image_edit_crop_draft_state(self):
        draft_state = self.temporary_event_data.get("image_edit_crop_draft_state")
        if draft_state is None:
            return None
        return self.normalize_image_edit_crop_state(draft_state)

    def discard_image_edit_crop_draft(self):
        self.temporary_event_data.pop("image_edit_crop_active", None)
        self.temporary_event_data.pop("image_edit_crop_draft_state", None)

    def reset_image_edit_crop(self):
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        if raw_width <= 0 or raw_height <= 0:
            return
        reset_state = {
            "center_x": raw_width * 0.5,
            "center_y": raw_height * 0.5,
            "width": raw_width,
            "height": raw_height,
            "angle": 0.0,
        }
        if self.is_image_edit_crop_active():
            self.temporary_event_data["image_edit_crop_draft_state"] = dict(reset_state)
            self.sync_image_edit_controls()
            return

        before_state = self.capture_data_state()
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                crop=reset_state,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.push_data_history("Reset Crop", before_state)
        self.log_image_edit_change("Reset Crop")

    def begin_image_edit_crop(self):
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        if raw_width <= 0 or raw_height <= 0:
            return
        if self.is_image_edit_uniform_exposure_area_active():
            self.end_image_edit_uniform_exposure_area()
        if self.is_image_edit_crop_active():
            self.sync_image_edit_controls()
            return

        current_state = self.current_image_edit_crop_state()
        if crop_state_is_identity(raw_width, raw_height, current_state):
            draft_state = {
                "center_x": float(raw_width) * 0.5,
                "center_y": float(raw_height) * 0.5,
                "width": float(raw_width),
                "height": float(raw_height),
                "angle": 0.0,
            }
        else:
            draft_state = current_state
        self.temporary_event_data["image_edit_crop_active"] = True
        self.temporary_event_data["image_edit_crop_draft_state"] = dict(draft_state)
        if self.tool_mode == "image-edit":
            self.view.setDragMode(QGraphicsView.NoDrag)
        if self.has_frames():
            self.updateImage(self.image_index)
        else:
            self.sync_image_edit_controls()

    def handle_image_edit_crop_primary_button(self):
        if self.is_image_edit_crop_active():
            self.cancel_image_edit_crop()
        else:
            self.begin_image_edit_crop()

    def apply_image_edit_crop(self):
        draft_state = self.get_image_edit_crop_draft_state()
        if draft_state is None:
            return
        before_state = self.capture_data_state()
        self.discard_image_edit_crop_draft()
        self.apply_image_edit_state(
            self.compose_image_edit_state(
                crop=draft_state,
            ),
            invalidate_results=True,
            refresh_display=True,
            sync_controls=True,
        )
        self.sync_image_edit_controls()
        if self.tool_mode == "image-edit":
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.push_data_history("Apply Crop", before_state)
        self.log_image_edit_change("Apply Crop")

    def trigger_image_edit_crop_apply_button(self):
        apply_button = getattr(self, "image_edit_crop_apply_button", None)
        if apply_button is not None and apply_button.isEnabled():
            apply_button.animateClick()
            return True
        self.apply_image_edit_crop()
        return True

    def cancel_image_edit_crop(self):
        if not self.is_image_edit_crop_active():
            return
        self.discard_image_edit_crop_draft()
        if self.tool_mode == "image-edit":
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        if self.has_frames():
            self.updateImage(self.image_index)
        else:
            self.sync_image_edit_controls()

    def handle_image_edit_crop_overlay_changed(self, crop_state, finalize=False):
        crop_state = self.normalize_image_edit_crop_state(crop_state)
        changed = crop_state != self.get_image_edit_crop_draft_state()
        if not changed:
            return
        self.temporary_event_data["image_edit_crop_draft_state"] = dict(crop_state)
        if finalize:
            self.sync_image_edit_controls()

    def ensure_image_edit_crop_overlay(self):
        overlay = getattr(self, "image_edit_crop_overlay", None)
        if overlay is not None and overlay.scene() is self.scene:
            return overlay
        overlay = ImageCropOverlayItem()
        overlay.cropChanged.connect(self.handle_image_edit_crop_overlay_changed)
        overlay.cropChangeFinished.connect(lambda state: self.handle_image_edit_crop_overlay_changed(state, finalize=True))
        self.scene.addItem(overlay)
        self.image_edit_crop_overlay = overlay
        return overlay

    def sync_image_edit_crop_overlay(self):
        overlay = getattr(self, "image_edit_crop_overlay", None)
        should_show = (
            self.tool_mode == "image-edit"
            and self.has_frames()
            and hasattr(self, "pixmap_item")
            and self.is_image_edit_crop_active()
        )
        if not should_show:
            if overlay is not None:
                overlay.hide()
            return
        overlay = self.ensure_image_edit_crop_overlay()
        overlay.show()
        overlay.sync_from_state(
            self.pixmap_item.sceneBoundingRect(),
            self.normalize_image_edit_crop_state(self.get_image_edit_crop_draft_state()),
        )

    def apply_session_metadata(self, metadata):
        metadata = metadata or {}
        self.session_project_name = str(metadata.get("project_name", "")).strip()
        self.session_user_name = str(metadata.get("user_name", "")).strip()
        self.session_institution = str(metadata.get("institution", "")).strip()
        self.session_date = str(metadata.get("date", "")).strip()
        self.update_session_metadata_status_label()

    def format_session_metadata_status_text(self):
        field_specs = (
            ("project_name", "Project"),
            ("user_name", "User"),
            ("institution", "Institution"),
            ("date", "Date"),
        )
        metadata = self.serialize_session_metadata()
        parts = []
        for key, label in field_specs:
            value = str(metadata.get(key, "")).strip()
            if value:
                parts.append(f"{label}: {value}")
        return " | ".join(parts)

    def update_session_metadata_status_label(self):
        label = getattr(self, "session_metadata_status_label", None)
        if label is None:
            return
        text = self.format_session_metadata_status_text()
        label.setText(text)
        label.setToolTip(text)
        label.setVisible(bool(text))

    def has_session_content(self):
        raw_width, raw_height = self.get_current_raw_image_dimensions()
        crop_is_identity = True
        if raw_width > 0 and raw_height > 0:
            crop_is_identity = crop_state_is_identity(
                raw_width,
                raw_height,
                self.current_image_edit_crop_state(),
            )
        return bool(
            self.has_frames()
            or self.cell_items
            or self.cell_records_by_id
            or self.sample_catalog
            or abs(float(getattr(self, "image_edit_exposure", 0.0))) > 1e-9
            or abs(float(getattr(self, "image_edit_contrast", 0.0))) > 1e-9
            or self.has_image_edit_uniform_exposure_area()
            or self.has_image_edit_uniform_exposure()
            or (not crop_is_identity)
            or self.grayscale_results_headers
            or self.grayscale_results_rows
            or self.freeze_results_headers
            or self.freeze_results_rows
            or self.freeze_count_timeseries_headers
            or self.freeze_count_timeseries_rows
        )

    def has_session_save_payload(self):
        return self.has_session_content() or any(self.serialize_session_metadata().values())

    def prompt_save_before_replacing_session(self, next_action_label="starting a new session"):
        if (not getattr(self, "session_active", False)) or (not self.has_session_save_payload()):
            return "discard"

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Question)
        dialog.setWindowTitle("Save Session")
        dialog.setText(f"Do you want to save this session before {next_action_label}?")
        dialog.setInformativeText("Undo/redo history will be cleared.")
        save_button = dialog.addButton("Save", QMessageBox.AcceptRole)
        dont_save_button = dialog.addButton("Don't Save", QMessageBox.DestructiveRole)
        cancel_button = dialog.addButton(QMessageBox.Cancel)
        dialog.setDefaultButton(save_button)
        dialog.exec()

        clicked_button = dialog.clickedButton()
        if clicked_button == cancel_button:
            return "cancel"
        if clicked_button == save_button:
            return "saved" if self.saveSession() else "cancel"
        return "discard"

    def prompt_new_session_metadata(self, *, window_title="New Session"):
        dialog = NewSessionMetadataDialog(
            self,
            self.serialize_session_metadata(),
            window_title=window_title,
        )
        if dialog.exec() != QDialog.Accepted:
            return None
        return dialog.get_metadata()

    def editSessionMetadata(self, checked=False):
        metadata = self.prompt_new_session_metadata(window_title="Edit Session Metadata")
        if metadata is None:
            return
        self.apply_session_metadata(metadata)
        self.session_active = True
        self.update_session_actions_state()
        self.log("Update session metadata")

    def newSession(self, checked=False):
        save_choice = self.prompt_save_before_replacing_session("starting a new session")
        if save_choice == "cancel":
            return

        metadata = self.prompt_new_session_metadata()
        if metadata is None:
            return

        self.clear_session(
            confirm=False,
            log_message="Started new session",
            record_history=False,
            new_metadata=metadata,
            activate_session=True,
        )
        self.undo_stack.clear()
        self.pending_analysis_before_state = None
        self.log("New session ready")

    def initUI(self):
        # Set main window properties
        self.setWindowTitle('Icescopy')
        self.setGeometry(100, 100, 1000, 700)
        if platform.system() == "Darwin":
            self.setWindowFlags(
                (self.windowFlags() | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowSystemMenuHint |
                 Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint) & ~Qt.WindowFullscreenButtonHint
            )

        # Create a menu bar
        menubar = self.menuBar()

        # Create the "IceScopy" menu
        icescopy_menu = menubar.addMenu("IceScopy")
        icescopy_menu.setFont(QFont("Arial", 10, QFont.Bold))

        # Add "About" action to "IceScopy" menu
        about_action = QAction("About", self)
        about_action.triggered.connect(self.showAboutDialog)
        icescopy_menu.addAction(about_action)
        icescopy_menu.addSeparator() # Add a separator to the menu

        self.preferences_action = QAction("Preferences", self)
        self.preferences_action.triggered.connect(self.showPreferencesDialog)
        icescopy_menu.addAction(self.preferences_action)

        file_menu = menubar.addMenu("File")
        edit_menu = menubar.addMenu("Edit")
        analysis_menu = menubar.addMenu("Analysis")
        window_menu = menubar.addMenu("Window")

        # Create actions with icons
        self.add_source_action = QAction("Add Source", self)
        self.add_images_action = QAction("Add Image Files...", self)
        self.add_folder_action = QAction("Add Image Folder...", self)
        self.open_video_action = QAction("Open Video Source...", self)
        self.remove_selected_action = QAction("Remove Selected", self)
        self.clear_images_action = QAction("Clear Images", self)
        self.new_session_action = QAction("New Session", self)
        self.open_session_action = QAction("Open Session", self)
        self.save_session_action = QAction("Save Session", self)
        self.save_session_as_action = QAction("Save Session As...", self)
        self.edit_session_metadata_action = QAction("Edit Session Metadata...", self)
        self.save_session_action.setShortcuts([QKeySequence.Save, QKeySequence("Ctrl+S")])
        self.save_session_as_action.setShortcuts([QKeySequence.SaveAs])
        self.relink_images_action = QAction("Relink Images Folder...", self)
        self.run_analysis_action = QAction("Run Analysis", self)
        self.output_results_action = QAction("Output Results", self)
        self.import_temperature_csv_action = QAction("Standard CSV import...", self)
        self.import_csu_is_dat_action = QAction("CSU IS .dat import...", self)
        self.import_tamu_linkam_xlsx_action = QAction("TAMU Linkam .xlsx import...", self)
        self.import_pku_linksys32_iml_action = QAction("PKU Linksys32 .iml import...", self)
        self.import_utk_csv_action = QAction("UTK CSV import...", self)
        self.sort_images_action = QAction("Sort Images", self)
        self.sample_manager_action = QAction("Sample Catalog Manager", self)
        self.image_edit_action = QAction("Image Edit", self)
        self.viewer_single_action = QAction("Show One Image", self)
        self.viewer_double_action = QAction("Show Two Images", self)
        self.viewer_triple_action = QAction("Show Three Images", self)
        self.viewer_orientation_toggle_action = QAction("Stack Top to Bottom", self)
        self.undo_action = QAction("Undo", self)
        self.redo_action = QAction("Redo", self)
        self.undo_action.setShortcuts([QKeySequence.Undo])
        if IS_WINDOWS:
            self.redo_action.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Shift+Z")])
        else:
            self.redo_action.setShortcuts([QKeySequence.Redo])
        self.reset_cursor_action = QAction("Cursor Tool (A)", self)
        self.select_tool_action = QAction("Add Cell (S)", self)
        self.grid_tool_action = QAction("Grid Tool (G)", self)
        self.edit_tool_action = QAction("Edit Cell (E)", self)
        self.deselect_tool_action = QAction("Delete Cells (D)", self)
        self.pan_tool_action = QAction("Pan and Zoom (Z)", self) 

        file_menu.addAction(self.new_session_action)
        file_menu.addAction(self.open_session_action)
        file_menu.addAction(self.save_session_action)
        file_menu.addAction(self.save_session_as_action)
        file_menu.addAction(self.edit_session_metadata_action)
        file_menu.addSeparator() # Add a separator to the menu
        file_menu.addAction(self.output_results_action)
        file_menu.addSeparator() # Add a separator to the menu
        file_menu.addAction(self.add_images_action)
        file_menu.addAction(self.add_folder_action)
        file_menu.addAction(self.open_video_action)
        file_menu.addSeparator()
        file_menu.addAction(self.relink_images_action)
        file_menu.addSeparator() # Add a separator to the menu
        file_menu.addAction(self.remove_selected_action)
        file_menu.addAction(self.clear_images_action)
        file_menu.addSeparator() # Add a separator to the menu
        file_menu.addAction(self.sort_images_action)

        analysis_menu.addAction(self.run_analysis_action)
        analysis_menu.addSeparator()
        import_temperature_menu = analysis_menu.addMenu("Import Temperature Data")
        import_temperature_menu.addAction(self.import_temperature_csv_action)
        import_temperature_menu.addSeparator()
        import_temperature_menu.addAction(self.import_csu_is_dat_action)
        import_temperature_menu.addAction(self.import_tamu_linkam_xlsx_action)
        import_temperature_menu.addAction(self.import_pku_linksys32_iml_action)
        import_temperature_menu.addAction(self.import_utk_csv_action)

        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator() # Add a separator to the menu
        edit_menu.addAction(self.reset_cursor_action)
        edit_menu.addAction(self.pan_tool_action)
        edit_menu.addAction(self.image_edit_action)
        edit_menu.addSeparator() # Add a separator to the menu
        edit_menu.addAction(self.select_tool_action)
        edit_menu.addAction(self.grid_tool_action)
        edit_menu.addAction(self.edit_tool_action)
        edit_menu.addAction(self.deselect_tool_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.sample_manager_action)
        


        if IS_MACOS:
            self.undo_action.setToolTip("Undo (Cmd+Z)")
            self.redo_action.setToolTip("Redo (Shift+Cmd+Z)")
        else:
            self.undo_action.setToolTip("Undo (Ctrl+Z)")
            self.redo_action.setToolTip("Redo (Ctrl+Y)")
        self.add_source_action.setToolTip("Add image files, an image folder, or a video source")
        self.deselect_tool_action.setToolTip(
            "Delete mode. Click cells to remove them. In Cursor mode, Delete or Backspace removes the selected cells."
        )

        self.add_source_action.triggered.connect(self.open_add_images_dialog)
        self.add_folder_action.triggered.connect(self.loadFolder)
        self.add_images_action.triggered.connect(self.loadImages)
        self.open_video_action.triggered.connect(self.open_video)
        self.new_session_action.triggered.connect(self.newSession)
        self.open_session_action.triggered.connect(self.openSession)
        self.save_session_action.triggered.connect(self.handle_save_session_action)
        self.save_session_as_action.triggered.connect(self.saveSessionAs)
        self.edit_session_metadata_action.triggered.connect(self.editSessionMetadata)
        self.relink_images_action.triggered.connect(self.relink_images_folder)
        self.output_results_action.triggered.connect(self.export_results_csv)
        self.import_temperature_csv_action.triggered.connect(self.import_standard_temperature_csv)
        self.import_csu_is_dat_action.triggered.connect(self.import_csu_is_dat)
        self.import_tamu_linkam_xlsx_action.triggered.connect(self.import_tamu_linkam_xlsx)
        self.import_pku_linksys32_iml_action.triggered.connect(self.import_pku_linksys32_iml)
        self.import_utk_csv_action.triggered.connect(self.import_utk_temperature_csv)
        self.remove_selected_action.triggered.connect(self.remove_selected_image)
        self.clear_images_action.triggered.connect(self.clear_loaded_images)
        self.run_analysis_action.triggered.connect(self.outputData)
        self.sort_images_action.triggered.connect(self.openSortImagesDialog)
        self.sample_manager_action.triggered.connect(self.show_sample_catalog_manager)
        self.image_edit_action.triggered.connect(self.imageEditTool)
        self.viewer_single_action.triggered.connect(lambda: self.set_viewer_image_count(1))
        self.viewer_double_action.triggered.connect(lambda: self.set_viewer_image_count(2))
        self.viewer_triple_action.triggered.connect(lambda: self.set_viewer_image_count(3))
        self.viewer_orientation_toggle_action.triggered.connect(self.toggle_viewer_split_orientation)
        self.undo_action.triggered.connect(self.undo)
        self.redo_action.triggered.connect(self.redo)
        self.reset_cursor_action.triggered.connect(self.reset_cursor_tool)
        self.reset_cursor_action.setCheckable(True)
        self.select_tool_action.triggered.connect(self.selectTool)
        self.select_tool_action.setCheckable(True)
        self.grid_tool_action.triggered.connect(self.gridTool)
        self.grid_tool_action.setCheckable(True)
        self.edit_tool_action.triggered.connect(self.editTool)
        self.edit_tool_action.setCheckable(True)
        self.deselect_tool_action.triggered.connect(self.deselectTool)
        self.deselect_tool_action.setCheckable(True)
        self.pan_tool_action.triggered.connect(self.panTool)
        self.pan_tool_action.setCheckable(True)
        self.image_edit_action.setCheckable(True)
        self.viewer_single_action.setCheckable(True)
        self.viewer_double_action.setCheckable(True)
        self.viewer_triple_action.setCheckable(True)
        self.undo_stack.canUndoChanged.connect(lambda _: self.set_undo_status())
        self.undo_stack.canRedoChanged.connect(lambda _: self.set_redo_status())
        self.preview_confirm_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.preview_confirm_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.preview_confirm_shortcut.activated.connect(self.handle_preview_confirm_shortcut)
        self.preview_confirm_shortcut_enter = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self.preview_confirm_shortcut_enter.setContext(Qt.WidgetWithChildrenShortcut)
        self.preview_confirm_shortcut_enter.activated.connect(self.handle_preview_confirm_shortcut)
        self.preview_cancel_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.preview_cancel_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.preview_cancel_shortcut.activated.connect(self.handle_preview_cancel_shortcut)
        self.update_preview_shortcut_enabled_state()

        # disable tools before loading data
        self.select_tool_action.setEnabled(False)
        self.grid_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.pan_tool_action.setEnabled(False)
        self.image_edit_action.setEnabled(False)
        self.add_source_action.setEnabled(False)
        self.add_images_action.setEnabled(False)
        self.add_folder_action.setEnabled(False)
        self.open_video_action.setEnabled(False)
        self.remove_selected_action.setEnabled(False)
        self.clear_images_action.setEnabled(False)
        self.save_session_action.setEnabled(False)
        self.save_session_as_action.setEnabled(False)
        self.relink_images_action.setEnabled(False)
        self.run_analysis_action.setEnabled(False)
        self.output_results_action.setEnabled(False)

        # Initialize toolbar
        self.toolbar = self.addToolBar("Tools")

        # Add actions to toolbar
        self.toolbar.addAction(self.preferences_action)
        self.toolbar.addAction(self.new_session_action)
        self.toolbar.addAction(self.open_session_action)
        self.toolbar.addAction(self.save_session_action)
        self.toolbar.addAction(self.output_results_action)
        self.toolbar.addSeparator()  # Add a separator between groups of actions
        self.toolbar.addAction(self.add_source_action)
        self.toolbar.addAction(self.remove_selected_action)
        self.toolbar.addAction(self.clear_images_action)
        self.toolbar.addAction(self.sort_images_action)
        self.toolbar.addAction(self.image_edit_action)
        self.toolbar.addAction(self.sample_manager_action)
        self.toolbar.addAction(self.run_analysis_action)
        self.toolbar.addSeparator()  # Add a separator between groups of actions
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addAction(self.reset_cursor_action)
        self.toolbar.addAction(self.pan_tool_action)
        self.toolbar.addAction(self.select_tool_action)
        self.toolbar.addAction(self.grid_tool_action)
        self.toolbar.addAction(self.deselect_tool_action)
        self.toolbar.addAction(self.edit_tool_action)
        self.toolbar.addSeparator()  # Add a separator between groups of actions
        self.toolbar.addAction(self.viewer_single_action)
        self.toolbar.addAction(self.viewer_double_action)
        self.toolbar.addAction(self.viewer_triple_action)
        self.toolbar.addAction(self.viewer_orientation_toggle_action)

        self.tool_name_dict = {"pan":self.pan_tool_action, 
                               "image-edit":self.image_edit_action,
                               "cursor":self.reset_cursor_action, 
                               "select":self.select_tool_action,
                               "grid":self.grid_tool_action,
                               "deselect":self.deselect_tool_action, 
                               "edit-choose":self.edit_tool_action, 
                               "edit-new":self.edit_tool_action}
        
        self.toolbar.setIconSize(QSize(32, 32))

        # Slider for navigating through images
        self.image_slider = FrameSlider(Qt.Horizontal, self)
        self.image_slider.setTracking(False)
        self.image_slider.valueChanged.connect(self.handle_committed_image_slider_value)
        self.image_slider.sliderMoved.connect(self.handle_preview_image_slider_value)
        self.image_slider.sliderPressed.connect(self.handle_image_slider_pressed)
        self.image_slider.sliderReleased.connect(self.handle_image_slider_released)
        self.image_slider.keyframeClicked.connect(self.update_keyframe_list)
        self.image_slider.analysisStartClicked.connect(self.update_analysis_start_frame_list)
        self.image_slider.analysisEndClicked.connect(self.update_analysis_end_frame_list)
        self.image_preview_timer = QTimer(self)
        self.image_preview_timer.setSingleShot(True)
        self.image_preview_timer.timeout.connect(self.flush_pending_preview_image)
        self.image_edit_preview_timer = QTimer(self)
        self.image_edit_preview_timer.setSingleShot(True)
        self.image_edit_preview_timer.setTimerType(Qt.PreciseTimer)
        self.image_edit_preview_timer.timeout.connect(self.flush_pending_image_edit_preview)
        self.image_edit_histogram_timer = QTimer(self)
        self.image_edit_histogram_timer.setSingleShot(True)
        self.image_edit_histogram_timer.setTimerType(Qt.PreciseTimer)
        self.image_edit_histogram_timer.timeout.connect(self.flush_pending_image_edit_histogram)
        self.analysis_progress_timer = QTimer(self)
        self.analysis_progress_timer.setSingleShot(True)
        self.analysis_progress_timer.timeout.connect(self.flush_pending_analysis_progress)
        
        # Text box to display slider value
        self.image_textbox = QLineEdit()
        self.image_textbox.returnPressed.connect(self.updateImageFromTextbox)

        view_slider_layout = QVBoxLayout()
        view_slider_layout.setContentsMargins(0, 0, 0, 0)

        # Button for slider manipulating and keyframe editing
        # Create the buttons
        self.leftButton = QPushButton()
        self.rightButton = QPushButton()
        self.keyframe_toggle_button = QPushButton()
        self.flag_toggle_button = QPushButton()
        self.analysis_start_toggle_button = QPushButton()
        self.analysis_end_toggle_button = QPushButton()
        self.flag_toggle_button.setToolTip("Mark or clear the current frame as frozen for selected cells")
        self.analysis_start_toggle_button.setToolTip("Toggle analysis start marker at the current frame")
        self.analysis_end_toggle_button.setToolTip("Toggle analysis end marker at the current frame")

        self.leftButton.clicked.connect(self.decreaseSliderValue)
        self.rightButton.clicked.connect(self.increaseSliderValue)
        self.keyframe_toggle_button.clicked.connect(self.image_slider.toggle_keyframe)
        self.flag_toggle_button.clicked.connect(self.image_slider.toggle_flagging)
        self.analysis_start_toggle_button.clicked.connect(self.image_slider.toggle_analysis_start)
        self.analysis_end_toggle_button.clicked.connect(self.image_slider.toggle_analysis_end)

        # Zoom slider for changing the granularity of the image_slider
        self.zoom_slider = SliderZoom_Slider(Qt.Horizontal, self)
        self.zoom_slider.valueChanged.connect(self.image_slider.update_zoomed_level)

        slider_buttons_layout = QHBoxLayout()
        slider_buttons_layout.addStretch(1)
        slider_buttons_layout.addWidget(self.keyframe_toggle_button)
        slider_buttons_layout.addWidget(self.flag_toggle_button)
        slider_buttons_layout.addWidget(self.leftButton)
        slider_buttons_layout.addWidget(self.zoom_slider)
        slider_buttons_layout.addWidget(self.rightButton)
        slider_buttons_layout.addWidget(self.analysis_start_toggle_button)
        slider_buttons_layout.addWidget(self.analysis_end_toggle_button)
        slider_buttons_layout.addStretch(1)
        slider_buttons_layout.setContentsMargins(0, 0, 0, 3)
        self.slider_buttons_layout = slider_buttons_layout

        slider_buttons_widget = QWidget()
        slider_buttons_widget.setLayout(slider_buttons_layout)
        self.slider_buttons_widget = slider_buttons_widget

        # Create a QHBoxLayout for image slider and text box
        image_navigation_layout = QVBoxLayout()
        image_navigation_layout.setContentsMargins(0, 0, 0, 0 if platform.system() == "Windows" else 6)
        image_navigation_layout.addWidget(self.image_slider)

        # CustomGraphicsView and QGraphicsScene for image display
        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.scene.selectionChanged.connect(self.handle_scene_cell_selection_changed)
        self.view = CustomGraphicsView(self.scene, self)
        
        view_slider_layout.addWidget(self.view)
        view_slider_layout.addWidget(slider_buttons_widget)
        view_slider_layout.addLayout(image_navigation_layout)
        view_slider_layout.setSpacing(0)
        view_slider_layout.setContentsMargins(0, 0, 0, 0)

        self.view_slider_widget = QWidget()
        self.view_slider_widget.setLayout(view_slider_layout)

        self.terminal = QTextEdit(self)
        self.terminal.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.terminal.setReadOnly(True)

        self.image_list_model = ImageListModel(self)
        self.image_list_widget = QListView(self)
        self.image_list_widget.setModel(self.image_list_model)
        self.image_list_widget.setAlternatingRowColors(True)
        self.image_list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.image_list_widget.setUniformItemSizes(True)
        self.image_list_widget.setWrapping(False)
        self.image_list_widget.setFocusPolicy(Qt.StrongFocus)
        self.image_list_widget.setMinimumWidth(SIDE_PANEL_DEFAULT_WIDTH)
        self.image_list_widget.clicked.connect(self.handle_image_list_selection)
        self.image_list_widget.selectionModel().currentChanged.connect(self.handle_image_list_current_changed)
        self.frozen_frames_only_checkbox = QCheckBox("Frozen only", self)
        self.frozen_frames_only_checkbox.setToolTip("Show only frames with freeze events for the current cell selection.")
        self.frozen_frames_only_checkbox.toggled.connect(self.set_frame_list_frozen_only)
        image_list_toolbar = QWidget(self)
        image_list_toolbar_layout = QHBoxLayout(image_list_toolbar)
        image_list_toolbar_layout.setContentsMargins(6, 2, 6, 2)
        image_list_toolbar_layout.setSpacing(6)
        image_list_toolbar_layout.addStretch(1)
        image_list_toolbar_layout.addWidget(self.frozen_frames_only_checkbox)
        self.image_list_panel = QWidget(self)
        image_list_panel_layout = QVBoxLayout(self.image_list_panel)
        image_list_panel_layout.setContentsMargins(0, 0, 0, 0)
        image_list_panel_layout.setSpacing(0)
        image_list_panel_layout.addWidget(image_list_toolbar)
        image_list_panel_layout.addWidget(self.image_list_widget)

        # These tables are retained for internal data/export handling only.
        # They are no longer docked in the UI, so they must not be visible
        # children of the main window.
        self.data_table = QTableWidget()
        self.freeze_table = QTableWidget()
        self.freeze_count_timeseries_table = QTableWidget()
        self.grayscale_plot_widget = GrayscalePlotWidget(self)
        self.setup_table_widget(self.data_table)
        self.setup_table_widget(self.freeze_table)
        self.setup_table_widget(self.freeze_count_timeseries_table)
        self.results_table_tabs = QTabWidget(self)
        self.results_table_tabs.addTab(self.data_table, "Measurements")
        self.results_table_tabs.addTab(self.freeze_table, "Freeze Events")
        self.results_table_tabs.addTab(self.freeze_count_timeseries_table, "Freeze Count Timeseries")
        self.results_table_tabs.setTabPosition(QTabWidget.South)
        self.results_table_tabs.tabBar().setExpanding(False)
        self.results_table_tabs.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: right;
            }
        """)
        self.update_results_table_visibility()
        self.tool_options_widget = self.build_tool_options_panel()
        self.sample_catalog_widget = self.build_sample_catalog_panel()
        self.cells_panel_widget = self.build_cells_panel()

        self.setCentralWidget(self.view_slider_widget)
        self.image_list_widget.installEventFilter(self)
        self.image_list_widget.viewport().installEventFilter(self)
        self.image_slider.installEventFilter(self)
        self.zoom_slider.installEventFilter(self)
        self.image_textbox.installEventFilter(self)
        self.grayscale_plot_widget.installEventFilter(self)
        self.grayscale_plot_widget.plot_widget.installEventFilter(self)
        self.setDockNestingEnabled(True)
        self.setDockOptions(
            self.dockOptions()
            | QMainWindow.AllowTabbedDocks
            | QMainWindow.AllowNestedDocks
            | QMainWindow.GroupedDragging
        )
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        self.image_list_dock = self.create_dock_widget("Images", self.image_list_panel, "imageListDock")
        self.console_dock = self.create_dock_widget("Console", self.terminal, "consoleDock")
        self.tool_options_dock = self.create_dock_widget("Tool Options", self.tool_options_widget, "toolOptionsDock")
        self.sample_catalog_dock = self.create_dock_widget("Sample Catalog", self.sample_catalog_widget, "sampleCatalogDock")
        self.cells_dock = self.create_dock_widget("Cells", self.cells_panel_widget, "cellsDock")
        self.grayscale_dock = None
        self.grayscale_plot_dock = self.create_dock_widget("Grayscale Plot", self.grayscale_plot_widget, "grayscalePlotDock")
        self.results_tables_dock = self.create_dock_widget("Results Tables", self.results_table_tabs, "resultsTablesDock")
        self.freeze_dock = None

        self.addDockWidget(Qt.LeftDockWidgetArea, self.image_list_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.tool_options_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.sample_catalog_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.cells_dock)
        self.tabifyDockWidget(self.tool_options_dock, self.sample_catalog_dock)
        self.tabifyDockWidget(self.sample_catalog_dock, self.cells_dock)
        self.tool_options_dock.raise_()
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.grayscale_plot_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.results_tables_dock)
        self.tabifyDockWidget(self.console_dock, self.grayscale_plot_dock)
        self.tabifyDockWidget(self.grayscale_plot_dock, self.results_tables_dock)
        self.console_dock.raise_()
        self.sample_catalog_dock.hide()
        self.cells_dock.hide()
        self.grayscale_plot_dock.hide()
        self.results_tables_dock.hide()
        self.cells_dock.visibilityChanged.connect(self.handle_cells_panel_visibility_changed)
        self.grayscale_plot_dock.visibilityChanged.connect(self.handle_grayscale_plot_visibility_changed)

        reset_layout_action = QAction("Reset Panel Layout", self)
        reset_layout_action.triggered.connect(self.reset_panel_layout)
        self.zoom_window_action = QAction("Zoom Window", self)
        self.zoom_window_action.triggered.connect(self.zoom_window)
        self.restore_window_action = QAction("Restore Window", self)
        self.restore_window_action.triggered.connect(self.restore_window)
        window_menu.addAction(self.zoom_window_action)
        window_menu.addAction(self.restore_window_action)
        window_menu.addSeparator()
        window_menu.addAction(self.viewer_single_action)
        window_menu.addAction(self.viewer_double_action)
        window_menu.addAction(self.viewer_triple_action)
        window_menu.addAction(self.viewer_orientation_toggle_action)
        window_menu.addSeparator()
        window_menu.addAction(reset_layout_action)
        window_menu.addSeparator()
        window_menu.addAction(self.image_list_dock.toggleViewAction())
        window_menu.addAction(self.tool_options_dock.toggleViewAction())
        window_menu.addAction(self.sample_catalog_dock.toggleViewAction())
        window_menu.addAction(self.cells_dock.toggleViewAction())
        window_menu.addAction(self.console_dock.toggleViewAction())
        window_menu.addAction(self.grayscale_plot_dock.toggleViewAction())
        window_menu.addAction(self.results_tables_dock.toggleViewAction())

        # Create a QHBoxLayout for circle radius and zoom level
        self.statusBar = QStatusBar()

        # Create labels and text boxes
        self.session_metadata_status_label = QLabel("", self)
        self.session_metadata_status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.session_metadata_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.session_metadata_status_label.setMinimumWidth(0)
        self.radius_status_label = QLabel("Circle Radius:")
        self.zoom_status_label = QLabel("Zoom Level:")
        self.frame_status_label = QLabel("Frame Number:")

        self.radius_textbox = QLineEdit() # Status text box showing the radius of the circle size for add circle
        self.zoom_textbox = QLineEdit()   # Level of magnifying for the image
        self.radius_textbox.returnPressed.connect(self.updateCircleRadius_from_textedit)
        self.zoom_textbox.returnPressed.connect(self.updateZoomLevel)

        # Set maximum width for the text boxes
        self.radius_textbox.setFixedWidth(60)
        self.zoom_textbox.setFixedWidth(60)
        self.image_textbox.setMinimumWidth(72)

        # Set image label
        self.image_name_label = QLabel('', self)

        self.tool_status_label = QLabel('', self)

        # Metadata stays on the left; the live frame/view controls stay grouped on the right.
        self.statusBar.addWidget(self.session_metadata_status_label, 1)
        self.statusBar.addPermanentWidget(self.radius_status_label)
        self.statusBar.addPermanentWidget(self.radius_textbox)
        self.statusBar.addPermanentWidget(self.zoom_status_label)
        self.statusBar.addPermanentWidget(self.zoom_textbox)
        self.statusBar.addPermanentWidget(self.frame_status_label)
        self.statusBar.addPermanentWidget(self.image_textbox)
        self.statusBar.addPermanentWidget(self.image_name_label)
        self.statusBar.addPermanentWidget(self.tool_status_label)

        # Set the status bar
        self.setStatusBar(self.statusBar)

        self.setFocusPolicy(Qt.StrongFocus)  # Enable keyboard focus for the main window

        # Default initializations
        self.reset_cursor_action.trigger()  # force reset the cursor
        self.resize_image_textbox() # set default size for the frame number textbox. Will get called when updating frames (changing slider value)
        self.reset_status_bar_stylesheet()
        self.update_session_metadata_status_label()
        self.updateRadiusTextbox()
        self.updateZoomTextbox()
        self.reset_toolbar_icon()
        self.reset_toolbar_stylesheet()
        self.reset_slider_stylesheet()
        self.reset_button_icon()
        self.reset_button_stylesheet()
        self.set_redo_status()
        self.set_undo_status()
        self.updateButtonStates()
        self.update_session_actions_state()
        QTimer.singleShot(0, self.finalize_initial_dock_layout)

        self.log("Initialized. Waiting for input...") # Initialize message in log terminal
        

    ##### END initUI() #####

    def finalize_initial_dock_layout(self):
        QTimer.singleShot(0, self.enforce_initial_right_dock_tab)

    def enforce_initial_right_dock_tab(self):
        if hasattr(self, "tool_options_dock") and self.tool_options_dock is not None:
            self.tool_options_dock.show()
            self.tool_options_dock.raise_()
        self.store_default_dock_state()

    def format_numeric_value(self, value):
        return f"{value:g}"

    def current_preview_absolute_coordinates(self):
        origin = getattr(self, "grid_preview_origin_pixels", None)
        if origin is None:
            return None
        try:
            return (
                float(origin[0]) + float(getattr(self, "preview_offset_x", 0.0)),
                float(origin[1]) + float(getattr(self, "preview_offset_y", 0.0)),
            )
        except (TypeError, ValueError, IndexError):
            return None

    def clamp_preview_absolute_coordinates(self, x_value, y_value):
        try:
            clamped_x = float(x_value)
            clamped_y = float(y_value)
        except (TypeError, ValueError):
            return 0.0, 0.0

        raw_width, raw_height = self.get_current_raw_image_dimensions()
        if raw_width <= 0 or raw_height <= 0:
            return clamped_x, clamped_y

        min_x = 0.0
        min_y = 0.0
        max_x = max(min_x, float(raw_width))
        max_y = max(min_y, float(raw_height))
        return (
            min(max(clamped_x, min_x), max_x),
            min(max(clamped_y, min_y), max_y),
        )

    def set_preview_absolute_coordinates(self, x_value, y_value):
        absolute_x, absolute_y = self.clamp_preview_absolute_coordinates(x_value, y_value)
        origin = getattr(self, "grid_preview_origin_pixels", None)
        if origin is None:
            self.grid_preview_origin_pixels = (absolute_x, absolute_y)
            self.preview_offset_x = 0.0
            self.preview_offset_y = 0.0
            return

        try:
            origin_x = float(origin[0])
            origin_y = float(origin[1])
        except (TypeError, ValueError, IndexError):
            self.grid_preview_origin_pixels = (absolute_x, absolute_y)
            self.preview_offset_x = 0.0
            self.preview_offset_y = 0.0
            return

        self.preview_offset_x = float(absolute_x) - origin_x
        self.preview_offset_y = float(absolute_y) - origin_y

    def build_tool_options_panel(self):
        panel = QWidget(self)
        panel.setObjectName("toolOptionsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        panel.setMinimumWidth(SIDE_PANEL_DEFAULT_WIDTH)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.tool_options_mode_label = QLabel("Tool Options")
        self.tool_options_mode_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.tool_options_mode_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #4a4a4a;")
        layout.addWidget(self.tool_options_mode_label)

        self.tool_options_stack = QStackedWidget(panel)
        self.tool_options_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.tool_options_none_page = ToolOptionsInfoPage(panel)
        self.tool_options_none_label = self.tool_options_none_page.message_label
        self.tool_options_none_page.set_message(
            "Choose a cell or image-edit tool. Tool-specific controls will appear here."
        )

        self.cursor_tool_page = ToolOptionsFormPage(panel)
        self.cursor_info_section_label = self.cursor_tool_page.add_section_label("Cell Info")
        self.cursor_info_row_widgets = {}
        self.cursor_info_label_widgets = {}
        self.cursor_info_value_labels = {}
        cursor_info_rows = (
            ("selected", "Selected:"),
            ("cell_id", "Cell ID:"),
            ("sample_name", "Name:"),
            ("x", "X:"),
            ("y", "Y:"),
            ("radius", "Radius:"),
        )
        for field_name, label_text in cursor_info_rows:
            row_widget, label_widget, value_widget = self.cursor_tool_page.add_value_row(label_text)
            self.cursor_info_row_widgets[field_name] = row_widget
            self.cursor_info_label_widgets[field_name] = label_widget
            self.cursor_info_value_labels[field_name] = value_widget

        self.cursor_info_edit_separator = self.cursor_tool_page.add_separator()
        self.cursor_edit_section_label = self.cursor_tool_page.add_section_label("Cell Edit")
        self.cursor_freeze_lineedit = QLineEdit(self.cursor_tool_page.column_widget)
        self.cursor_freeze_lineedit.setPlaceholderText("None")
        self.cursor_tool_page._configure_control(self.cursor_freeze_lineedit)
        self.cursor_freeze_lineedit.installEventFilter(self)
        self.cursor_freeze_lineedit.editingFinished.connect(self.apply_cursor_freeze_frames_edit)
        self.cursor_freeze_row, self.cursor_freeze_apply_button = self.cursor_tool_page.add_row_with_button(
            "Freeze Frame:",
            self.cursor_freeze_lineedit,
            "Set",
            self.apply_cursor_freeze_frames_edit,
        )

        self.cursor_sample_combo = self.cursor_tool_page.create_combo_box(
            index_handler=self.assign_selected_cells_to_current_sample,
        )
        self.cursor_sample_row = self.cursor_tool_page.add_row("Sample ID:", self.cursor_sample_combo)

        self.cursor_sample_button_row, self.cursor_sample_new_button = self.cursor_tool_page.add_centered_button_row(
            "New Sample",
            self.create_sample_from_cursor_controls,
        )
        self.cursor_tool_hint = self.cursor_tool_page.add_hint(
            "Select cells in Cursor mode to inspect them. Edit freeze frames for one cell or assign samples to one or more cells."
        )
        self.cursor_tool_page.add_bottom_stretch()

        self.delete_tool_page = ToolOptionsFormPage(panel)
        self.delete_tool_hint = self.delete_tool_page.add_hint(
            "Click a cell to delete it. In Cursor mode, select one or more cells and press Delete or Backspace to remove them."
        )
        self.delete_tool_page.add_bottom_stretch()

        self.image_edit_tool_page = ToolOptionsFormPage(
            panel,
            content_width=TOOL_OPTIONS_CONTENT_WIDTH,
            label_width=72,
            field_width=180,
            shortcut_width=0,
        )
        self.image_edit_histogram_widget = ImageHistogramWidget(self.image_edit_tool_page.column_widget)
        self.image_edit_histogram_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_histogram_widget)
        self.image_edit_histogram_separator = self.image_edit_tool_page.add_separator()

        self.image_edit_exposure_block = QWidget(self.image_edit_tool_page.column_widget)
        self.image_edit_exposure_block.setFixedWidth(self.image_edit_tool_page.content_width)
        self.image_edit_exposure_block.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        image_edit_exposure_block_layout = QVBoxLayout(self.image_edit_exposure_block)
        image_edit_exposure_block_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_exposure_block_layout.setSpacing(4)

        self.image_edit_exposure_header = QWidget(self.image_edit_exposure_block)
        self.image_edit_exposure_header.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        image_edit_exposure_header_layout = QHBoxLayout(self.image_edit_exposure_header)
        image_edit_exposure_header_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_exposure_header_layout.setSpacing(8)

        self.image_edit_exposure_label = QLabel("Exposure", self.image_edit_exposure_header)
        self.image_edit_exposure_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        image_edit_exposure_header_layout.addWidget(self.image_edit_exposure_label, 1)

        self.image_edit_exposure_spinbox = QDoubleSpinBox(self.image_edit_exposure_header)
        self.image_edit_exposure_spinbox.setRange(-4.0, 4.0)
        self.image_edit_exposure_spinbox.setDecimals(1)
        self.image_edit_exposure_spinbox.setSingleStep(0.1)
        self.image_edit_exposure_spinbox.setFixedWidth(60)
        self.image_edit_exposure_spinbox.valueChanged.connect(self.handle_image_edit_exposure_spinbox_changed)
        image_edit_exposure_header_layout.addWidget(self.image_edit_exposure_spinbox, 0)
        image_edit_exposure_block_layout.addWidget(self.image_edit_exposure_header)

        self.image_edit_exposure_slider = QSlider(Qt.Horizontal, self.image_edit_exposure_block)
        self.image_edit_exposure_slider.setObjectName("imageEditExposureSlider")
        self.image_edit_exposure_slider.setRange(-40, 40)
        self.image_edit_exposure_slider.setSingleStep(1)
        self.image_edit_exposure_slider.setPageStep(5)
        self.image_edit_exposure_slider.installEventFilter(self)
        self.image_edit_exposure_slider.valueChanged.connect(self.handle_image_edit_exposure_slider_changed)
        self.image_edit_exposure_slider.sliderReleased.connect(self.handle_image_edit_exposure_slider_released)
        self.image_edit_exposure_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        image_edit_exposure_block_layout.addWidget(self.image_edit_exposure_slider)
        self.image_edit_exposure_block.setFixedHeight(self.image_edit_exposure_block.sizeHint().height())
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_exposure_block)
        self.image_edit_exposure_separator = self.image_edit_tool_page.add_separator()

        self.image_edit_contrast_block = QWidget(self.image_edit_tool_page.column_widget)
        self.image_edit_contrast_block.setFixedWidth(self.image_edit_tool_page.content_width)
        self.image_edit_contrast_block.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        image_edit_contrast_block_layout = QVBoxLayout(self.image_edit_contrast_block)
        image_edit_contrast_block_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_contrast_block_layout.setSpacing(4)

        self.image_edit_contrast_header = QWidget(self.image_edit_contrast_block)
        self.image_edit_contrast_header.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        image_edit_contrast_header_layout = QHBoxLayout(self.image_edit_contrast_header)
        image_edit_contrast_header_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_contrast_header_layout.setSpacing(8)

        self.image_edit_contrast_label = QLabel("Contrast", self.image_edit_contrast_header)
        self.image_edit_contrast_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        image_edit_contrast_header_layout.addWidget(self.image_edit_contrast_label, 1)

        self.image_edit_contrast_spinbox = QSpinBox(self.image_edit_contrast_header)
        self.image_edit_contrast_spinbox.setRange(-100, 100)
        self.image_edit_contrast_spinbox.setSingleStep(1)
        self.image_edit_contrast_spinbox.setFixedWidth(60)
        self.image_edit_contrast_spinbox.valueChanged.connect(self.handle_image_edit_contrast_spinbox_changed)
        image_edit_contrast_header_layout.addWidget(self.image_edit_contrast_spinbox, 0)
        image_edit_contrast_block_layout.addWidget(self.image_edit_contrast_header)

        self.image_edit_contrast_slider = QSlider(Qt.Horizontal, self.image_edit_contrast_block)
        self.image_edit_contrast_slider.setObjectName("imageEditContrastSlider")
        self.image_edit_contrast_slider.setRange(-100, 100)
        self.image_edit_contrast_slider.setSingleStep(1)
        self.image_edit_contrast_slider.setPageStep(10)
        self.image_edit_contrast_slider.installEventFilter(self)
        self.image_edit_contrast_slider.valueChanged.connect(self.handle_image_edit_contrast_slider_changed)
        self.image_edit_contrast_slider.sliderReleased.connect(self.handle_image_edit_contrast_slider_released)
        self.image_edit_contrast_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        image_edit_contrast_block_layout.addWidget(self.image_edit_contrast_slider)
        self.image_edit_contrast_block.setFixedHeight(self.image_edit_contrast_block.sizeHint().height())
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_contrast_block)
        self.image_edit_contrast_separator = self.image_edit_tool_page.add_separator()

        self.image_edit_uniform_exposure_section_label = self.image_edit_tool_page.add_section_label("Uniform Exposure")
        self.image_edit_uniform_exposure_button_row = QWidget(self.image_edit_tool_page.column_widget)
        image_edit_uniform_exposure_button_layout = QHBoxLayout(self.image_edit_uniform_exposure_button_row)
        image_edit_uniform_exposure_button_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_uniform_exposure_button_layout.setSpacing(TOOL_OPTIONS_BUTTON_SPACING)
        self.image_edit_uniform_exposure_area_button = self.image_edit_tool_page._create_button(
            "Set Area",
            self.image_edit_uniform_exposure_button_row,
            self.handle_image_edit_uniform_exposure_area_button,
        )
        self.image_edit_uniform_exposure_run_button = self.image_edit_tool_page._create_button(
            "Run",
            self.image_edit_uniform_exposure_button_row,
            self.run_image_edit_uniform_exposure,
        )
        self.image_edit_uniform_exposure_reset_button = self.image_edit_tool_page._create_button(
            "Reset",
            self.image_edit_uniform_exposure_button_row,
            self.reset_image_edit_uniform_exposure,
        )
        uniform_button_width = int(
            (
                self.image_edit_tool_page.content_width
                - (2 * TOOL_OPTIONS_BUTTON_SPACING)
            ) / 3
        )
        self.image_edit_uniform_exposure_area_button.setFixedWidth(uniform_button_width)
        self.image_edit_uniform_exposure_run_button.setFixedWidth(uniform_button_width)
        self.image_edit_uniform_exposure_reset_button.setFixedWidth(uniform_button_width)
        image_edit_uniform_exposure_button_layout.addWidget(self.image_edit_uniform_exposure_area_button)
        image_edit_uniform_exposure_button_layout.addWidget(self.image_edit_uniform_exposure_run_button)
        image_edit_uniform_exposure_button_layout.addWidget(self.image_edit_uniform_exposure_reset_button)
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_uniform_exposure_button_row)
        self.image_edit_uniform_exposure_hint = self.image_edit_tool_page.add_hint(
            "Use the current frame as the reference. Set one control area, then Run to match each image's area brightness to that frame."
        )
        self.image_edit_uniform_exposure_separator = self.image_edit_tool_page.add_separator()

        self.image_edit_crop_section_label = self.image_edit_tool_page.add_section_label("Crop")
        self.image_edit_crop_button_row = QWidget(self.image_edit_tool_page.column_widget)
        image_edit_crop_button_layout = QHBoxLayout(self.image_edit_crop_button_row)
        image_edit_crop_button_layout.setContentsMargins(0, 0, 0, 0)
        image_edit_crop_button_layout.setSpacing(TOOL_OPTIONS_BUTTON_SPACING)
        self.image_edit_crop_start_button = self.image_edit_tool_page._create_button(
            "Crop",
            self.image_edit_crop_button_row,
            self.handle_image_edit_crop_primary_button,
        )
        self.image_edit_crop_apply_button = self.image_edit_tool_page._create_button(
            "Apply",
            self.image_edit_crop_button_row,
            self.apply_image_edit_crop,
        )
        self.image_edit_crop_reset_button = self.image_edit_tool_page._create_button(
            "Reset",
            self.image_edit_crop_button_row,
            self.reset_image_edit_crop,
        )
        button_width = int(
            (
                self.image_edit_tool_page.content_width
                - (2 * TOOL_OPTIONS_BUTTON_SPACING)
            ) / 3
        )
        self.image_edit_crop_start_button.setFixedWidth(button_width)
        self.image_edit_crop_apply_button.setFixedWidth(button_width)
        self.image_edit_crop_reset_button.setFixedWidth(button_width)
        image_edit_crop_button_layout.addWidget(self.image_edit_crop_start_button)
        image_edit_crop_button_layout.addWidget(self.image_edit_crop_apply_button)
        image_edit_crop_button_layout.addWidget(self.image_edit_crop_reset_button)
        self.image_edit_tool_page.column_layout.addWidget(self.image_edit_crop_button_row)

        self.image_edit_tool_hint = self.image_edit_tool_page.add_hint(
            "Exposure and contrast apply to all images. Uniform Exposure matches one control area across frames. Press Crop, adjust the box, then Apply. Reset restores the committed crop to the full image."
        )
        self.image_edit_tool_page.add_bottom_stretch()

        self.circle_tool_page = ToolOptionsFormPage(panel)
        self.circle_radius_spinbox = self.circle_tool_page.create_double_spin_box(
            1,
            100000,
            value_handler=self.handle_circle_radius_spinbox_changed,
        )
        self.circle_offset_x_spinbox = self.circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.circle_offset_y_spinbox = self.circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.circle_tool_page.add_row("Radius", self.circle_radius_spinbox, "scroll")
        self.circle_tool_page.add_row("X", self.circle_offset_x_spinbox)
        self.circle_tool_page.add_row("Y", self.circle_offset_y_spinbox)
        self.circle_tool_page.add_action_row(
            self.handle_circle_apply_action,
            self.handle_circle_float_action,
            self.handle_circle_cancel_action,
        )
        self.circle_tool_hint = self.circle_tool_page.add_hint(
            "Move the preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
        )
        self.circle_apply_button = self.circle_tool_page.apply_button
        self.circle_float_button = self.circle_tool_page.float_button
        self.circle_cancel_button = self.circle_tool_page.cancel_button
        self.circle_tool_page.add_bottom_stretch()

        self.edit_circle_tool_page = ToolOptionsFormPage(panel)
        self.edit_circle_cell_id_spinbox = self.edit_circle_tool_page.create_spin_box(0, 100000)
        self.edit_circle_cell_id_spinbox.editingFinished.connect(self.apply_edit_circle_cell_id_edit)
        self.edit_circle_radius_spinbox = self.edit_circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_circle_radius_spinbox_changed,
        )
        self.edit_circle_offset_x_spinbox = self.edit_circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.edit_circle_offset_y_spinbox = self.edit_circle_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.edit_circle_tool_page.add_row("Cell ID", self.edit_circle_cell_id_spinbox)
        self.edit_circle_tool_page.add_row("Radius Delta", self.edit_circle_radius_spinbox, "scroll")
        self.edit_circle_tool_page.add_row("X Offset", self.edit_circle_offset_x_spinbox)
        self.edit_circle_tool_page.add_row("Y Offset", self.edit_circle_offset_y_spinbox)
        self.edit_circle_tool_page.add_action_row(
            self.handle_circle_apply_action,
            self.handle_circle_float_action,
            self.handle_circle_cancel_action,
        )
        self.edit_circle_tool_hint = self.edit_circle_tool_page.add_hint(
            "Move the lifted circle over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
        )
        self.edit_circle_apply_button = self.edit_circle_tool_page.apply_button
        self.edit_circle_float_button = self.edit_circle_tool_page.float_button
        self.edit_circle_cancel_button = self.edit_circle_tool_page.cancel_button
        self.edit_circle_tool_page.add_bottom_stretch()

        self.grid_tool_page = ToolOptionsFormPage(panel)
        self.grid_rows_spinbox = self.grid_tool_page.create_spin_box(
            1,
            100,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_columns_spinbox = self.grid_tool_page.create_spin_box(
            1,
            100,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_radius_spinbox = self.grid_tool_page.create_double_spin_box(
            1,
            100000,
            value_handler=self.handle_grid_radius_change,
        )
        self.grid_hpitch_spinbox = self.grid_tool_page.create_double_spin_box(
            1,
            100000,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_vpitch_spinbox = self.grid_tool_page.create_double_spin_box(
            1,
            100000,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_rotation_spinbox = self.grid_tool_page.create_double_spin_box(
            -180,
            180,
            value_handler=self.handle_grid_parameter_change,
        )
        self.grid_offset_x_spinbox = self.grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.grid_offset_y_spinbox = self.grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.grid_tool_page.add_row("Rows", self.grid_rows_spinbox)
        self.grid_tool_page.add_row("Cols", self.grid_columns_spinbox)
        self.grid_tool_page.add_row("Radius", self.grid_radius_spinbox, "scroll")
        self.grid_tool_page.add_row("H Pitch", self.grid_hpitch_spinbox, self.grid_horizontal_pitch_shortcut_label())
        self.grid_tool_page.add_row("V Pitch", self.grid_vpitch_spinbox, self.grid_vertical_pitch_shortcut_label())
        self.grid_tool_page.add_row("Tilt", self.grid_rotation_spinbox, self.grid_tilt_shortcut_label())
        self.grid_tool_page.add_row("X", self.grid_offset_x_spinbox)
        self.grid_tool_page.add_row("Y", self.grid_offset_y_spinbox)
        self.grid_tool_page.add_action_row(
            self.handle_grid_apply_action,
            self.handle_grid_float_action,
            self.handle_grid_cancel_action,
        )
        self.grid_tool_hint = self.grid_tool_page.add_hint(
            "Move the preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
        )
        self.grid_apply_button = self.grid_tool_page.apply_button
        self.grid_float_button = self.grid_tool_page.float_button
        self.grid_cancel_button = self.grid_tool_page.cancel_button
        self.grid_tool_page.add_bottom_stretch()

        self.edit_grid_tool_page = ToolOptionsFormPage(panel)
        self.edit_grid_radius_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_grid_radius_change,
        )
        self.edit_grid_hpitch_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_grid_parameter_change,
        )
        self.edit_grid_vpitch_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_grid_parameter_change,
        )
        self.edit_grid_rotation_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -180,
            180,
            value_handler=self.handle_grid_parameter_change,
        )
        self.edit_grid_offset_x_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.edit_grid_offset_y_spinbox = self.edit_grid_tool_page.create_double_spin_box(
            -100000,
            100000,
            value_handler=self.handle_preview_offset_change,
        )
        self.edit_grid_tool_page.add_row("Radius Delta", self.edit_grid_radius_spinbox, "scroll")
        self.edit_grid_tool_page.add_row("X Pitch", self.edit_grid_hpitch_spinbox, self.grid_horizontal_pitch_shortcut_label())
        self.edit_grid_tool_page.add_row("Y Pitch", self.edit_grid_vpitch_spinbox, self.grid_vertical_pitch_shortcut_label())
        self.edit_grid_tool_page.add_row("Rotation", self.edit_grid_rotation_spinbox, self.grid_tilt_shortcut_label())
        self.edit_grid_tool_page.add_row("X Offset", self.edit_grid_offset_x_spinbox)
        self.edit_grid_tool_page.add_row("Y Offset", self.edit_grid_offset_y_spinbox)
        self.edit_grid_tool_page.add_action_row(
            self.handle_grid_apply_action,
            self.handle_grid_float_action,
            self.handle_grid_cancel_action,
        )
        self.edit_grid_tool_hint = self.edit_grid_tool_page.add_hint(
            "Move the group preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
        )
        self.edit_grid_apply_button = self.edit_grid_tool_page.apply_button
        self.edit_grid_float_button = self.edit_grid_tool_page.float_button
        self.edit_grid_cancel_button = self.edit_grid_tool_page.cancel_button
        self.edit_grid_tool_page.add_bottom_stretch()

        self.tool_options_stack.addWidget(self.tool_options_none_page)
        self.tool_options_stack.addWidget(self.cursor_tool_page)
        self.tool_options_stack.addWidget(self.delete_tool_page)
        self.tool_options_stack.addWidget(self.image_edit_tool_page)
        self.tool_options_stack.addWidget(self.circle_tool_page)
        self.tool_options_stack.addWidget(self.grid_tool_page)
        self.tool_options_stack.addWidget(self.edit_circle_tool_page)
        self.tool_options_stack.addWidget(self.edit_grid_tool_page)
        layout.addWidget(self.tool_options_stack, 1)

        panel.setStyleSheet(f"""
            QLabel {{ line-height: 1.3; }}
            {TOOL_OPTIONS_CONTROL_QSS}
        """)

        self.sync_tool_options_panel()
        return panel

    def build_cells_panel(self):
        panel = QWidget(self)
        panel.setMinimumWidth(SIDE_PANEL_DEFAULT_WIDTH)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.cells_tree_widget = QTreeWidget(panel)
        self.cells_tree_widget.setColumnCount(2)
        self.cells_tree_widget.setHeaderLabels(["Field", "Value"])
        self.cells_tree_widget.setRootIsDecorated(True)
        self.cells_tree_widget.setUniformRowHeights(True)
        self.cells_tree_widget.setAlternatingRowColors(True)
        self.cells_tree_widget.setAnimated(False)
        self.cells_tree_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cells_tree_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.cells_tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.cells_tree_widget.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.cells_tree_widget.itemSelectionChanged.connect(self.handle_cells_panel_selection_changed)
        layout.addWidget(self.cells_tree_widget, 1)

        hint = QLabel(
            "Shows mostly static cell record data. Sample assignment stays in Cursor mode and Sample Catalog.",
            panel,
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.addWidget(hint)

        self.cells_panel_last_snapshot = None
        self.cells_panel_dirty = False
        self.cells_panel_force_refresh = False
        self.refresh_cells_panel()
        return panel

    def update_cursor_sample_controls(self):
        if not hasattr(self, "cursor_tool_page") or not hasattr(self, "cursor_sample_combo") or not hasattr(self, "cursor_sample_new_button"):
            return

        if self.tool_mode != "cursor":
            return

        self.ensure_sample_catalog_matches_cell_records()

        selected_items = sorted(
            self.get_selected_cell_items(),
            key=lambda item: int(getattr(item, "cell_id", 0)),
        )
        selected_sample_ids = set()
        for item in selected_items:
            record = self.ensure_cell_record(item.cell_id)
            sample_id = str(getattr(record, "sample_id", ""))
            selected_sample_ids.add(sample_id)

        has_mixed_selection = bool(selected_items) and len(selected_sample_ids) > 1
        self.refresh_cursor_sample_combo_catalog(include_mixed_item=has_mixed_selection)

        blocker = QSignalBlocker(self.cursor_sample_combo)
        if not selected_items:
            self.cursor_sample_combo.setCurrentIndex(0)
        elif len(selected_sample_ids) == 1:
            target_sample = next(iter(selected_sample_ids))
            sample_index = self.cursor_sample_combo.findData(target_sample)
            self.cursor_sample_combo.setCurrentIndex(sample_index if sample_index >= 0 else 0)
        else:
            sample_index = self.cursor_sample_combo.findData("__mixed__")
            self.cursor_sample_combo.setCurrentIndex(sample_index if sample_index >= 0 else 0)

        self.refresh_cursor_selection_info(selected_items=selected_items)
        self.update_cursor_record_edit_state(selected_items=selected_items)
        self.update_cursor_sample_assignment_state()

    def update_cursor_sample_assignment_state(self):
        selected_count = len(self.get_selected_cell_items())
        self.cursor_sample_new_button.setEnabled(self.tool_mode == "cursor")
        if hasattr(self, "cursor_sample_combo"):
            self.cursor_sample_combo.setEnabled(self.tool_mode == "cursor" and selected_count > 0)

    def assign_selected_cells_to_current_sample(self):
        selected_items = self.get_selected_cell_items()
        if not selected_items:
            return
        sample_value = self.cursor_sample_combo.currentData() if hasattr(self, "cursor_sample_combo") else None
        if sample_value in (None, "__mixed__"):
            return
        sample_id = str(sample_value)

        before_state = self.capture_data_state()
        changed = False
        for item in selected_items:
            record = self.ensure_cell_record(item.cell_id)
            if record is None:
                continue
            if str(getattr(record, "sample_id", "")) == sample_id:
                continue
            record.sample_id = sample_id
            changed = True

        if not changed:
            return

        self.invalidate_freeze_count_timeseries_results("sample assignments changed")
        self.push_data_history("Assign Sample", before_state)
        if sample_id:
            self.log(f"Assign sample {sample_id} to {len(selected_items)} selected cell(s)")
        else:
            self.log(f"Clear sample assignment for {len(selected_items)} selected cell(s)")
        self.refresh_cell_sample_visuals()
        self.update_cursor_sample_controls()
        self.refresh_cells_panel()

    def create_sample_from_cursor_controls(self):
        before_state = self.capture_data_state()
        sample_id = self.allocate_sample_id()
        self.sample_catalog[int(sample_id)] = self.default_sample_record(sample_id)
        selected_items = self.get_selected_cell_items()
        for item in selected_items:
            record = self.ensure_cell_record(item.cell_id)
            if record is not None:
                record.sample_id = str(sample_id)

        self.recompute_next_sample_id(preserve_if_larger=False)
        self.refresh_sample_catalog_tree(select_sample_id=sample_id, preserve_selection=False)
        if selected_items:
            self.invalidate_freeze_count_timeseries_results("sample assignments changed")
            self.push_data_history("Create and Assign Sample", before_state)
            self.log(f"Create sample {sample_id} and assign to {len(selected_items)} selected cell(s)")
        else:
            self.refresh_freeze_count_timeseries_metadata_from_sample_catalog()
            self.push_data_history("Add Sample", before_state)
            self.log(f"Add sample {sample_id}")
        self.refresh_cell_sample_visuals()
        self.update_cursor_sample_controls()
        self.refresh_cells_panel()

    def sync_tool_options_panel(self):
        # Keep the panel in sync with the current tool state without letting the
        # spin boxes fire recursive updates while we are just mirroring state.
        #
        # Add and Edit intentionally do not share one population source:
        # Add uses the session's live add parameters; Edit must reflect the
        # item/group being edited.
        if not hasattr(self, "tool_options_stack"):
            return

        if self.tool_mode == "select":
            self.tool_options_mode_label.setText("Single Circle")
            self.tool_options_stack.setCurrentWidget(self.circle_tool_page)
            self.sync_circle_tool_panel(radius=self.circle_radius, is_edit=False)
        elif self.cell_controller.uses_grid_panel():
            if self.cell_controller.is_group_edit_mode():
                self.tool_options_mode_label.setText("Edit Group")
                self.tool_options_stack.setCurrentWidget(self.edit_grid_tool_page)
                self.sync_grid_tool_panel(is_edit=True)
            else:
                self.tool_options_mode_label.setText("Grid Placement")
                self.tool_options_stack.setCurrentWidget(self.grid_tool_page)
                self.sync_grid_tool_panel(is_edit=False)
        elif self.tool_mode == "edit-new":
            self.tool_options_mode_label.setText("Edit Cell")
            self.tool_options_stack.setCurrentWidget(self.edit_circle_tool_page)
            self.sync_circle_tool_panel(radius=0.0, is_edit=True)
        elif self.tool_mode == "edit-choose":
            self.tool_options_mode_label.setText("Edit Cell")
            self.tool_options_none_label.setText("Select one circle to edit it, or select several circles in Cursor mode and then choose Edit.")
            self.tool_options_stack.setCurrentWidget(self.tool_options_none_page)
        elif self.tool_mode == "grid":
            self.tool_options_mode_label.setText("Grid Placement")
            self.tool_options_stack.setCurrentWidget(self.grid_tool_page)
            self.sync_grid_tool_panel(is_edit=False)
        elif self.tool_mode == "cursor":
            self.tool_options_mode_label.setText("Cursor")
            self.tool_options_stack.setCurrentWidget(self.cursor_tool_page)
        elif self.tool_mode == "deselect":
            self.tool_options_mode_label.setText("Delete Cells")
            self.tool_options_stack.setCurrentWidget(self.delete_tool_page)
        elif self.tool_mode == "image-edit":
            self.tool_options_mode_label.setText("Image Edit")
            self.tool_options_stack.setCurrentWidget(self.image_edit_tool_page)
            self.sync_image_edit_controls()
            self.request_image_edit_histogram_refresh()
        else:
            self.tool_options_mode_label.setText("Tool Options")
            self.tool_options_none_label.setText("Choose a cell or image-edit tool. Tool-specific controls will appear here.")
            self.tool_options_stack.setCurrentWidget(self.tool_options_none_page)

        self.sync_image_edit_crop_overlay()
        desired_crop_applied = self.should_apply_crop_in_display()
        if self.has_frames() and self.displayed_image_edit_crop_applied != desired_crop_applied:
            self.updateImage(self.image_index)

        self.update_preview_shortcut_enabled_state()
        self.update_cursor_sample_controls()
        self.update_grid_apply_state()

    def update_preview_shortcut_enabled_state(self):
        preview_shortcuts_enabled = (
            hasattr(self, "cell_controller")
            and self.cell_controller.uses_grid_preview()
        )
        for shortcut_name in (
            "preview_confirm_shortcut",
            "preview_confirm_shortcut_enter",
            "preview_cancel_shortcut",
        ):
            shortcut = getattr(self, shortcut_name, None)
            if shortcut is not None:
                shortcut.setEnabled(preview_shortcuts_enabled)

    def current_circle_controls(self):
        if self.tool_mode == "edit-new":
            return {
                "radius": self.edit_circle_radius_spinbox,
                "offset_x": self.edit_circle_offset_x_spinbox,
                "offset_y": self.edit_circle_offset_y_spinbox,
                "hint": self.edit_circle_tool_hint,
                "apply": self.edit_circle_apply_button,
                "float": self.edit_circle_float_button,
                "cancel": self.edit_circle_cancel_button,
            }
        return {
            "radius": self.circle_radius_spinbox,
            "offset_x": self.circle_offset_x_spinbox,
            "offset_y": self.circle_offset_y_spinbox,
            "hint": self.circle_tool_hint,
            "apply": self.circle_apply_button,
            "float": self.circle_float_button,
            "cancel": self.circle_cancel_button,
        }

    def current_grid_controls(self):
        if self.cell_controller.is_group_edit_mode():
            return {
                "rows": None,
                "cols": None,
                "radius": self.edit_grid_radius_spinbox,
                "hpitch": self.edit_grid_hpitch_spinbox,
                "vpitch": self.edit_grid_vpitch_spinbox,
                "rotation": self.edit_grid_rotation_spinbox,
                "offset_x": self.edit_grid_offset_x_spinbox,
                "offset_y": self.edit_grid_offset_y_spinbox,
                "hint": self.edit_grid_tool_hint,
                "apply": self.edit_grid_apply_button,
                "float": self.edit_grid_float_button,
                "cancel": self.edit_grid_cancel_button,
            }
        return {
            "rows": self.grid_rows_spinbox,
            "cols": self.grid_columns_spinbox,
            "radius": self.grid_radius_spinbox,
            "hpitch": self.grid_hpitch_spinbox,
            "vpitch": self.grid_vpitch_spinbox,
            "rotation": self.grid_rotation_spinbox,
            "offset_x": self.grid_offset_x_spinbox,
            "offset_y": self.grid_offset_y_spinbox,
            "hint": self.grid_tool_hint,
            "apply": self.grid_apply_button,
            "float": self.grid_float_button,
            "cancel": self.grid_cancel_button,
        }

    def sync_circle_tool_panel(self, radius, is_edit=False):
        controls = self.current_circle_controls() if is_edit else {
            "radius": self.circle_radius_spinbox,
            "offset_x": self.circle_offset_x_spinbox,
            "offset_y": self.circle_offset_y_spinbox,
        }
        if is_edit:
            self.edit_circle_cell_id_spinbox.blockSignals(True)
        controls["radius"].blockSignals(True)
        controls["offset_x"].blockSignals(True)
        controls["offset_y"].blockSignals(True)
        if is_edit:
            target_item = self.current_single_edit_target_item()
            if target_item is not None:
                self.edit_circle_cell_id_spinbox.setValue(int(target_item.cell_id))
                self.edit_circle_cell_id_spinbox.setEnabled(True)
            else:
                self.edit_circle_cell_id_spinbox.setValue(0)
                self.edit_circle_cell_id_spinbox.setEnabled(False)
            radius_delta = 0.0 if abs(float(self.edit_single_radius_delta)) < 1e-9 else float(self.edit_single_radius_delta)
            controls["radius"].setValue(radius_delta)
            controls["offset_x"].setValue(float(self.preview_offset_x))
            controls["offset_y"].setValue(float(self.preview_offset_y))
        else:
            controls["radius"].setValue(float(radius))
            absolute_coordinates = self.current_preview_absolute_coordinates()
            if absolute_coordinates is None:
                display_x = float(self.preview_offset_x)
                display_y = float(self.preview_offset_y)
            else:
                display_x, display_y = absolute_coordinates
            controls["offset_x"].setValue(display_x)
            controls["offset_y"].setValue(display_y)
        if is_edit:
            self.edit_circle_cell_id_spinbox.blockSignals(False)
        controls["radius"].blockSignals(False)
        controls["offset_x"].blockSignals(False)
        controls["offset_y"].blockSignals(False)

    def sync_grid_tool_panel(self, is_edit=False):
        controls = self.current_grid_controls() if is_edit else {
            "rows": self.grid_rows_spinbox,
            "cols": self.grid_columns_spinbox,
            "radius": self.grid_radius_spinbox,
            "hpitch": self.grid_hpitch_spinbox,
            "vpitch": self.grid_vpitch_spinbox,
            "rotation": self.grid_rotation_spinbox,
            "offset_x": self.grid_offset_x_spinbox,
            "offset_y": self.grid_offset_y_spinbox,
        }
        if controls["rows"] is not None:
            controls["rows"].blockSignals(True)
        if controls["cols"] is not None:
            controls["cols"].blockSignals(True)
        controls["radius"].blockSignals(True)
        controls["hpitch"].blockSignals(True)
        controls["vpitch"].blockSignals(True)
        controls["rotation"].blockSignals(True)
        controls["offset_x"].blockSignals(True)
        controls["offset_y"].blockSignals(True)
        if controls["rows"] is not None:
            controls["rows"].setValue(int(self.grid_rows))
        if controls["cols"] is not None:
            controls["cols"].setValue(int(self.grid_columns))
        if is_edit:
            radius_delta = 0.0 if abs(float(self.edit_group_radius_delta)) < 1e-9 else float(self.edit_group_radius_delta)
            hpitch_delta = 0.0 if abs(float(self.edit_group_horizontal_pitch_delta)) < 1e-9 else float(self.edit_group_horizontal_pitch_delta)
            vpitch_delta = 0.0 if abs(float(self.edit_group_vertical_pitch_delta)) < 1e-9 else float(self.edit_group_vertical_pitch_delta)
            rotation_delta = 0.0 if abs(float(self.edit_group_rotation_delta)) < 1e-9 else float(self.edit_group_rotation_delta)
            controls["radius"].setValue(radius_delta)
            controls["hpitch"].setValue(hpitch_delta)
            controls["vpitch"].setValue(vpitch_delta)
            controls["rotation"].setValue(rotation_delta)
        else:
            controls["radius"].setValue(float(self.circle_radius))
            controls["hpitch"].setValue(float(self.grid_horizontal_pitch))
            controls["vpitch"].setValue(float(self.grid_vertical_pitch))
            controls["rotation"].setValue(float(self.grid_rotation_degrees))
            absolute_coordinates = self.current_preview_absolute_coordinates()
            if absolute_coordinates is None:
                display_x = float(self.preview_offset_x)
                display_y = float(self.preview_offset_y)
            else:
                display_x, display_y = absolute_coordinates
            controls["offset_x"].setValue(display_x)
            controls["offset_y"].setValue(display_y)
        if is_edit:
            controls["offset_x"].setValue(float(self.preview_offset_x))
            controls["offset_y"].setValue(float(self.preview_offset_y))
        if controls["rows"] is not None:
            controls["rows"].blockSignals(False)
        if controls["cols"] is not None:
            controls["cols"].blockSignals(False)
        controls["radius"].blockSignals(False)
        controls["hpitch"].blockSignals(False)
        controls["vpitch"].blockSignals(False)
        controls["rotation"].blockSignals(False)
        controls["offset_x"].blockSignals(False)
        controls["offset_y"].blockSignals(False)

    def sync_active_preview_coordinate_controls(self):
        if not hasattr(self, "tool_options_stack"):
            return

        if self.cell_controller.is_group_edit_mode():
            self.sync_grid_tool_panel(is_edit=True)
            return

        if self.tool_mode == "select":
            self.sync_circle_tool_panel(radius=self.circle_radius, is_edit=False)
        elif self.tool_mode == "grid":
            self.sync_grid_tool_panel(is_edit=False)
        elif self.tool_mode == "edit-new":
            self.sync_circle_tool_panel(radius=0.0, is_edit=True)

    def handle_circle_radius_spinbox_changed(self, value):
        sender = self.sender()
        if sender is self.edit_circle_radius_spinbox:
            self.edit_single_radius_delta = float(value)
        else:
            self.circle_radius = float(value)
            self.updateRadiusTextbox()
        if self.tool_mode in {'select', 'edit-new'}:
            if self.cell_controller.uses_grid_preview():
                self.update_grid_preview()
        elif self.cell_controller.uses_grid_preview():
            self.update_grid_preview()

    def handle_grid_radius_change(self, value):
        sender = self.sender()
        if sender is self.edit_grid_radius_spinbox:
            self.edit_group_radius_delta = float(value)
        else:
            self.circle_radius = float(value)
            self.updateRadiusTextbox()
        self.handle_grid_parameter_change()

    def handle_preview_offset_change(self, *_args):
        current_widget = self.tool_options_stack.currentWidget()
        if current_widget == self.circle_tool_page:
            self.set_preview_absolute_coordinates(
                float(self.circle_offset_x_spinbox.value()),
                float(self.circle_offset_y_spinbox.value()),
            )
        elif current_widget == self.edit_circle_tool_page:
            self.preview_offset_x = float(self.edit_circle_offset_x_spinbox.value())
            self.preview_offset_y = float(self.edit_circle_offset_y_spinbox.value())
        else:
            controls = self.current_grid_controls()
            if current_widget == self.grid_tool_page:
                self.set_preview_absolute_coordinates(
                    float(controls["offset_x"].value()),
                    float(controls["offset_y"].value()),
                )
            else:
                self.preview_offset_x = float(controls["offset_x"].value())
                self.preview_offset_y = float(controls["offset_y"].value())
        if self.cell_controller.uses_grid_preview():
            self.update_grid_preview()

    def handle_grid_parameter_change(self, *_args):
        controls = self.current_grid_controls()
        if controls["rows"] is not None:
            self.grid_rows = controls["rows"].value()
        if controls["cols"] is not None:
            self.grid_columns = controls["cols"].value()
        if self.cell_controller.is_group_edit_mode():
            self.edit_group_horizontal_pitch_delta = float(controls["hpitch"].value())
            self.edit_group_vertical_pitch_delta = float(controls["vpitch"].value())
            self.edit_group_rotation_delta = float(controls["rotation"].value())
        else:
            self.grid_horizontal_pitch = float(controls["hpitch"].value())
            self.grid_vertical_pitch = float(controls["vpitch"].value())
            self.grid_rotation_degrees = float(controls["rotation"].value())
        if self.cell_controller.uses_grid_preview():
            self.update_grid_preview()

    def clear_grid_preview(self):
        # Thin wrapper kept on the main window because the view/event code
        # already calls this name in several places.
        self.cell_controller.clear_preview()

    def cancel_grid_preview(self):
        self.cell_controller.cancel_preview()

    def float_grid_preview(self):
        self.cell_controller.float_preview()

    def update_grid_preview_from_scene_pos(self, scene_pos, pin=False):
        self.cell_controller.update_preview_from_scene_pos(scene_pos, pin)

    def get_grid_preview_definitions(self):
        return self.cell_controller.get_preview_definitions()

    def update_grid_preview(self):
        self.cell_controller.update_preview()

    def update_grid_apply_state(self):
        self.cell_controller.update_grid_panel_state()

    def handle_grid_apply_action(self):
        self.cell_controller.handle_grid_apply_action()

    def handle_circle_apply_action(self):
        self.cell_controller.handle_circle_apply_action()

    def focus_is_text_entry_widget(self):
        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return False
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QAbstractSpinBox)):
            return True
        if isinstance(focus_widget, QComboBox) and focus_widget.isEditable():
            return True
        parent = focus_widget.parentWidget()
        while parent is not None:
            if isinstance(parent, (QLineEdit, QTextEdit, QAbstractSpinBox)):
                return True
            if isinstance(parent, QComboBox) and parent.isEditable():
                return True
            parent = parent.parentWidget()
        return False

    def focus_is_tool_options_editor(self):
        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return False
        if not self.focus_widget_is_within(
            focus_widget,
            [
                getattr(self, "tool_options_widget", None),
                getattr(self, "tool_options_dock", None),
            ],
        ):
            return False
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QAbstractSpinBox)):
            return True
        if isinstance(focus_widget, QComboBox) and focus_widget.isEditable():
            return True
        parent = focus_widget.parentWidget()
        while parent is not None:
            if isinstance(parent, (QLineEdit, QTextEdit, QAbstractSpinBox)):
                return True
            if isinstance(parent, QComboBox) and parent.isEditable():
                return True
            parent = parent.parentWidget()
        return False

    def focus_widget_is_within(self, focus_widget, roots):
        if focus_widget is None:
            return False
        valid_roots = [root for root in roots if root is not None]
        current = focus_widget
        while current is not None:
            if any(current is root for root in valid_roots):
                return True
            current = current.parentWidget()
        return False

    def focus_allows_preview_shortcut(self):
        if not self.cell_controller.uses_grid_preview():
            return False

        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return True
        if self.focus_is_text_entry_widget() and not self.focus_is_tool_options_editor():
            return False
        return True

    def confirm_active_preview(self):
        if not self.cell_controller.uses_grid_preview():
            return False
        if self.grid_preview_floating and not self.cell_controller.pin_current_preview(log_change=False):
            return False
        if self.cell_controller.is_single_preview_mode():
            self.handle_circle_apply_action()
        else:
            self.handle_grid_apply_action()
        return True

    def handle_preview_confirm_shortcut(self):
        if not self.focus_allows_preview_shortcut():
            return
        self.confirm_active_preview()

    def handle_circle_float_action(self):
        if self.cell_controller.uses_grid_preview():
            self.float_grid_preview()

    def handle_circle_cancel_action(self):
        self.cell_controller.handle_circle_cancel_action()

    def handle_preview_cancel_shortcut(self):
        if not self.focus_allows_preview_shortcut():
            return
        if self.cell_controller.is_single_preview_mode():
            self.handle_circle_cancel_action()
        else:
            self.handle_grid_cancel_action()

    def handle_grid_float_action(self):
        if self.cell_controller.uses_grid_preview():
            self.float_grid_preview()

    def handle_grid_cancel_action(self):
        self.cell_controller.handle_grid_cancel_action()

    def get_selected_cell_items(self):
        return self.cell_controller.selected_scene_items()

    def delete_selected_cells(self):
        cell_ids = self.cell_controller.selected_scene_cell_ids()
        if not cell_ids:
            return False

        before_state = self.capture_cell_state(include_analysis=True)
        removed_cell_ids = sorted(set(cell_ids))
        removed_id_set = set(removed_cell_ids)
        kept_items = [
            item for item in self.cell_items
            if item.cell_id not in removed_id_set
        ]

        if len(kept_items) == len(self.cell_items):
            return False

        self.cell_items = kept_items
        self.cell_controller.redraw_current_cells(preserve_selection=False)
        self.delete_cell_items_to_keyframes(removed_cell_ids)
        self.prune_analysis_results_for_deleted_cells(removed_cell_ids)
        self.ensure_cell_registry_matches_scene_cells()
        self.recompute_next_cell_id(preserve_if_larger=False)
        self.refresh_cells_panel()
        joined_numbers = ", ".join(str(number) for number in removed_cell_ids)
        label = "cell" if len(removed_cell_ids) == 1 else "cells"
        self.log(f"Delete {label} {joined_numbers}")
        self.push_cell_history("Delete Cells", before_state, include_analysis=True)
        self.apply_cursor_tool_ui()
        self.refresh_grayscale_plot()
        return True

    def get_edit_target_items(self):
        return self.cell_controller.get_target_items()

    def handle_scene_cell_selection_changed(self):
        if hasattr(self, "tool_options_stack"):
            self.sync_tool_options_panel()
        self.sync_cells_panel_selection()
        self.refresh_freeze_flag_markers()
        self.updateButtonStates()
        self.refresh_grayscale_plot()
        self.request_image_edit_histogram_refresh()

    def reselect_cell_ids(self, cell_ids, sync_tool_panel=True):
        # Scene items are rebuilt whenever circles are re-anchored/redrawn, so we
        # restore selection by stable cell_id instead of holding stale
        # item references.
        number_set = set(cell_ids)
        current_selected = {
            item.cell_id
            for item in self.scene.selectedItems()
            if isinstance(item, CellCircle)
        }
        if current_selected == number_set:
            if sync_tool_panel:
                self.sync_tool_options_panel()
            return
        scene_blocker = QSignalBlocker(self.scene)
        try:
            for item in self.scene.items():
                if isinstance(item, CellCircle):
                    item.setSelected(item.cell_id in number_set)
        finally:
            del scene_blocker
        if sync_tool_panel:
            self.handle_scene_cell_selection_changed()

    def apply_grid_preview(self):
        self.cell_controller.apply_grid_add()

    def show_sample_catalog_manager(self):
        if not hasattr(self, "sample_catalog_dock") or self.sample_catalog_dock is None:
            return
        self.refresh_sample_catalog_tree(preserve_selection=False)
        self.show_dock_widget(self.sample_catalog_dock)

    def zoom_window(self):
        self.showMaximized()
        self.log("Zoom Window")

    def restore_window(self):
        self.showNormal()
        self.log("Restore Window")

    def create_dock_widget(self, title, widget, object_name):
        dock_widget = QDockWidget(title, self)
        dock_widget.setObjectName(object_name)
        if isinstance(widget, QFrame):
            widget.setFrameShape(QFrame.NoFrame)
            widget.setLineWidth(0)
        content_container = QWidget(dock_widget)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(widget)
        dock_widget._content_widget = widget
        dock_widget.setWidget(content_container)
        dock_widget.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        dock_widget.setStyleSheet("QDockWidget { border: none; }")
        dock_widget.setTitleBarWidget(DockTitleBar(dock_widget, title, dock_widget))
        return dock_widget

    def show_dock_widget(self, dock_widget):
        if dock_widget is None or (not shiboken6.isValid(dock_widget)):
            return
        dock_widget.show()
        dock_widget.raise_()
        child_widget = getattr(dock_widget, "_content_widget", dock_widget.widget())
        if child_widget is not None and shiboken6.isValid(child_widget):
            child_widget.setFocus(Qt.OtherFocusReason)

    def store_default_dock_state(self):
        self.default_dock_state = self.saveState()

    def reset_panel_layout(self):
        if self.default_dock_state is not None:
            self.restoreState(self.default_dock_state)
            if self.tool_options_dock is not None and shiboken6.isValid(self.tool_options_dock):
                self.tool_options_dock.raise_()

    def get_slider_handle_rect(self, slider):
        if slider is None:
            return QRectF()
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle_rect = slider.style().subControlRect(
            QStyle.CC_Slider,
            option,
            QStyle.SC_SliderHandle,
            slider,
        )
        return QRectF(handle_rect)

    def reset_image_edit_slider_to_default(self, slider):
        if slider is getattr(self, "image_edit_exposure_slider", None):
            self.begin_image_edit_history("Reset Exposure")
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            self.apply_image_edit_state(
                self.compose_image_edit_state(exposure=0.0),
                invalidate_results=True,
                refresh_display=True,
                sync_controls=True,
            )
            self.commit_image_edit_history("Reset Exposure")
            return True
        if slider is getattr(self, "image_edit_contrast_slider", None):
            self.begin_image_edit_history("Reset Contrast")
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            self.apply_image_edit_state(
                self.compose_image_edit_state(contrast=0.0),
                invalidate_results=True,
                refresh_display=True,
                sync_controls=True,
            )
            self.commit_image_edit_history("Reset Contrast")
            return True
        return False

    def eventFilter(self, watched, event):
        if watched is getattr(self, "cursor_freeze_lineedit", None):
            if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if getattr(self, "cursor_freeze_apply_button", None) is not None:
                    self.cursor_freeze_apply_button.animateClick()
                else:
                    self.apply_cursor_freeze_frames_edit()
                event.accept()
                return True
        elif watched in (self.image_list_widget, self.image_list_widget.viewport()):
            if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
                self.set_active_image_panel("list")
            if event.type() == QEvent.KeyPress:
                if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                    self.remove_selected_list_images()
                    event.accept()
                    return True
                if event.key() == Qt.Key_Space:
                    self.keyPressEvent(event)
                    event.accept()
                    return True
            if event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_Space:
                    self.keyReleaseEvent(event)
                    event.accept()
                    return True
        elif watched in (
            self.image_slider,
            self.zoom_slider,
            getattr(self, "image_edit_exposure_slider", None),
            getattr(self, "image_edit_contrast_slider", None),
            self.grayscale_plot_widget,
            self.grayscale_plot_widget.plot_widget,
        ):
            if watched in (
                getattr(self, "image_edit_exposure_slider", None),
                getattr(self, "image_edit_contrast_slider", None),
            ):
                if event.type() == QEvent.Wheel:
                    event.accept()
                    return True
                if (
                    event.type() == QEvent.MouseButtonDblClick
                    and event.button() == Qt.LeftButton
                    and self.get_slider_handle_rect(watched).contains(event.position())
                ):
                    if self.reset_image_edit_slider_to_default(watched):
                        event.accept()
                        return True
            if event.type() == QEvent.KeyPress and self.handle_frame_navigation_shortcut(event.key()):
                event.accept()
                return True

        return super().eventFilter(watched, event)

    def setup_table_widget(self, table_widget):
        table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        table_widget.setAlternatingRowColors(True)
        table_widget.verticalHeader().setVisible(True)
        table_widget.horizontalHeader().setStretchLastSection(False)
        table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

    def set_table_data(self, table_widget, headers, rows):
        table_widget.setUpdatesEnabled(False)
        table_widget.clear()
        table_widget.setRowCount(0)
        table_widget.setColumnCount(0)

        if not headers:
            table_widget.setUpdatesEnabled(True)
            return

        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        table_widget.setRowCount(len(rows))
        table_widget.setVerticalHeaderLabels([str(index) for index in range(len(rows))])

        for row_index, row_values in enumerate(rows):
            for col_index, value in enumerate(row_values):
                item = QTableWidgetItem("" if value is None else str(value))
                table_widget.setItem(row_index, col_index, item)

        if len(headers) <= 12 and len(rows) <= 300:
            table_widget.resizeColumnsToContents()
        else:
            table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table_widget.horizontalHeader().setStretchLastSection(False)
        table_widget.setUpdatesEnabled(True)

    def update_results_tables(self):
        self.sync_cell_analysis_from_results()
        self.set_table_data(self.data_table, self.grayscale_results_headers, self.grayscale_results_rows)
        self.set_table_data(self.freeze_table, self.freeze_results_headers, self.freeze_results_rows)
        self.update_results_table_visibility()
        self.refresh_freeze_flag_markers()
        self.refresh_grayscale_plot()
        self.refresh_cells_panel()
        self.update_cursor_record_edit_state()

    def refresh_freeze_annotation_views(self, selected_items=None):
        if hasattr(self, "freeze_table"):
            self.set_table_data(self.freeze_table, self.freeze_results_headers, self.freeze_results_rows)
        self.update_results_table_visibility()
        self.refresh_freeze_flag_markers(selected_items=selected_items)
        self.refresh_grayscale_plot()
        self.refresh_cells_panel()
        self.update_cursor_record_edit_state(selected_items=selected_items)

    def replace_freeze_table_rows_for_cells(self, cell_ids):
        if not hasattr(self, "freeze_table"):
            return
        if not hasattr(self.freeze_table, "setUpdatesEnabled"):
            self.set_table_data(self.freeze_table, self.freeze_results_headers, self.freeze_results_rows)
            return

        target_labels = {
            f"cell_{int(cell_id)}"
            for cell_id in (cell_ids or [])
            if cell_id is not None
        }
        if not target_labels or not self.freeze_results_headers:
            self.set_table_data(self.freeze_table, self.freeze_results_headers, self.freeze_results_rows)
            return

        table_widget = self.freeze_table
        headers = self.freeze_results_headers
        replacement_rows = [
            (row_index, list(row_values))
            for row_index, row_values in enumerate(self.freeze_results_rows)
            if row_values and str(row_values[0]) in target_labels
        ]

        table_widget.setUpdatesEnabled(False)
        try:
            if table_widget.columnCount() != len(headers):
                table_widget.clear()
                table_widget.setColumnCount(len(headers))
            table_widget.setHorizontalHeaderLabels(headers)

            for row_index in range(table_widget.rowCount() - 1, -1, -1):
                item = table_widget.item(row_index, 0)
                if item is not None and item.text() in target_labels:
                    table_widget.removeRow(row_index)

            for desired_index, row_values in replacement_rows:
                insert_at = min(desired_index, table_widget.rowCount())
                table_widget.insertRow(insert_at)
                for column_index in range(len(headers)):
                    value = row_values[column_index] if column_index < len(row_values) else ""
                    table_widget.setItem(
                        insert_at,
                        column_index,
                        QTableWidgetItem("" if value is None else str(value)),
                    )

            table_widget.setVerticalHeaderLabels([
                str(index)
                for index in range(table_widget.rowCount())
            ])
            if len(headers) <= 12 and table_widget.rowCount() <= 300:
                table_widget.resizeColumnsToContents()
            else:
                table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            table_widget.horizontalHeader().setStretchLastSection(False)
        finally:
            table_widget.setUpdatesEnabled(True)

    def set_freeze_flag_marker_fast(self, frame_index, is_flagged):
        try:
            frame_index = int(frame_index)
        except (TypeError, ValueError):
            return
        current_flags = set(getattr(self, "flagframe_list", []))
        if is_flagged:
            current_flags.add(frame_index)
        else:
            current_flags.discard(frame_index)
        self.flagframe_list = sorted(current_flags)
        if hasattr(self, "image_slider") and hasattr(self.image_slider, "set_flag_marker"):
            self.image_slider.set_flag_marker(frame_index, is_flagged)
        elif hasattr(self, "image_slider"):
            self.image_slider.sync_marker_state(
                self.keyframe_list,
                self.flagframe_list,
                self.analysis_start_frame_list,
                self.analysis_end_frame_list,
            )
        self.update_image_list_annotations([frame_index])
        self.update_toggle_flagging_button_icon()

    def refresh_freeze_annotation_views_fast(
        self,
        changed_cell_ids,
        *,
        selected_items=None,
        marker_updates=None,
        refresh_plot=False,
    ):
        self.replace_freeze_table_rows_for_cells(changed_cell_ids)
        self.update_results_table_visibility()
        if marker_updates is None:
            self.refresh_freeze_flag_markers(selected_items=selected_items)
        else:
            for frame_index, is_flagged in marker_updates.items():
                self.set_freeze_flag_marker_fast(frame_index, is_flagged)
        if refresh_plot:
            self.refresh_grayscale_plot()
        self.update_cursor_record_edit_state(selected_items=selected_items)

    def update_freeze_count_timeseries_table(self):
        if hasattr(self, "freeze_count_timeseries_table"):
            self.set_table_data(self.freeze_count_timeseries_table, self.freeze_count_timeseries_headers, self.freeze_count_timeseries_rows)
        self.update_results_table_visibility()

    def clear_freeze_count_timeseries_table_widget(self):
        if not hasattr(self, "freeze_count_timeseries_table"):
            return
        table_widget = self.freeze_count_timeseries_table
        table_widget.setUpdatesEnabled(False)
        table_widget.clear()
        table_widget.setRowCount(0)
        table_widget.setColumnCount(0)
        table_widget.setUpdatesEnabled(True)

    def update_results_table_visibility(self):
        if hasattr(self, "results_table_tabs"):
            grayscale_visible = bool(self.grayscale_results_headers)
            freeze_visible = bool(self.freeze_results_headers)
            temperature_visible = bool(self.freeze_count_timeseries_headers)
            self.results_table_tabs.setTabVisible(0, grayscale_visible)
            self.results_table_tabs.setTabVisible(1, freeze_visible)
            self.results_table_tabs.setTabVisible(2, temperature_visible)
            visible_count = int(grayscale_visible) + int(freeze_visible) + int(temperature_visible)
            current_index = self.results_table_tabs.currentIndex()
            if current_index < 0 or not self.results_table_tabs.isTabVisible(current_index):
                for index in range(self.results_table_tabs.count()):
                    if self.results_table_tabs.isTabVisible(index):
                        self.results_table_tabs.setCurrentIndex(index)
                        break
            if hasattr(self, "results_tables_dock") and self.results_tables_dock is not None:
                if visible_count == 0:
                    self.results_tables_dock.hide()

    def set_freeze_count_timeseries_results(self, headers, rows, summary=None):
        self.freeze_count_timeseries_headers = [str(value) for value in (headers or [])]
        self.freeze_count_timeseries_rows = [
            ["" if value is None else str(value) for value in row]
            for row in (rows or [])
        ]
        self.freeze_count_timeseries_summary = dict(summary or {})
        self.freeze_count_timeseries_summary.setdefault(
            "sample_metadata_schema",
            self.serialize_sample_metadata_schema(),
        )
        self.update_freeze_count_timeseries_table()
        if self.freeze_count_timeseries_headers:
            if hasattr(self, "results_table_tabs"):
                self.results_table_tabs.setCurrentIndex(2)
            self.show_dock_widget(self.results_tables_dock)
        self.update_session_actions_state()

    def relabel_freeze_count_timeseries_header_sample_name(self, header_text, sample_name):
        current_header = str(header_text or "")
        replacement_name = str(sample_name or "").strip()
        if not replacement_name:
            return current_header
        for marker in (
            " corrected temperature_C",
            " number total",
            " number frozen",
        ):
            marker_index = current_header.rfind(marker)
            if marker_index >= 0:
                return f"{replacement_name}{current_header[marker_index:]}"
        return current_header

    def refresh_freeze_count_timeseries_metadata_from_sample_catalog(self, *, relabel_headers=False):
        if not self.freeze_count_timeseries_headers:
            return False

        summary = dict(self.freeze_count_timeseries_summary or {})
        summary["sample_metadata_schema"] = (
            self.serialize_sample_metadata_schema()
            if hasattr(self, "serialize_sample_metadata_schema")
            else sample_metadata_schema_to_payload(getattr(self, "sample_metadata_schema", None))
        )
        sample_column_metadata = list(summary.get("sample_column_metadata") or [])
        if not sample_column_metadata:
            return False

        refreshed_sample_metadata = []
        for sample_metadata in sample_column_metadata:
            sample_id = str(sample_metadata.get("sample_id", "") or "").strip()
            if sample_id:
                refreshed_metadata = self.build_freeze_count_timeseries_sample_column_metadata(
                    {"sample_id": sample_id}
                )
            else:
                refreshed_metadata = dict(sample_metadata)
            refreshed_sample_metadata.append(refreshed_metadata)
        summary["sample_column_metadata"] = refreshed_sample_metadata

        refreshed_headers = list(self.freeze_count_timeseries_headers)
        headers_changed = False
        if relabel_headers:
            sample_index = 0
            column_index = 0
            while column_index < len(refreshed_headers) and sample_index < len(refreshed_sample_metadata):
                sample_name = str(refreshed_sample_metadata[sample_index].get("sample_name", "") or "")
                current_header = refreshed_headers[column_index]
                if current_header.endswith(" corrected temperature_C"):
                    refreshed_headers[column_index] = self.relabel_freeze_count_timeseries_header_sample_name(
                        current_header,
                        sample_name,
                    )
                    column_index += 1
                    if column_index >= len(refreshed_headers):
                        break

                if (
                    column_index + 1 < len(refreshed_headers)
                    and refreshed_headers[column_index].endswith(" number total")
                    and refreshed_headers[column_index + 1].endswith(" number frozen")
                ):
                    for offset in range(2):
                        refreshed_headers[column_index + offset] = (
                            self.relabel_freeze_count_timeseries_header_sample_name(
                                refreshed_headers[column_index + offset],
                                sample_name,
                            )
                        )
                    column_index += 2
                    sample_index += 1
                    continue

                column_index += 1
            headers_changed = refreshed_headers != self.freeze_count_timeseries_headers

        refreshed_sample_totals = []
        matched_samples = []
        matched_blank_samples = []
        for sample_entry in list(summary.get("sample_total_cells") or []):
            refreshed_entry = dict(sample_entry)
            sample_id = str(refreshed_entry.get("sample_id", "") or "").strip()
            if sample_id:
                refreshed_name = self.sample_name_for_id(sample_id)
                if refreshed_name:
                    refreshed_entry["sample_name"] = refreshed_name
            refreshed_sample_totals.append(refreshed_entry)
            sample_name = str(refreshed_entry.get("sample_name", "") or "").strip()
            if not sample_name:
                continue
            if str(refreshed_entry.get("role", "sample") or "sample") == "blank":
                matched_blank_samples.append(sample_name)
            else:
                matched_samples.append(sample_name)
        if refreshed_sample_totals:
            summary["sample_total_cells"] = refreshed_sample_totals
            summary["matched_samples"] = matched_samples
            summary["matched_blank_samples"] = matched_blank_samples

        self.freeze_count_timeseries_summary = summary
        if headers_changed:
            self.freeze_count_timeseries_headers = refreshed_headers
            if hasattr(self, "freeze_count_timeseries_table"):
                self.freeze_count_timeseries_table.setHorizontalHeaderLabels(refreshed_headers)
        self.update_session_actions_state()
        return True

    def invalidate_freeze_count_timeseries_results(self, reason=None, refresh_table=True):
        had_results = bool(self.freeze_count_timeseries_headers or self.freeze_count_timeseries_rows)
        self.freeze_count_timeseries_headers = []
        self.freeze_count_timeseries_rows = []
        self.freeze_count_timeseries_summary = {}
        self.last_temperature_import_path = None
        if refresh_table:
            self.update_freeze_count_timeseries_table()
        else:
            self.clear_freeze_count_timeseries_table_widget()
            self.update_results_table_visibility()
        self.update_session_actions_state()
        if had_results and reason:
            self.log(f"Freeze Count Timeseries cleared: {reason}. Re-import the temperature data file.")

    def invalidate_analysis_results(self, reason=None):
        had_results = bool(
            self.grayscale_results_headers
            or self.grayscale_results_rows
            or self.freeze_results_headers
            or self.freeze_results_rows
        )
        self.last_grayscale_output_path = None
        self.last_freeze_output_path = None
        self.grayscale_results_headers = []
        self.grayscale_results_rows = []
        self.freeze_results_headers = []
        self.freeze_results_rows = []
        self.clear_cell_analysis()
        self.update_results_tables()
        self.invalidate_freeze_count_timeseries_results("analysis results changed")
        if had_results and reason:
            self.log(f"Analysis cleared: {reason}. Run Analysis again.")

    def get_plot_target_cell_ids(self):
        selected_cell_ids = [item.cell_id for item in self.get_selected_cell_items()]
        if selected_cell_ids:
            return sorted(set(selected_cell_ids))

        edit_target_numbers = [item.cell_id for item in self.get_edit_target_items()]
        if edit_target_numbers:
            return sorted(set(edit_target_numbers))

        return []

    def refresh_grayscale_plot(self):
        if not hasattr(self, "grayscale_plot_widget"):
            return
        self.grayscale_plot_widget.update_plot_data(
            self.grayscale_results_headers,
            self.grayscale_results_rows,
            self.freeze_results_rows,
            self.get_plot_target_cell_ids(),
            self.get_plot_current_image_index(),
            self.freeze_finder_head_extend_points,
            self.freeze_finder_tail_extend_points,
            self.convolution_half_window_points,
            self.convolution_ramp_points,
            self.timeseries_palette,
            self.timeseries_line_width,
            self.timeseries_convolution_line_width,
            self.get_qcolor(self.timeseries_freeze_line_color).getRgb(),
            self.timeseries_freeze_line_width,
            self.get_qcolor(self.timeseries_current_frame_color).getRgb(),
            self.timeseries_current_frame_line_width,
            current_image_name=None if self.is_video_source() else self.get_plot_current_image_name(),
        )

    def grayscale_plot_is_visible(self):
        plot_widget = getattr(self, "grayscale_plot_widget", None)
        if plot_widget is None:
            return False
        plot_dock = getattr(self, "grayscale_plot_dock", None)
        if plot_dock is not None:
            try:
                return bool(plot_dock.isVisible())
            except RuntimeError:
                return False
        return bool(plot_widget.isVisible())

    def update_grayscale_plot_current_frame(self, force=False):
        if not hasattr(self, "grayscale_plot_widget"):
            return
        if not self.grayscale_plot_is_visible():
            return
        current_image_name = None if self.is_video_source() else self.get_plot_current_image_name()
        self.grayscale_plot_widget.set_current_image_index(
            self.get_plot_current_image_index(),
            current_image_name,
            force=force,
        )

    def get_plot_current_image_index(self):
        if self.pending_preview_image_index is not None:
            return self.pending_preview_image_index
        if self.has_frames() and (0 <= self.image_index < self.frame_count()):
            return self.image_index
        return None

    def get_plot_current_image_name(self):
        current_index = self.get_plot_current_image_index()
        if current_index is None:
            return None
        if 0 <= int(current_index) < self.frame_count():
            return self.frame_name(int(current_index))
        return None

    def capture_session_state(self):
        return {
            "session_metadata": copy.deepcopy(self.serialize_session_metadata()),
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "cell_items": copy.deepcopy(self.cell_items),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_metadata_schema": self.serialize_sample_metadata_schema(),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "keyframe_list": self.keyframe_list.copy(),
            "flagframe_list": self.flagframe_list.copy(),
            "analysis_start_frame_list": self.analysis_start_frame_list.copy(),
            "analysis_end_frame_list": self.analysis_end_frame_list.copy(),
            "keyframe_cell_items_dict": copy.deepcopy(self.keyframe_cell_items_dict),
            "image_width": self.image_width,
            "frame_source": copy.deepcopy(self.frame_source_session_payload()),
            "imagePaths": self.imagePaths.copy(),
            "imageNames": self.imageNames.copy(),
            "image_index": self.image_index,
            "image_list_entry_ids": self.image_list_entry_ids.copy(),
            "next_image_list_entry_id": self.next_image_list_entry_id,
            "sort_mode": self.sort_mode,
            "last_grayscale_output_path": self.last_grayscale_output_path,
            "last_freeze_output_path": self.last_freeze_output_path,
            "last_temperature_import_path": self.last_temperature_import_path,
            "last_temperature_calibration_path": self.last_temperature_calibration_path,
            "last_temperature_reset_temperature": self.last_temperature_reset_temperature,
            "last_temperature_blank_sample_names": list(self.last_temperature_blank_sample_names),
            "last_standard_temperature_image_timestamp_source": self.last_standard_temperature_image_timestamp_source,
            "last_standard_temperature_image_timestamp_style": self.last_standard_temperature_image_timestamp_style,
            "last_standard_temperature_temperature_timestamp_style": self.last_standard_temperature_temperature_timestamp_style,
            "last_standard_temperature_use_image_timestamp_style": self.last_standard_temperature_use_image_timestamp_style,
            "last_standard_temperature_generated_start_text": self.last_standard_temperature_generated_start_text,
            "last_standard_temperature_frame_interval_seconds": self.last_standard_temperature_frame_interval_seconds,
            "last_standard_temperature_temperature_unit": self.last_standard_temperature_temperature_unit,
            "grayscale_results_headers": self.grayscale_results_headers.copy(),
            "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_cell_state(self, include_analysis=False):
        state = {
            "cell_items": copy.deepcopy(self.cell_items),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_metadata_schema": self.serialize_sample_metadata_schema(),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "keyframe_list": self.keyframe_list.copy(),
            "flagframe_list": self.flagframe_list.copy(),
            "analysis_start_frame_list": self.analysis_start_frame_list.copy(),
            "analysis_end_frame_list": self.analysis_end_frame_list.copy(),
            "keyframe_cell_items_dict": copy.deepcopy(self.keyframe_cell_items_dict),
            "image_index": self.image_index,
            "tool_mode": getattr(self, "tool_mode", "cursor"),
            "last_temperature_import_path": self.last_temperature_import_path,
            "last_temperature_calibration_path": self.last_temperature_calibration_path,
            "last_temperature_reset_temperature": self.last_temperature_reset_temperature,
            "last_temperature_blank_sample_names": list(self.last_temperature_blank_sample_names),
            "last_standard_temperature_image_timestamp_source": self.last_standard_temperature_image_timestamp_source,
            "last_standard_temperature_image_timestamp_style": self.last_standard_temperature_image_timestamp_style,
            "last_standard_temperature_temperature_timestamp_style": self.last_standard_temperature_temperature_timestamp_style,
            "last_standard_temperature_use_image_timestamp_style": self.last_standard_temperature_use_image_timestamp_style,
            "last_standard_temperature_generated_start_text": self.last_standard_temperature_generated_start_text,
            "last_standard_temperature_frame_interval_seconds": self.last_standard_temperature_frame_interval_seconds,
            "last_standard_temperature_temperature_unit": self.last_standard_temperature_temperature_unit,
            "freeze_count_timeseries_headers": self.freeze_count_timeseries_headers.copy(),
            "freeze_count_timeseries_rows": copy.deepcopy(self.freeze_count_timeseries_rows),
            "freeze_count_timeseries_summary": dict(self.freeze_count_timeseries_summary),
        }
        if include_analysis:
            state.update({
                "last_grayscale_output_path": self.last_grayscale_output_path,
                "last_freeze_output_path": self.last_freeze_output_path,
                "grayscale_results_headers": self.grayscale_results_headers.copy(),
                "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
                "freeze_results_headers": self.freeze_results_headers.copy(),
                "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            })
        return state

    def capture_data_state(self):
        return {
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_metadata_schema": self.serialize_sample_metadata_schema(),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "last_grayscale_output_path": self.last_grayscale_output_path,
            "last_freeze_output_path": self.last_freeze_output_path,
            "last_temperature_import_path": self.last_temperature_import_path,
            "last_temperature_calibration_path": self.last_temperature_calibration_path,
            "last_temperature_reset_temperature": self.last_temperature_reset_temperature,
            "last_temperature_blank_sample_names": list(self.last_temperature_blank_sample_names),
            "last_standard_temperature_image_timestamp_source": self.last_standard_temperature_image_timestamp_source,
            "last_standard_temperature_image_timestamp_style": self.last_standard_temperature_image_timestamp_style,
            "last_standard_temperature_temperature_timestamp_style": self.last_standard_temperature_temperature_timestamp_style,
            "last_standard_temperature_use_image_timestamp_style": self.last_standard_temperature_use_image_timestamp_style,
            "last_standard_temperature_generated_start_text": self.last_standard_temperature_generated_start_text,
            "last_standard_temperature_frame_interval_seconds": self.last_standard_temperature_frame_interval_seconds,
            "last_standard_temperature_temperature_unit": self.last_standard_temperature_temperature_unit,
            "grayscale_results_headers": self.grayscale_results_headers.copy(),
            "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "freeze_count_timeseries_headers": self.freeze_count_timeseries_headers.copy(),
            "freeze_count_timeseries_rows": copy.deepcopy(self.freeze_count_timeseries_rows),
            "freeze_count_timeseries_summary": dict(self.freeze_count_timeseries_summary),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_freeze_annotation_state(self):
        return {
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "last_freeze_output_path": self.last_freeze_output_path,
            "flagframe_list": self.flagframe_list.copy(),
            "image_index": int(getattr(self, "image_index", 0)),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def freeze_annotation_changed_cell_ids(self, before_payload, after_payload):
        before_payload = before_payload if isinstance(before_payload, dict) else {}
        after_payload = after_payload if isinstance(after_payload, dict) else {}
        changed_cell_ids = []
        def sort_key(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0

        for key in sorted(set(before_payload) | set(after_payload), key=sort_key):
            before_record = before_payload.get(key, {}) if isinstance(before_payload.get(key, {}), dict) else {}
            after_record = after_payload.get(key, {}) if isinstance(after_payload.get(key, {}), dict) else {}
            if (
                before_record.get("freeze_event_indices", []) != after_record.get("freeze_event_indices", [])
                or before_record.get("freeze_rows", []) != after_record.get("freeze_rows", [])
            ):
                try:
                    changed_cell_ids.append(int(key))
                except (TypeError, ValueError):
                    continue
        return changed_cell_ids

    def capture_image_edit_history_state(self):
        return {
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_image_session_state(self):
        return {
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "cell_items": copy.deepcopy(self.cell_items),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_metadata_schema": self.serialize_sample_metadata_schema(),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "keyframe_list": self.keyframe_list.copy(),
            "flagframe_list": self.flagframe_list.copy(),
            "analysis_start_frame_list": self.analysis_start_frame_list.copy(),
            "analysis_end_frame_list": self.analysis_end_frame_list.copy(),
            "keyframe_cell_items_dict": copy.deepcopy(self.keyframe_cell_items_dict),
            "frame_source": copy.deepcopy(self.frame_source_session_payload()),
            "imagePaths": self.imagePaths.copy(),
            "imageNames": self.imageNames.copy(),
            "image_index": self.image_index,
            "image_list_entry_ids": self.image_list_entry_ids.copy(),
            "next_image_list_entry_id": self.next_image_list_entry_id,
            "sort_mode": self.sort_mode,
            "last_grayscale_output_path": self.last_grayscale_output_path,
            "last_freeze_output_path": self.last_freeze_output_path,
            "last_temperature_import_path": self.last_temperature_import_path,
            "last_temperature_calibration_path": self.last_temperature_calibration_path,
            "last_temperature_reset_temperature": self.last_temperature_reset_temperature,
            "last_temperature_blank_sample_names": list(self.last_temperature_blank_sample_names),
            "last_standard_temperature_image_timestamp_source": self.last_standard_temperature_image_timestamp_source,
            "last_standard_temperature_image_timestamp_style": self.last_standard_temperature_image_timestamp_style,
            "last_standard_temperature_temperature_timestamp_style": self.last_standard_temperature_temperature_timestamp_style,
            "last_standard_temperature_use_image_timestamp_style": self.last_standard_temperature_use_image_timestamp_style,
            "last_standard_temperature_generated_start_text": self.last_standard_temperature_generated_start_text,
            "last_standard_temperature_frame_interval_seconds": self.last_standard_temperature_frame_interval_seconds,
            "last_standard_temperature_temperature_unit": self.last_standard_temperature_temperature_unit,
            "grayscale_results_headers": self.grayscale_results_headers.copy(),
            "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_timeline_marker_state(self):
        return {
            "keyframe_list": self.keyframe_list.copy(),
            "flagframe_list": self.flagframe_list.copy(),
            "analysis_start_frame_list": self.analysis_start_frame_list.copy(),
            "analysis_end_frame_list": self.analysis_end_frame_list.copy(),
            "keyframe_cell_items_dict": copy.deepcopy(self.keyframe_cell_items_dict),
            "image_index": int(self.image_index),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def capture_loaded_images_state(self):
        return {
            "image_edit_state": copy.deepcopy(self.serialize_image_edit_state()),
            "next_cell_id": int(getattr(self, "next_cell_id", 0)),
            "cell_records_by_id": copy.deepcopy(self.serialize_cell_records()),
            "sample_metadata_schema": self.serialize_sample_metadata_schema(),
            "sample_catalog": copy.deepcopy(self.serialize_sample_catalog()),
            "next_sample_id": int(getattr(self, "next_sample_id", 0)),
            "frame_source": copy.deepcopy(self.frame_source_session_payload()),
            "imagePaths": self.imagePaths.copy(),
            "imageNames": self.imageNames.copy(),
            "image_index": self.image_index,
            "image_list_entry_ids": self.image_list_entry_ids.copy(),
            "next_image_list_entry_id": self.next_image_list_entry_id,
            "sort_mode": self.sort_mode,
            "last_grayscale_output_path": self.last_grayscale_output_path,
            "last_freeze_output_path": self.last_freeze_output_path,
            "grayscale_results_headers": self.grayscale_results_headers.copy(),
            "grayscale_results_rows": copy.deepcopy(self.grayscale_results_rows),
            "freeze_results_headers": self.freeze_results_headers.copy(),
            "freeze_results_rows": copy.deepcopy(self.freeze_results_rows),
            "tool_mode": getattr(self, "tool_mode", "cursor"),
        }

    def get_active_tool_for_restore(self):
        """Return the user-facing tool to preserve across undo/redo.

        Undo/redo should revert data changes, not unexpectedly switch the user
        to whatever tool happened to be active when the command was created.
        """
        previous_edit_mode = self.temporary_event_data.get("previous_edit_mode")
        if self.cell_controller.is_any_edit_mode() or previous_edit_mode in ["edit-choose", "edit-new", "edit-group"]:
            # In-progress edit is transient interaction state. Undo/redo should
            # cancel that interaction and act on the last committed command.
            return "cursor"
        return getattr(self, "tool_mode", "cursor")

    def cancel_transient_history_state(self):
        """Clear unfinished interaction state before undo/redo.

        Preview/edit state is not itself an undoable command. If the user hits
        undo/redo mid-edit, we should discard the transient interaction first
        and then apply the history command to committed state only.
        """
        previous_edit_mode = self.temporary_event_data.get("previous_edit_mode")
        if self.cell_controller.uses_grid_preview():
            self.cell_controller.cancel_preview(log_message=False)
        elif self.cell_controller.is_any_edit_mode() or previous_edit_mode in ["edit-choose", "edit-new", "edit-group"]:
            self.cancel_edit_state()
            self.tool_mode = "cursor"
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
            self.set_view_cursor_shape(Qt.ArrowCursor)
            self.set_tools_highlight(self.tool_mode)
            self.update_cell_items_selectable_state()
            self.tool_status_label.setText('Select / Move')
            self.sync_tool_options_panel()

    def restore_tool_mode_ui(self, restored_tool_mode=None):
        """Reapply cursor/drag/action state after undo/redo restores data."""
        restored_tool_mode = restored_tool_mode or getattr(self, "tool_mode", "cursor")

        if not self.has_frames():
            self.tool_mode = "cursor"
            self.grid_preview_origin_pixels = None
            self.grid_preview_floating = True
            self.cell_controller.clear_preview()
            self.set_tools_highlight(self.tool_mode)
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
            self.set_view_cursor_shape(Qt.ArrowCursor)
            self.tool_status_label.setText('Select / Move')
            self.update_cell_items_selectable_state()
            self.sync_tool_options_panel()
            return

        if restored_tool_mode in ["edit", "edit-choose", "edit-new", "edit-group"]:
            self.temporary_event_data["previous_edit_mode"] = restored_tool_mode
            self.editTool(self.edit_tool_action.isChecked())
        elif restored_tool_mode == "pan":
            self.pan_tool_action.trigger()
        elif restored_tool_mode == "image-edit":
            self.image_edit_action.trigger()
        elif restored_tool_mode == "select":
            self.select_tool_action.trigger()
        elif restored_tool_mode == "grid":
            self.grid_tool_action.trigger()
        elif restored_tool_mode == "deselect":
            self.deselect_tool_action.trigger()
        else:
            self.reset_cursor_action.trigger()

    def redraw_no_image_cell_template_view(self, *, fit_view=False):
        """Draw stored cells on a blank scene when no images are loaded."""
        if hasattr(self, "pixmap_item") or not hasattr(self, "cell_controller"):
            return
        self.cell_controller.redraw_current_cells(
            preserve_selection=False,
            force_scene_scan=True,
        )
        if fit_view and getattr(self, "rendered_cell_items", []) and hasattr(self, "view"):
            self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)

    def restore_image_session_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.invalidate_freeze_count_timeseries_results()
            self.clear_image_caches()
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            current_source_payload = self.frame_source_session_payload()
            current_image_paths = self.imagePaths.copy()
            current_current_key = self.frame_key(self.image_index) if self.has_frames() and 0 <= self.image_index < self.frame_count() else None
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            self.cell_items = copy.deepcopy(state["cell_items"])
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", {}))
            self.sample_metadata_schema = sample_metadata_schema_from_payload(
                state.get("sample_metadata_schema", self.serialize_sample_metadata_schema())
            )
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.keyframe_list = state["keyframe_list"].copy()
            self.flagframe_list = state["flagframe_list"].copy()
            self.analysis_start_frame_list = state.get("analysis_start_frame_list", []).copy()
            self.analysis_end_frame_list = state.get("analysis_end_frame_list", []).copy()
            self.keyframe_cell_items_dict = copy.deepcopy(state["keyframe_cell_items_dict"])
            frame_source_payload = state.get("frame_source", {
                "kind": SOURCE_KIND_IMAGE_SEQUENCE,
                "image_paths": state.get("imagePaths", []),
            })
            self.set_frame_source(frame_source_from_session_payload(frame_source_payload), reset_frame_ids=False)
            self.image_index = state["image_index"]
            self.last_committed_image_index = int(self.image_index)
            self.image_list_entry_ids = state["image_list_entry_ids"].copy()
            self.next_image_list_entry_id = state["next_image_list_entry_id"]
            self.sort_mode = state.get("sort_mode", self.sort_mode)
            self.apply_image_edit_state(
                state.get("image_edit_state", self.serialize_image_edit_state()),
                invalidate_results=False,
                refresh_display=False,
                sync_controls=False,
            )
            self.last_grayscale_output_path = state.get("last_grayscale_output_path")
            self.last_freeze_output_path = state.get("last_freeze_output_path")
            self.last_temperature_import_path = state.get("last_temperature_import_path")
            self.last_temperature_calibration_path = state.get("last_temperature_calibration_path")
            self.last_temperature_reset_temperature = state.get("last_temperature_reset_temperature")
            self.last_temperature_blank_sample_names = list(state.get("last_temperature_blank_sample_names", []))
            self.last_standard_temperature_image_timestamp_source = state.get("last_standard_temperature_image_timestamp_source", IMAGE_TIMESTAMP_SOURCE_FILENAME)
            self.last_standard_temperature_image_timestamp_style = state.get("last_standard_temperature_image_timestamp_style", TIMESTAMP_STYLE_AUTO)
            self.last_standard_temperature_temperature_timestamp_style = state.get("last_standard_temperature_temperature_timestamp_style", TIMESTAMP_STYLE_AUTO)
            self.last_standard_temperature_use_image_timestamp_style = state.get("last_standard_temperature_use_image_timestamp_style", True)
            self.last_standard_temperature_generated_start_text = state.get("last_standard_temperature_generated_start_text", "")
            self.last_standard_temperature_frame_interval_seconds = state.get("last_standard_temperature_frame_interval_seconds", 1.0)
            self.last_standard_temperature_temperature_unit = state.get("last_standard_temperature_temperature_unit", TEMPERATURE_UNIT_CELSIUS)
            self.grayscale_results_headers = state.get("grayscale_results_headers", []).copy()
            self.grayscale_results_rows = copy.deepcopy(state.get("grayscale_results_rows", []))
            self.freeze_results_headers = state.get("freeze_results_headers", []).copy()
            self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", []))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()

            self.update_results_tables()
            self.refresh_sample_catalog_tree(preserve_selection=False)

            image_set_changed = current_image_paths != self.imagePaths or current_source_payload != self.frame_source_session_payload()
            new_current_key = self.frame_key(self.image_index) if self.has_frames() and 0 <= self.image_index < self.frame_count() else None

            if self.has_frames():
                self.image_slider.blockSignals(True)
                self.image_slider.setEnabled(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(self.frame_count() - 1)
                self.image_slider.setValue(self.image_index)
                self.image_slider.blockSignals(False)
                self.image_slider.sync_marker_state(
                    self.keyframe_list,
                    self.flagframe_list,
                    self.analysis_start_frame_list,
                    self.analysis_end_frame_list,
                )
                self.image_textbox.setText(str(self.image_index))

                self.select_tool_action.setEnabled(True)
                self.grid_tool_action.setEnabled(True)
                self.pan_tool_action.setEnabled(True)
                self.deselect_tool_action.setEnabled(True)
                self.edit_tool_action.setEnabled(True)

                if image_set_changed:
                    self.populate_image_list()
                else:
                    self.update_image_list_annotations()
                    self.sync_image_list_selection()

                if current_current_key != new_current_key or not hasattr(self, 'pixmap_item'):
                    self.updateImage(self.image_index)
                    self.finalize_frame_update(self.image_index)
                else:
                    self.cell_controller.redraw_current_cells(preserve_selection=False, force_scene_scan=True)
                    self.image_name_label.setText(self.frame_name(self.image_index))
                    self.resize_image_textbox()
                    self.updateButtonStates()
                    self.update_toggle_keyframe_button_icon()
                    self.update_toggle_flagging_button_icon()
                    self.update_toggle_analysis_start_button_icon()
                    self.update_toggle_analysis_end_button_icon()
                    self.sync_image_list_selection()
            else:
                self.populate_image_list()
                self.reset_transient_interaction_state()
                preserved_cell_items = copy.deepcopy(self.cell_items)
                self.scene.clear()
                if hasattr(self, 'pixmap_item'):
                    del(self.pixmap_item)
                self.cell_items = preserved_cell_items
                self.rendered_cell_items = []
                self.redraw_no_image_cell_template_view(fit_view=True)
                self.image_name_label.clear()
                self.image_textbox.clear()
                self.image_slider.blockSignals(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(0)
                self.image_slider.setValue(0)
                self.image_slider.blockSignals(False)
                self.image_slider.setEnabled(False)
                self.image_slider.clear_marker_state()
                self.sync_image_list_selection()
                self.select_tool_action.setEnabled(False)
                self.grid_tool_action.setEnabled(False)
                self.pan_tool_action.setEnabled(False)
                self.deselect_tool_action.setEnabled(False)
                self.edit_tool_action.setEnabled(False)

            self.update_session_actions_state()
            self.updateButtonStates()
            self.image_slider.set_custom_ticks()
            self.zoom_slider_set_maximum()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_loaded_images_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.invalidate_freeze_count_timeseries_results()
            self.clear_image_caches()
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            current_source_payload = self.frame_source_session_payload()
            current_image_paths = self.imagePaths.copy()
            current_current_key = self.frame_key(self.image_index) if self.has_frames() and 0 <= self.image_index < self.frame_count() else None
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            frame_source_payload = state.get("frame_source", {
                "kind": SOURCE_KIND_IMAGE_SEQUENCE,
                "image_paths": state.get("imagePaths", []),
            })
            self.set_frame_source(frame_source_from_session_payload(frame_source_payload), reset_frame_ids=False)
            self.image_index = state["image_index"]
            self.last_committed_image_index = int(self.image_index)
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", self.serialize_cell_records()))
            self.sample_metadata_schema = sample_metadata_schema_from_payload(
                state.get("sample_metadata_schema", self.serialize_sample_metadata_schema())
            )
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.image_list_entry_ids = state["image_list_entry_ids"].copy()
            self.next_image_list_entry_id = state["next_image_list_entry_id"]
            self.sort_mode = state.get("sort_mode", self.sort_mode)
            self.apply_image_edit_state(
                state.get("image_edit_state", self.serialize_image_edit_state()),
                invalidate_results=False,
                refresh_display=False,
                sync_controls=False,
            )
            self.last_grayscale_output_path = state.get("last_grayscale_output_path")
            self.last_freeze_output_path = state.get("last_freeze_output_path")
            self.grayscale_results_headers = state.get("grayscale_results_headers", []).copy()
            self.grayscale_results_rows = copy.deepcopy(state.get("grayscale_results_rows", []))
            self.freeze_results_headers = state.get("freeze_results_headers", []).copy()
            self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", []))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()

            self.update_results_tables()
            self.refresh_sample_catalog_tree(preserve_selection=False)

            image_set_changed = current_image_paths != self.imagePaths or current_source_payload != self.frame_source_session_payload()
            new_current_key = self.frame_key(self.image_index) if self.has_frames() and 0 <= self.image_index < self.frame_count() else None

            if self.has_frames():
                self.image_slider.blockSignals(True)
                self.image_slider.setEnabled(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(self.frame_count() - 1)
                self.image_slider.setValue(self.image_index)
                self.image_slider.blockSignals(False)
                self.image_slider.sync_marker_state(
                    self.keyframe_list,
                    self.flagframe_list,
                    self.analysis_start_frame_list,
                    self.analysis_end_frame_list,
                )
                self.image_textbox.setText(str(self.image_index))

                self.select_tool_action.setEnabled(True)
                self.grid_tool_action.setEnabled(True)
                self.pan_tool_action.setEnabled(True)
                self.deselect_tool_action.setEnabled(True)
                self.edit_tool_action.setEnabled(True)

                if image_set_changed:
                    self.populate_image_list()
                else:
                    self.update_image_list_annotations()
                    self.sync_image_list_selection()

                if current_current_key != new_current_key or not hasattr(self, 'pixmap_item'):
                    self.updateImage(self.image_index)
                    self.finalize_frame_update(self.image_index)
                else:
                    self.image_name_label.setText(self.frame_name(self.image_index))
                    self.resize_image_textbox()
                    self.updateButtonStates()
                    self.update_toggle_keyframe_button_icon()
                    self.update_toggle_flagging_button_icon()
                    self.update_toggle_analysis_start_button_icon()
                    self.update_toggle_analysis_end_button_icon()
                    self.sync_image_list_selection()
            else:
                self.populate_image_list()
                self.reset_transient_interaction_state()
                self.scene.clear()
                if hasattr(self, 'pixmap_item'):
                    del(self.pixmap_item)
                self.rendered_cell_items = []
                self.redraw_no_image_cell_template_view(fit_view=True)
                self.image_name_label.clear()
                self.image_textbox.clear()
                self.image_slider.blockSignals(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(0)
                self.image_slider.setValue(0)
                self.image_slider.blockSignals(False)
                self.image_slider.setEnabled(False)
                self.image_slider.clear_marker_state()
                self.sync_image_list_selection()
                self.select_tool_action.setEnabled(False)
                self.grid_tool_action.setEnabled(False)
                self.pan_tool_action.setEnabled(False)
                self.deselect_tool_action.setEnabled(False)
                self.edit_tool_action.setEnabled(False)

            self.update_session_actions_state()
            self.updateButtonStates()
            self.image_slider.set_custom_ticks()
            self.zoom_slider_set_maximum()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_session_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.invalidate_freeze_count_timeseries_results()
            self.clear_image_caches()
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            self.session_active = True
            if "console_history" in state and hasattr(self, "terminal"):
                self.terminal.setPlainText(state["console_history"])
            self.apply_session_metadata(state.get("session_metadata", self.serialize_session_metadata()))

            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", "cursor")
            current_source_payload = self.frame_source_session_payload()
            current_image_paths = self.imagePaths.copy()
            current_image_names = self.imageNames.copy()
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False
            self.cell_items = copy.deepcopy(state["cell_items"])
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", {}))
            self.sample_metadata_schema = sample_metadata_schema_from_payload(
                state.get("sample_metadata_schema", self.serialize_sample_metadata_schema())
            )
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.keyframe_list = state["keyframe_list"].copy()
            self.flagframe_list = state["flagframe_list"].copy()
            self.analysis_start_frame_list = state.get("analysis_start_frame_list", []).copy()
            self.analysis_end_frame_list = state.get("analysis_end_frame_list", []).copy()
            self.keyframe_cell_items_dict = copy.deepcopy(state["keyframe_cell_items_dict"])
            self.image_width = state["image_width"]
            frame_source_payload = state.get("frame_source", {
                "kind": SOURCE_KIND_IMAGE_SEQUENCE,
                "image_paths": state.get("imagePaths", []),
            })
            self.set_frame_source(frame_source_from_session_payload(frame_source_payload), reset_frame_ids=False)
            self.image_index = state["image_index"]
            self.last_committed_image_index = int(self.image_index)
            default_entry_ids = (
                list(range(self.frame_count()))
                if self.source_kind() == SOURCE_KIND_IMAGE_SEQUENCE
                else []
            )
            self.image_list_entry_ids = state.get("image_list_entry_ids", default_entry_ids)
            self.next_image_list_entry_id = state.get("next_image_list_entry_id", len(self.image_list_entry_ids))
            self.sort_mode = state.get("sort_mode", self.sort_mode)
            self.apply_image_edit_state(
                state.get("image_edit_state", self.serialize_image_edit_state()),
                invalidate_results=False,
                refresh_display=False,
                sync_controls=False,
            )
            self.last_grayscale_output_path = state["last_grayscale_output_path"]
            self.last_freeze_output_path = state["last_freeze_output_path"]
            self.last_temperature_import_path = state.get("last_temperature_import_path")
            self.last_temperature_calibration_path = state.get("last_temperature_calibration_path")
            self.last_temperature_reset_temperature = state.get("last_temperature_reset_temperature")
            self.last_temperature_blank_sample_names = list(state.get("last_temperature_blank_sample_names", []))
            self.last_standard_temperature_image_timestamp_source = state.get("last_standard_temperature_image_timestamp_source", IMAGE_TIMESTAMP_SOURCE_FILENAME)
            self.last_standard_temperature_image_timestamp_style = state.get("last_standard_temperature_image_timestamp_style", TIMESTAMP_STYLE_AUTO)
            self.last_standard_temperature_temperature_timestamp_style = state.get("last_standard_temperature_temperature_timestamp_style", TIMESTAMP_STYLE_AUTO)
            self.last_standard_temperature_use_image_timestamp_style = state.get("last_standard_temperature_use_image_timestamp_style", True)
            self.last_standard_temperature_generated_start_text = state.get("last_standard_temperature_generated_start_text", "")
            self.last_standard_temperature_frame_interval_seconds = state.get("last_standard_temperature_frame_interval_seconds", 1.0)
            self.last_standard_temperature_temperature_unit = state.get("last_standard_temperature_temperature_unit", TEMPERATURE_UNIT_CELSIUS)
            self.apply_tool_settings(state.get("tool_settings", self.default_tool_settings()))
            self.grayscale_results_headers = state["grayscale_results_headers"].copy()
            self.grayscale_results_rows = copy.deepcopy(state["grayscale_results_rows"])
            self.freeze_results_headers = state["freeze_results_headers"].copy()
            self.freeze_results_rows = copy.deepcopy(state["freeze_results_rows"])
            self.freeze_count_timeseries_headers = state.get("freeze_count_timeseries_headers", []).copy()
            self.freeze_count_timeseries_rows = copy.deepcopy(state.get("freeze_count_timeseries_rows", []))
            self.freeze_count_timeseries_summary = dict(state.get("freeze_count_timeseries_summary", {}))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()

            self.update_results_tables()
            self.update_freeze_count_timeseries_table()
            self.refresh_sample_catalog_tree(preserve_selection=False)

            image_set_changed = (
                current_image_paths != self.imagePaths or
                current_image_names != self.imageNames or
                current_source_payload != self.frame_source_session_payload()
            )

            if self.has_frames():
                self.image_slider.blockSignals(True)
                self.image_slider.setEnabled(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(self.frame_count() - 1)
                self.image_slider.setValue(self.image_index)
                self.image_slider.blockSignals(False)
                self.image_slider.sync_marker_state(
                    self.keyframe_list,
                    self.flagframe_list,
                    self.analysis_start_frame_list,
                    self.analysis_end_frame_list,
                )
                self.image_textbox.setText(str(self.image_index))

                self.select_tool_action.setEnabled(True)
                self.grid_tool_action.setEnabled(True)
                self.pan_tool_action.setEnabled(True)
                self.deselect_tool_action.setEnabled(True)
                self.edit_tool_action.setEnabled(True)

                if image_set_changed:
                    self.populate_image_list()
                else:
                    self.update_image_list_annotations()
                    self.sync_image_list_selection()
                self.updateImage(self.image_index)
                self.finalize_frame_update(self.image_index)
            else:
                self.populate_image_list()
                self.image_slider.blockSignals(True)
                self.image_slider.setMinimum(0)
                self.image_slider.setMaximum(0)
                self.image_slider.setValue(0)
                self.image_slider.blockSignals(False)
                self.image_slider.setEnabled(False)
                self.image_slider.clear_marker_state()
                self.image_textbox.clear()
                self.image_name_label.clear()
                self.reset_transient_interaction_state()
                self.scene.clear()
                if hasattr(self, 'pixmap_item'):
                    del(self.pixmap_item)
                self.rendered_cell_items = []
                self.redraw_no_image_cell_template_view(fit_view=True)
                self.sync_image_list_selection()

                self.select_tool_action.setEnabled(False)
                self.grid_tool_action.setEnabled(False)
                self.pan_tool_action.setEnabled(False)
                self.deselect_tool_action.setEnabled(False)
                self.edit_tool_action.setEnabled(False)

            self.update_session_actions_state()
            self.updateButtonStates()
            self.image_slider.set_custom_ticks()
            self.zoom_slider_set_maximum()
            self.update_toggle_keyframe_button_icon()
            self.update_toggle_flagging_button_icon()
            self.update_toggle_analysis_start_button_icon()
            self.update_toggle_analysis_end_button_icon()
            if self.freeze_count_timeseries_headers:
                if hasattr(self, "results_table_tabs"):
                    self.results_table_tabs.setCurrentIndex(2)
                self.show_dock_widget(self.results_tables_dock)

            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_cell_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            if not self.has_frames():
                self.cell_items = copy.deepcopy(state.get("cell_items", []))
                self.rendered_cell_items = []
                self.next_cell_id = int(state.get("next_cell_id", 0))
                self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", {}))
                self.sample_metadata_schema = sample_metadata_schema_from_payload(
                    state.get("sample_metadata_schema", self.serialize_sample_metadata_schema())
                )
                self.sample_catalog = self.deserialize_sample_catalog(
                    state.get("sample_catalog", self.serialize_sample_catalog())
                )
                try:
                    self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
                except (TypeError, ValueError):
                    self.next_sample_id = int(getattr(self, "next_sample_id", 0))
                self.keyframe_list = []
                self.flagframe_list = []
                self.analysis_start_frame_list = []
                self.analysis_end_frame_list = []
                self.keyframe_cell_items_dict = {}
                self.scene.clear()
                if hasattr(self, 'pixmap_item'):
                    del(self.pixmap_item)
                self.recompute_next_cell_id(preserve_if_larger=True)
                self.ensure_sample_catalog_matches_cell_records()
                self.redraw_no_image_cell_template_view(fit_view=True)
                self.refresh_sample_catalog_tree(preserve_selection=False)
                self.restore_tool_mode_ui(restore_tool_mode)
                return

            frame_count = self.frame_count()
            restored_keyframes = sorted(
                frame
                for frame in state.get("keyframe_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            restored_flagframes = sorted(
                frame
                for frame in state.get("flagframe_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            restored_analysis_starts = sorted(
                frame
                for frame in state.get("analysis_start_frame_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            restored_analysis_ends = sorted(
                frame
                for frame in state.get("analysis_end_frame_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            restored_keyframe_dict = {
                frame: copy.deepcopy(items)
                for frame, items in state.get("keyframe_cell_items_dict", {}).items()
                if isinstance(frame, int) and 0 <= frame < frame_count
            }

            self.cell_items = copy.deepcopy(state.get("cell_items", []))
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", {}))
            self.sample_metadata_schema = sample_metadata_schema_from_payload(
                state.get("sample_metadata_schema", self.serialize_sample_metadata_schema())
            )
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.keyframe_list = restored_keyframes
            self.flagframe_list = restored_flagframes
            self.analysis_start_frame_list = restored_analysis_starts
            self.analysis_end_frame_list = restored_analysis_ends
            self.keyframe_cell_items_dict = restored_keyframe_dict
            has_analysis_payload = any(
                key in state
                for key in (
                    "last_grayscale_output_path",
                    "last_freeze_output_path",
                    "grayscale_results_headers",
                    "grayscale_results_rows",
                    "freeze_results_headers",
                    "freeze_results_rows",
                )
            )
            has_freeze_count_timeseries_payload = any(
                key in state
                for key in (
                    "last_temperature_import_path",
                    "last_temperature_calibration_path",
                    "last_temperature_reset_temperature",
                    "last_temperature_blank_sample_names",
                    "last_standard_temperature_image_timestamp_source",
                    "last_standard_temperature_image_timestamp_style",
                    "last_standard_temperature_temperature_timestamp_style",
                    "last_standard_temperature_use_image_timestamp_style",
                    "last_standard_temperature_generated_start_text",
                    "last_standard_temperature_frame_interval_seconds",
                    "last_standard_temperature_temperature_unit",
                    "freeze_count_timeseries_headers",
                    "freeze_count_timeseries_rows",
                    "freeze_count_timeseries_summary",
                )
            )
            if has_analysis_payload:
                self.last_grayscale_output_path = state.get("last_grayscale_output_path", self.last_grayscale_output_path)
                self.last_freeze_output_path = state.get("last_freeze_output_path", self.last_freeze_output_path)
                self.grayscale_results_headers = state.get("grayscale_results_headers", self.grayscale_results_headers).copy()
                self.grayscale_results_rows = copy.deepcopy(state.get("grayscale_results_rows", self.grayscale_results_rows))
                self.freeze_results_headers = state.get("freeze_results_headers", self.freeze_results_headers).copy()
                self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", self.freeze_results_rows))
            if has_freeze_count_timeseries_payload:
                self.last_temperature_import_path = state.get("last_temperature_import_path")
                self.last_temperature_calibration_path = state.get("last_temperature_calibration_path")
                self.last_temperature_reset_temperature = state.get("last_temperature_reset_temperature")
                self.last_temperature_blank_sample_names = list(state.get("last_temperature_blank_sample_names", []))
                self.last_standard_temperature_image_timestamp_source = state.get("last_standard_temperature_image_timestamp_source", IMAGE_TIMESTAMP_SOURCE_FILENAME)
                self.last_standard_temperature_image_timestamp_style = state.get("last_standard_temperature_image_timestamp_style", TIMESTAMP_STYLE_AUTO)
                self.last_standard_temperature_temperature_timestamp_style = state.get("last_standard_temperature_temperature_timestamp_style", TIMESTAMP_STYLE_AUTO)
                self.last_standard_temperature_use_image_timestamp_style = state.get("last_standard_temperature_use_image_timestamp_style", True)
                self.last_standard_temperature_generated_start_text = state.get("last_standard_temperature_generated_start_text", "")
                self.last_standard_temperature_frame_interval_seconds = state.get("last_standard_temperature_frame_interval_seconds", 1.0)
                self.last_standard_temperature_temperature_unit = state.get("last_standard_temperature_temperature_unit", TEMPERATURE_UNIT_CELSIUS)
                self.freeze_count_timeseries_headers = state.get("freeze_count_timeseries_headers", []).copy()
                self.freeze_count_timeseries_rows = copy.deepcopy(state.get("freeze_count_timeseries_rows", []))
                self.freeze_count_timeseries_summary = dict(state.get("freeze_count_timeseries_summary", {}))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()
            if has_analysis_payload:
                self.update_results_tables()
            if has_freeze_count_timeseries_payload:
                self.update_freeze_count_timeseries_table()

            target_index = state.get("image_index", self.image_index)
            if not isinstance(target_index, int):
                target_index = self.image_index
            target_index = max(0, min(target_index, frame_count - 1))

            self.ensure_slider_window_contains_index(target_index)
            self.image_slider.blockSignals(True)
            self.image_slider.setValue(target_index)
            self.image_slider.blockSignals(False)
            self.image_slider.sync_marker_state(
                self.keyframe_list,
                self.flagframe_list,
                self.analysis_start_frame_list,
                self.analysis_end_frame_list,
            )
            self.update_image_list_annotations()

            if target_index != self.image_index:
                self.updateImage(target_index, preview=False)
                self.finalize_frame_update(target_index)
            else:
                self.cell_controller.redraw_current_cells(preserve_selection=False)
                self.finalize_frame_update(target_index)

            if not has_analysis_payload:
                self.refresh_grayscale_plot()
            self.refresh_sample_catalog_tree(preserve_selection=False)
            self.update_session_actions_state()
            self.updateButtonStates()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_timeline_marker_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            frame_count = self.frame_count()
            if frame_count <= 0:
                self.keyframe_list = []
                self.flagframe_list = []
                self.analysis_start_frame_list = []
                self.analysis_end_frame_list = []
                self.keyframe_cell_items_dict = {}
                self.image_slider.clear_marker_state()
                self.update_toggle_keyframe_button_icon()
                self.update_toggle_flagging_button_icon()
                self.update_toggle_analysis_start_button_icon()
                self.update_toggle_analysis_end_button_icon()
                self.update_image_list_annotations()
                self.restore_tool_mode_ui(restore_tool_mode)
                return

            self.keyframe_list = sorted(
                frame for frame in state.get("keyframe_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            self.flagframe_list = sorted(
                frame for frame in state.get("flagframe_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            self.analysis_start_frame_list = sorted(
                frame for frame in state.get("analysis_start_frame_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            self.analysis_end_frame_list = sorted(
                frame for frame in state.get("analysis_end_frame_list", [])
                if isinstance(frame, int) and 0 <= frame < frame_count
            )
            self.keyframe_cell_items_dict = {
                frame: copy.deepcopy(items)
                for frame, items in state.get("keyframe_cell_items_dict", {}).items()
                if isinstance(frame, int) and 0 <= frame < frame_count
            }

            target_index = state.get("image_index", self.image_index)
            if not isinstance(target_index, int):
                target_index = self.image_index
            target_index = max(0, min(target_index, frame_count - 1))

            self.ensure_slider_window_contains_index(target_index)
            self.image_slider.blockSignals(True)
            self.image_slider.setValue(target_index)
            self.image_slider.blockSignals(False)
            self.image_slider.sync_marker_state(
                self.keyframe_list,
                self.flagframe_list,
                self.analysis_start_frame_list,
                self.analysis_end_frame_list,
            )
            self.update_image_list_annotations()

            if target_index != self.image_index:
                self.updateImage(target_index, preview=False)
                self.finalize_frame_update(target_index)
            else:
                self.interpolate_and_displayMarkedRegions(target_index, preview=False)
                self.finalize_frame_update(target_index)

            self.update_toggle_keyframe_button_icon()
            self.update_toggle_flagging_button_icon()
            self.update_toggle_analysis_start_button_icon()
            self.update_toggle_analysis_end_button_icon()
            self.update_session_actions_state()
            self.updateButtonStates()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_analysis_marker_state(self, marker_kind, frame_index, is_marked, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.set_analysis_window_marker(marker_kind, frame_index, is_marked)
            if not preserve_active_tool:
                restore_tool_mode = getattr(self, "tool_mode", "cursor")
                self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_data_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            self.apply_image_edit_state(state.get("image_edit_state", self.serialize_image_edit_state()), invalidate_results=False, refresh_display=False, sync_controls=False)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            self.last_grayscale_output_path = state.get("last_grayscale_output_path")
            self.last_freeze_output_path = state.get("last_freeze_output_path")
            self.last_temperature_import_path = state.get("last_temperature_import_path")
            self.last_temperature_calibration_path = state.get("last_temperature_calibration_path")
            self.last_temperature_reset_temperature = state.get("last_temperature_reset_temperature")
            self.last_temperature_blank_sample_names = list(state.get("last_temperature_blank_sample_names", []))
            self.last_standard_temperature_image_timestamp_source = state.get("last_standard_temperature_image_timestamp_source", IMAGE_TIMESTAMP_SOURCE_FILENAME)
            self.last_standard_temperature_image_timestamp_style = state.get("last_standard_temperature_image_timestamp_style", TIMESTAMP_STYLE_AUTO)
            self.last_standard_temperature_temperature_timestamp_style = state.get("last_standard_temperature_temperature_timestamp_style", TIMESTAMP_STYLE_AUTO)
            self.last_standard_temperature_use_image_timestamp_style = state.get("last_standard_temperature_use_image_timestamp_style", True)
            self.last_standard_temperature_generated_start_text = state.get("last_standard_temperature_generated_start_text", "")
            self.last_standard_temperature_frame_interval_seconds = state.get("last_standard_temperature_frame_interval_seconds", 1.0)
            self.last_standard_temperature_temperature_unit = state.get("last_standard_temperature_temperature_unit", TEMPERATURE_UNIT_CELSIUS)
            self.grayscale_results_headers = state.get("grayscale_results_headers", []).copy()
            self.grayscale_results_rows = copy.deepcopy(state.get("grayscale_results_rows", []))
            self.freeze_results_headers = state.get("freeze_results_headers", []).copy()
            self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", []))
            self.freeze_count_timeseries_headers = state.get("freeze_count_timeseries_headers", []).copy()
            self.freeze_count_timeseries_rows = copy.deepcopy(state.get("freeze_count_timeseries_rows", []))
            self.freeze_count_timeseries_summary = dict(state.get("freeze_count_timeseries_summary", {}))
            self.next_cell_id = int(state.get("next_cell_id", getattr(self, "next_cell_id", 0)))
            self.cell_records_by_id = self.deserialize_cell_records(state.get("cell_records_by_id", self.serialize_cell_records()))
            self.sample_metadata_schema = sample_metadata_schema_from_payload(
                state.get("sample_metadata_schema", self.serialize_sample_metadata_schema())
            )
            self.sample_catalog = self.deserialize_sample_catalog(
                state.get("sample_catalog", self.serialize_sample_catalog())
            )
            try:
                self.next_sample_id = int(state.get("next_sample_id", getattr(self, "next_sample_id", 0)))
            except (TypeError, ValueError):
                self.next_sample_id = int(getattr(self, "next_sample_id", 0))
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()
            self.update_results_tables()
            self.update_freeze_count_timeseries_table()
            self.refresh_sample_catalog_tree(preserve_selection=False)
            self.update_session_actions_state()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_freeze_annotation_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            previous_cell_records_payload = self.serialize_cell_records()
            previous_flag_frames = set(getattr(self, "flagframe_list", []))
            selected_items = self.get_selected_cell_items() if hasattr(self, "cell_controller") else []
            self.last_freeze_output_path = state.get("last_freeze_output_path")
            restored_cell_records_payload = state.get("cell_records_by_id", self.serialize_cell_records())
            self.cell_records_by_id = self.deserialize_cell_records(restored_cell_records_payload)
            self.freeze_results_headers = state.get("freeze_results_headers", []).copy()
            self.freeze_results_rows = copy.deepcopy(state.get("freeze_results_rows", []))
            self.freeze_count_timeseries_headers = []
            self.freeze_count_timeseries_rows = []
            self.freeze_count_timeseries_summary = {}
            self.last_temperature_import_path = None
            self.ensure_cell_registry_matches_scene_cells()
            self.recompute_next_cell_id(preserve_if_larger=True)
            self.ensure_sample_catalog_matches_cell_records()

            changed_cell_ids = self.freeze_annotation_changed_cell_ids(
                previous_cell_records_payload,
                restored_cell_records_payload,
            )
            if changed_cell_ids:
                self.replace_freeze_table_rows_for_cells(changed_cell_ids)
            elif hasattr(self, "freeze_table"):
                self.set_table_data(self.freeze_table, self.freeze_results_headers, self.freeze_results_rows)
            self.clear_freeze_count_timeseries_table_widget()
            self.update_results_table_visibility()

            desired_flag_frames = set(self.selected_cell_freeze_frames(selected_items=selected_items))
            for frame_index in sorted(previous_flag_frames | desired_flag_frames):
                self.set_freeze_flag_marker_fast(frame_index, frame_index in desired_flag_frames)
            self.refresh_cursor_selection_info(selected_items=selected_items)
            self.update_cursor_record_edit_state(selected_items=selected_items)
            self.update_session_actions_state()
            if not preserve_active_tool:
                self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_image_edit_history_state(self, state, preserve_active_tool=False):
        self.history_restoring = True
        try:
            self.reset_pending_image_edit_preview_state(stop_timer=True)
            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else state.get("tool_mode", getattr(self, "tool_mode", "cursor"))
            self.apply_image_edit_state(
                state.get("image_edit_state", self.serialize_image_edit_state()),
                invalidate_results=False,
                refresh_display=True,
                sync_controls=True,
            )
            self.update_session_actions_state()
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def restore_navigation_index(self, index, preserve_active_tool=False):
        self.history_restoring = True
        try:
            if not self.has_frames():
                return

            restore_tool_mode = self.get_active_tool_for_restore() if preserve_active_tool else getattr(self, "tool_mode", "cursor")
            self.pending_navigation_before_index = None
            self.pending_navigation_history_text = "Change Frame"
            self.slider_drag_start_index = None
            self.pending_preview_image_index = None
            self.preview_frame_update_in_progress = False

            target_index = max(0, min(int(index), self.frame_count() - 1))
            if target_index == self.image_index:
                self.finalize_frame_update(target_index)
            else:
                self.updateImage(target_index, preview=False)
                self.finalize_frame_update(target_index)
            self.restore_tool_mode_ui(restore_tool_mode)
        finally:
            self.history_restoring = False
            self.set_undo_status()
            self.set_redo_status()

    def push_snapshot_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_session_state()
        self.undo_stack.push(SessionSnapshotCommand(self, text, before_state, after_state))

    def push_cell_history(self, text, before_state, include_analysis=False):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_cell_state(include_analysis=include_analysis)
        self.undo_stack.push(SessionCellCommand(self, text, before_state, after_state))

    def push_timeline_marker_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_timeline_marker_state()
        self.undo_stack.push(SessionTimelineMarkersCommand(self, text, before_state, after_state))

    def push_analysis_marker_history(self, text, marker_kind, frame_index, before_active, after_active):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return
        if bool(before_active) == bool(after_active):
            return

        self.undo_stack.push(
            SessionAnalysisMarkerCommand(
                self,
                text,
                marker_kind,
                frame_index,
                before_active,
                after_active,
            )
        )

    def push_image_session_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_image_session_state()
        self.undo_stack.push(SessionImageListCommand(self, text, before_state, after_state))

    def push_loaded_images_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_loaded_images_state()
        self.undo_stack.push(SessionLoadedImagesCommand(self, text, before_state, after_state))

    def push_data_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_data_state()
        self.undo_stack.push(SessionDataCommand(self, text, before_state, after_state))

    def push_freeze_annotation_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_freeze_annotation_state()
        self.undo_stack.push(SessionFreezeAnnotationCommand(self, text, before_state, after_state))

    def push_image_edit_history(self, text, before_state):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return

        after_state = self.capture_image_edit_history_state()
        self.undo_stack.push(SessionImageEditCommand(self, text, before_state, after_state))

    def push_navigation_history(self, text, before_index, after_index):
        if not self.undo_redo_enabled:
            return
        if self.history_restoring:
            return
        if before_index == after_index:
            return

        history_label = f"{text} ({before_index} -> {after_index})"
        self.undo_stack.push(FrameNavigationCommand(self, history_label, before_index, after_index))

    def format_frame_list_entry(self, index):
        markers = []
        if index in self.keyframe_list:
            markers.append("K")
        if index in self.flagframe_list:
            markers.append("F")
        if index in self.analysis_start_frame_list:
            markers.append("S")
        if index in self.analysis_end_frame_list:
            markers.append("E")

        marker_text = f"[{' '.join(markers)}] " if markers else ""
        if self.is_video_source():
            return f"{marker_text}{self.frame_name(index)}"
        entry_id = self.image_list_entry_ids[index] if index < len(self.image_list_entry_ids) else index
        return f"{entry_id:06d} {marker_text}{self.frame_name(index)}"

    def format_image_list_entry(self, index):
        return self.format_frame_list_entry(index)

    def frame_list_row_count(self):
        if getattr(self, "frame_list_frozen_only", False):
            return len(getattr(self, "frame_list_visible_indices", []))
        return self.frame_count()

    def frame_list_source_index_for_row(self, row):
        try:
            row = int(row)
        except (TypeError, ValueError):
            return None
        if getattr(self, "frame_list_frozen_only", False):
            visible_indices = getattr(self, "frame_list_visible_indices", [])
            if 0 <= row < len(visible_indices):
                return int(visible_indices[row])
            return None
        if 0 <= row < self.frame_count():
            return row
        return None

    def frame_list_row_for_source_index(self, source_index):
        try:
            source_index = int(source_index)
        except (TypeError, ValueError):
            return None
        if getattr(self, "frame_list_frozen_only", False):
            visible_indices = getattr(self, "frame_list_visible_indices", [])
            try:
                return visible_indices.index(source_index)
            except ValueError:
                return None
        if 0 <= source_index < self.frame_count():
            return source_index
        return None

    def refresh_frame_list_filter(self, *, preserve_selection=True):
        if getattr(self, "frame_list_frozen_only", False):
            self.frame_list_visible_indices = self.selected_cell_freeze_frames()
        else:
            self.frame_list_visible_indices = []
        if hasattr(self, "image_list_model"):
            self.image_list_model.set_items([], [])
        if preserve_selection:
            self.sync_image_list_selection()

    def set_frame_list_frozen_only(self, checked):
        checked = bool(checked)
        if getattr(self, "frame_list_frozen_only", False) == checked:
            return
        self.frame_list_frozen_only = checked
        self.refresh_frame_list_filter()

    def populate_image_list(self):
        if not self.image_list_enabled:
            self.image_list_model.set_items([], [])
            return
        self.refresh_frame_list_filter(preserve_selection=False)
        self.sync_image_list_selection()

    def update_image_list_annotations(self, rows=None):
        if not self.image_list_enabled:
            return
        if getattr(self, "frame_list_frozen_only", False):
            self.refresh_frame_list_filter()
            return
        if rows is None:
            rows = range(self.frame_count())

        row_data = {}
        for source_row in rows:
            model_row = self.frame_list_row_for_source_index(source_row)
            if model_row is None:
                continue
            row_data[model_row] = (
                self.format_frame_list_entry(source_row),
                self.frame_tooltip(source_row),
            )

        self.image_list_model.update_items(row_data)

    def sync_image_list_selection(self):
        if not self.image_list_enabled:
            return
        selection_model = self.image_list_widget.selectionModel()
        if selection_model is None:
            return

        if not self.has_frames() or not (0 <= self.image_index < self.frame_count()):
            self.syncing_image_list_selection = True
            try:
                selection_model.clearSelection()
                self.image_list_widget.setCurrentIndex(QModelIndex())
            finally:
                self.syncing_image_list_selection = False
            return

        model_row = self.frame_list_row_for_source_index(self.image_index)
        if model_row is None:
            self.syncing_image_list_selection = True
            try:
                selection_model.clearSelection()
                self.image_list_widget.setCurrentIndex(QModelIndex())
            finally:
                self.syncing_image_list_selection = False
            return

        model_index = self.image_list_model.index(model_row, 0)
        if not model_index.isValid():
            return

        self.syncing_image_list_selection = True
        try:
            selected_rows = [
                selected_index.row()
                for selected_index in selection_model.selectedRows(0)
                if selected_index.isValid()
            ]
            if len(selected_rows) <= 1:
                selection_model.setCurrentIndex(
                    model_index,
                    QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
                )
            else:
                selection_model.setCurrentIndex(model_index, QItemSelectionModel.NoUpdate)
            self.image_list_widget.setCurrentIndex(model_index)
        finally:
            self.syncing_image_list_selection = False

        if not self.image_slider.isSliderDown():
            visible_rect = self.image_list_widget.visualRect(model_index)
            if not visible_rect.isValid() or not self.image_list_widget.viewport().rect().contains(visible_rect.center()):
                self.image_list_widget.scrollTo(model_index, QListView.EnsureVisible)

    def handle_image_list_selection(self, index):
        if not self.image_list_enabled:
            return
        if self.syncing_image_list_selection:
            return

        modifiers = QGuiApplication.keyboardModifiers()
        if modifiers & (Qt.ControlModifier | Qt.ShiftModifier | Qt.MetaModifier):
            return

        row = self.frame_list_source_index_for_row(index.row())
        if row is not None and 0 <= row < self.frame_count() and row != self.image_index:
            self.navigate_to_image(row)

    def handle_image_list_current_changed(self, current, previous):
        if not self.image_list_enabled:
            return
        if self.syncing_image_list_selection or not current.isValid():
            return
        self.handle_image_list_selection(current)

    def update_session_actions_state(self):
        session_active = bool(getattr(self, "session_active", False))
        has_frames = session_active and self.has_frames()
        has_image_files = has_frames and self.supports_image_file_operations()
        has_sortable_video_clips = has_frames and self.supports_video_clip_sorting()
        has_results = session_active and bool(
            self.grayscale_results_headers
            or self.freeze_results_headers
            or self.freeze_count_timeseries_headers
        )
        interactive = session_active and (not self.output_state)
        video_source_loaded = has_frames and self.is_video_source()
        can_add_image_source = interactive and not video_source_loaded
        can_open_video_source = interactive and not has_frames

        self.add_source_action.setEnabled(can_add_image_source)
        self.add_images_action.setEnabled(can_add_image_source)
        self.add_folder_action.setEnabled(can_add_image_source)
        self.open_video_action.setEnabled(can_open_video_source)
        self.remove_selected_action.setEnabled(self.image_list_enabled and has_image_files and not self.output_state)
        self.clear_images_action.setEnabled(has_frames and not self.output_state)
        self.sort_images_action.setEnabled((has_image_files or has_sortable_video_clips) and not self.output_state)
        self.sort_images_action.setText("Sort Video Clips" if has_sortable_video_clips else "Sort Images")
        self.relink_images_action.setEnabled(has_image_files and not self.output_state)
        self.sample_manager_action.setEnabled(interactive)
        self.new_session_action.setEnabled(not self.output_state)
        self.open_session_action.setEnabled(not self.output_state)
        self.save_session_action.setEnabled(session_active and not self.output_state)
        self.save_session_as_action.setEnabled(session_active and not self.output_state)
        self.edit_session_metadata_action.setEnabled(session_active and not self.output_state)
        self.run_analysis_action.setEnabled(has_frames and not self.output_state)
        self.output_results_action.setEnabled(has_results and not self.output_state)
        self.import_csu_is_dat_action.setEnabled(has_frames and not self.output_state)
        self.import_tamu_linkam_xlsx_action.setEnabled(has_frames and not self.output_state)
        self.import_pku_linksys32_iml_action.setEnabled(has_frames and not self.output_state)
        self.import_utk_csv_action.setEnabled(has_frames and not self.output_state)
        self.import_temperature_csv_action.setEnabled(has_frames and not self.output_state)
        self.viewer_single_action.setEnabled(interactive)
        self.viewer_double_action.setEnabled(interactive)
        self.viewer_triple_action.setEnabled(interactive)
        self.viewer_orientation_toggle_action.setEnabled(interactive and self.viewer_image_count in (2, 3))
        self.image_edit_action.setEnabled(has_frames and not self.output_state)

        if session_active:
            self.set_undo_status()
            self.set_redo_status()
        else:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)

        self.update_document_interface_state()

    def update_document_interface_state(self):
        session_active = bool(getattr(self, "session_active", False))
        has_frames = session_active and self.has_frames()
        interactive_images = has_frames and (not self.output_state)

        viewer_widget = getattr(self, "view_slider_widget", None)
        if viewer_widget is not None and shiboken6.isValid(viewer_widget):
            viewer_widget.setEnabled(session_active)

        for dock_name in (
            "image_list_dock",
            "tool_options_dock",
            "sample_catalog_dock",
            "cells_dock",
            "console_dock",
            "grayscale_plot_dock",
            "results_tables_dock",
        ):
            dock = getattr(self, dock_name, None)
            if dock is None or (not shiboken6.isValid(dock)):
                continue
            if (dock_name == "image_list_dock") and (not self.image_list_enabled):
                dock.setEnabled(False)
                toggle_action = dock.toggleViewAction()
                if toggle_action is not None:
                    toggle_action.setEnabled(False)
                continue
            dock.setEnabled(session_active)
            toggle_action = dock.toggleViewAction()
            if toggle_action is not None:
                toggle_action.setEnabled(session_active)

        for widget_name in (
            "radius_status_label",
            "zoom_status_label",
            "frame_status_label",
            "radius_textbox",
            "zoom_textbox",
            "image_textbox",
            "image_name_label",
            "tool_status_label",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setEnabled(interactive_images)

    def set_active_image_panel(self, panel_name):
        self.active_image_panel = panel_name

    def get_selected_image_rows(self):
        selection_model = self.image_list_widget.selectionModel()
        if selection_model is None:
            return []
        source_rows = set()
        for model_index in selection_model.selectedRows(0):
            if not model_index.isValid():
                continue
            source_row = self.frame_list_source_index_for_row(model_index.row())
            if source_row is not None:
                source_rows.add(source_row)
        return sorted(source_rows)

    def navigate_to_image(self, index, history_text="Change Frame"):
        if not self.has_frames():
            return

        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        index = max(0, min(index, self.frame_count() - 1))
        committed_index = max(
            0,
            min(int(getattr(self, "last_committed_image_index", self.image_index)), self.frame_count() - 1),
        )
        if index == committed_index and not self.image_slider.isSliderDown():
            return

        if (
            not self.history_restoring
            and self.cell_controller.uses_grid_preview()
            and not (
                self.cell_controller.is_any_edit_mode()
                or self.temporary_event_data.get("previous_edit_mode") in ["edit-choose", "edit-new", "edit-group"]
            )
        ):
            self.cancel_unfinished_tool_workflow()

        if not self.history_restoring and self.pending_navigation_before_index is None:
            self.pending_navigation_before_index = committed_index
            self.pending_navigation_history_text = history_text

        self.ensure_slider_window_contains_index(index)
        self.image_slider.setValue(index)

    def commit_slider_release_navigation(self):
        if self.history_restoring or not self.has_frames():
            return
        before_index = max(
            0,
            min(int(getattr(self, "last_committed_image_index", self.image_index)), self.frame_count() - 1),
        )
        self.finalize_frame_update(self.image_index)
        if self.analysis_progress_navigation_suppressed:
            return
        if before_index != self.image_index:
            self.log(f"Change Frame: {before_index} -> {self.image_index}")
            self.push_navigation_history("Change Frame", before_index, self.image_index)

    def load_grayscale_results(self, file_path):
        try:
            with open(file_path, newline='') as csv_file:
                rows = list(csv.reader(csv_file))
        except OSError as err:
            self.log(f"Unable to load grayscale results table: {err}")
            return

        if len(rows) < 2:
            self.grayscale_results_headers = []
            self.grayscale_results_rows = []
        else:
            self.grayscale_results_headers = rows[1]
            self.grayscale_results_rows = rows[2:]

        self.update_results_tables()

    def set_freeze_results(self, headers, rows):
        self.freeze_results_headers = headers
        self.freeze_results_rows = rows
        self.update_results_tables()
        if self.freeze_results_headers:
            if hasattr(self, "results_table_tabs"):
                self.results_table_tabs.setCurrentIndex(1)
            self.show_dock_widget(self.results_tables_dock)
        self.invalidate_freeze_count_timeseries_results("freeze results changed")

    def import_standard_temperature_csv(self, checked=False):
        if not self.has_frames():
            QMessageBox.information(
                self,
                "Standard temperature CSV import",
                "Load images or a video before importing a temperature CSV.",
            )
            return

        available_sample_names = self.available_sample_choices()
        video_mode = self.is_video_source()

        dialog = StandardTemperatureImportDialog(
            self,
            self.last_temperature_import_path,
            available_sample_names,
            getattr(self, "last_temperature_reset_temperature", None),
            getattr(self, "last_temperature_blank_sample_names", []),
            (
                IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS
                if video_mode
                else getattr(self, "last_standard_temperature_image_timestamp_source", IMAGE_TIMESTAMP_SOURCE_FILENAME)
            ),
            getattr(self, "last_standard_temperature_image_timestamp_style", TIMESTAMP_STYLE_AUTO),
            getattr(self, "last_standard_temperature_temperature_timestamp_style", TIMESTAMP_STYLE_AUTO),
            False if video_mode else getattr(self, "last_standard_temperature_use_image_timestamp_style", True),
            getattr(self, "last_standard_temperature_generated_start_text", ""),
            getattr(self, "last_standard_temperature_frame_interval_seconds", 1.0),
            getattr(self, "last_standard_temperature_temperature_unit", TEMPERATURE_UNIT_CELSIUS),
            video_mode,
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        dialog_values = dialog.get_values()
        file_path = dialog_values["file_path"]
        reset_temperature = dialog_values["reset_temperature"]
        blank_sample_names = dialog_values["blank_sample_names"]
        image_timestamp_source = dialog_values["image_timestamp_source"]
        image_timestamp_style = dialog_values["image_timestamp_style"]
        temperature_timestamp_style = dialog_values["temperature_timestamp_style"]
        use_image_timestamp_style = dialog_values["use_image_timestamp_style"]
        generated_start_text = dialog_values["generated_start_text"]
        frame_interval_seconds = dialog_values["frame_interval_seconds"]
        temperature_unit = dialog_values["temperature_unit"]

        try:
            parsed_timeseries = parse_standard_temperature_csv(
                file_path,
                timestamp_style=temperature_timestamp_style,
                temperature_unit=temperature_unit,
            )
            headers, rows, summary = self.build_standard_freeze_count_timeseries_results(
                parsed_timeseries,
                blank_sample_names=blank_sample_names,
                image_timestamp_source=image_timestamp_source,
                image_timestamp_style=image_timestamp_style,
                generated_start_text=generated_start_text,
                frame_interval_seconds=frame_interval_seconds,
                temperature_timestamp_style=temperature_timestamp_style,
                temperature_unit=temperature_unit,
                reset_temperature=reset_temperature,
            )
        except (OSError, TemperatureImportError) as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "Standard temperature CSV import failed",
                "The standard temperature CSV import failed.",
                err,
                detail_text,
            )
            self.log(f"Standard temperature CSV import failed: {err}")
            return
        except Exception as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "Standard temperature CSV import failed",
                "The standard temperature CSV import failed due to an unexpected internal error.",
                err,
                detail_text,
            )
            self.log("Standard temperature CSV import failed with an unexpected internal error.")
            self.log(detail_text.rstrip())
            return

        self.last_temperature_import_path = str(file_path)
        self.last_temperature_reset_temperature = self.normalize_temperature_reset_threshold(
            reset_temperature
        )
        self.last_temperature_calibration_path = ""
        self.last_temperature_blank_sample_names = list(blank_sample_names)
        self.last_standard_temperature_image_timestamp_source = str(image_timestamp_source)
        self.last_standard_temperature_image_timestamp_style = str(image_timestamp_style)
        self.last_standard_temperature_temperature_timestamp_style = str(temperature_timestamp_style)
        self.last_standard_temperature_use_image_timestamp_style = bool(use_image_timestamp_style)
        self.last_standard_temperature_generated_start_text = str(generated_start_text)
        self.last_standard_temperature_frame_interval_seconds = float(frame_interval_seconds)
        self.last_standard_temperature_temperature_unit = str(temperature_unit)
        self.set_freeze_count_timeseries_results(headers, rows, summary)

        matched_samples = summary.get("matched_samples", [])
        matched_blank_samples = summary.get("matched_blank_samples", [])
        unmatched_blank = summary.get("unmatched_blank_samples", [])
        parsed_image_count = int(summary.get("parsed_image_count", 0))
        total_images = int(summary.get("total_images", 0))
        frame_label = "Frames" if video_mode else "Images"
        timestamp_label = "Frame timestamp" if video_mode else "Image timestamp"
        in_range_image_count = int(summary.get("in_range_image_count", 0))
        out_of_range_image_count = int(summary.get("out_of_range_image_count", 0))
        unparsed_image_count = int(summary.get("unparsed_image_count", 0))
        cycle_count = int(summary.get("cycle_count", 1))
        reset_temperature = summary.get("reset_temperature")
        grouping_mode = str(summary.get("grouping_mode", "samples"))
        grouping_label = (
            "Current sample setup"
            if grouping_mode == "samples"
            else "No sample (all cells as one sample)"
        )

        message_lines = [
            f"Grouping: {grouping_label}",
            f"{frame_label} with parsed timestamps: {parsed_image_count}/{total_images}",
            f"{frame_label} inside timeseries range: {in_range_image_count}/{total_images}",
            f"Timeseries start: {summary.get('timeseries_start_timestamp', '')}",
            f"Detected cooling cycles: {cycle_count}",
            "Frozen counts reset at each cycle. Within a cycle, a cell is counted after its first freeze event.",
        ]
        if reset_temperature is not None:
            message_lines.append(
                f"Reset threshold: {float(reset_temperature):.1f} °C"
            )
        message_lines.append(f"{timestamp_label} source: " + str(summary.get("image_timestamp_source", "")))
        message_lines.append(f"{timestamp_label} style: " + str(summary.get("image_timestamp_style", "")))
        message_lines.append("Temperature timestamp style: " + str(summary.get("temperature_timestamp_style", "")))
        message_lines.append("Temperature column unit: " + str(summary.get("temperature_unit", "")))
        if matched_samples:
            message_lines.append("Output samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            message_lines.append("Water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_blank:
            message_lines.append("Selected water blank sample(s) not matched to app samples: " + ", ".join(unmatched_blank))
        if out_of_range_image_count:
            message_lines.append(
                f"{frame_label} outside the timeseries range: {out_of_range_image_count}"
            )
        if unparsed_image_count:
            preview = ", ".join(summary.get("unparsed_images_preview", []))
            if preview:
                message_lines.append(
                    f"{frame_label} with unparseable timestamps: {unparsed_image_count} ({preview})"
                )
            else:
                message_lines.append(
                    f"{frame_label} with unparseable timestamps: {unparsed_image_count}"
                )

        self.show_detailed_information_dialog(
            "Standard temperature CSV import",
            "Standard temperature CSV import completed successfully.\n\n"
            f"Created {len(rows)} synchronized output rows from {parsed_image_count} parsed {frame_label.lower()} timestamps.",
            "\n".join(message_lines),
        )
        self.log(f"Imported standard temperature CSV: {file_path}")
        self.log(f"Standard temperature grouping mode: {grouping_label}")
        if matched_samples:
            self.log("Standard temperature output samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            self.log("Standard temperature water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_blank:
            self.log("Standard temperature unmatched selected water blank samples: " + ", ".join(unmatched_blank))

    def import_utk_temperature_csv(self, checked=False):
        if not self.has_frames():
            QMessageBox.information(
                self,
                "UTK CSV import",
                "Load images or a video before importing a UTK CSV file.",
            )
            return

        available_sample_names = self.available_sample_choices()
        video_mode = self.is_video_source()
        dialog = UTKTemperatureImportDialog(
            self,
            self.last_temperature_import_path,
            available_sample_names,
            getattr(self, "last_temperature_reset_temperature", None),
            getattr(self, "last_temperature_blank_sample_names", []),
            video_mode,
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        dialog_values = dialog.get_values()
        file_path = dialog_values["file_path"]
        blank_sample_names = dialog_values["blank_sample_names"]
        reset_temperature = dialog_values["reset_temperature"]

        try:
            parsed_timeseries = parse_utk_temperature_csv(file_path)
            if video_mode:
                source_paths = self.active_frame_source().source_paths()
                start_timestamp = parse_utk_video_start_timestamp(source_paths[0] if source_paths else "")
                if start_timestamp is None:
                    raise TemperatureImportError(
                        "UTK video import requires a video filename like 2026_0507_093532_002.MP4 so the first frame timestamp can be derived."
                    )
                image_timestamp_source = IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS
                image_timestamp_style = TIMESTAMP_STYLE_AUTO
                generated_start_text = start_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                image_timestamp_source = IMAGE_TIMESTAMP_SOURCE_FILENAME
                image_timestamp_style = TIMESTAMP_STYLE_AUTO
                generated_start_text = ""

            headers, rows, summary = self.build_standard_freeze_count_timeseries_results(
                parsed_timeseries,
                blank_sample_names=blank_sample_names,
                image_timestamp_source=image_timestamp_source,
                image_timestamp_style=image_timestamp_style,
                generated_start_text=generated_start_text,
                frame_interval_seconds=1.0,
                temperature_timestamp_style="UTK Time column",
                temperature_unit=TEMPERATURE_UNIT_CELSIUS,
                reset_temperature=reset_temperature,
            )
        except (OSError, TemperatureImportError) as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "UTK CSV import failed",
                "The UTK CSV import failed.",
                err,
                detail_text,
            )
            self.log(f"UTK CSV import failed: {err}")
            return
        except Exception as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "UTK CSV import failed",
                "The UTK CSV import failed due to an unexpected internal error.",
                err,
                detail_text,
            )
            self.log("UTK CSV import failed with an unexpected internal error.")
            self.log(detail_text.rstrip())
            return

        self.last_temperature_import_path = str(file_path)
        self.last_temperature_reset_temperature = self.normalize_temperature_reset_threshold(reset_temperature)
        self.last_temperature_calibration_path = ""
        self.last_temperature_blank_sample_names = list(blank_sample_names)
        self.set_freeze_count_timeseries_results(headers, rows, summary)

        matched_samples = summary.get("matched_samples", [])
        matched_blank_samples = summary.get("matched_blank_samples", [])
        unmatched_blank = summary.get("unmatched_blank_samples", [])
        parsed_image_count = int(summary.get("parsed_image_count", 0))
        total_images = int(summary.get("total_images", 0))
        in_range_image_count = int(summary.get("in_range_image_count", 0))
        out_of_range_image_count = int(summary.get("out_of_range_image_count", 0))
        unparsed_image_count = int(summary.get("unparsed_image_count", 0))
        cycle_count = int(summary.get("cycle_count", 1))
        reset_temperature = summary.get("reset_temperature")
        grouping_mode = str(summary.get("grouping_mode", "samples"))
        grouping_label = "Current sample setup" if grouping_mode == "samples" else "No sample (all cells as one sample)"
        frame_label = "Frames" if video_mode else "Images"

        message_lines = [
            f"Grouping: {grouping_label}",
            f"{frame_label} with parsed timestamps: {parsed_image_count}/{total_images}",
            f"{frame_label} inside timeseries range: {in_range_image_count}/{total_images}",
            f"Timeseries start: {summary.get('timeseries_start_timestamp', '')}",
            f"Detected cooling cycles: {cycle_count}",
            "Frozen counts reset at each cycle. Within a cycle, a cell is counted after its first freeze event.",
        ]
        if reset_temperature is not None:
            message_lines.append(f"Reset threshold: {float(reset_temperature):.1f} °C")
        if video_mode:
            message_lines.append("Frame timestamp source: UTK video filename start + video time")
        else:
            message_lines.append("Image timestamp source: filename")
        message_lines.append("Temperature timestamp style: UTK Time column")
        message_lines.append("Temperature column: PV(C)1")
        if matched_samples:
            message_lines.append("Output samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            message_lines.append("Water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_blank:
            message_lines.append("Selected water blank sample(s) not matched to app samples: " + ", ".join(unmatched_blank))
        if out_of_range_image_count:
            message_lines.append(f"{frame_label} outside the timeseries range: {out_of_range_image_count}")
        if unparsed_image_count:
            preview = ", ".join(summary.get("unparsed_images_preview", []))
            if preview:
                message_lines.append(f"{frame_label} with unparseable timestamps: {unparsed_image_count} ({preview})")
            else:
                message_lines.append(f"{frame_label} with unparseable timestamps: {unparsed_image_count}")

        self.show_detailed_information_dialog(
            "UTK CSV import",
            "UTK CSV import completed successfully.\n\n"
            f"Created {len(rows)} synchronized output rows from {parsed_image_count} parsed {frame_label.lower()} timestamps.",
            "\n".join(message_lines),
        )
        self.log(f"Imported UTK CSV file: {file_path}")
        self.log(f"UTK grouping mode: {grouping_label}")
        if matched_samples:
            self.log("UTK output samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            self.log("UTK water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_blank:
            self.log("UTK unmatched selected water blank samples: " + ", ".join(unmatched_blank))

    def import_csu_is_dat(self, checked=False):
        if not self.has_frames():
            QMessageBox.information(self, "CSU IS .dat import", "Load images before importing a CSU .dat file.")
            return
        if self.is_video_source():
            QMessageBox.information(self, "CSU IS .dat import", "The CSU importer requires image files and is not available for video sources.")
            return

        available_sample_names = self.available_sample_choices()
        dialog = CSUTemperatureImportDialog(
            self,
            self.last_temperature_import_path,
            available_sample_names,
            getattr(self, "last_temperature_reset_temperature", None),
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        dialog_values = dialog.get_values()
        file_path = dialog_values["file_path"]
        blank_sample_names = dialog_values["blank_sample_names"]
        reset_temperature = dialog_values["reset_temperature"]

        try:
            parsed_data = parse_csu_is_dat(file_path)
            headers, rows, summary = self.build_csu_freeze_count_timeseries_results(
                parsed_data,
                blank_sample_names=blank_sample_names,
                reset_temperature=reset_temperature,
            )
        except (OSError, TemperatureImportError) as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "CSU IS .dat import failed",
                "The CSU IS .dat import failed.",
                err,
                detail_text,
            )
            self.log(f"CSU IS .dat import failed: {err}")
            return
        except Exception as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "CSU IS .dat import failed",
                "The CSU IS .dat import failed due to an unexpected internal error.",
                err,
                detail_text,
            )
            self.log("CSU IS .dat import failed with an unexpected internal error.")
            self.log(detail_text.rstrip())
            return

        self.last_temperature_import_path = str(file_path)
        self.last_temperature_reset_temperature = self.normalize_temperature_reset_threshold(reset_temperature)
        self.last_temperature_blank_sample_names = list(blank_sample_names)
        self.set_freeze_count_timeseries_results(headers, rows, summary)

        matched_samples = summary.get("matched_samples", [])
        matched_blank_samples = summary.get("matched_blank_samples", [])
        unmatched_app = summary.get("unmatched_app_samples", [])
        unmatched_dat = summary.get("unmatched_dat_samples", [])
        unmatched_blank = summary.get("unmatched_blank_samples", [])
        matched_picture_rows = int(summary.get("matched_picture_rows", 0))
        total_picture_rows = int(summary.get("total_picture_rows", 0))
        cycle_count = int(summary.get("cycle_count", 1))
        reset_temperature = summary.get("reset_temperature")

        message_lines = [
            f"Matched samples: {len(matched_samples)}",
            f"Matched picture rows: {matched_picture_rows}/{total_picture_rows}",
            f"Detected cycles: {cycle_count}",
        ]
        if reset_temperature is not None:
            message_lines.append(f"Reset threshold: {float(reset_temperature):.1f} °C")
        if matched_samples:
            message_lines.append("Matched sample names: " + ", ".join(matched_samples))
        if matched_blank_samples:
            message_lines.append("Water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_app:
            message_lines.append("No CSU column match for app sample(s): " + ", ".join(unmatched_app))
        if unmatched_dat:
            message_lines.append("No app sample match for CSU column(s): " + ", ".join(unmatched_dat))
        if unmatched_blank:
            message_lines.append("Selected water blank sample(s) not matched to CSU columns: " + ", ".join(unmatched_blank))

        self.show_detailed_information_dialog(
            "CSU IS .dat import",
            "CSU IS .dat import completed successfully.\n\n"
            f"Matched {len(matched_samples)} sample(s) across {matched_picture_rows}/{total_picture_rows} picture rows.",
            "\n".join(message_lines),
        )
        self.log(f"Imported CSU IS .dat file: {file_path}")
        if matched_samples:
            self.log("CSU matched samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            self.log("CSU water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_app:
            self.log("CSU unmatched app samples: " + ", ".join(unmatched_app))
        if unmatched_dat:
            self.log("CSU unmatched .dat samples: " + ", ".join(unmatched_dat))
        if unmatched_blank:
            self.log("CSU unmatched selected water blank samples: " + ", ".join(unmatched_blank))

    def import_tamu_linkam_xlsx(self, checked=False):
        if not self.has_frames():
            QMessageBox.information(self, "TAMU Linkam .xlsx import", "Load images before importing a TAMU workbook.")
            return
        if self.is_video_source():
            QMessageBox.information(self, "TAMU Linkam .xlsx import", "The TAMU importer requires image files and is not available for video sources.")
            return

        available_sample_names = self.available_sample_choices()

        dialog = TAMUTemperatureImportDialog(
            self,
            self.last_temperature_import_path,
            available_sample_names,
            getattr(self, "last_temperature_calibration_path", ""),
            getattr(self, "last_temperature_reset_temperature", None),
            getattr(self, "last_temperature_blank_sample_names", []),
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        dialog_values = dialog.get_values()
        file_path = dialog_values["file_path"]
        calibration_path = dialog_values["calibration_path"]
        reset_temperature = dialog_values["reset_temperature"]
        blank_sample_names = dialog_values["blank_sample_names"]

        try:
            parsed_timeseries = parse_tamu_linkam_xlsx(file_path)
            if getattr(parsed_timeseries, "start_timestamp", None) is None:
                raise TemperatureImportError("The selected TAMU workbook does not expose a usable absolute start timestamp.")
            calibration_by_well = None
            if calibration_path:
                calibration_by_well = parse_ice_array_calibration_csv(calibration_path)
            headers, rows, summary = self.build_tamu_freeze_count_timeseries_results(
                parsed_timeseries,
                calibration_by_well=calibration_by_well,
                blank_sample_names=blank_sample_names,
                reset_temperature=reset_temperature,
            )
        except (OSError, TemperatureImportError) as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "TAMU Linkam .xlsx import failed",
                "The TAMU Linkam .xlsx import failed.",
                err,
                detail_text,
            )
            self.log(f"TAMU Linkam .xlsx import failed: {err}")
            return
        except Exception as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "TAMU Linkam .xlsx import failed",
                "The TAMU Linkam .xlsx import failed due to an unexpected internal error.",
                err,
                detail_text,
            )
            self.log("TAMU Linkam .xlsx import failed with an unexpected internal error.")
            self.log(detail_text.rstrip())
            return

        self.last_temperature_import_path = str(file_path)
        self.last_temperature_calibration_path = str(calibration_path or "")
        self.last_temperature_reset_temperature = self.normalize_temperature_reset_threshold(reset_temperature)
        self.last_temperature_blank_sample_names = list(blank_sample_names)
        self.set_freeze_count_timeseries_results(headers, rows, summary)

        matched_samples = summary.get("matched_samples", [])
        matched_blank_samples = summary.get("matched_blank_samples", [])
        unmatched_blank = summary.get("unmatched_blank_samples", [])
        parsed_image_count = int(summary.get("parsed_image_count", 0))
        total_images = int(summary.get("total_images", 0))
        in_range_image_count = int(summary.get("in_range_image_count", 0))
        out_of_range_image_count = int(summary.get("out_of_range_image_count", 0))
        unparsed_image_count = int(summary.get("unparsed_image_count", 0))
        calibrated_cell_count = int(summary.get("calibrated_cell_count", 0))
        cycle_count = int(summary.get("cycle_count", 1))
        reset_temperature = summary.get("reset_temperature")
        grouping_mode = str(summary.get("grouping_mode", "samples"))
        grouping_label = "Current sample setup" if grouping_mode == "samples" else "No sample (all cells as one sample)"

        message_lines = [
            f"Grouping: {grouping_label}",
            f"Images with parsed timestamps: {parsed_image_count}/{total_images}",
            f"Images inside timeseries range: {in_range_image_count}/{total_images}",
            f"Timeseries start: {summary.get('timeseries_start_timestamp', '')}",
            f"Detected cooling cycles: {cycle_count}",
            "Frozen counts reset at each cycle. Within a cycle, a cell is counted after its first freeze event.",
        ]
        if reset_temperature is not None:
            message_lines.append(f"Reset threshold: {float(reset_temperature):.1f} °C")
        if matched_samples:
            message_lines.append("Output samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            message_lines.append("Water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_blank:
            message_lines.append("Selected water blank sample(s) not matched to app samples: " + ", ".join(unmatched_blank))
        if calibration_path:
            message_lines.append(f"Calibration applied to {calibrated_cell_count} cell(s).")
        if out_of_range_image_count:
            message_lines.append(f"Images outside the timeseries range: {out_of_range_image_count}")
        if unparsed_image_count:
            preview = ", ".join(summary.get("unparsed_images_preview", []))
            if preview:
                message_lines.append(f"Images with unparseable timestamps: {unparsed_image_count} ({preview})")
            else:
                message_lines.append(f"Images with unparseable timestamps: {unparsed_image_count}")

        self.show_detailed_information_dialog(
            "TAMU Linkam .xlsx import",
            "TAMU Linkam .xlsx import completed successfully.\n\n"
            f"Created {len(rows)} synchronized output rows from {parsed_image_count} parsed image timestamps.",
            "\n".join(message_lines),
        )
        self.log(f"Imported TAMU Linkam workbook: {file_path}")
        self.log(f"TAMU grouping mode: {grouping_label}")
        if matched_samples:
            self.log("TAMU output samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            self.log("TAMU water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_blank:
            self.log("TAMU unmatched selected water blank samples: " + ", ".join(unmatched_blank))
        if calibration_path:
            self.log(f"TAMU calibration applied to {calibrated_cell_count} cell(s): {calibration_path}")

    def import_pku_linksys32_iml(self, checked=False):
        if not self.has_frames():
            QMessageBox.information(self, "PKU Linksys32 .iml import", "Load images before importing a PKU Linksys32 .iml file.")
            return
        if self.is_video_source():
            QMessageBox.information(self, "PKU Linksys32 .iml import", "The PKU importer requires image files and is not available for video sources.")
            return

        available_sample_names = self.available_sample_choices()

        dialog = PKUTemperatureImportDialog(
            main_window=self,
            initial_path=self.last_temperature_import_path,
            sample_names=available_sample_names,
            initial_reset_temperature=getattr(self, "last_temperature_reset_temperature", None),
            initial_blank_sample_names=getattr(self, "last_temperature_blank_sample_names", []),
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        dialog_values = dialog.get_values()
        file_path = dialog_values["file_path"]
        reset_temperature = dialog_values["reset_temperature"]
        blank_sample_names = dialog_values["blank_sample_names"]

        try:
            parsed_timeseries = parse_linksys32_iml(file_path)
            headers, rows, summary = self.build_pku_linksys32_freeze_count_timeseries_results(
                parsed_timeseries,
                blank_sample_names=blank_sample_names,
                reset_temperature=reset_temperature,
            )
        except (OSError, TemperatureImportError) as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "PKU Linksys32 .iml import failed",
                "The PKU Linksys32 .iml import failed.",
                err,
                detail_text,
            )
            self.log(f"PKU Linksys32 .iml import failed: {err}")
            return
        except Exception as err:
            detail_text = traceback.format_exc()
            self.show_detailed_error_dialog(
                "PKU Linksys32 .iml import failed",
                "The PKU Linksys32 .iml import failed due to an unexpected internal error.",
                err,
                detail_text,
            )
            self.log("PKU Linksys32 .iml import failed with an unexpected internal error.")
            self.log(detail_text.rstrip())
            return

        self.last_temperature_import_path = str(file_path)
        self.last_temperature_reset_temperature = self.normalize_temperature_reset_threshold(reset_temperature)
        self.last_temperature_blank_sample_names = list(blank_sample_names)
        self.set_freeze_count_timeseries_results(headers, rows, summary)

        matched_samples = summary.get("matched_samples", [])
        matched_blank_samples = summary.get("matched_blank_samples", [])
        unmatched_blank = summary.get("unmatched_blank_samples", [])
        parsed_image_count = int(summary.get("parsed_image_count", 0))
        total_images = int(summary.get("total_images", 0))
        tagged_temperature_count = int(summary.get("tagged_temperature_count", 0))
        unparsed_image_count = int(summary.get("unparsed_image_count", 0))
        cycle_count = int(summary.get("cycle_count", 1))
        image_record_count = int(summary.get("image_record_count", 0))
        reset_temperature = summary.get("reset_temperature")
        grouping_mode = str(summary.get("grouping_mode", "samples"))
        grouping_label = "Current sample setup" if grouping_mode == "samples" else "No sample (all cells as one sample)"

        message_lines = [
            f"Grouping: {grouping_label}",
            f"Matched .iml image records: {image_record_count}/{total_images}",
            f"Images with .iml timestamps: {parsed_image_count}/{total_images}",
            f"Images with .iml tagged temperatures: {tagged_temperature_count}/{total_images}",
            f"Timeseries start: {summary.get('timeseries_start_timestamp', '')}",
            f"Detected cooling cycles: {cycle_count}",
            "Frozen counts reset at each cycle. Within a cycle, a cell is counted after its first freeze event.",
        ]
        if reset_temperature is not None:
            message_lines.append(f"Reset threshold: {float(reset_temperature):.1f} °C")
        if matched_samples:
            message_lines.append("Output samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            message_lines.append("Water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_blank:
            message_lines.append("Selected water blank sample(s) not matched to app samples: " + ", ".join(unmatched_blank))
        if unparsed_image_count:
            preview = ", ".join(summary.get("unparsed_images_preview", []))
            if preview:
                message_lines.append(f"Images with unparseable timestamps: {unparsed_image_count} ({preview})")
            else:
                message_lines.append(f"Images with unparseable timestamps: {unparsed_image_count}")

        self.show_detailed_information_dialog(
            "PKU Linksys32 .iml import",
            "PKU Linksys32 .iml import completed successfully.\n\n"
            f"Created {len(rows)} synchronized output rows from {parsed_image_count} .iml image timestamps.",
            "\n".join(message_lines),
        )
        self.log(f"Imported PKU Linksys32 .iml file: {file_path}")
        self.log(f"PKU grouping mode: {grouping_label}")
        if matched_samples:
            self.log("PKU output samples: " + ", ".join(matched_samples))
        if matched_blank_samples:
            self.log("PKU water blank correction samples: " + ", ".join(matched_blank_samples))
        if unmatched_blank:
            self.log("PKU unmatched selected water blank samples: " + ", ".join(unmatched_blank))

    def export_grayscale_results_for_external_tool(self):
        if not self.grayscale_results_headers or not self.grayscale_results_rows:
            raise ValueError("No grayscale results available")

        image_folder = self.active_frame_source().source_path() if self.has_frames() else ""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="icescopy_grayscale_",
            delete=False,
            newline="",
        )
        with temp_file as handle:
            handle.write(image_folder)
            handle.write("\n")
            writer = csv.writer(handle)
            writer.writerow(self.grayscale_results_headers)
            writer.writerows(self.grayscale_results_rows)
        return temp_file.name

    def write_csv_table(self, file_path, headers, rows):
        with open(file_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if headers:
                writer.writerow(headers)
            writer.writerows(rows)

    def write_freeze_count_timeseries_csv(self, file_path):
        with open(file_path, "w", newline="", encoding="utf-8") as handle:
            handle.write(
                build_freeze_count_timeseries_csv_text(
                    self.freeze_count_timeseries_headers,
                    self.freeze_count_timeseries_rows,
                    session_metadata=self.serialize_session_metadata(),
                    summary=self.freeze_count_timeseries_summary,
                )
            )

    def export_results_csv(self, checked=False):
        has_grayscale = bool(self.grayscale_results_headers)
        has_freeze = bool(self.freeze_results_headers)
        has_freeze_count_timeseries = bool(self.freeze_count_timeseries_headers)
        if not (has_grayscale or has_freeze or has_freeze_count_timeseries):
            QMessageBox.information(self, "Output Results", "No results available to export.")
            return

        dialog = OutputResultsDialog(
            self,
            include_grayscale=has_grayscale,
            include_freeze=has_freeze,
            include_freeze_count_timeseries=has_freeze_count_timeseries,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        selected_exports = dialog.selected_exports()
        dialog.deleteLater()
        QApplication.processEvents()

        def choose_csv_path(title, default_name):
            file_dialog = QFileDialog(self, title)
            file_dialog.setAcceptMode(QFileDialog.AcceptSave)
            file_dialog.setFileMode(QFileDialog.AnyFile)
            file_dialog.setNameFilters(["CSV Files (*.csv)", "All Files (*)"])
            file_dialog.selectFile(default_name)
            file_dialog.setDefaultSuffix("csv")
            file_dialog.setOptions(self.file_dialog_options())
            if file_dialog.exec() != QDialog.Accepted:
                return ""
            selected_files = file_dialog.selectedFiles()
            path = selected_files[0] if selected_files else ""
            if path and not path.lower().endswith(".csv"):
                path = f"{path}.csv"
            return path

        def choose_output_directory():
            file_dialog = QFileDialog(self, "Choose Output Folder for Selected CSV Files")
            file_dialog.setFileMode(QFileDialog.Directory)
            file_dialog.setOption(QFileDialog.ShowDirsOnly, True)
            file_dialog.setOptions(self.file_dialog_options())
            if file_dialog.exec() != QDialog.Accepted:
                return ""
            selected_files = file_dialog.selectedFiles()
            return selected_files[0] if selected_files else ""

        export_targets = [
            (
                "grayscale",
                "Grayscale Measurements CSV",
                "grayscale_measurements.csv",
                self.grayscale_results_headers,
                self.grayscale_results_rows,
                "table",
            ),
            (
                "freeze",
                "Freeze Events CSV",
                "freeze_events.csv",
                self.freeze_results_headers,
                self.freeze_results_rows,
                "table",
            ),
            (
                "freeze_count_timeseries",
                "Freeze Count Timeseries CSV",
                "freeze_count_timeseries.csv",
                self.freeze_count_timeseries_headers,
                self.freeze_count_timeseries_rows,
                "freeze_count_timeseries",
            ),
        ]

        chosen_targets = [
            target for target in export_targets
            if selected_exports.get(target[0], False)
        ]
        if not chosen_targets:
            return
        includes_temperature_export = any(
            writer_kind == "freeze_count_timeseries" for *_, writer_kind in chosen_targets
        )

        try:
            exported_freeze_count_timeseries_paths = []
            if len(chosen_targets) == 1:
                _, export_title, default_name, headers, rows, writer_kind = chosen_targets[0]
                path = choose_csv_path(f"Save {export_title}", default_name)
                if not path:
                    return
                if writer_kind == "table":
                    self.write_csv_table(path, headers, rows)
                else:
                    self.write_freeze_count_timeseries_csv(path)
                    exported_freeze_count_timeseries_paths.append(path)
                self.log(f"Saved {export_title.lower()} at {path}")
                self.show_freeze_count_timeseries_export_notice(exported_freeze_count_timeseries_paths)
                return

            output_directory = choose_output_directory()
            if not output_directory:
                return

            for _, export_title, default_name, headers, rows, writer_kind in chosen_targets:
                path = os.path.join(output_directory, default_name)
                if writer_kind == "table":
                    self.write_csv_table(path, headers, rows)
                else:
                    self.write_freeze_count_timeseries_csv(path)
                    exported_freeze_count_timeseries_paths.append(path)
                self.log(f"Saved {export_title.lower()} at {path}")
            self.show_freeze_count_timeseries_export_notice(exported_freeze_count_timeseries_paths)
        except ValueError as err:
            detail_text = traceback.format_exc()
            title = "Freeze Count Timeseries CSV export failed" if includes_temperature_export else "Output Results failed"
            summary = (
                "The Freeze Count Timeseries CSV export failed."
                if includes_temperature_export
                else "The results export failed."
            )
            self.show_detailed_error_dialog(title, summary, err, detail_text)
        except OSError as err:
            detail_text = traceback.format_exc()
            title = "Freeze Count Timeseries CSV export failed" if includes_temperature_export else "Output Results failed"
            summary = (
                "The Freeze Count Timeseries CSV export failed while writing the output file."
                if includes_temperature_export
                else "The results export failed while writing the output file."
            )
            self.show_detailed_error_dialog(title, summary, err, detail_text)
        except Exception as err:
            detail_text = traceback.format_exc()
            title = "Freeze Count Timeseries CSV export failed" if includes_temperature_export else "Output Results failed"
            summary = (
                "The Freeze Count Timeseries CSV export failed due to an unexpected internal error."
                if includes_temperature_export
                else "The results export failed due to an unexpected internal error."
            )
            self.show_detailed_error_dialog(title, summary, err, detail_text)

    def update_keyframe_list(self, is_adding):
        # function is called when toggling the keyframe button, connected to the keyframe clicked signal
        # grab the current keyframes from image_slider
        self.keyframe_list = list(sorted(self.image_slider.keyframes))
        # add the current frame (the newly added keyframe)

        if is_adding: 
            # adding keyframe
            self.keyframe_cell_items_dict[self.image_index] = copy.deepcopy(self.cell_items)
        else: 
            # deleting keyframe
            self.keyframe_cell_items_dict.pop(self.image_index, None)

        self.update_image_list_annotations([self.image_index])
        self.update_toggle_keyframe_button_icon()

    
    def update_analysis_start_frame_list(self, is_adding):
        self.analysis_start_frame_list = list(sorted(self.image_slider.analysis_startframes))
        self.update_image_list_annotations([self.image_index])
        self.update_toggle_analysis_start_button_icon()

    def update_analysis_end_frame_list(self, is_adding):
        self.analysis_end_frame_list = list(sorted(self.image_slider.analysis_endframes))
        self.update_image_list_annotations([self.image_index])
        self.update_toggle_analysis_end_button_icon()

    def analysis_marker_list_attr(self, marker_kind):
        if marker_kind == "start":
            return "analysis_start_frame_list"
        if marker_kind == "end":
            return "analysis_end_frame_list"
        raise ValueError(f"Unknown analysis marker kind: {marker_kind}")

    def set_analysis_window_marker(self, marker_kind, frame_index, is_marked):
        if not self.has_frames():
            return False
        try:
            frame_index = int(frame_index)
        except (TypeError, ValueError):
            return False
        if not (0 <= frame_index < self.frame_count()):
            return False

        list_attr = self.analysis_marker_list_attr(marker_kind)
        marker_frames = set(getattr(self, list_attr, []))
        was_marked = frame_index in marker_frames
        if is_marked:
            marker_frames.add(frame_index)
        else:
            marker_frames.discard(frame_index)
        setattr(self, list_attr, sorted(marker_frames))

        if hasattr(self, "image_slider") and hasattr(self.image_slider, "set_analysis_marker"):
            self.image_slider.set_analysis_marker(marker_kind, frame_index, is_marked)
        elif hasattr(self, "image_slider"):
            self.image_slider.sync_marker_state(
                self.keyframe_list,
                self.flagframe_list,
                self.analysis_start_frame_list,
                self.analysis_end_frame_list,
            )

        self.update_image_list_annotations([frame_index])
        self.update_toggle_analysis_start_button_icon()
        self.update_toggle_analysis_end_button_icon()
        self.update_session_actions_state()
        return was_marked != bool(is_marked)

    def toggle_analysis_window_marker(self, marker_kind):
        if not self.has_frames():
            return False
        frame_index = int(self.image_index)
        list_attr = self.analysis_marker_list_attr(marker_kind)
        before_active = frame_index in set(getattr(self, list_attr, []))
        after_active = not before_active
        self.set_analysis_window_marker(marker_kind, frame_index, after_active)

        label = "start" if marker_kind == "start" else "end"
        action = "Added" if after_active else "Removed"
        self.log(f"{action} analysis {label} marker at frame {frame_index}")
        history_text = "Toggle Analysis Start" if marker_kind == "start" else "Toggle Analysis End"
        self.push_analysis_marker_history(
            history_text,
            marker_kind,
            frame_index,
            before_active,
            after_active,
        )
        return True

    
    def edit_current_keyframe_cell_item(self):
        # this function will be called if edits are made to the current cell_items
        # if the current frame is a key frame, update the cell_items of that key frame in keyframe_cell_items_dict
        # otherwise do nothing

        # the interlopation function will take care of the case when there is no keyframe at all

        if self.keyframe_list: # if any keyframe exist
            if self.image_index in self.keyframe_list:
                self.keyframe_cell_items_dict[self.image_index] = copy.deepcopy(self.cell_items)
                self.log('Edit registered for this keyframe')
            else:
                self.log('Edit unregistered for non-keyframe')


    def add_cell_item_to_keyframes(self, added_items=None):
        # Called when adding one or more cells. Cell IDs are persistent, so each
        # keyframe receives only the missing IDs rather than index-based appends.
        if not self.keyframe_list:
            return

        source_items = list(added_items or self.cell_items)
        for a_keyframe in self.keyframe_list:
            if a_keyframe == self.image_index:
                self.keyframe_cell_items_dict[a_keyframe] = copy.deepcopy(self.cell_items)
                continue

            if a_keyframe not in self.keyframe_cell_items_dict:
                self.keyframe_cell_items_dict[a_keyframe] = copy.deepcopy(self.cell_items)
                continue

            keyframe_items = self.keyframe_cell_items_dict[a_keyframe]
            existing_ids = {
                int(item.cell_id)
                for item in keyframe_items
            }
            for item in source_items:
                cell_id = int(item.cell_id)
                if cell_id in existing_ids:
                    continue
                keyframe_items.append(copy.deepcopy(item))
                existing_ids.add(cell_id)

    def delete_cell_item_to_keyframes(self, cell_id):
        self.delete_cell_items_to_keyframes([cell_id])

    def delete_cell_items_to_keyframes(self, cell_ids):
        if not cell_ids or not self.keyframe_list:
            return

        removed_number_set = {int(number) for number in cell_ids}
        for a_keyframe in self.keyframe_list:
            if a_keyframe != self.image_index:
                keyframe_items = self.keyframe_cell_items_dict.get(a_keyframe)
                if keyframe_items is None:
                    continue
                self.keyframe_cell_items_dict[a_keyframe] = [
                    item
                    for item in keyframe_items
                    if int(item.cell_id) not in removed_number_set
                ]
            else:
                self.keyframe_cell_items_dict[a_keyframe] = copy.deepcopy(self.cell_items)

    def keyframe_interpolation(self, frame_number):
        # return the cell_items list of a frame interplated

        # check if the frame_number is already a keyframe, if true then just return the cell_items of that frame
        if frame_number in self.keyframe_list:
            return self.keyframe_cell_items_dict.get(frame_number, self.cell_items)
        else:
            keyframe_array = np.array(self.keyframe_list)

            if np.any(keyframe_array<frame_number) and np.any(keyframe_array>frame_number):
                # check if the frame_number passed in is between two keyframes
                previous_kf_index = np.max(keyframe_array[keyframe_array<frame_number])
                next_kf_index     = np.min(keyframe_array[keyframe_array>frame_number])

                interped_item_lists = []
                previous_items = self.keyframe_cell_items_dict.get(previous_kf_index, [])
                next_items = self.keyframe_cell_items_dict.get(next_kf_index, [])
                previous_items_by_id = {
                    int(item.cell_id): item
                    for item in previous_items
                }
                next_items_by_id = {
                    int(item.cell_id): item
                    for item in next_items
                }
                ordered_ids = [
                    int(item.cell_id)
                    for item in previous_items
                ]
                for item in next_items:
                    cell_id = int(item.cell_id)
                    if cell_id not in previous_items_by_id:
                        ordered_ids.append(cell_id)

                # (x-x1)/(x2-x1)
                ratio = (frame_number-previous_kf_index)/(next_kf_index-previous_kf_index)

                for cell_id in ordered_ids:
                    previous_item = previous_items_by_id.get(cell_id)
                    next_item = next_items_by_id.get(cell_id)

                    if previous_item is None and next_item is None:
                        continue
                    if previous_item is None:
                        interped_item_lists.append(next_item)
                        continue
                    if next_item is None:
                        interped_item_lists.append(previous_item)
                        continue

                    # (x-x1)/(x2-x1) * (y2-y1) + y1
                    interp_circle_position_x = ratio * (next_item.circle_positions[0]       -previous_item.circle_positions[0])      + previous_item.circle_positions[0]
                    interp_circle_position_y = ratio * (next_item.circle_positions[1]       -previous_item.circle_positions[1])      + previous_item.circle_positions[1]
                    interp_circle_sizes      = ratio * (next_item.circle_sizes              -previous_item.circle_sizes)             + previous_item.circle_sizes
                    interp_pixel_position_x  = ratio * (next_item.circle_pixel_positions[0] -previous_item.circle_pixel_positions[0])+ previous_item.circle_pixel_positions[0]
                    interp_pixel_position_y  = ratio * (next_item.circle_pixel_positions[1] -previous_item.circle_pixel_positions[1])+ previous_item.circle_pixel_positions[1]

                    interp_circle_positions = (interp_circle_position_x, interp_circle_position_y)
                    interp_circle_pixel_positions = (interp_pixel_position_x, interp_pixel_position_y)

                    interp_item = CellSnapshot(
                        circle_positions=interp_circle_positions,
                        circle_sizes=interp_circle_sizes,
                        circle_pixel_positions=interp_circle_pixel_positions,
                        cell_id=cell_id,
                    )
                    interped_item_lists.append(interp_item)

                return interped_item_lists
            
            elif np.any(keyframe_array<frame_number) or np.any(keyframe_array>frame_number):
                # left is 0 or right is the right end. then use the closest kf values
                closest_kf = min(keyframe_array, key=lambda x: abs(x - frame_number))
                return self.keyframe_cell_items_dict.get(int(closest_kf), self.cell_items)
            
            else: # no kf at all, just use the cell_items
                return self.cell_items
                
    def grid_horizontal_pitch_shortcut_label(self):
        return "Option scroll" if IS_MACOS else "Caps Lock scroll"

    def grid_vertical_pitch_shortcut_label(self):
        return "Command scroll" if IS_MACOS else "Ctrl scroll"

    def grid_tilt_shortcut_label(self):
        return "Control scroll" if IS_MACOS else "Shift scroll"

    def is_caps_lock_pressed(self):
        if not IS_WINDOWS:
            return False
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x14) & 0x8000)
        except Exception:
            return False

    def is_grid_horizontal_pitch_modifier_active(self, modifiers):
        if IS_MACOS:
            return bool(modifiers & Qt.AltModifier)
        return self.is_caps_lock_pressed()

    def is_grid_tilt_modifier_active(self, modifiers):
        if IS_MACOS:
            return bool(modifiers & Qt.MetaModifier)
        return bool(modifiers & Qt.ShiftModifier)


    def showAboutDialog(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    def showPreferencesDialog(self):
        dlg = PreferencesDialog(self)
        dlg.exec()

    def zoom_slider_set_maximum(self):
        #set max zoom value so at max zoom each step is about 10 pixel
        original_range = self.frame_count()
        maximum_zoom_value = int(original_range * self.slider_maxzoom_pixel_interval / self.image_slider.width())
        if maximum_zoom_value <= 1:
            maximum_zoom_value = 2
        self.zoom_slider.setMaximum(maximum_zoom_value)

    def log(self, message):
        # Function to append messages to the terminal
        self.terminal.append(f"> {message}")

    def show_detailed_error_dialog(self, title, summary_text, err, detail_text=""):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Critical)
        dialog.setTextFormat(Qt.PlainText)
        dialog.setText("")
        dialog.setInformativeText(f"{summary_text}\n\n{err}")
        if detail_text:
            dialog.setDetailedText(str(detail_text).rstrip())
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()

    def show_detailed_information_dialog(self, title, summary_text, detail_text=""):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Information)
        dialog.setTextFormat(Qt.PlainText)
        dialog.setText("")
        dialog.setInformativeText(str(summary_text).rstrip())
        if detail_text:
            dialog.setDetailedText(str(detail_text).rstrip())
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()

    def file_dialog_options(self):
        return QFileDialog.Options()

    def set_tools_highlight(self, tool_mode):
        for key, value in self.tool_name_dict.items():
            if key == tool_mode:
                value.setChecked(True)
            else:
                if (tool_mode in ["edit-choose", "edit-new", "edit-group"]) and (key in ["edit-choose", "edit-new"]):
                    value.setChecked(True)
                else:
                    value.setChecked(False)

    def restore_after_edit_mode(self):
        """Restore controls that are temporarily disabled during single-edit."""
        self.image_slider.setEnabled(self.has_frames() and (not self.output_state))
        self.updateButtonStates()
        self.set_undo_status()
        self.set_redo_status()

    def reset_transient_interaction_state(self):
        """Hard-clear unfinished preview/edit state without changing the active tool.

        Use this before scene clears, session restores, and other structural UI
        resets so the controller does not keep pointing at deleted preview items
        or remembered edit submodes.
        """
        self.temporary_event_data.pop("previous_edit_mode", None)
        self.temporary_event_data.pop("original_tool_mode", None)
        self.temporary_event_data.pop("image_edit_uniform_exposure_area_active", None)
        self.grid_preview_origin_pixels = None
        self.grid_preview_floating = True
        self.preview_offset_x = 0.0
        self.preview_offset_y = 0.0
        if hasattr(self, "cell_controller"):
            self.cell_controller.clear_preview()
            self.cell_controller.clear_group_cells()
        self.reset_cell_items_edit_chosen()

    def cancel_edit_state(self):
        """Cancel any active or remembered edit workflow before switching tools.

        Pan is the only tool that is allowed to preserve edit state. All other
        tool transitions should clear lifted-edit markers and any group-edit
        preview state so the next tool starts cleanly.
        """
        previous_edit_mode = self.temporary_event_data.get("previous_edit_mode")
        had_edit_state = self.cell_controller.is_any_edit_mode() or previous_edit_mode in ["edit-choose", "edit-new", "edit-group"]
        if not had_edit_state:
            return

        self.reset_transient_interaction_state()
        self.restore_after_edit_mode()

    def cancel_unfinished_tool_workflow(self):
        """Drop any transient add/edit/grid interaction before a real tool switch.

        Tool switches should not reinterpret a live preview as another tool's
        preview. They should always start from a clean interaction state unless
        we are explicitly suspending work for temporary pan.
        """
        if self.is_image_edit_uniform_exposure_area_active():
            self.end_image_edit_uniform_exposure_area()
        if self.is_image_edit_crop_active():
            self.cancel_image_edit_crop()
        if self.cell_controller.uses_grid_preview():
            self.cell_controller.cancel_preview(log_message=False)
        elif self.cell_controller.is_any_edit_mode() or self.temporary_event_data.get("previous_edit_mode") in ["edit-choose", "edit-new", "edit-group"]:
            self.cancel_edit_state()
        else:
            self.reset_transient_interaction_state()

    def preserve_edit_state_for_pan(self):
        """Remember the current edit workflow so pan can return to it."""
        if self.cell_controller.is_any_edit_mode():
            self.temporary_event_data["previous_edit_mode"] = self.tool_mode

    def set_view_cursor_shape(self, cursor_shape):
        self.view.unsetCursor()
        self.view.viewport().unsetCursor()
        self.view.setCursor(cursor_shape)
        self.view.viewport().setCursor(cursor_shape)

    def apply_cursor_tool_ui(self):
        self.tool_mode = "cursor"
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.set_view_cursor_shape(Qt.ArrowCursor)
        self.reset_cell_items_edit_chosen()
        self.set_tools_highlight(self.tool_mode)
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Select / Move')
        self.sync_tool_options_panel()

    def apply_image_edit_tool_ui(self):
        self.tool_mode = "image-edit"
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.set_view_cursor_shape(Qt.ArrowCursor)
        self.reset_cell_items_edit_chosen()
        self.set_tools_highlight(self.tool_mode)
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Image Edit')
        self.prewarm_current_image_edit_render_cache()
        self.sync_tool_options_panel()

    def finalize_tool_mode_after_commit(self):
        """Clear transient override state without changing the active tool."""
        self.space_held = False
        self.temporary_event_data.pop("original_tool_mode", None)
        self.temporary_event_data.pop("previous_edit_mode", None)

    def apply_select_tool_ui(self, preserve_preview=False):
        self.tool_mode = 'select'
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.set_view_cursor_shape(Qt.CrossCursor)
        self.set_tools_highlight(self.tool_mode)
        self.reset_cell_items_edit_chosen()
        self.update_cell_items_selectable_state()
        if not preserve_preview:
            self.unselect_all_cell_items()
        self.tool_status_label.setText('Add Cell')
        self.sync_tool_options_panel()

    def apply_grid_tool_ui(self, preserve_preview=False):
        self.tool_mode = 'grid'
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.set_view_cursor_shape(Qt.CrossCursor)
        self.set_tools_highlight(self.tool_mode)
        self.reset_cell_items_edit_chosen()
        self.update_cell_items_selectable_state()
        if not preserve_preview:
            self.unselect_all_cell_items()
        self.tool_status_label.setText('Grid Placement')
        self.sync_tool_options_panel()
        if not preserve_preview:
            self.update_grid_preview()
            self.log("Grid tool active. Move to float the grid, click to pin it, then Apply or press Enter.")

    def apply_deselect_tool_ui(self):
        self.tool_mode = 'deselect'
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.set_view_cursor_shape(Qt.PointingHandCursor)
        self.set_tools_highlight(self.tool_mode)
        self.reset_cell_items_edit_chosen()
        self.update_cell_items_selectable_state()
        self.unselect_all_cell_items()
        self.tool_status_label.setText('Delete Cells')
        self.sync_tool_options_panel()

    def reset_cursor_tool(self, checked):
        if self.tool_mode != "cursor":
            self.cancel_unfinished_tool_workflow()
        self.apply_cursor_tool_ui()

    def panTool(self, checked):
        self.preserve_edit_state_for_pan()
        self.tool_mode = 'pan'
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)  # Enable panning in pan mode
        self.set_view_cursor_shape(Qt.OpenHandCursor)
        self.set_tools_highlight(self.tool_mode)
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Zoom and Pan')
        self.sync_tool_options_panel()

    def is_pan_interaction_active(self):
        return bool(
            self.tool_mode == 'pan'
            or (self.space_held and (self.temporary_event_data.get("original_tool_mode") is not None))
        )

    def enter_temporary_pan_mode(self):
        self.preserve_edit_state_for_pan()
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.set_view_cursor_shape(Qt.OpenHandCursor)
        self.set_tools_highlight("pan")
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Zoom and Pan')

    def imageEditTool(self, checked):
        if self.tool_mode != "image-edit":
            self.cancel_unfinished_tool_workflow()
        self.apply_image_edit_tool_ui()

    def selectTool(self, checked):
        if self.tool_mode != "select":
            self.cancel_unfinished_tool_workflow()
        self.apply_select_tool_ui()

    def gridTool(self, checked):
        if self.tool_mode != "grid":
            self.cancel_unfinished_tool_workflow()
        self.apply_grid_tool_ui()

    def activate_edit_cell_item(self, cell_item):
        if cell_item is None:
            return
        self.cell_controller.clear_group_cells()
        self.reset_cell_items_edit_chosen()
        cell_item.edit_chosen = True
        cell_item.update()
        self.preview_offset_x = 0.0
        self.preview_offset_y = 0.0
        self.edit_single_base_radius = float(cell_item.circle_sizes)
        self.edit_single_radius_delta = 0.0
        self.tool_mode = 'edit-new'
        self.set_tools_highlight(self.tool_mode)
        self.set_undo_status()
        self.set_redo_status()
        self.set_view_cursor_shape(Qt.CrossCursor)
        self.tool_status_label.setText('Edit Cell')
        self.grid_preview_origin_pixels = (
            float(cell_item.circle_pixel_positions[0]),
            float(cell_item.circle_pixel_positions[1]),
        )
        self.grid_preview_floating = False
        self.update_grid_preview()
        self.sync_tool_options_panel()
        self.refresh_grayscale_plot()
    
    def editTool(self, checked):
        if (not self.cell_controller.is_any_edit_mode()) and ("previous_edit_mode" not in self.temporary_event_data):
            self.cancel_unfinished_tool_workflow()
        if "previous_edit_mode" in self.temporary_event_data:
            edit_mode = self.temporary_event_data["previous_edit_mode"]
            self.temporary_event_data.pop("previous_edit_mode")
        else:
            edit_mode = self.tool_mode if self.cell_controller.is_any_edit_mode() else 'edit-choose'

        self.cell_controller.enter_edit_mode(edit_mode)
        self.set_tools_highlight(self.tool_mode)
        self.update_cell_items_selectable_state()
        self.tool_status_label.setText('Edit Cell')
        self.sync_tool_options_panel()
    
    def deselectTool(self, checked):
        if self.delete_selected_cells():
            return
        if self.tool_mode != "deselect":
            self.cancel_unfinished_tool_workflow()
        self.apply_deselect_tool_ui()

    
    def get_image_paths_from_folder(self, input_dirpath):
        image_extensions = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}
        input_imagePath = []

        def is_hidden_image_entry(name):
            return name.startswith("_") or name.startswith(".")

        for root, dirs, files in os.walk(input_dirpath):
            dirs[:] = [directory for directory in dirs if not is_hidden_image_entry(directory)]
            for file in files:
                if is_hidden_image_entry(file):
                    continue
                if file.split('.')[-1].lower() in image_extensions:
                    input_imagePath.append(os.path.join(root, file))
        return self.sort_image_paths(input_imagePath)

    def natural_sort_key(self, file_path):
        filename = os.path.basename(file_path)
        parts = re.split(r'(\d+)', filename.lower())
        key = [int(part) if part.isdigit() else part for part in parts]
        return (key, file_path.lower())

    def get_exif_sort_value(self, file_path):
        try:
            image = Image.open(file_path)
            exif = image.getexif()
            exif_datetime = exif.get(306)
            if not exif_datetime:
                return None
            return exif_datetime
        except Exception:
            return None

    def is_sort_mode_available(self, mode, file_paths=None):
        paths = file_paths if file_paths is not None else self.imagePaths
        if not paths:
            return True
        if mode == "exif_time":
            return all(self.get_exif_sort_value(path) is not None for path in paths)
        if mode == "created_time":
            try:
                return all(os.path.exists(path) and os.stat(path).st_birthtime for path in paths)
            except AttributeError:
                return False
            except OSError:
                return False
        if mode == "modified_time":
            try:
                return all(os.path.exists(path) for path in paths)
            except OSError:
                return False
        return True

    def get_sort_availability(self, file_paths=None):
        return {
            "natural_filename": True,
            "filename_asc": True,
            "filename_desc": True,
            "created_time": self.is_sort_mode_available("created_time", file_paths),
            "modified_time": self.is_sort_mode_available("modified_time", file_paths),
            "exif_time": self.is_sort_mode_available("exif_time", file_paths),
        }

    def sort_image_paths(self, file_paths, mode=None):
        sort_mode = mode or self.sort_mode
        paths = list(file_paths)
        if sort_mode == "natural_filename":
            return sorted(paths, key=self.natural_sort_key)
        if sort_mode == "filename_asc":
            return sorted(paths, key=lambda path: (os.path.basename(path).lower(), path.lower()))
        if sort_mode == "filename_desc":
            return sorted(paths, key=lambda path: (os.path.basename(path).lower(), path.lower()), reverse=True)
        if sort_mode == "created_time":
            return sorted(paths, key=lambda path: (os.stat(path).st_birthtime, os.path.basename(path).lower()))
        if sort_mode == "modified_time":
            return sorted(paths, key=lambda path: (os.path.getmtime(path), os.path.basename(path).lower()))
        if sort_mode == "exif_time":
            return sorted(paths, key=lambda path: (self.get_exif_sort_value(path), os.path.basename(path).lower()))
        return paths

    def sort_video_paths_for_concatenation(self, file_paths, mode=None):
        return self.sort_image_paths(file_paths, mode=mode or self.sort_mode)

    def openSortImagesDialog(self):
        sorting_video_clips = self.supports_video_clip_sorting()
        if not self.supports_image_file_operations() and not sorting_video_clips:
            QMessageBox.information(
                self,
                "Sort Source",
                "Sorting is available for image files or multi-clip video sources.",
            )
            return
        sort_paths = (
            self.active_frame_source().source_paths()
            if sorting_video_clips
            else self.imagePaths
        )
        availability = self.get_sort_availability(sort_paths)
        if sorting_video_clips:
            availability["exif_time"] = False
        dialog = SortImagesDialog(
            self,
            availability,
            self.sort_mode,
            self,
            source_kind_label="video_clips" if sorting_video_clips else "images",
        )
        if dialog.exec() != QDialog.Accepted:
            return

        selected_mode = dialog.selected_mode()
        if not self.is_sort_mode_available(selected_mode, sort_paths):
            title = "Sort Video Clips" if sorting_video_clips else "Sort Images"
            QMessageBox.warning(
                self,
                title,
                "The selected sort method is not available for the current session.",
            )
            return

        before_state = self.capture_session_state() if self.has_frames() else None
        self.sort_mode = selected_mode
        if sorting_video_clips:
            self.resort_current_video_clips()
            if before_state is not None:
                self.push_snapshot_history("Sort Video Clips", before_state)
        elif self.imagePaths:
            self.resort_current_session()
            if before_state is not None:
                self.push_snapshot_history("Sort Images", before_state)
        self.log(f"Sort mode: {selected_mode.replace('_', ' ')}")

    def resort_current_session(self):
        if not self.imagePaths or not self.supports_image_file_operations():
            return

        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.clear_image_caches()
        current_path = self.imagePaths[self.image_index]
        keyed_entries = list(zip(
            self.imagePaths,
            self.imageNames,
            self.image_list_entry_ids,
            range(len(self.imagePaths)),
        ))
        sorted_paths = self.sort_image_paths([entry[0] for entry in keyed_entries])
        sorted_entries = []
        remaining_entries = keyed_entries.copy()
        for path in sorted_paths:
            for idx, entry in enumerate(remaining_entries):
                if entry[0] == path:
                    sorted_entries.append(entry)
                    remaining_entries.pop(idx)
                    break

        old_to_new = {old_index: new_index for new_index, (_, _, _, old_index) in enumerate(sorted_entries)}
        self.imagePaths = [entry[0] for entry in sorted_entries]
        self.rebuild_image_sequence_frame_source()
        self.image_list_entry_ids = [entry[2] for entry in sorted_entries]
        self.keyframe_list = sorted(old_to_new[index] for index in self.keyframe_list if index in old_to_new)
        self.flagframe_list = sorted(old_to_new[index] for index in self.flagframe_list if index in old_to_new)
        self.analysis_start_frame_list = sorted(
            old_to_new[index]
            for index in self.analysis_start_frame_list
            if index in old_to_new
        )
        self.analysis_end_frame_list = sorted(
            old_to_new[index]
            for index in self.analysis_end_frame_list
            if index in old_to_new
        )
        self.keyframe_cell_items_dict = {
            old_to_new[index]: circles
            for index, circles in self.keyframe_cell_items_dict.items()
            if index in old_to_new
        }
        self.image_index = self.imagePaths.index(current_path) if current_path in self.imagePaths else 0
        self.populate_image_list()
        self.updateImage(self.image_index)
        self.invalidate_analysis_results("image order changed")

    def resort_current_video_clips(self):
        if not self.supports_video_clip_sorting():
            return

        old_source = self.active_frame_source()
        old_paths = old_source.source_paths()
        sorted_paths = self.sort_video_paths_for_concatenation(old_paths)
        if sorted_paths == old_paths:
            return

        current_reference = old_source.frame_reference(self.image_index)
        keyframe_references = {
            int(index): old_source.frame_reference(index)
            for index in self.keyframe_list
            if 0 <= int(index) < old_source.frame_count()
        }
        flagframe_references = {
            int(index): old_source.frame_reference(index)
            for index in self.flagframe_list
            if 0 <= int(index) < old_source.frame_count()
        }
        analysis_start_references = {
            int(index): old_source.frame_reference(index)
            for index in self.analysis_start_frame_list
            if 0 <= int(index) < old_source.frame_count()
        }
        analysis_end_references = {
            int(index): old_source.frame_reference(index)
            for index in self.analysis_end_frame_list
            if 0 <= int(index) < old_source.frame_count()
        }
        keyframe_items_by_reference = {
            old_source.frame_reference(index): circles
            for index, circles in self.keyframe_cell_items_dict.items()
            if 0 <= int(index) < old_source.frame_count()
        }

        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.clear_image_caches()
        frame_source = VideoSequenceFrameSource(sorted_paths)
        new_current_index = frame_source.global_index_for_reference(*current_reference)
        if new_current_index is None:
            new_current_index = 0

        self.keyframe_list = sorted(
            new_index
            for new_index in (
                frame_source.global_index_for_reference(*reference)
                for reference in keyframe_references.values()
            )
            if new_index is not None
        )
        self.flagframe_list = sorted(
            new_index
            for new_index in (
                frame_source.global_index_for_reference(*reference)
                for reference in flagframe_references.values()
            )
            if new_index is not None
        )
        self.analysis_start_frame_list = sorted(
            new_index
            for new_index in (
                frame_source.global_index_for_reference(*reference)
                for reference in analysis_start_references.values()
            )
            if new_index is not None
        )
        self.analysis_end_frame_list = sorted(
            new_index
            for new_index in (
                frame_source.global_index_for_reference(*reference)
                for reference in analysis_end_references.values()
            )
            if new_index is not None
        )
        self.keyframe_cell_items_dict = {
            new_index: circles
            for reference, circles in keyframe_items_by_reference.items()
            for new_index in [frame_source.global_index_for_reference(*reference)]
            if new_index is not None
        }

        self.image_index = int(new_current_index)
        self.last_committed_image_index = int(new_current_index)
        self.set_frame_source(frame_source, reset_frame_ids=True)
        self.populate_image_list()
        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(self.frame_count() - 1)
        self.image_slider.setValue(self.image_index)
        self.image_slider.blockSignals(False)
        self.image_slider.sync_marker_state(
            self.keyframe_list,
            self.flagframe_list,
            self.analysis_start_frame_list,
            self.analysis_end_frame_list,
        )
        self.updateImage(self.image_index)
        self.finalize_frame_update(self.image_index)
        self.invalidate_analysis_results("video clip order changed")

    def open_add_images_dialog(self):
        if self.has_frames() and self.is_video_source():
            QMessageBox.information(
                self,
                "Add Source",
                "A video source is already loaded. Clear the current source before adding images or opening another video.",
            )
            return

        source_dialog = QMessageBox(self)
        source_dialog.setWindowTitle("Add Images")
        source_dialog.setText("Choose what to add to this session.")
        add_files_button = source_dialog.addButton("Images...", QMessageBox.AcceptRole)
        # On macOS, QMessageBox action-role buttons are laid out in reverse insertion order.
        open_video_button = source_dialog.addButton("Video...", QMessageBox.ActionRole)
        add_folder_button = source_dialog.addButton("Image Folder...", QMessageBox.ActionRole)
        if self.has_frames():
            open_video_button.setEnabled(False)
            open_video_button.setToolTip("Clear the current source before opening a video.")
        source_dialog.addButton(QMessageBox.Cancel)
        source_dialog.exec()

        clicked_button = source_dialog.clickedButton()
        if clicked_button == add_files_button:
            self.loadImages()
        elif clicked_button == add_folder_button:
            self.loadFolder()
        elif clicked_button == open_video_button:
            self.open_video()

    def loadFolder(self):
        input_dirpath = QFileDialog.getExistingDirectory(
            self,
            'Select Folder',
            "",
            options=self.file_dialog_options(),
        )
        if input_dirpath:
            self.load_aux(self.get_image_paths_from_folder(input_dirpath))

    def loadImages(self):
        input_imagePath, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Image(s)",
            "",
            "Image Files (*.png *.jpg *.jpeg);;All Files (*)",
            options=self.file_dialog_options(),
        )
        if input_imagePath:
            self.load_aux(self.sort_image_paths(input_imagePath))

    def open_video(self):
        if self.has_frames():
            QMessageBox.information(
                self,
                "Open Video",
                "A source is already loaded. Clear the current source before opening a video.",
            )
            return

        if not VideoFrameSource.available():
            detail = VideoFrameSource.import_error_message()
            message = (
                "Video input requires PyAV, but the app could not load it."
            )
            if detail:
                message += f"\n\nImport error:\n{detail}"
            QMessageBox.warning(
                self,
                "Open Video",
                message,
            )
            return
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Video(s)",
            "",
            "Video Files (*.mp4 *.mov *.avi *.mkv *.m4v);;All Files (*)",
            options=self.file_dialog_options(),
        )
        if file_paths:
            self.load_videos(file_paths)

    def load_video(self, file_path):
        IceScopy.load_videos(self, [file_path])

    def load_videos(self, file_paths):
        if self.has_frames():
            QMessageBox.information(
                self,
                "Open Video",
                "A source is already loaded. Clear the current source before opening a video.",
            )
            return

        video_paths = [str(path) for path in (file_paths or []) if str(path)]
        if not video_paths:
            return
        video_paths = self.sort_video_paths_for_concatenation(video_paths, mode="natural_filename")
        before_state = self.capture_loaded_images_state()
        try:
            frame_source = (
                VideoFrameSource(video_paths[0])
                if len(video_paths) == 1
                else VideoSequenceFrameSource(video_paths)
            )
        except Exception as err:
            QMessageBox.warning(self, "Open Video Failed", str(err))
            self.log(f"Failed to open video: {err}")
            return
        if frame_source.frame_count() <= 0:
            QMessageBox.warning(self, "Open Video Failed", "The selected video does not contain decoded frames.")
            return

        self.reset_transient_interaction_state()
        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.clear_image_caches()
        self.keyframe_list = []
        self.flagframe_list = []
        self.analysis_start_frame_list = []
        self.analysis_end_frame_list = []
        self.keyframe_cell_items_dict = {}
        self.image_width = None
        self.image_index = 0
        self.last_committed_image_index = 0
        self.set_frame_source(frame_source, reset_frame_ids=True)
        self.invalidate_analysis_results("frame source changed")

        if hasattr(self, 'pixmap_item'):
            self.scene.removeItem(self.pixmap_item)
            del(self.pixmap_item)

        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(self.frame_count() - 1)
        self.image_slider.setValue(0)
        self.image_slider.blockSignals(False)
        self.image_slider.setEnabled(True)
        self.image_slider.sync_marker_state(
            self.keyframe_list,
            self.flagframe_list,
            self.analysis_start_frame_list,
            self.analysis_end_frame_list,
        )
        self.image_textbox.setText("0")
        self.populate_image_list()
        self.updateImage(0)
        self.finalize_frame_update(0)

        self.select_tool_action.setEnabled(True)
        self.grid_tool_action.setEnabled(True)
        self.pan_tool_action.setEnabled(True)
        self.deselect_tool_action.setEnabled(True)
        self.edit_tool_action.setEnabled(True)
        self.update_session_actions_state()
        self.updateButtonStates()
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()
        if len(video_paths) == 1:
            self.log(f"Loaded video with {self.frame_count()} frames")
        else:
            self.log(f"Loaded {len(video_paths)} video clips with {self.frame_count()} total frames")
        self.push_loaded_images_history("Open Video", before_state)

    def openSession(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Session",
            "",
            "Icescopy Session (*.icescopy);;All Files (*)",
            options=self.file_dialog_options(),
        )
        if not file_path:
            return

        self.open_session_file_path(file_path, next_action_label="opening another session")

    def open_session_file_path(self, file_path, *, next_action_label="opening another session"):
        file_path = os.path.abspath(os.path.expanduser(str(file_path)))
        if not file_path.lower().endswith(".icescopy"):
            QMessageBox.warning(
                self,
                "Open Session",
                "Icescopy can only open .icescopy session files.",
            )
            return False
        if not os.path.isfile(file_path):
            QMessageBox.warning(
                self,
                "Open Session",
                f"Session file not found:\n{file_path}",
            )
            return False

        save_choice = self.prompt_save_before_replacing_session(next_action_label)
        if save_choice == "cancel":
            return False

        try:
            payload, grayscale_table, freeze_table, freeze_count_timeseries_table = load_session_bundle(file_path)
            state = build_restore_state(
                self,
                payload,
                grayscale_table,
                freeze_table,
                freeze_count_timeseries_table,
            )
            self.session_active = True
            self.current_session_file_path = file_path
            self.restore_session_state(state)
            self.undo_stack.clear()
            self.pending_analysis_before_state = None
            self.log(f"Opened session {os.path.basename(file_path)}")
            missing_images = self.get_missing_session_image_paths()
            if missing_images:
                QMessageBox.information(
                    self,
                    "Session Images Missing",
                    "Some session image files could not be found.\n\nUse File -> Relink Images Folder... to point the session to the current image folder.",
                )
            return True
        except Exception as err:
            QMessageBox.critical(self, "Open Session Failed", str(err))
            self.log(f"Failed to open session: {err}")
            return False

    def get_missing_session_image_paths(self):
        missing_paths = []
        for image_path in getattr(self, "imagePaths", []):
            try:
                if not os.path.isfile(image_path):
                    missing_paths.append(str(image_path))
            except OSError:
                missing_paths.append(str(image_path))
        return missing_paths

    def relink_images_folder(self, checked=False):
        if not self.imagePaths or not self.supports_image_file_operations():
            QMessageBox.information(self, "Relink Images Folder", "No session images are loaded.")
            return

        initial_dir = ""
        for image_path in self.imagePaths:
            try:
                if os.path.isfile(image_path):
                    initial_dir = os.path.dirname(image_path)
                    break
            except OSError:
                continue
        if not initial_dir:
            first_path = str(self.imagePaths[0])
            if first_path:
                initial_dir = os.path.dirname(first_path)

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Relink Images Folder",
            initial_dir,
            options=self.file_dialog_options(),
        )
        if not selected_dir:
            return

        candidate_paths = self.get_image_paths_from_folder(selected_dir)
        if not candidate_paths:
            QMessageBox.warning(self, "Relink Images Folder", "No image files were found in the selected folder.")
            return

        candidates_by_name = {}
        for candidate_path in candidate_paths:
            basename = os.path.basename(candidate_path).casefold()
            candidates_by_name.setdefault(basename, []).append(candidate_path)

        before_state = self.capture_image_session_state()
        old_image_paths = list(self.imagePaths)
        raw_image_edit_state = self.serialize_image_edit_state()
        all_images_missing_before = True
        for image_path in old_image_paths:
            try:
                if os.path.isfile(image_path):
                    all_images_missing_before = False
                    break
            except OSError:
                continue
        new_image_paths = []
        relinked_count = 0
        ambiguous_names = []
        missing_names = []

        for index, old_path in enumerate(old_image_paths):
            image_name = os.path.basename(str(old_path or "")) or str(self.imageNames[index] if index < len(self.imageNames) else "")
            matches = candidates_by_name.get(image_name.casefold(), [])
            if len(matches) == 1:
                resolved_path = matches[0]
                if os.path.normcase(os.path.normpath(resolved_path)) != os.path.normcase(os.path.normpath(str(old_path))):
                    relinked_count += 1
                new_image_paths.append(resolved_path)
            elif len(matches) > 1:
                ambiguous_names.append(image_name)
                new_image_paths.append(old_path)
            else:
                missing_names.append(image_name)
                new_image_paths.append(old_path)

        if relinked_count == 0 and not ambiguous_names and missing_names:
            QMessageBox.warning(
                self,
                "Relink Images Folder",
                "No matching image filenames were found in the selected folder.",
            )
            return

        offset_map = {
            str(path): float(value)
            for path, value in dict(getattr(self, "image_edit_uniform_exposure_offsets", {})).items()
            if abs(float(value)) > 1e-9
        }
        remapped_offsets = {}
        for old_path, new_path in zip(old_image_paths, new_image_paths):
            old_key = os.path.normcase(os.path.normpath(str(old_path)))
            new_key = os.path.normcase(os.path.normpath(str(new_path)))
            if old_key in offset_map:
                remapped_offsets[new_key] = float(offset_map[old_key])
            elif str(old_path) in offset_map:
                remapped_offsets[new_key] = float(offset_map[str(old_path)])

        resolved_indexes = []
        for index, image_path in enumerate(new_image_paths):
            try:
                if os.path.isfile(image_path):
                    resolved_indexes.append(index)
            except OSError:
                continue

        self.imagePaths = list(new_image_paths)
        self.rebuild_image_sequence_frame_source()
        self.image_edit_uniform_exposure_offsets = remapped_offsets
        self.raw_image_size_cache = {}
        self.clear_image_caches()
        self.clear_context_pixmaps()
        if hasattr(self, "pixmap_item"):
            try:
                self.scene.removeItem(self.pixmap_item)
            except Exception:
                pass
            del self.pixmap_item
        self.view.resetTransform()
        self.view.horizontalScrollBar().setValue(0)
        self.view.verticalScrollBar().setValue(0)

        if resolved_indexes:
            if self.image_index not in resolved_indexes:
                self.image_index = int(resolved_indexes[0])
            self.last_committed_image_index = int(self.image_index)

            raw_width, raw_height = self.get_raw_image_dimensions(self.image_index)
            crop_state = dict((raw_image_edit_state or {}).get("crop", {}) or {})
            try:
                crop_center_x = float(crop_state.get("center_x", 0.0))
                crop_center_y = float(crop_state.get("center_y", 0.0))
                crop_width = float(crop_state.get("width", 1.0))
                crop_height = float(crop_state.get("height", 1.0))
                crop_angle = float(crop_state.get("angle", 0.0))
            except (TypeError, ValueError):
                crop_center_x = 0.0
                crop_center_y = 0.0
                crop_width = 1.0
                crop_height = 1.0
                crop_angle = 0.0

            collapsed_missing_image_crop = (
                all_images_missing_before
                and raw_width > 0
                and raw_height > 0
                and abs(crop_center_x) <= 1e-9
                and abs(crop_center_y) <= 1e-9
                and abs(crop_width - 1.0) <= 1e-9
                and abs(crop_height - 1.0) <= 1e-9
                and abs(crop_angle) <= 1e-9
            )
            if collapsed_missing_image_crop:
                raw_image_edit_state["crop"] = {
                    "center_x": float(raw_width) * 0.5,
                    "center_y": float(raw_height) * 0.5,
                    "width": float(raw_width),
                    "height": float(raw_height),
                    "angle": 0.0,
                }

            self.apply_image_edit_state(
                raw_image_edit_state,
                invalidate_results=False,
                refresh_display=False,
                sync_controls=False,
            )

        self.populate_image_list()
        if resolved_indexes:
            self.updateImage(self.image_index)
            self.finalize_frame_update(self.image_index)
            self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)
        elif self.imagePaths:
            self.image_name_label.setText(self.imageNames[self.image_index] if 0 <= self.image_index < len(self.imageNames) else "")
            self.image_textbox.setText(str(self.image_index))
        self.push_image_session_history("Relink Images Folder", before_state)

        message_lines = [f"Relinked images: {relinked_count}"]
        if resolved_indexes and self.image_index != before_state.get("image_index", self.image_index):
            message_lines.append(f"Showing first resolved image at index {self.image_index}")
        if missing_names:
            preview = ", ".join(missing_names[:6])
            if len(missing_names) > 6:
                preview += f", +{len(missing_names) - 6} more"
            message_lines.append("Still missing: " + preview)
        if ambiguous_names:
            preview = ", ".join(ambiguous_names[:6])
            if len(ambiguous_names) > 6:
                preview += f", +{len(ambiguous_names) - 6} more"
            message_lines.append("Ambiguous filenames not changed: " + preview)

        persisted_relink = False
        current_session_file_path = str(getattr(self, "current_session_file_path", "") or "").strip()
        if current_session_file_path:
            persisted_relink = self.persist_session_to_current_file(show_errors=False)
            if persisted_relink:
                message_lines.append(f"Session updated: {os.path.basename(current_session_file_path)}")
            else:
                message_lines.append("Session file was not updated. Use Save Session to persist relinked paths.")

        QMessageBox.information(self, "Relink Images Folder", "\n".join(message_lines))
        self.log(f"Relink Images Folder: {relinked_count} image path(s) updated")

    def handle_save_session_action(self):
        self.key_press_toolbutton_highlight(self.save_session_action)
        return self.saveSession()

    def persist_session_to_path(self, file_path, *, show_errors=True):
        try:
            payload = build_session_payload(self)
            save_session_bundle(
                file_path,
                payload,
                self.grayscale_results_headers,
                self.grayscale_results_rows,
                self.freeze_results_headers,
                self.freeze_results_rows,
                self.freeze_count_timeseries_headers,
                self.freeze_count_timeseries_rows,
            )
            self.current_session_file_path = file_path
            self.log(f"Saved session at {file_path}")
            return True
        except Exception as err:
            if show_errors:
                QMessageBox.critical(self, "Save Session Failed", str(err))
            self.log(f"Failed to save session: {err}")
            return False

    def persist_session_to_current_file(self, *, show_errors=True):
        file_path = str(getattr(self, "current_session_file_path", "") or "").strip()
        if not file_path:
            return False
        return self.persist_session_to_path(file_path, show_errors=show_errors)

    def saveSession(self):
        if not getattr(self, "session_active", False):
            self.log("No active session to save")
            return False

        current_session_file_path = str(getattr(self, "current_session_file_path", "") or "").strip()
        if current_session_file_path:
            return self.persist_session_to_current_file(show_errors=True)

        return self.saveSessionAs()

    def saveSessionAs(self):
        if not getattr(self, "session_active", False):
            self.log("No active session to save")
            return False

        initial_path = str(getattr(self, "current_session_file_path", "") or "").strip()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Session As",
            initial_path,
            "Icescopy Session (*.icescopy);;All Files (*)",
            options=self.file_dialog_options(),
        )
        if not file_path:
            return False

        if not file_path.lower().endswith(".icescopy"):
            file_path = f"{file_path}.icescopy"

        return self.persist_session_to_path(file_path, show_errors=True)

    def load_aux(self, input_imagePath):
        if self.has_frames() and not self.supports_image_file_operations():
            QMessageBox.warning(
                self,
                "Add Images",
                "Image files cannot be added to a video source. Clear the current source before loading image files.",
            )
            return
        if not input_imagePath:
            if not self.has_frames():
                self.log("No image loaded")
            return

        before_state = self.capture_loaded_images_state()

        normalized_existing_paths = {
            os.path.normcase(os.path.normpath(existing_path))
            for existing_path in self.imagePaths
        }
        unique_new_paths = []
        for image_path in input_imagePath:
            normalized_path = os.path.normcase(os.path.normpath(image_path))
            if normalized_path not in normalized_existing_paths:
                unique_new_paths.append(image_path)
                normalized_existing_paths.add(normalized_path)
        unique_new_paths = self.sort_image_paths(unique_new_paths)

        if not unique_new_paths:
            self.log("No new images added")
            return

        is_first_load = not self.has_frames()
        new_entry_ids = list(range(self.next_image_list_entry_id, self.next_image_list_entry_id + len(unique_new_paths)))
        self.next_image_list_entry_id += len(unique_new_paths)
        self.imagePaths.extend(unique_new_paths)
        self.rebuild_image_sequence_frame_source()
        self.image_list_entry_ids.extend(new_entry_ids)

        if is_first_load:
            self.log(f"Loaded {len(unique_new_paths)} images")
            if hasattr(self, 'pixmap_item'):
                self.scene.removeItem(self.pixmap_item)
                del(self.pixmap_item)
        else:
            self.log(f"Added {len(unique_new_paths)} images to this session")

        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(self.frame_count() - 1)
        if is_first_load:
            self.image_slider.setValue(0)
        self.image_slider.blockSignals(False)

        self.select_tool_action.setEnabled(True)
        self.grid_tool_action.setEnabled(True)
        self.pan_tool_action.setEnabled(True)
        self.image_slider.setEnabled(True)
        self.deselect_tool_action.setEnabled(True)
        self.edit_tool_action.setEnabled(True)
        self.update_session_actions_state()
        self.updateButtonStates()
        self.set_redo_status()
        self.set_undo_status()
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()
        new_rows = range(self.frame_count() - len(unique_new_paths), self.frame_count())
        new_entries = [self.format_image_list_entry(index) for index in new_rows]
        if is_first_load:
            self.image_list_model.set_items(new_entries, unique_new_paths)
        else:
            self.image_list_model.append_items(new_entries, unique_new_paths)

        if is_first_load:
            self.image_textbox.setText("0")
            self.updateImage(0)
            self.finalize_frame_update(0)
        else:
            self.sync_image_list_selection()

        self.invalidate_analysis_results("image list changed")

        self.push_loaded_images_history("Add Images", before_state)

    def remove_selected_image(self):
        if not self.has_frames() or not self.supports_image_file_operations():
            return

        if self.active_image_panel == "list":
            self.remove_selected_list_images()
        else:
            self.remove_current_viewer_image()

    def remove_selected_list_images(self):
        if not self.has_frames() or not self.supports_image_file_operations():
            return

        selected_rows = self.get_selected_image_rows()
        if not selected_rows:
            current_index = self.image_list_widget.currentIndex()
            if current_index.isValid():
                current_source_row = self.frame_list_source_index_for_row(current_index.row())
                selected_rows = [] if current_source_row is None else [current_source_row]
            else:
                selected_rows = [self.image_index]

        self.remove_images_from_session(selected_rows)

    def remove_current_viewer_image(self):
        if not self.has_frames() or not self.supports_image_file_operations():
            return
        self.remove_images_from_session([self.image_index])

    def remove_images_from_session(self, rows):
        if not self.supports_image_file_operations():
            QMessageBox.information(self, "Remove Frames", "Individual frame removal is not available for video sources.")
            return
        rows_to_remove = sorted({row for row in rows if 0 <= row < len(self.imagePaths)})
        if not rows_to_remove:
            return

        if len(rows_to_remove) >= len(self.imagePaths):
            self.clear_loaded_images(confirm=False, log_message="Cleared all loaded images from this session")
            return

        before_state = self.capture_image_session_state()
        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.clear_image_caches()

        removed_rows = set(rows_to_remove)
        old_image_index = self.image_index
        removed_before_current = sum(1 for row in rows_to_remove if row < old_image_index)
        current_removed = old_image_index in removed_rows

        self.imagePaths = [path for index, path in enumerate(self.imagePaths) if index not in removed_rows]
        self.rebuild_image_sequence_frame_source()
        self.image_list_entry_ids = [entry_id for index, entry_id in enumerate(self.image_list_entry_ids) if index not in removed_rows]

        self.keyframe_cell_items_dict = {
            old_index - sum(1 for removed_row in rows_to_remove if removed_row < old_index): value
            for old_index, value in self.keyframe_cell_items_dict.items()
            if old_index not in removed_rows
        }
        self.keyframe_list = [
            old_index - sum(1 for removed_row in rows_to_remove if removed_row < old_index)
            for old_index in self.keyframe_list
            if old_index not in removed_rows
        ]
        self.flagframe_list = [
            old_index - sum(1 for removed_row in rows_to_remove if removed_row < old_index)
            for old_index in self.flagframe_list
            if old_index not in removed_rows
        ]
        self.analysis_start_frame_list = [
            old_index - sum(1 for removed_row in rows_to_remove if removed_row < old_index)
            for old_index in self.analysis_start_frame_list
            if old_index not in removed_rows
        ]
        self.analysis_end_frame_list = [
            old_index - sum(1 for removed_row in rows_to_remove if removed_row < old_index)
            for old_index in self.analysis_end_frame_list
            if old_index not in removed_rows
        ]

        new_image_index = max(0, min(old_image_index - removed_before_current, len(self.imagePaths) - 1))

        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(self.frame_count() - 1)
        self.image_slider.setValue(new_image_index)
        self.image_slider.blockSignals(False)
        self.image_slider.sync_marker_state(
            self.keyframe_list,
            self.flagframe_list,
            self.analysis_start_frame_list,
            self.analysis_end_frame_list,
        )
        self.image_textbox.setText(str(new_image_index))

        self.image_list_model.remove_rows(rows_to_remove)
        if self.has_frames():
            annotation_start = min(rows_to_remove)
            self.update_image_list_annotations(range(annotation_start, self.frame_count()))
        else:
            self.populate_image_list()
        # Always refresh frame display/interpolation after image removal because
        # shifting frame indices can change keyframe interpolation even when the
        # current image path itself did not change.
        self.updateImage(new_image_index)
        self.finalize_frame_update(new_image_index)
        self.invalidate_analysis_results("image list changed")
        self.update_session_actions_state()
        self.updateButtonStates()
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()
        self.log(f"Removed {len(rows_to_remove)} image(s) from this session")
        self.push_image_session_history("Remove Images", before_state)

    def clear_loaded_images(self, checked=False, confirm=True, log_message="Cleared all loaded images from this session"):
        if not self.has_frames():
            return

        if confirm:
            reply = QMessageBox.question(
                self,
                "Clear Images",
                "Remove all loaded images from this session? Cells and sample assignments are kept. Keyframes and analysis results tied to the images are cleared, but files are not deleted from disk.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        before_state = self.capture_image_session_state()
        preserved_cell_items = copy.deepcopy(self.cell_items)
        preserved_next_cell_id = int(getattr(self, "next_cell_id", 0))
        preserved_cell_records = copy.deepcopy(self.serialize_cell_records())

        self.reset_transient_interaction_state()
        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.clear_image_caches()
        self.keyframe_list = []
        self.flagframe_list = []
        self.analysis_start_frame_list = []
        self.analysis_end_frame_list = []
        self.keyframe_cell_items_dict = {}
        self.image_width = None
        stop_video_preview_decoder = getattr(self, "stop_video_preview_decoder", None)
        if callable(stop_video_preview_decoder):
            stop_video_preview_decoder()
        old_frame_source = getattr(self, "frame_source", None)
        if old_frame_source is not None:
            close_source = getattr(old_frame_source, "close", None)
            if callable(close_source):
                close_source()
        self.imagePaths = []
        self.imageNames = []
        self.frame_source = ImageSequenceFrameSource([])
        self.image_index = 0
        self.last_committed_image_index = 0
        self.image_list_entry_ids = []
        self.next_image_list_entry_id = 0

        self.scene.clear()
        if hasattr(self, 'pixmap_item'):
            del(self.pixmap_item)
        self.cell_items = preserved_cell_items
        self.rendered_cell_items = []
        self.next_cell_id = preserved_next_cell_id
        self.cell_records_by_id = self.deserialize_cell_records(preserved_cell_records)
        self.ensure_cell_registry_matches_scene_cells()
        self.recompute_next_cell_id(preserve_if_larger=True)

        self.image_name_label.clear()
        self.image_textbox.clear()
        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(0)
        self.image_slider.setValue(0)
        self.image_slider.blockSignals(False)
        self.image_slider.setEnabled(False)
        self.image_slider.clear_marker_state()

        self.select_tool_action.setEnabled(False)
        self.grid_tool_action.setEnabled(False)
        self.pan_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.update_session_actions_state()
        self.updateButtonStates()
        self.invalidate_analysis_results("image list changed")
        self.populate_image_list()
        self.reset_cursor_action.trigger()
        self.redraw_no_image_cell_template_view(fit_view=True)
        self.log(log_message)
        self.push_image_session_history("Clear Images", before_state)

    def clear_session(self, checked=False, confirm=True, log_message="Cleared session", record_history=True, new_metadata=None, activate_session=False):
        has_results = bool(
            self.grayscale_results_headers
            or self.freeze_results_headers
            or self.freeze_count_timeseries_headers
        )
        if confirm and (self.has_frames() or has_results):
            reply = QMessageBox.question(
                self,
                "Clear Session",
                "Clear the entire current session? This removes loaded images and in-app analysis data, but does not delete files from disk.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        before_state = self.capture_session_state() if record_history else None

        self.initData()
        self.session_active = bool(activate_session)
        if activate_session:
            self.apply_tool_settings(self.default_tool_settings())
        if new_metadata is not None:
            self.apply_session_metadata(new_metadata)

        self.reset_transient_interaction_state()
        self.reset_pending_frame_navigation_state(stop_timer=True)
        self.scene.clear()
        if hasattr(self, 'pixmap_item'):
            del(self.pixmap_item)

        self.image_name_label.clear()
        self.image_textbox.clear()
        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(0)
        self.image_slider.setValue(0)
        self.image_slider.blockSignals(False)
        self.image_slider.setEnabled(False)
        self.image_slider.clear_marker_state()

        self.select_tool_action.setEnabled(False)
        self.grid_tool_action.setEnabled(False)
        self.pan_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.update_session_actions_state()
        self.updateButtonStates()
        self.update_results_tables()
        self.update_freeze_count_timeseries_table()
        self.refresh_sample_catalog_tree(preserve_selection=False)
        self.populate_image_list()
        self.reset_cursor_action.trigger()
        if hasattr(self, "terminal"):
            self.terminal.clear()
        self.log(log_message)
        if record_history and before_state is not None:
            self.push_snapshot_history("Clear Session", before_state)

    def reset_pending_frame_navigation_state(self, stop_timer=False):
        self.pending_navigation_before_index = None
        self.pending_navigation_history_text = "Change Frame"
        self.slider_drag_start_index = None
        self.pending_preview_image_index = None
        self.preview_frame_update_in_progress = False
        self.video_preview_target_index = None
        if stop_timer and hasattr(self, "image_preview_timer"):
            self.image_preview_timer.stop()

    def clear_image_caches(self):
        if hasattr(self, "raw_image_cache"):
            self.raw_image_cache.clear()
        if hasattr(self, "raw_image_size_cache"):
            self.raw_image_size_cache.clear()
        if hasattr(self, "preview_raw_frame_keys"):
            self.preview_raw_frame_keys.clear()
        if hasattr(self, "image_cache"):
            self.image_cache.clear()
        if hasattr(self, "pixmap_cache"):
            self.pixmap_cache.clear()
        self.displayed_image_edit_crop_applied = None

    def get_cached_raw_image(self, index):
        index = int(index)
        frame_key = self.frame_key(index)
        cached_image = self.raw_image_cache.get(frame_key)
        if cached_image is not None:
            self.raw_image_cache.move_to_end(frame_key)
            return cached_image

        cached_image = self.active_frame_source().get_qimage(index)
        self.raw_image_cache[frame_key] = cached_image
        self.raw_image_cache.move_to_end(frame_key)
        if hasattr(self, "preview_raw_frame_keys"):
            self.preview_raw_frame_keys.discard(frame_key)

        if hasattr(self, "raw_image_size_cache"):
            self.raw_image_size_cache[frame_key] = (int(cached_image.width()), int(cached_image.height()))

        while len(self.raw_image_cache) > self.raw_image_cache_size:
            evicted_path, _ = self.raw_image_cache.popitem(last=False)
            if hasattr(self, "raw_image_size_cache"):
                self.raw_image_size_cache.pop(evicted_path, None)

        return cached_image

    def cache_raw_frame_image(self, index, q_image, frame_key=None, *, preview_cache=False):
        index = int(index)
        if frame_key is None:
            frame_key = self.frame_key(index)
        if q_image is None or q_image.isNull():
            return
        self.raw_image_cache[frame_key] = q_image
        self.raw_image_cache.move_to_end(frame_key)
        if hasattr(self, "preview_raw_frame_keys"):
            if preview_cache:
                self.preview_raw_frame_keys.add(frame_key)
            else:
                self.preview_raw_frame_keys.discard(frame_key)
        if hasattr(self, "raw_image_size_cache"):
            self.raw_image_size_cache[frame_key] = (int(q_image.width()), int(q_image.height()))
        while len(self.raw_image_cache) > self.raw_image_cache_size:
            evicted_path, _ = self.raw_image_cache.popitem(last=False)
            if hasattr(self, "raw_image_size_cache"):
                self.raw_image_size_cache.pop(evicted_path, None)
            if hasattr(self, "preview_raw_frame_keys"):
                self.preview_raw_frame_keys.discard(evicted_path)

    def discard_preview_raw_frame_cache(self, index):
        frame_key = self.frame_key(index)
        if frame_key not in getattr(self, "preview_raw_frame_keys", set()):
            return
        self.preview_raw_frame_keys.discard(frame_key)
        self.raw_image_cache.pop(frame_key, None)
        self.raw_image_size_cache.pop(frame_key, None)
        for cache_key in list(self.image_cache):
            if cache_key[0] == frame_key:
                self.image_cache.pop(cache_key, None)
        for cache_key in list(self.pixmap_cache):
            if cache_key[0] == frame_key:
                self.pixmap_cache.pop(cache_key, None)

    def raw_frame_image_is_cached(self, index):
        try:
            frame_key = self.frame_key(index)
        except Exception:
            return False
        return frame_key in self.raw_image_cache

    def request_video_preview_frame(self, index):
        if not self.is_video_source():
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= self.frame_count():
            return

        self.video_preview_target_index = index
        self.pending_preview_image_index = index
        self.image_textbox.setText(str(index))
        self.image_name_label.setText(self.frame_name(index))
        self.update_grayscale_plot_current_frame()

        if self.raw_frame_image_is_cached(index):
            self.updateImage(index, preview=True)
            return

        if self.video_preview_decoder is None:
            self.start_video_preview_decoder()
        if self.video_preview_decoder is None or self.video_preview_decode_in_flight:
            return

        self.video_preview_decode_in_flight = True
        self.video_preview_decoder.request_decode(index)

    def handle_video_preview_decoded(self, index, q_image, frame_key, source_token):
        self.video_preview_decode_in_flight = False
        if not self.is_video_source() or self.active_frame_source().source_token() != source_token:
            return

        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if not (0 <= index < self.frame_count()):
            return

        self.cache_raw_frame_image(index, q_image, frame_key=frame_key, preview_cache=True)
        if self.image_slider.isSliderDown() and self.video_preview_target_index == index:
            self.updateImage(index, preview=True)

        target_index = self.video_preview_target_index
        if (
            self.image_slider.isSliderDown()
            and target_index is not None
            and target_index != index
        ):
            self.request_video_preview_frame(target_index)

    def handle_video_preview_failed(self, index, message, source_token):
        self.video_preview_decode_in_flight = False
        if self.is_video_source() and self.active_frame_source().source_token() == source_token:
            self.log(f"Video preview decode failed at frame {index}: {message}")

    def handle_preview_image_slider_value(self, index):
        if not self.has_frames():
            return
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        if index < 0 or index >= self.frame_count():
            return

        self.pending_preview_image_index = index
        if self.preview_frame_update_in_progress:
            return
        if not self.image_preview_timer.isActive():
            self.image_preview_timer.start(self.get_preview_frame_interval_ms())

    def handle_image_slider_pressed(self):
        if not self.has_frames() or self.history_restoring:
            return
        committed_index = max(
            0,
            min(int(getattr(self, "last_committed_image_index", self.image_index)), self.frame_count() - 1),
        )
        self.slider_drag_start_index = committed_index
        self.pending_navigation_before_index = committed_index
        self.pending_navigation_history_text = "Change Frame"

    def handle_image_slider_released(self):
        # Drag-release can occur without a committed value change. In that case,
        # clear pending navigation start so it cannot leak into the next move.
        if self.history_restoring:
            return
        if self.image_slider.isSliderDown():
            return
        if self.slider_drag_start_index is None:
            return
        if self.image_slider.sliderPosition() != self.slider_drag_start_index:
            return
        restore_index = int(self.slider_drag_start_index)
        preview_diverged = (
            self.image_index != restore_index
            or (
                self.pending_preview_image_index is not None
                and int(self.pending_preview_image_index) != restore_index
            )
        )
        self.reset_pending_frame_navigation_state(stop_timer=True)
        if preview_diverged and self.has_frames():
            self.updateImage(restore_index, preview=False)

    def get_preview_frame_interval_ms(self):
        if self.is_video_source():
            return 80
        return 16

    def flush_pending_preview_image(self):
        if self.pending_preview_image_index is None or self.preview_frame_update_in_progress:
            return
        pending_index = int(self.pending_preview_image_index)
        self.pending_preview_image_index = None
        if not self.has_frames():
            return
        if pending_index < 0 or pending_index >= self.frame_count():
            return
        if pending_index == self.image_index:
            return

        if self.is_video_source():
            self.request_video_preview_frame(pending_index)
            return

        self.preview_frame_update_in_progress = True
        try:
            self.updateImage(pending_index, preview=True)
        finally:
            self.preview_frame_update_in_progress = False

        if (
            self.pending_preview_image_index is not None
            and self.pending_preview_image_index != self.image_index
        ):
            self.image_preview_timer.start(self.get_preview_frame_interval_ms())

    def handle_committed_image_slider_value(self, index):
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        drag_start_index = self.slider_drag_start_index
        before_index = self.pending_navigation_before_index
        history_text = self.pending_navigation_history_text
        self.reset_pending_frame_navigation_state(stop_timer=True)
        if before_index is None and drag_start_index is not None:
            before_index = drag_start_index
        if before_index is None and not self.history_restoring:
            before_index = self.last_committed_image_index
        needs_full_video_frame = (
            self.is_video_source()
            and self.has_frames()
            and self.frame_key(index) in getattr(self, "preview_raw_frame_keys", set())
        )
        if self.has_frames() and self.image_index == index and not needs_full_video_frame:
            self.finalize_frame_update(index)
        else:
            self.updateImage(index, preview=False)
        if self.analysis_progress_navigation_suppressed and not self.history_restoring:
            return
        if before_index is not None and not self.history_restoring and before_index != self.image_index:
            self.log(f"{history_text}: {before_index} -> {self.image_index}")
            self.push_navigation_history(history_text, before_index, self.image_index)

    def finalize_frame_update(self, index):
        if not self.has_frames() or not (0 <= index < self.frame_count()):
            return
        self.last_committed_image_index = int(index)
        if not self.image_slider.isSliderDown():
            self.ensure_slider_window_contains_index(index)
            if self.image_slider.value() != index:
                self.image_slider.blockSignals(True)
                self.image_slider.setValue(index)
                self.image_slider.blockSignals(False)
        self.image_name_label.setText(self.frame_name(index))
        self.resize_image_textbox()
        self.updateButtonStates()
        self.update_toggle_keyframe_button_icon()
        self.update_toggle_flagging_button_icon()
        self.update_toggle_analysis_start_button_icon()
        self.update_toggle_analysis_end_button_icon()
        self.sync_image_list_selection()
        self.update_grayscale_plot_current_frame(force=True)

    def ensure_slider_window_contains_index(self, index):
        if not self.has_frames():
            return

        target_index = max(0, min(int(index), self.frame_count() - 1))
        slider_min = self.image_slider.minimum()
        slider_max = self.image_slider.maximum()
        if slider_min <= target_index <= slider_max:
            return

        window_size = max(0, slider_max - slider_min)
        if target_index < slider_min:
            new_min = target_index
            new_max = target_index + window_size
        else:
            new_max = target_index
            new_min = target_index - window_size

        max_index = self.frame_count() - 1
        new_min = max(0, int(new_min))
        new_max = min(max_index, int(new_max))
        if new_max - new_min < window_size:
            if new_min == 0:
                new_max = min(max_index, new_min + window_size)
            else:
                new_min = max(0, new_max - window_size)

        self.image_slider.blockSignals(True)
        self.image_slider.setMinimum(new_min)
        self.image_slider.setMaximum(new_max)
        self.image_slider.blockSignals(False)

    def updateImage(self, index, preview=False):
            if self.has_frames():
                try:
                    index = int(index)
                except (TypeError, ValueError):
                    index = int(getattr(self, "last_committed_image_index", self.image_index))
                index = max(0, min(index, self.frame_count() - 1))
                current_transform = self.view.transform()
                current_hscroll = self.view.horizontalScrollBar().value()
                current_vscroll = self.view.verticalScrollBar().value()
                had_pixmap_item = hasattr(self, 'pixmap_item')

                self.view.setUpdatesEnabled(False)
                try:
                    self.image_index = index
                    self.image_textbox.setText(str(index))
                    if (not preview) and self.is_video_source():
                        self.discard_preview_raw_frame_cache(index)
                    q_image = self.update_display_pixmaps(index, preview=preview)
                    if not had_pixmap_item:
                        self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)

                    self.view.setTransform(current_transform)
                    self.view.horizontalScrollBar().setValue(current_hscroll)
                    self.view.verticalScrollBar().setValue(current_vscroll)

                    self.image_width = self.get_raw_image_dimensions(index)[0]
                    self.interpolate_and_displayMarkedRegions(index, preview=preview)
                    if self.cell_controller.uses_grid_preview():
                        self.cell_controller.rebase_edit_preview_to_current_frame()
                        self.update_grid_preview()
                    self.update_grayscale_plot_current_frame()
                    if (not preview) or self.tool_mode == "image-edit":
                        self.request_image_edit_histogram_refresh(q_image)
                    if self.tool_mode == "image-edit":
                        self.sync_image_edit_controls()

                    if not preview:
                        self.finalize_frame_update(index)
                finally:
                    self.view.setUpdatesEnabled(True)

                
                    
    def decreaseSliderValue(self):
        current_value = self.image_slider.value()
        if current_value > self.image_slider.minimum():
            self.navigate_to_image(current_value - 1)

        elif current_value > 0:
            self.image_slider.setMinimum(self.image_slider.minimum()-1)
            self.image_slider.setMaximum(self.image_slider.maximum()-1)
            self.navigate_to_image(current_value - 1)

    def increaseSliderValue(self):
        current_value = self.image_slider.value()
        if current_value < self.image_slider.maximum():
            self.navigate_to_image(current_value + 1)
        
        elif current_value < (self.frame_count()-1):
            self.image_slider.setMinimum(self.image_slider.minimum()+1)
            self.image_slider.setMaximum(self.image_slider.maximum()+1)
            self.navigate_to_image(current_value + 1)

    def handle_frame_navigation_shortcut(self, key):
        if key in (Qt.Key_Left, Qt.Key_Comma):
            if self.leftButton.isEnabled():
                self.leftButton.click()
                self.key_press_button_highlight(self.leftButton)
                return True
            return False
        if key in (Qt.Key_Right, Qt.Key_Period):
            if self.rightButton.isEnabled():
                self.rightButton.click()
                self.key_press_button_highlight(self.rightButton)
                return True
            return False
        return False
            
    def updateImageFromTextbox(self):
        # Update displayed image based on textbox value by changing the slider value
        try:
            index = int(self.image_textbox.text())
            index = max(0, min(index, self.frame_count() - 1))  # Ensure valid index
            self.navigate_to_image(index)
        except ValueError:
            pass  # Ignore non-integer input
    
    def resize_image_textbox(self):
        font_metrics = self.image_textbox.fontMetrics()
        current_text = self.image_textbox.text() or "0"
        text_width = font_metrics.horizontalAdvance(current_text)
        if self.has_frames():
            max_index_text = str(max(0, self.frame_count() - 1))
        else:
            max_index_text = "000"
        range_width = font_metrics.horizontalAdvance(max_index_text)
        minimum_width = font_metrics.horizontalAdvance("000")
        padding = 20  # extra padding
        new_width = max(text_width, range_width, minimum_width) + padding
        self.image_textbox.setFixedWidth(new_width)

    def get_cached_image(self, index, *, apply_crop=None):
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        frame_key = self.frame_key(index)
        cache_key = (frame_key, bool(apply_crop))
        cached_image = self.image_cache.get(cache_key)
        if cached_image is not None:
            self.image_cache.move_to_end(cache_key)
            return cached_image

        raw_q_image = self.get_cached_raw_image(index)
        crop_state = self.current_image_edit_crop_state(index=index)
        cached_image = apply_image_adjustments_to_qimage(
            raw_q_image,
            self.current_image_edit_total_exposure(index=index, image_path=frame_key),
            self.image_edit_contrast,
            crop_state,
            apply_crop=bool(apply_crop),
        )
        self.image_cache[cache_key] = cached_image
        self.image_cache.move_to_end(cache_key)

        while len(self.image_cache) > self.image_cache_size:
            self.image_cache.popitem(last=False)

        return cached_image

    def get_cached_pixmap(self, index, *, apply_crop=None):
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        frame_key = self.frame_key(index)
        cache_key = (frame_key, bool(apply_crop))
        cached_pixmap = self.pixmap_cache.get(cache_key)
        if cached_pixmap is not None:
            self.pixmap_cache.move_to_end(cache_key)
            return cached_pixmap

        cached_pixmap = QPixmap.fromImage(self.get_cached_image(index, apply_crop=apply_crop))
        self.pixmap_cache[cache_key] = cached_pixmap
        self.pixmap_cache.move_to_end(cache_key)

        while len(self.pixmap_cache) > self.pixmap_cache_size:
            self.pixmap_cache.popitem(last=False)

        return cached_pixmap

    def get_display_slots(self, current_index):
        total_images = self.frame_count()
        if total_images <= 0:
            return []

        count = max(1, min(self.viewer_image_count, 3))
        if count == 1:
            return [current_index]
        if count == 2:
            before_index = current_index - 1 if current_index > 0 else None
            return [before_index, current_index]

        before_index = current_index - 1 if current_index > 0 else None
        after_index = current_index + 1 if current_index < total_images - 1 else None
        return [before_index, current_index, after_index]

    def is_viewer_split_vertical(self):
        return int(getattr(self, "viewer_image_count", 1)) in (2, 3) and str(getattr(self, "viewer_split_orientation", "horizontal")) == "vertical"

    def clear_context_pixmaps(self):
        for item in self.context_pixmap_items:
            self.scene.removeItem(item)
        self.context_pixmap_items = []
        for item in self.placeholder_items:
            self.scene.removeItem(item)
        self.placeholder_items = []

    def update_display_pixmaps(self, current_index, *, apply_crop=None, preview=False):
        if apply_crop is None:
            apply_crop = self.should_apply_crop_in_display()
        display_slots = [current_index] if (preview and self.is_video_source()) else self.get_display_slots(current_index)
        if not display_slots:
            return None

        spacing = 30
        layout_vertical = self.is_viewer_split_vertical()
        active_image = self.get_cached_image(current_index, apply_crop=apply_crop)
        active_pixmap = self.get_cached_pixmap(current_index, apply_crop=apply_crop)
        slot_width = active_pixmap.width()
        slot_height = active_pixmap.height()

        entries = []
        current_left = 0
        current_top = 0
        for display_index in display_slots:
            if display_index is None:
                entries.append((None, None, None, current_left, current_top))
                if layout_vertical:
                    current_top += slot_height + spacing
                else:
                    current_left += slot_width + spacing
                continue

            q_image = self.get_cached_image(display_index, apply_crop=apply_crop)
            pixmap = self.get_cached_pixmap(display_index, apply_crop=apply_crop)
            entries.append((display_index, pixmap, q_image, current_left, current_top))
            if layout_vertical:
                current_top += slot_height + spacing
            else:
                current_left += slot_width + spacing

        active_entry = next((entry for entry in entries if entry[0] == current_index), entries[-1])
        active_x = active_entry[3]
        active_y = active_entry[4]

        if hasattr(self, 'pixmap_item'):
            self.pixmap_item.setPixmap(active_pixmap)
        else:
            self.pixmap_item = self.scene.addPixmap(active_pixmap)
        self.pixmap_item.setZValue(-100)
        self.pixmap_item.setPos(active_x, active_y)

        self.clear_context_pixmaps()
        for display_index, pixmap, _, x_pos, y_pos in entries:
            if display_index is None:
                border_color = QColor(160, 160, 160, 180) if darkdetect.isDark() else QColor(175, 175, 175, 180)
                fill_color = QColor(255, 255, 255, 18) if darkdetect.isDark() else QColor(0, 0, 0, 10)
                placeholder_item = self.scene.addRect(
                    x_pos,
                    y_pos,
                    slot_width,
                    slot_height,
                    QPen(border_color, 1, Qt.DashLine),
                    QBrush(fill_color),
                )
                placeholder_item.setZValue(-110)
                self.placeholder_items.append(placeholder_item)
                continue
            if display_index == current_index:
                continue
            context_item = self.scene.addPixmap(pixmap)
            context_item.setZValue(-120)
            context_item.setPos(x_pos, y_pos)
            self.context_pixmap_items.append(context_item)

        scene_rect = self.pixmap_item.sceneBoundingRect()
        for item in self.context_pixmap_items:
            scene_rect = scene_rect.united(item.sceneBoundingRect())
        for item in self.placeholder_items:
            scene_rect = scene_rect.united(item.sceneBoundingRect())
        self.view.setSceneRect(scene_rect)
        self.displayed_image_edit_crop_applied = bool(apply_crop)
        self.image_width = self.get_raw_image_dimensions(current_index)[0]
        return active_image

    def displayMarkedRegions(self):
        # Delegate circle redraw to the controller so add/edit/delete and frame
        # redraw all use the same anchoring + cell-preservation path.
        self.cell_controller.redraw_current_cells()

    def interpolate_and_displayMarkedRegions(self, index, preview=False):
        if (not self.cell_items) and (not self.keyframe_list):
            if self.rendered_cell_items:
                for item in list(self.rendered_cell_items):
                    if shiboken6.isValid(item) and item.scene() is self.scene:
                        self.scene.removeItem(item)
                self.rendered_cell_items = []
            return
        self.cell_controller.redraw_interpolated_cells(index, preview=preview)

    def anchor_cell_items_to_current_image(self, cell_items):
        return self.cell_controller.anchor_to_current_image(cell_items)

    def updateRadiusTextbox(self):
        if self.circle_radius is not None:
            self.radius_textbox.setText(self.format_numeric_value(self.circle_radius))
            if hasattr(self, "circle_radius_spinbox"):
                self.circle_radius_spinbox.blockSignals(True)
                self.circle_radius_spinbox.setValue(float(self.circle_radius))
                self.circle_radius_spinbox.blockSignals(False)
            if hasattr(self, "grid_radius_spinbox"):
                self.grid_radius_spinbox.blockSignals(True)
                self.grid_radius_spinbox.setValue(float(self.circle_radius))
                self.grid_radius_spinbox.blockSignals(False)
        else:
            self.radius_textbox.clear()  # Clear the text box if circle radius is None

    def updateCircleRadius_from_textedit(self):
        try:
            radius = float(self.radius_textbox.text())
            if radius != self.circle_radius:
                self.circle_radius = radius
                if self.tool_mode in {'select', 'edit-new', 'grid', 'edit-group'}:
                    self.update_grid_preview()
                self.sync_tool_options_panel()
        except ValueError:
            pass  # Ignore non-integer input


    def updateZoomTextbox(self):
        zoom_factor = self.view.transform().m11()  # Current zoom level
        self.zoom_textbox.setText(f"{zoom_factor * 100:.0f}")  # Update the zoom level text box

    def updateZoomLevel(self):
        try:
            zoom_percentage = float(self.zoom_textbox.text())
            zoom_factor = zoom_percentage / 100.0
            self.view.setTransform(QTransform().scale(zoom_factor, zoom_factor))
            self.updateZoomTextbox()  # Update the zoom text box after manual change
        except ValueError:
            pass  # Ignore non-numeric input
    
    def updateButtonStates(self):
        frame_count = self.frame_count()
        has_frames = frame_count > 0
        has_selected_cells = (
            hasattr(self, "cell_controller")
            and hasattr(self, "scene")
            and bool(self.get_selected_cell_items())
        )
        # Update left button state
        if (self.image_slider.value() <= 0) or self.output_state or (not has_frames):
            self.leftButton.setEnabled(False)
        else:
            self.leftButton.setEnabled(True)

        # Update right button state
        if (self.image_slider.value() >= frame_count - 1) or self.output_state or (not has_frames):
            self.rightButton.setEnabled(False)
        else:
            self.rightButton.setEnabled(True)

        if self.output_state or (not has_frames):
            self.keyframe_toggle_button.setEnabled(False)
            self.flag_toggle_button.setEnabled(False)
            self.analysis_start_toggle_button.setEnabled(False)
            self.analysis_end_toggle_button.setEnabled(False)
            self.zoom_slider.setEnabled(False)
        else:
            self.keyframe_toggle_button.setEnabled(True)
            self.flag_toggle_button.setEnabled(has_selected_cells)
            self.analysis_start_toggle_button.setEnabled(True)
            self.analysis_end_toggle_button.setEnabled(True)
            self.zoom_slider.setEnabled(True)

    def set_undo_status(self):
        if not getattr(self, "undo_redo_enabled", True):
            self.undo_action.setEnabled(False)
            return
        if (not hasattr(self, "undo_stack")) or (not shiboken6.isValid(self.undo_stack)):
            return
        if self.undo_stack.canUndo():
            self.undo_action.setEnabled(True)
        else:
            self.undo_action.setEnabled(False)

    def set_redo_status(self):
        if not getattr(self, "undo_redo_enabled", True):
            self.redo_action.setEnabled(False)
            return
        if (not hasattr(self, "undo_stack")) or (not shiboken6.isValid(self.undo_stack)):
            return
        if self.undo_stack.canRedo():
            self.redo_action.setEnabled(True)
        else:
            self.redo_action.setEnabled(False)

    def undo(self):
        if not getattr(self, "undo_redo_enabled", True):
            return
        if (not hasattr(self, "undo_stack")) or (not shiboken6.isValid(self.undo_stack)):
            return
        if self.undo_stack.canUndo():
            self.cancel_transient_history_state()
            action_text = self.undo_stack.undoText() or "Undo"
            self.log(f"Undo: {action_text}")
            self.undo_stack.undo()
            self.set_undo_status()
            self.set_redo_status()

    def redo(self):
        if not getattr(self, "undo_redo_enabled", True):
            return
        if (not hasattr(self, "undo_stack")) or (not shiboken6.isValid(self.undo_stack)):
            return
        if self.undo_stack.canRedo():
            self.cancel_transient_history_state()
            action_text = self.undo_stack.redoText() or "Redo"
            self.log(f"Redo: {action_text}")
            self.undo_stack.redo()
            self.set_undo_status()
            self.set_redo_status()

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        no_modifiers = modifiers == Qt.NoModifier
        windows_ctrl_y_redo = (
            IS_WINDOWS
            and event.key() == Qt.Key_Y
            and bool(modifiers & Qt.ControlModifier)
            and not bool(modifiers & (Qt.ShiftModifier | Qt.AltModifier | Qt.MetaModifier))
        )

        if event.matches(QKeySequence.Redo) or windows_ctrl_y_redo:
            if self.redo_action.isEnabled():
                self.redo_action.trigger()
                self.key_press_toolbutton_highlight(self.redo_action)
            return
        elif event.matches(QKeySequence.Undo):
            if self.undo_action.isEnabled():
                self.undo_action.trigger()
                self.key_press_toolbutton_highlight(self.undo_action)
            return
        elif event.key() == Qt.Key_Z and no_modifiers:
            if self.pan_tool_action.isEnabled():
                self.pan_tool_action.trigger()
                self.key_press_toolbutton_highlight(self.pan_tool_action)
        elif event.key() == Qt.Key_S and no_modifiers:
            # Select Add cell key
            if self.select_tool_action.isEnabled():
                self.select_tool_action.trigger() # S for Add Cell
                self.key_press_toolbutton_highlight(self.select_tool_action)
        elif event.key() == Qt.Key_D and no_modifiers:
            # Select Add cell key
            if self.deselect_tool_action.isEnabled():
                self.deselect_tool_action.trigger() # D for Delete Cells
                self.key_press_toolbutton_highlight(self.deselect_tool_action)
        elif event.key() == Qt.Key_G and no_modifiers:
            if self.grid_tool_action.isEnabled():
                self.grid_tool_action.trigger()
                self.key_press_toolbutton_highlight(self.grid_tool_action)
        elif event.key() == Qt.Key_E and no_modifiers:
            # Select Add cell key
            if self.edit_tool_action.isEnabled():
                self.edit_tool_action.trigger() # E for Delete Cells
                self.key_press_toolbutton_highlight(self.edit_tool_action)
        elif event.key() == Qt.Key_A and no_modifiers:
            # Select Default Cursor Key
            if self.reset_cursor_action.isEnabled():
                self.reset_cursor_action.trigger() # A for Delete Cells
                self.key_press_toolbutton_highlight(self.reset_cursor_action)
        elif event.key() == Qt.Key_Comma and no_modifiers:
            if self.leftButton.isEnabled():
                self.leftButton.click()
                self.key_press_button_highlight(self.leftButton)
        elif event.key() == Qt.Key_Period and no_modifiers:
            if self.rightButton.isEnabled():
                self.rightButton.click()
                self.key_press_button_highlight(self.rightButton)

        elif (event.key() == Qt.Key_Space) and (self.space_held == False) and no_modifiers:
            # Temporarily switch to zoom and pan

            if self.has_frames():
                # Store original_tool_mode in temporary data
                self.temporary_event_data["original_tool_mode"] = self.tool_mode

                for key, value in self.tool_name_dict.items():
                    if key in ['pan', self.tool_mode]:
                        value.setEnabled(True)
                    elif (self.cell_controller.is_any_edit_mode()) and (key in ["edit-choose", "edit-new"]):
                        value.setEnabled(True)
                    else:
                        value.setEnabled(False)

                if self.pan_tool_action.isEnabled():
                    self.enter_temporary_pan_mode()
                    self.key_press_toolbutton_highlight(self.pan_tool_action)

                self.space_held = True

        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:

            if self.has_frames():
                # Retrieve the original tool mode from the temporary data dict
                self.space_held = False

                original_tool_mode = self.temporary_event_data.pop("original_tool_mode", None)
                if original_tool_mode is None:
                    for key, value in self.tool_name_dict.items():
                        value.setEnabled(True)
                    return

                if original_tool_mode == "pan":
                    self.pan_tool_action.trigger()
                    self.key_press_toolbutton_highlight(self.pan_tool_action)
                elif original_tool_mode == "cursor":
                    self.apply_cursor_tool_ui()
                    self.key_press_toolbutton_highlight(self.reset_cursor_action)
                elif original_tool_mode == "select":
                    self.apply_select_tool_ui(preserve_preview=True)
                    self.key_press_toolbutton_highlight(self.select_tool_action)
                elif original_tool_mode == "deselect":
                    self.apply_deselect_tool_ui()
                    self.key_press_toolbutton_highlight(self.deselect_tool_action)
                elif original_tool_mode in ["edit-choose", "edit-new", "edit-group"]:
                    self.temporary_event_data["previous_edit_mode"] = original_tool_mode
                    self.editTool(self.edit_tool_action.isChecked())
                    self.key_press_toolbutton_highlight(self.edit_tool_action)
                elif original_tool_mode == "grid":
                    self.apply_grid_tool_ui(preserve_preview=True)
                    self.key_press_toolbutton_highlight(self.grid_tool_action)
                elif original_tool_mode == "image-edit":
                    self.apply_image_edit_tool_ui()
                    self.key_press_toolbutton_highlight(self.image_edit_action)
                    

                for key, value in self.tool_name_dict.items():
                    value.setEnabled(True)

        else:
            super().keyReleaseEvent(event)

    @staticmethod
    def normalize_analysis_marker_ranges(start_frames, end_frames, frame_count):
        return normalize_analysis_marker_ranges(start_frames, end_frames, frame_count)

    def analysis_frame_ranges(self):
        return self.normalize_analysis_marker_ranges(
            self.analysis_start_frame_list,
            self.analysis_end_frame_list,
            self.frame_count(),
        )

    @staticmethod
    def frame_count_from_ranges(frame_ranges):
        return frame_count_from_ranges(frame_ranges)

    def outputData(self):
        if not self.has_frames():
            self.log("No images loaded")
            return

        self.pending_analysis_before_state = self.capture_data_state()
        self.analysis_progress_start_index = int(getattr(self, "last_committed_image_index", self.image_index))
        self.analysis_progress_navigation_suppressed = True
        self.log("Start analyzing")

        analysis_frame_ranges = self.analysis_frame_ranges()
        analysis_frame_count = self.frame_count_from_ranges(analysis_frame_ranges)
        if analysis_frame_count <= 0:
            self.log("No frames inside analysis windows")
            return
        if analysis_frame_ranges != [(0, self.frame_count() - 1)]:
            range_text = ", ".join(f"{start}-{end}" for start, end in analysis_frame_ranges)
            self.log(f"Analysis windows: {range_text}")

        list_of_cell_items = self.out_put_interpolation(analysis_frame_ranges)

        self.worker = Image_analysis_thread(
            None,
            self.imagePaths.copy(),
            self.imageNames.copy(),
            list_of_cell_items,
            image_edit_exposure=self.image_edit_exposure,
            image_edit_contrast=self.image_edit_contrast,
            image_edit_uniform_exposure_offsets=copy.deepcopy(getattr(self, "image_edit_uniform_exposure_offsets", {})),
            image_edit_crop_state=self.current_image_edit_crop_state(),
            freeze_finder_width=self.freeze_finder_width,
            freeze_finder_prominence=self.freeze_finder_prominence,
            freeze_finder_head_extend_points=self.freeze_finder_head_extend_points,
            freeze_finder_tail_extend_points=self.freeze_finder_tail_extend_points,
            convolution_half_window_points=self.convolution_half_window_points,
            convolution_ramp_points=self.convolution_ramp_points,
            freeze_finder_detect_brightening=self.freeze_finder_detect_brightening,
            video_grayscale_mode=self.video_grayscale_mode,
            frame_source=self.active_frame_source(),
            analysis_frame_ranges=analysis_frame_ranges,
        )
        self.worker.analysis_done.connect(self.onAnalysisDone)
        self.updateButtonStates()
        self.zoom_slider.setValue(1)
        
        self.reset_cursor_action.trigger()
        self.select_tool_action.setEnabled(False)
        self.grid_tool_action.setEnabled(False)
        self.deselect_tool_action.setEnabled(False)
        self.edit_tool_action.setEnabled(False)
        self.remove_selected_action.setEnabled(False)
        self.new_session_action.setEnabled(False)

        self.image_slider.setEnabled(False)
        self.image_slider.setValue(0)
        self.timer = time.time()
        self.output_state = True
        self.update_session_actions_state()
        self.worker.start()
        self.worker.finished.connect(self.onThreadFinished)

    def out_put_interpolation(self, analysis_frame_ranges=None):
        frame_count = self.frame_count()
        list_of_cell_items = [[] for _ in range(frame_count)]
        frame_ranges = analysis_frame_ranges or [(0, frame_count - 1)]
        for start, end in frame_ranges:
            for an_image_index in range(int(start), int(end) + 1):
                if 0 <= an_image_index < frame_count:
                    list_of_cell_items[an_image_index] = self.keyframe_interpolation(an_image_index)
        
        return list_of_cell_items
            
    def onAnalysisDone(self, index, results):
        # Finish anayzing each image
        # self.log(f"Analyzed image {results['file_name']}")
        self.enqueue_analysis_progress_frame(index)
        

    def onThreadFinished(self):
        # Finish anayzing all images
        before_state = self.pending_analysis_before_state
        self.pending_analysis_before_state = None
        if hasattr(self, "analysis_progress_timer"):
            self.analysis_progress_timer.stop()
        self.flush_pending_analysis_progress()
        worker = self.worker
        endTime = time.time()
        elapsed_time = endTime - self.timer
        self.log("Analysis complete")
        if getattr(worker, 'freeze_output_path', None):
            self.log(f"Saved freeze detection output at {worker.freeze_output_path}")
        self.log(f"Time used: {elapsed_time:.3f} seconds")
        timing = getattr(worker, "analysis_timing", {}) or {}
        if timing:
            frames_analyzed = int(timing.get("frames_analyzed", 0) or 0)
            frame_count = int(timing.get("frame_count", 0) or 0)
            cell_count = int(timing.get("cell_count", 0) or 0)
            worker_seconds = float(timing.get("total_worker_seconds", elapsed_time) or 0.0)
            fps = frames_analyzed / worker_seconds if worker_seconds > 0 else 0.0
            cell_frames_per_second = (
                (frames_analyzed * cell_count) / worker_seconds
                if worker_seconds > 0 and cell_count > 0
                else 0.0
            )
            self.log(
                "Analysis timing: "
                f"source={timing.get('source_kind', 'unknown')}, "
                f"video_gray={timing.get('video_grayscale_mode', 'n/a')}, "
                f"frames={frames_analyzed}/{frame_count}, "
                f"cells={cell_count}, "
                f"decode+gray={float(timing.get('decode_gray_seconds', 0.0)):.3f}s, "
                f"ROI mean={float(timing.get('grayscale_mean_seconds', 0.0)):.3f}s, "
                f"freeze finder={float(timing.get('freeze_finder_seconds', 0.0)):.3f}s, "
                f"result tables={float(timing.get('result_build_seconds', 0.0)):.3f}s"
            )
            self.log(
                "Analysis rate: "
                f"{fps:.2f} frames/s"
                + (
                    f", {cell_frames_per_second:.0f} cell-frames/s"
                    if cell_count > 0
                    else ""
                )
            )
        self.last_grayscale_output_path = getattr(worker, 'filePath', None)
        self.last_freeze_output_path = getattr(worker, 'freeze_output_path', None)
        self.timer = None
        self.output_state = False
        self.image_slider.setEnabled(True)
        self.updateButtonStates()
        self.select_tool_action.setEnabled(True)
        self.grid_tool_action.setEnabled(True)
        self.deselect_tool_action.setEnabled(True)
        self.edit_tool_action.setEnabled(True)
        self.update_session_actions_state()
        self.grayscale_results_headers = getattr(worker, 'grayscale_result_headers', [])
        self.grayscale_results_rows = getattr(worker, 'grayscale_result_rows', [])
        self.freeze_results_headers = getattr(worker, 'freeze_result_headers', [])
        self.freeze_results_rows = getattr(worker, 'freeze_result_rows', [])
        self.invalidate_freeze_count_timeseries_results("analysis results changed")
        self.update_results_tables()
        if self.grayscale_results_headers or self.freeze_results_headers:
            if hasattr(self, "results_table_tabs"):
                self.results_table_tabs.setCurrentIndex(0 if self.grayscale_results_headers else 1)
            self.show_dock_widget(self.results_tables_dock)
        if self.grayscale_results_rows:
            self.show_dock_widget(self.grayscale_plot_dock)
        final_frame = int(getattr(self, "last_committed_image_index", self.image_index))
        start_frame = self.analysis_progress_start_index
        self.analysis_progress_navigation_suppressed = False
        self.analysis_progress_start_index = None
        self.pending_analysis_progress_index = None
        if (
            start_frame is not None
            and not self.history_restoring
            and int(start_frame) != final_frame
        ):
            self.log(f"Change Frame: {int(start_frame)} -> {final_frame}")
            self.push_navigation_history("Change Frame", int(start_frame), final_frame)
        if before_state is not None:
            self.push_data_history("Run Analysis", before_state)
        worker.deleteLater()
        self.worker = None


    def key_press_toolbutton_highlight(self, an_action):
        toolbutton = self.toolbar.widgetForAction(an_action)
        if toolbutton:
            # Set a unique object name for styling
            toolbutton.setObjectName("triggeredButton")
            current_stylesheet = self.toolbar.styleSheet()
            if darkdetect.isDark():
                style_sheet_to_add = "QToolButton#triggeredButton {background-color: rgba(10, 132, 255, 120)}"
            else:
                style_sheet_to_add = "QToolButton#triggeredButton {background-color: rgba(0, 122, 255, 200)}"
            self.toolbar.setStyleSheet(current_stylesheet + style_sheet_to_add)
            QTimer.singleShot(150, lambda: self.reset_toolbar_stylesheet())
    
    def key_press_button_highlight(self, button):
        if button:
            # Set a unique object name for styling
            button.setObjectName("triggeredButton")
            current_stylesheet = button.styleSheet()
            if darkdetect.isDark():
                style_sheet_to_add = "QPushButton#triggeredButton {background-color: rgba(10, 132, 255, 120)}"
            else:
                style_sheet_to_add = "QPushButton#triggeredButton {background-color: rgba(0, 122, 255, 200)}"
            button.setStyleSheet(current_stylesheet + style_sheet_to_add)
            QTimer.singleShot(150, lambda: self.reset_button_stylesheet())
            button.setObjectName(None)

    def reset_toolbar_stylesheet(self, theme=None):
        for action in self.toolbar.actions():
            button = self.toolbar.widgetForAction(action)
            button.setObjectName(None)
        if theme == "Dark" or darkdetect.isDark():
            self.toolbar.setStyleSheet(icescopy_stylesheet.darkmode_toolbar_style_sheet)
        else:
            self.toolbar.setStyleSheet(icescopy_stylesheet.light_mode_toolbar_style_sheet)

    def sync_zoom_slider_row_geometry(self):
        if not IS_WINDOWS:
            return
        zoom_slider = getattr(self, "zoom_slider", None)
        row_widget = getattr(self, "slider_buttons_widget", None)
        row_layout = getattr(self, "slider_buttons_layout", None)
        if zoom_slider is None or row_widget is None or row_layout is None:
            return

        zoom_slider.ensurePolished()
        row_widget.ensurePolished()

        zoom_slider_height = max(28, zoom_slider.sizeHint().height(), zoom_slider.minimumSizeHint().height())
        zoom_slider.setFixedHeight(int(zoom_slider_height))
        zoom_slider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        button_heights = [
            widget.sizeHint().height()
            for widget in (
                getattr(self, "keyframe_toggle_button", None),
                getattr(self, "flag_toggle_button", None),
                getattr(self, "analysis_start_toggle_button", None),
                getattr(self, "analysis_end_toggle_button", None),
                getattr(self, "leftButton", None),
                getattr(self, "rightButton", None),
            )
            if widget is not None
        ]
        content_height = max(button_heights + [zoom_slider.height()])
        margins = row_layout.contentsMargins()
        row_height = int(content_height + margins.top() + margins.bottom())
        row_widget.setFixedHeight(row_height)
        row_widget.updateGeometry()
    
    def reset_slider_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.image_slider.setStyleSheet(icescopy_stylesheet.dark_mode_time_line_slider_style)
            self.zoom_slider.setStyleSheet(icescopy_stylesheet.dark_zoom_slider_stylesheet)
        else:
            self.image_slider.setStyleSheet(icescopy_stylesheet.light_mode_time_line_slider_style)
            self.zoom_slider.setStyleSheet(icescopy_stylesheet.light_zoom_slider_stylesheet)
        self.image_slider.sync_timeline_geometry()
        if platform.system() == "Windows":
            self.sync_zoom_slider_row_geometry()
            self.image_slider.updateGeometry()
            if self.view_slider_widget.layout() is not None:
                self.view_slider_widget.layout().activate()
    
    def reset_status_bar_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.statusBar.setStyleSheet(icescopy_stylesheet.dark_mode_status_bar_stylesheet)
            self.radius_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
            self.zoom_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
            self.image_textbox.setStyleSheet(icescopy_stylesheet.dark_mode_line_edit_style_sheet)
        else:
            self.statusBar.setStyleSheet(icescopy_stylesheet.light_mode_status_bar_stylesheet)
            self.radius_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
            self.zoom_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
            self.image_textbox.setStyleSheet(icescopy_stylesheet.light_mode_line_edit_style_sheet)
    
    def reset_button_stylesheet(self, theme=None):
        if darkdetect.isDark():
            self.keyframe_toggle_button.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.leftButton.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.rightButton.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.flag_toggle_button.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.analysis_start_toggle_button.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
            self.analysis_end_toggle_button.setStyleSheet(icescopy_stylesheet.dark_mode_button_stylesheet)
        else:
            self.keyframe_toggle_button.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.leftButton.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.rightButton.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.flag_toggle_button.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.analysis_start_toggle_button.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)
            self.analysis_end_toggle_button.setStyleSheet(icescopy_stylesheet.light_mode_button_stylesheet)

    def toolbar_icon(self, mode_folder, icon_name):
        return QIcon(os.path.join(resources_dir, "tool_bar", mode_folder, "large", icon_name))

    def reset_toolbar_icon(self, theme=None):
        mode_folder = "dark-mode" if darkdetect.isDark() else "light-mode"
        self.preferences_action.setIcon(self.toolbar_icon(mode_folder, "gear.svg"))
        self.add_source_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-add.svg"))
        self.add_images_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-add.svg"))
        self.add_folder_action.setIcon(self.toolbar_icon(mode_folder, "folder-document.svg"))
        self.new_session_action.setIcon(self.toolbar_icon(mode_folder, "document-new-filled.svg"))
        self.open_session_action.setIcon(self.toolbar_icon(mode_folder, "folder-document.svg"))
        self.remove_selected_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-remove.svg"))
        self.clear_images_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-trash.svg"))
        self.save_session_action.setIcon(self.toolbar_icon(mode_folder, "save-document.svg"))
        self.run_analysis_action.setIcon(self.toolbar_icon(mode_folder, "media-play-filled.svg"))
        self.output_results_action.setIcon(self.toolbar_icon(mode_folder, "document-action-arrow-down-filled.svg"))
        self.sort_images_action.setIcon(self.toolbar_icon(mode_folder, "sort.svg"))
        self.sample_manager_action.setIcon(self.toolbar_icon(mode_folder, "menu-hamburger-tag.svg"))
        self.image_edit_action.setIcon(self.toolbar_icon(mode_folder, "image-multiple-edit-filled.svg"))
        self.viewer_single_action.setIcon(self.toolbar_icon(mode_folder, "page-landscape-number-1.svg"))
        self.viewer_double_action.setIcon(self.toolbar_icon(mode_folder, "page-landscape-number-2.svg"))
        self.viewer_triple_action.setIcon(self.toolbar_icon(mode_folder, "page-landscape-number-3.svg"))
        self.update_viewer_orientation_toggle_action(mode_folder=mode_folder)
        self.undo_action.setIcon(self.toolbar_icon(mode_folder, "command-undo.svg"))
        self.redo_action.setIcon(self.toolbar_icon(mode_folder, "command-redo.svg"))
        self.reset_cursor_action.setIcon(self.toolbar_icon(mode_folder, "pointer.svg"))
        self.select_tool_action.setIcon(self.toolbar_icon(mode_folder, "media-record-add-filled.svg"))
        self.grid_tool_action.setIcon(self.toolbar_icon(mode_folder, "media-record-table-filled.svg"))
        self.edit_tool_action.setIcon(self.toolbar_icon(mode_folder, "media-record-edit-filled.svg"))
        self.deselect_tool_action.setIcon(self.toolbar_icon(mode_folder, "media-record-remove-filled.svg"))
        self.pan_tool_action.setIcon(self.toolbar_icon(mode_folder, "hand-left.svg"))

    def update_viewer_mode_actions(self):
        self.viewer_single_action.setChecked(self.viewer_image_count == 1)
        self.viewer_double_action.setChecked(self.viewer_image_count == 2)
        self.viewer_triple_action.setChecked(self.viewer_image_count == 3)
        self.update_viewer_orientation_toggle_action()

    def update_viewer_orientation_toggle_action(self, mode_folder=None):
        if mode_folder is None:
            mode_folder = "dark-mode" if darkdetect.isDark() else "light-mode"

        if self.is_viewer_split_vertical():
            self.viewer_orientation_toggle_action.setText("Stack Left to Right")
            self.viewer_orientation_toggle_action.setToolTip("Switch two- and three-image view to left-right layout")
            self.viewer_orientation_toggle_action.setIcon(self.toolbar_icon(mode_folder, "view-separate-vertical.svg"))
        else:
            self.viewer_orientation_toggle_action.setText("Stack Top to Bottom")
            self.viewer_orientation_toggle_action.setToolTip("Switch two- and three-image view to top-down layout")
            self.viewer_orientation_toggle_action.setIcon(self.toolbar_icon(mode_folder, "view-separate-horizontal.svg"))
        self.viewer_orientation_toggle_action.setEnabled(
            bool(getattr(self, "session_active", False))
            and (not getattr(self, "output_state", False))
            and int(getattr(self, "viewer_image_count", 1)) in (2, 3)
        )

    def set_viewer_image_count(self, count):
        self.viewer_image_count = count
        self.update_viewer_mode_actions()
        self.log(f"Viewer layout: show {count} image(s)")
        if self.has_frames():
            self.updateImage(self.image_index)

    def toggle_viewer_split_orientation(self):
        self.viewer_split_orientation = "vertical" if not self.is_viewer_split_vertical() else "horizontal"
        self.update_viewer_orientation_toggle_action()
        layout_label = "top-down" if self.is_viewer_split_vertical() else "left-right"
        self.log(f"Viewer split layout: {layout_label}")
        if self.has_frames() and self.viewer_image_count in (2, 3):
            self.updateImage(self.image_index)

    def _analysis_triangle_icon(self, direction, active):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(52, 199, 89, 255) if direction == "start" else QColor(255, 149, 0, 255)
        inactive_color = QColor(128, 128, 128, 190)
        if direction == "start":
            points = QPolygonF([
                QPointF(11, 10),
                QPointF(11, 22),
                QPointF(22, 16),
            ])
        else:
            points = QPolygonF([
                QPointF(21, 10),
                QPointF(21, 22),
                QPointF(10, 16),
            ])
        if active:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
        else:
            pen = QPen(inactive_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(points)
        painter.end()
        return QIcon(pixmap)

    def update_toggle_keyframe_button_icon(self, theme=None):
        is_keyframe = self.image_index in self.keyframe_list
        if darkdetect.isDark():
            if is_keyframe:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'diamond_key.png')))
            else:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'diamond.png')))
        else:
            if is_keyframe:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'diamond_key_2.png')))
            else:
                self.keyframe_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'diamond_2.png')))
    
    def update_toggle_flagging_button_icon(self, theme=None):
        is_flagged, _has_all = self.selected_cells_freeze_state_at_current_frame()
        if darkdetect.isDark():
            if is_flagged:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'flag_red.png')))
            else:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'flag.png')))
        else:
            if is_flagged:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'flag_red_2.png')))
            else:
                self.flag_toggle_button.setIcon(QIcon(os.path.join(ui_images_dir, 'flag_2.png')))

    def update_toggle_analysis_start_button_icon(self, theme=None):
        is_start = self.image_index in self.analysis_start_frame_list
        self.analysis_start_toggle_button.setIcon(self._analysis_triangle_icon("start", is_start))
        self.analysis_start_toggle_button.setIconSize(QSize(20, 20))

    def update_toggle_analysis_end_button_icon(self, theme=None):
        is_end = self.image_index in self.analysis_end_frame_list
        self.analysis_end_toggle_button.setIcon(self._analysis_triangle_icon("end", is_end))
        self.analysis_end_toggle_button.setIconSize(QSize(20, 20))

    def reset_button_icon(self, theme=None):
        self.update_toggle_keyframe_button_icon()
        self.update_toggle_flagging_button_icon()
        self.update_toggle_analysis_start_button_icon()
        self.update_toggle_analysis_end_button_icon()
        if darkdetect.isDark():
            self.leftButton.setIcon(QIcon(os.path.join(ui_images_dir, "caret-left.png")))
            self.rightButton.setIcon(QIcon(os.path.join(ui_images_dir, 'caret-right.png')))
        else:
            self.leftButton.setIcon(QIcon(os.path.join(ui_images_dir, 'caret-left_2.png')))
            self.rightButton.setIcon(QIcon(os.path.join(ui_images_dir, 'caret-right_2.png')))

    def update_cell_items_selectable_state(self): # update items in the scenes, called when changing tools.
        self.cell_controller.update_scene_selectable_state()

    def unselect_all_cell_items(self):
        self.cell_controller.clear_scene_selection()
    
    def reset_cell_items_edit_chosen(self): # update items in the data list, called by the self.displayMarkedRegions()
        self.cell_controller.reset_edit_chosen()
        self.refresh_grayscale_plot()

    def switch_light_dark_mode(self, theme=None):
        self.reset_toolbar_stylesheet(theme)
        self.reset_toolbar_icon(theme)
        self.reset_slider_stylesheet(theme)
        self.reset_button_icon(theme)
        self.reset_status_bar_stylesheet(theme)
        self.reset_button_stylesheet(theme)

    def resizeEvent(self, event):
        super().resizeEvent(event)  # Call the base class resizeEvent
        self.image_slider.set_custom_ticks()
        self.zoom_slider_set_maximum()

    def closeEvent(self, event):
        self.stop_video_preview_decoder()
        frame_source = getattr(self, "frame_source", None)
        if frame_source is not None:
            close_source = getattr(frame_source, "close", None)
            if callable(close_source):
                close_source()
        super().closeEvent(event)

    def load_preferences_from_xml(self):
        tree = ET.parse(os.path.join(resources_dir,"preferences.xml"))
        root = tree.getroot()
        
        preferences = {}

        circle_radius_element = root.find('DefaultCircleRadius')
        if circle_radius_element is not None and circle_radius_element.text is not None:
            preferences['DefaultCircleRadius'] = float(circle_radius_element.text)

        maximum_zoom_element = root.find('MaximumZoom')
        if maximum_zoom_element is not None and maximum_zoom_element.text is not None:
            preferences['MaximumZoom'] = float(maximum_zoom_element.text)
        
        pen_width_element = root.find('PenWidth')
        if pen_width_element is not None and pen_width_element.text is not None:
            preferences['PenWidth'] = float(pen_width_element.text)

        dot_size_element = root.find('DotSize')
        if dot_size_element is not None and dot_size_element.text is not None:
            preferences['DotSize'] = float(dot_size_element.text)

        slide_maxzoom_element = root.find('SliderMaxZoomPixelInterval')
        if slide_maxzoom_element is not None and slide_maxzoom_element.text is not None:
            preferences['SliderMaxZoomPixelInterval'] = float(slide_maxzoom_element.text)
        
        slide_tickpix_element = root.find('SliderTickPixelInterval')
        if slide_tickpix_element is not None and slide_tickpix_element.text is not None:
            preferences['SliderTickPixelInterval'] = float(slide_tickpix_element.text)

        undo_limit_element = root.find('UndoLimit')
        if undo_limit_element is not None and undo_limit_element.text is not None:
            preferences['UndoLimit'] = int(float(undo_limit_element.text))

        sample_name_pattern_element = root.find('SampleNamePattern')
        if sample_name_pattern_element is not None and sample_name_pattern_element.text is not None:
            preferences['SampleNamePattern'] = sample_name_pattern_element.text

        preferences["SampleMetadataSchema"] = sample_metadata_schema_from_xml(root)

        viewer_image_count_element = root.find('ViewerImageCount')
        if viewer_image_count_element is not None and viewer_image_count_element.text is not None:
            preferences['ViewerImageCount'] = int(float(viewer_image_count_element.text))

        sort_mode_element = root.find('SortMode')
        if sort_mode_element is not None and sort_mode_element.text is not None:
            preferences['SortMode'] = sort_mode_element.text

        grid_rows_element = root.find('GridRows')
        if grid_rows_element is not None and grid_rows_element.text is not None:
            preferences['GridRows'] = int(float(grid_rows_element.text))

        grid_columns_element = root.find('GridColumns')
        if grid_columns_element is not None and grid_columns_element.text is not None:
            preferences['GridColumns'] = int(float(grid_columns_element.text))

        grid_horizontal_pitch_element = root.find('GridHorizontalPitch')
        if grid_horizontal_pitch_element is not None and grid_horizontal_pitch_element.text is not None:
            preferences['GridHorizontalPitch'] = float(grid_horizontal_pitch_element.text)

        grid_vertical_pitch_element = root.find('GridVerticalPitch')
        if grid_vertical_pitch_element is not None and grid_vertical_pitch_element.text is not None:
            preferences['GridVerticalPitch'] = float(grid_vertical_pitch_element.text)

        grid_rotation_degrees_element = root.find('GridRotationDegrees')
        if grid_rotation_degrees_element is not None and grid_rotation_degrees_element.text is not None:
            preferences['GridRotationDegrees'] = float(grid_rotation_degrees_element.text)

        grid_cell_id_direction_element = root.find('GridCellIdDirection')
        if grid_cell_id_direction_element is not None and grid_cell_id_direction_element.text is not None:
            preferences['GridCellIdDirection'] = str(grid_cell_id_direction_element.text)

        radius_wheel_step_element = root.find('RadiusWheelStep')
        if radius_wheel_step_element is not None and radius_wheel_step_element.text is not None:
            preferences['RadiusWheelStep'] = float(radius_wheel_step_element.text)

        grid_pitch_wheel_step_element = root.find('GridPitchWheelStep')
        if grid_pitch_wheel_step_element is not None and grid_pitch_wheel_step_element.text is not None:
            preferences['GridPitchWheelStep'] = float(grid_pitch_wheel_step_element.text)

        grid_tilt_wheel_step_element = root.find('GridTiltWheelStep')
        if grid_tilt_wheel_step_element is not None and grid_tilt_wheel_step_element.text is not None:
            preferences['GridTiltWheelStep'] = float(grid_tilt_wheel_step_element.text)

        freeze_finder_width_element = root.find('FreezeFinderWidth')
        if freeze_finder_width_element is not None and freeze_finder_width_element.text is not None:
            preferences['FreezeFinderWidth'] = float(freeze_finder_width_element.text)

        freeze_finder_prominence_element = root.find('FreezeFinderProminence')
        if freeze_finder_prominence_element is not None and freeze_finder_prominence_element.text is not None:
            preferences['FreezeFinderProminence'] = float(freeze_finder_prominence_element.text)

        freeze_finder_head_extend_points_element = root.find('FreezeFinderHeadExtendPoints')
        if (
            freeze_finder_head_extend_points_element is not None
            and freeze_finder_head_extend_points_element.text is not None
        ):
            preferences['FreezeFinderHeadExtendPoints'] = int(float(freeze_finder_head_extend_points_element.text))

        freeze_finder_tail_extend_points_element = root.find('FreezeFinderTailExtendPoints')
        if (
            freeze_finder_tail_extend_points_element is not None
            and freeze_finder_tail_extend_points_element.text is not None
        ):
            preferences['FreezeFinderTailExtendPoints'] = int(float(freeze_finder_tail_extend_points_element.text))

        convolution_half_window_points_element = root.find('ConvolutionHalfWindowPoints')
        if (
            convolution_half_window_points_element is not None
            and convolution_half_window_points_element.text is not None
        ):
            preferences['ConvolutionHalfWindowPoints'] = int(float(convolution_half_window_points_element.text))

        convolution_ramp_points_element = root.find('ConvolutionRampPoints')
        if convolution_ramp_points_element is not None and convolution_ramp_points_element.text is not None:
            preferences['ConvolutionRampPoints'] = int(float(convolution_ramp_points_element.text))

        freeze_finder_detect_brightening_element = root.find('FreezeFinderDetectBrightening')
        if (
            freeze_finder_detect_brightening_element is not None
            and freeze_finder_detect_brightening_element.text is not None
        ):
            preferences['FreezeFinderDetectBrightening'] = (
                str(freeze_finder_detect_brightening_element.text).strip().lower() in {"1", "true", "yes", "on"}
            )

        video_grayscale_mode_element = root.find('VideoGrayscaleMode')
        if video_grayscale_mode_element is not None and video_grayscale_mode_element.text is not None:
            preferences['VideoGrayscaleMode'] = normalize_video_grayscale_mode(
                video_grayscale_mode_element.text
            )

        temperature_cycle_warmup_hysteresis_c_element = root.find('TemperatureCycleWarmupHysteresisC')
        if (
            temperature_cycle_warmup_hysteresis_c_element is not None
            and temperature_cycle_warmup_hysteresis_c_element.text is not None
        ):
            preferences['TemperatureCycleWarmupHysteresisC'] = float(
                temperature_cycle_warmup_hysteresis_c_element.text
            )

        timeseries_palette_element = root.find('TimeseriesPalette')
        if timeseries_palette_element is not None and timeseries_palette_element.text is not None:
            preferences['TimeseriesPalette'] = timeseries_palette_element.text

        timeseries_line_width_element = root.find('TimeseriesLineWidth')
        if timeseries_line_width_element is not None and timeseries_line_width_element.text is not None:
            preferences['TimeseriesLineWidth'] = float(timeseries_line_width_element.text)

        timeseries_convolution_line_width_element = root.find('TimeseriesConvolutionLineWidth')
        if (
            timeseries_convolution_line_width_element is not None
            and timeseries_convolution_line_width_element.text is not None
        ):
            preferences['TimeseriesConvolutionLineWidth'] = float(timeseries_convolution_line_width_element.text)

        timeseries_freeze_line_color_element = root.find('TimeseriesFreezeLineColor')
        if timeseries_freeze_line_color_element is not None and timeseries_freeze_line_color_element.text is not None:
            preferences['TimeseriesFreezeLineColor'] = timeseries_freeze_line_color_element.text

        timeseries_freeze_line_width_element = root.find('TimeseriesFreezeLineWidth')
        if timeseries_freeze_line_width_element is not None and timeseries_freeze_line_width_element.text is not None:
            preferences['TimeseriesFreezeLineWidth'] = float(timeseries_freeze_line_width_element.text)

        timeseries_current_frame_color_element = root.find('TimeseriesCurrentFrameColor')
        if (
            timeseries_current_frame_color_element is not None
            and timeseries_current_frame_color_element.text is not None
        ):
            preferences['TimeseriesCurrentFrameColor'] = timeseries_current_frame_color_element.text

        timeseries_current_frame_line_width_element = root.find('TimeseriesCurrentFrameLineWidth')
        if (
            timeseries_current_frame_line_width_element is not None
            and timeseries_current_frame_line_width_element.text is not None
        ):
            preferences['TimeseriesCurrentFrameLineWidth'] = float(timeseries_current_frame_line_width_element.text)

        preview_handle_size_element = root.find('PreviewHandleSize')
        if preview_handle_size_element is not None and preview_handle_size_element.text is not None:
            preferences['PreviewHandleSize'] = float(preview_handle_size_element.text)

        circle_label_font_size_element = root.find('CircleLabelFontSize')
        if circle_label_font_size_element is not None and circle_label_font_size_element.text is not None:
            preferences['CircleLabelFontSize'] = float(circle_label_font_size_element.text)

        circle_label_offset_x_element = root.find('CircleLabelOffsetX')
        if circle_label_offset_x_element is not None and circle_label_offset_x_element.text is not None:
            preferences['CircleLabelOffsetX'] = float(circle_label_offset_x_element.text)

        circle_label_offset_y_element = root.find('CircleLabelOffsetY')
        if circle_label_offset_y_element is not None and circle_label_offset_y_element.text is not None:
            preferences['CircleLabelOffsetY'] = float(circle_label_offset_y_element.text)

        for key in DEFAULT_VISUAL_COLORS:
            color_element = root.find(key)
            if color_element is not None and color_element.text is not None:
                preferences[key] = color_element.text
        
        return preferences

if __name__ == '__main__':
    if "--check-video-dependencies" in sys.argv:
        if VideoFrameSource.available():
            print("PyAV import OK")
            sys.exit(0)
        print(f"PyAV import failed: {VideoFrameSource.import_error_message()}", file=sys.stderr)
        sys.exit(1)

    app = IcescopyApplication(sys.argv)
    if platform.system() == "Windows" and "Fusion" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Fusion"))
    app.setWindowIcon(QIcon(os.path.join(resources_dir, "app_icons", "IcescopyApp.png")))
    window = IceScopy()
    app.set_main_window(window)
    window.show()

    for argument in sys.argv[1:]:
        if str(argument).lower().endswith(".icescopy"):
            QTimer.singleShot(0, partial(app.open_session_path, argument))
    
    app.exec()
