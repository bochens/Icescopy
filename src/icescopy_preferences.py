"""Validated preference values; bundled XML supplies the application defaults."""
import math
from pathlib import Path
from xml.etree import ElementTree as ET

from icescopy_frame_source import normalize_video_grayscale_mode
from icescopy_sample_metadata import default_sample_metadata_schema, sample_metadata_schema_from_xml

VISUAL_COLOR_KEYS = (
    "CircleDefaultColor", "CircleHoverColor", "CircleSelectedColor", "CircleEditColor",
    "CirclePressedColor", "GridPreviewOutlineColor", "GridPreviewFillColor",
)

def read_preference_values(path):
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "Preferences":
        raise ValueError("The settings file must contain a Preferences element.")

    preferences = {}
    warnings = []
    # Keep these limits aligned with the controls in PreferencesDialog.
    numeric_fields = {
        "InptkSampleLineWidth": (float, 1.0, 12.0),
        "InptkCombinedLineWidth": (float, 1.0, 12.0),
        "InptkMarkerSize": (float, 0.0, 16.0),
        "InptkOutsideOpacity": (float, 10.0, 80.0),
        "InptkUncertaintyOpacity": (float, 5.0, 50.0),
        "InptkGridOpacity": (float, 0.0, 40.0),
        "InptkLegendFontSize": (float, 8.0, 20.0),
        "DefaultCircleRadius": (float, 0.1, 100000.0),
        "MaximumZoom": (float, 0.1, 1000.0),
        "PenWidth": (float, 0.1, 100.0),
        "SliderMaxZoomPixelInterval": (float, 1.0, 1000.0),
        "SliderTickPixelInterval": (float, 1.0, 1000.0),
        "UndoLimit": (int, 1, 1000),
        "ViewerImageCount": (int, 1, 3),
        "GridRows": (int, 1, 100),
        "GridColumns": (int, 1, 100),
        "GridHorizontalPitch": (float, 0.1, 100000.0),
        "GridVerticalPitch": (float, 0.1, 100000.0),
        "GridRotationDegrees": (float, -180.0, 180.0),
        "RadiusWheelStep": (float, 0.1, 1000.0),
        "GridPitchWheelStep": (float, 0.1, 1000.0),
        "GridTiltWheelStep": (float, 0.1, 90.0),
        "FreezeFinderWidth": (float, 0.1, 100000.0),
        "FreezeFinderProminence": (float, 0.1, 1000000.0),
        "FreezeFinderHeadExtendPoints": (int, 0, 1000),
        "FreezeFinderTailExtendPoints": (int, 0, 1000),
        "ConvolutionHalfWindowPoints": (int, 0, 100000),
        "ConvolutionRampPoints": (int, 0, 1000),
        "TemperatureCycleWarmupHysteresisC": (float, 0.0, 10.0),
        "TimeseriesLineWidth": (float, 0.1, 20.0),
        "TimeseriesConvolutionLineWidth": (float, 0.1, 20.0),
        "TimeseriesFreezeLineWidth": (float, 0.1, 20.0),
        "TimeseriesCurrentFrameLineWidth": (float, 0.1, 20.0),
        "PreviewHandleSize": (float, 2.0, 100.0),
        "CircleLabelFontSize": (float, 1.0, 200.0),
        "CircleLabelOffsetX": (float, -500.0, 500.0),
        "CircleLabelOffsetY": (float, -500.0, 500.0),
    }
    for key, (converter, minimum, maximum) in numeric_fields.items():
        element = root.find(key)
        if element is None or element.text is None:
            continue
        try:
            # Older settings may store integer controls as e.g. "20.0".
            value = float(element.text)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError("outside the supported range")
            preferences[key] = converter(value)
        except (TypeError, ValueError, OverflowError):
            warnings.append(
                f"{key}: ignored {element.text!r}; expected a finite number "
                f"from {minimum:g} to {maximum:g}."
            )

    text_fields = (
        "InptkExecutablePath",
        "SampleNamePattern", "SortMode", "GridCellIdDirection",
        "TimeseriesPalette", "TimeseriesFreezeLineColor",
        "TimeseriesCurrentFrameColor", *VISUAL_COLOR_KEYS,
    )
    for key in text_fields:
        element = root.find(key)
        if element is not None:
            preferences[key] = element.text or ""

    for key in ("InptkSampleColumns", "InptkRangeColumns"):
        inp_columns_element = root.find(key)
        if inp_columns_element is not None:
            preferences[key] = inp_columns_element.text or ""

    droplet_model_element = root.find("DropletModelPath")
    preferences["DropletModelPath"] = (
        (droplet_model_element.text or "").strip() if droplet_model_element is not None else ""
    )

    try:
        preferences["SampleMetadataSchema"] = sample_metadata_schema_from_xml(root)
    except (TypeError, ValueError) as err:
        preferences["SampleMetadataSchema"] = default_sample_metadata_schema()
        warnings.append(f"SampleMetadataSchema: {err}; using the default fields.")

    for key in ("FreezeFinderDetectBrightening", "InptkLogConcentration"):
        element = root.find(key)
        if element is not None and element.text is not None:
            preferences[key] = element.text.strip().lower() in {"1", "true", "yes", "on"}
    grayscale_element = root.find("VideoGrayscaleMode")
    if grayscale_element is not None and grayscale_element.text is not None:
        preferences["VideoGrayscaleMode"] = normalize_video_grayscale_mode(
            grayscale_element.text
        )

    if warnings:
        preferences["_load_warnings"] = warnings
    return preferences

_module_dir = Path(__file__).resolve().parent
_resources = _module_dir / 'resources'
if not _resources.is_dir():
    _resources = _module_dir.parent / 'resources'
DEFAULT_PREFERENCE_VALUES = read_preference_values(_resources / 'preferences.xml')
DEFAULT_VISUAL_COLORS = {key: DEFAULT_PREFERENCE_VALUES[key] for key in VISUAL_COLOR_KEYS}
