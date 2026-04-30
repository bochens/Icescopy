from __future__ import annotations

import csv
import math
import os
import re
import struct
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

from PIL import Image


CSU_IS_TIMESTAMP_RE = re.compile(r":\.(\d+)$")
LINKSYS32_IML_TEMPERATURE_RE = re.compile(
    r"\bTemp\s+([-+]?\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)
TAMU_IMAGE_TIMESTAMP_RE = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})-"
    r"(?P<hour>\d{2})-(?P<minute>\d{2})-(?P<second>\d{2})-"
    r"(?P<microsecond>\d{6})$"
)
TAMU_LDF_TIMESTAMP_RE = re.compile(
    r"(?P<day>\d{2})-(?P<month>\d{2})-(?P<year>\d{2})\s+"
    r"(?P<hour>\d{2})-(?P<minute>\d{2})-(?P<second>\d{2})-(?P<centisecond>\d{2})"
)
GENERIC_FILENAME_TIMESTAMP_RE = re.compile(
    r"(?P<year>\d{4})[-_/](?P<month>\d{2})[-_/](?P<day>\d{2})"
    r"(?:[T _-]+(?P<hour>\d{2})[-:._](?P<minute>\d{2})"
    r"(?:[-:._](?P<second>\d{2})(?:[.,_-](?P<fraction>\d{1,6}))?)?)"
)
COMPACT_FILENAME_TIMESTAMP_RE = re.compile(
    r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})"
    r"(?:[T _-]?(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})(?P<fraction>\d{1,6})?)"
)
XLSX_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
COMMON_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y_%m_%d %H_%M_%S_%f",
    "%Y_%m_%d %H_%M_%S",
    "%Y_%m_%d %H_%M",
    "%Y%m%d %H%M%S",
    "%Y%m%d_%H%M%S",
    "%Y%m%dT%H%M%S",
)
YEAR4_DASH_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)
YEAR4_T_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
)
YEAR4_SLASH_DATETIME_FORMATS = (
    "%Y/%m/%d %H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
)
YEAR4_COMPACT_DATETIME_FORMATS = (
    "%Y%m%d_%H%M%S",
    "%Y%m%d %H%M%S",
    "%Y%m%dT%H%M%S",
    "%Y%m%d%H%M%S",
)
YEAR2_COMPACT_DATETIME_FORMATS = (
    "%y%m%d_%H%M",
    "%y%m%d %H%M",
    "%y%m%d-%H%M",
    "%y%m%dT%H%M",
    "%y%m%d%H%M",
    "%y%m%d_%H%M%S",
    "%y%m%d %H%M%S",
    "%y%m%d-%H%M%S",
    "%y%m%dT%H%M%S",
    "%y%m%d%H%M%S",
)
YEAR2_SLASH_DATETIME_FORMATS = (
    "%y/%m/%d %H:%M:%S.%f",
    "%y/%m/%d %H:%M:%S",
    "%y/%m/%d %H:%M",
)
SLASH_DAY_MONTH_DATETIME_FORMATS = (
    "%m/%d/%Y %H:%M:%S.%f",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S.%f",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%y %H:%M:%S.%f",
    "%m/%d/%y %H:%M:%S",
    "%m/%d/%y %H:%M",
    "%d/%m/%y %H:%M:%S.%f",
    "%d/%m/%y %H:%M:%S",
    "%d/%m/%y %H:%M",
)
EXIF_DATETIME_FORMATS = (
    "%Y:%m:%d %H:%M:%S.%f",
    "%Y:%m:%d %H:%M:%S",
)
INLINE_EXIF_TIMESTAMP_RE = re.compile(
    r"(?<!\d)(\d{4}:\d{2}:\d{2}[ T_-]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)(?!\d)"
)
EPOCH_TIMESTAMP_RE = re.compile(r"(?<!\d)(-?(?:\d{10}|\d{13}))(?!\d)")

FILETIME_EPOCH = datetime(1601, 1, 1)
LINKSYS32_IML_MIN_HEADER_BYTES = 0x108
LINKSYS32_IML_DATA_COUNT_OFFSET = 0xF0
LINKSYS32_IML_IMAGE_COUNT_OFFSET = 0xF4
LINKSYS32_IML_SAMPLE_PERIOD_OFFSET = 0xFC
LINKSYS32_IML_START_FILETIME_OFFSET = 0x100
LINKSYS32_IML_DATA_RECORD_BYTES = 256
LINKSYS32_IML_IMAGE_RECORD_BYTES = 348
LINKSYS32_IML_IMAGE_RECORD_HEADER_BYTES = 28
LINKSYS32_IML_IMAGE_TEXT_BYTES = 256
LINKSYS32_IML_IMAGE_NOTE_BYTES = 64

TIMESTAMP_STYLE_AUTO = "auto"
TIMESTAMP_STYLE_COMMON = "common_datetime"
TIMESTAMP_STYLE_YEAR4_DASH = "year4_dash_datetime"
TIMESTAMP_STYLE_YEAR4_T = "year4_t_datetime"
TIMESTAMP_STYLE_YEAR4_SLASH = "year4_slash_datetime"
TIMESTAMP_STYLE_YEAR4_COMPACT = "year4_compact_datetime"
TIMESTAMP_STYLE_YEAR2_COMPACT = "year2_compact_datetime"
TIMESTAMP_STYLE_YEAR2_SLASH = "year2_slash_datetime"
TIMESTAMP_STYLE_EXIF = "exif_datetime"
TIMESTAMP_STYLE_EPOCH_SECONDS = "epoch_seconds"
TIMESTAMP_STYLE_EPOCH_MILLISECONDS = "epoch_milliseconds"

IMAGE_TIMESTAMP_SOURCE_FILENAME = "filename"
IMAGE_TIMESTAMP_SOURCE_EXIF = "exif"
IMAGE_TIMESTAMP_SOURCE_CREATED = "creation_time"
IMAGE_TIMESTAMP_SOURCE_MODIFIED = "modified_time"
IMAGE_TIMESTAMP_SOURCE_GENERATED = "generated_sequence"
IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS = "video_pts"

TEMPERATURE_UNIT_CELSIUS = "celsius"
TEMPERATURE_UNIT_KELVIN = "kelvin"

TIMESTAMP_STYLE_CHOICES = (
    (TIMESTAMP_STYLE_AUTO, "Auto detect"),
    (TIMESTAMP_STYLE_YEAR4_DASH, "YYYY-MM-DD HH:MM[:SS[.ffffff]]"),
    (TIMESTAMP_STYLE_YEAR4_T, "YYYY-MM-DDTHH:MM[:SS[.ffffff]]"),
    (TIMESTAMP_STYLE_YEAR4_SLASH, "YYYY/MM/DD HH:MM[:SS[.ffffff]]"),
    (TIMESTAMP_STYLE_YEAR4_COMPACT, "YYYYMMDD_HHMMSS or YYYYMMDD HHMMSS"),
    (TIMESTAMP_STYLE_YEAR2_COMPACT, "YYMMDD_HHMMSS, YYMMDD HHMMSS, YYMMDD HHMM, or YYMMDD-HHMMSS"),
    (TIMESTAMP_STYLE_YEAR2_SLASH, "YY/MM/DD HH:MM[:SS[.ffffff]]"),
    (TIMESTAMP_STYLE_EXIF, "EXIF text (YYYY:MM:DD HH:MM:SS)"),
    (TIMESTAMP_STYLE_EPOCH_SECONDS, "Unix epoch seconds (10 digits; since 1970-01-01 00:00:00 UTC)"),
    (TIMESTAMP_STYLE_EPOCH_MILLISECONDS, "Unix epoch milliseconds (13 digits; since 1970-01-01 00:00:00 UTC)"),
)

IMAGE_TIMESTAMP_SOURCE_CHOICES = (
    (IMAGE_TIMESTAMP_SOURCE_FILENAME, "Filename"),
    (IMAGE_TIMESTAMP_SOURCE_EXIF, "EXIF"),
    (IMAGE_TIMESTAMP_SOURCE_CREATED, "Creation time"),
    (IMAGE_TIMESTAMP_SOURCE_MODIFIED, "Modification time"),
    (IMAGE_TIMESTAMP_SOURCE_GENERATED, "Generated from first timestamp"),
)

TEMPERATURE_UNIT_CHOICES = (
    (TEMPERATURE_UNIT_CELSIUS, "Celsius"),
    (TEMPERATURE_UNIT_KELVIN, "Kelvin"),
)


class TemperatureImportError(ValueError):
    pass


@dataclass
class CSUISDatRow:
    row_index: int
    timestamp: datetime | None
    timestamp_text: str
    avg_temp: float | None
    picture_name: str
    sample_counts: dict[str, int]


@dataclass
class TAMULinkamTimeseries:
    file_path: str
    start_timestamp: datetime | None
    start_timestamp_text: str
    timeseries_seconds: list[float]
    temperature_values: list[float]
    sample_period_seconds: float | None
    timeseries_row_count: int


@dataclass
class Linksys32IMLImageRecord:
    image_index: int
    image_offset: int
    image_byte_count: int
    timestamp: datetime
    timestamp_text: str
    temperature_value: float
    status_text: str
    note_text: str


@dataclass
class Linksys32IMLTimeseries:
    file_path: str
    version: str
    start_timestamp: datetime
    start_timestamp_text: str
    sample_period_seconds: float
    timeseries_seconds: list[float]
    timeseries_datetimes: list[datetime]
    timeseries_timestamp_texts: list[str]
    temperature_values: list[float]
    status_texts: list[str]
    timeseries_row_count: int
    image_records: list[Linksys32IMLImageRecord]
    image_record_count: int


@dataclass
class StandardTemperatureTimeseries:
    file_path: str
    timeseries_datetimes: list[datetime]
    timeseries_timestamp_texts: list[str]
    temperature_values: list[float]
    timeseries_row_count: int


@dataclass
class ResolvedImageTimestamps:
    image_timestamps: list[datetime | None]
    parsed_count: int
    unparsed_images: list[str]


def normalize_sample_name(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _parse_csu_is_timestamp(date_text, time_text):
    date_text = str(date_text or "").strip()
    time_text = str(time_text or "").strip()
    if not date_text or not time_text:
        return None, ""

    normalized_time = CSU_IS_TIMESTAMP_RE.sub(r".\1", time_text)
    timestamp_text = f"{date_text} {normalized_time}"
    for time_format in ("%m/%d/%y %H:%M:%S.%f", "%m/%d/%y %H:%M:%S"):
        try:
            timestamp = datetime.strptime(timestamp_text, time_format)
            return timestamp, timestamp.isoformat(timespec="milliseconds")
        except ValueError:
            continue
    return None, timestamp_text


def _safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        if default is None:
            return None
        return int(default)


def _safe_float(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _decode_linksys32_iml_text(raw_bytes):
    return bytes(raw_bytes).split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


def _parse_filetime(raw_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    try:
        microseconds, _ = divmod(value, 10)
        return FILETIME_EPOCH + timedelta(microseconds=microseconds)
    except OverflowError:
        return None


def _parse_linksys32_iml_temperature(status_text):
    match = LINKSYS32_IML_TEMPERATURE_RE.search(str(status_text or ""))
    if not match:
        return None
    return _safe_float(match.group(1))


def _normalize_parsed_datetime(value):
    if value is None:
        return None
    if value.tzinfo is not None:
        return None
    return value


def _parse_datetime_with_formats(text, formats):
    for fmt in formats:
        try:
            return _normalize_parsed_datetime(datetime.strptime(text, fmt))
        except ValueError:
            continue
    return None


def parse_flexible_datetime_text(text):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    if re.fullmatch(r"-?\d+", normalized):
        return None

    iso_candidate = normalized.replace("Z", "+00:00").replace("z", "+00:00")
    try:
        return _normalize_parsed_datetime(datetime.fromisoformat(iso_candidate))
    except ValueError:
        pass

    direct_value = _parse_datetime_with_formats(normalized, COMMON_DATETIME_FORMATS)
    if direct_value is not None:
        return direct_value

    slash_candidates = set()
    for fmt in SLASH_DAY_MONTH_DATETIME_FORMATS:
        try:
            slash_candidates.add(
                _normalize_parsed_datetime(datetime.strptime(normalized, fmt))
            )
        except ValueError:
            continue
    if len(slash_candidates) == 1:
        return next(iter(slash_candidates))
    return None


def parse_exif_datetime_text(text):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    return _parse_datetime_with_formats(normalized, EXIF_DATETIME_FORMATS)


def parse_year4_dash_datetime_text(text):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    return _parse_datetime_with_formats(normalized, YEAR4_DASH_DATETIME_FORMATS)


def parse_year4_t_datetime_text(text):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    return _parse_datetime_with_formats(normalized, YEAR4_T_DATETIME_FORMATS)


def parse_year4_slash_datetime_text(text):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    return _parse_datetime_with_formats(normalized, YEAR4_SLASH_DATETIME_FORMATS)


def parse_year4_compact_datetime_text(text):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    return _parse_datetime_with_formats(normalized, YEAR4_COMPACT_DATETIME_FORMATS)


def parse_year2_compact_datetime_text(text):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    return _parse_datetime_with_formats(normalized, YEAR2_COMPACT_DATETIME_FORMATS)


def parse_year2_slash_datetime_text(text):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    return _parse_datetime_with_formats(normalized, YEAR2_SLASH_DATETIME_FORMATS)


def parse_epoch_datetime_text(text, unit="auto"):
    normalized = str(text or "").strip().strip("\"'").strip()
    if not normalized:
        return None
    if re.fullmatch(r"-?\d+", normalized) is None:
        return None
    digit_count = len(normalized.lstrip("-"))
    if unit == TIMESTAMP_STYLE_EPOCH_SECONDS:
        if digit_count != 10:
            return None
        seconds_value = int(normalized)
    elif unit == TIMESTAMP_STYLE_EPOCH_MILLISECONDS:
        if digit_count != 13:
            return None
        seconds_value = int(normalized) / 1000.0
    else:
        if digit_count == 10:
            seconds_value = int(normalized)
        elif digit_count == 13:
            seconds_value = int(normalized) / 1000.0
        else:
            return None

    try:
        return datetime.fromtimestamp(seconds_value, tz=timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return None


def parse_timestamp_text(text, style=TIMESTAMP_STYLE_AUTO):
    normalized_style = str(style or TIMESTAMP_STYLE_AUTO).strip() or TIMESTAMP_STYLE_AUTO
    normalized_text = str(text or "").strip().strip("\"'").strip()
    if normalized_style == TIMESTAMP_STYLE_AUTO and re.fullmatch(r"-?\d+", normalized_text):
        return None
    if normalized_style == TIMESTAMP_STYLE_YEAR4_DASH:
        return parse_year4_dash_datetime_text(text)
    if normalized_style == TIMESTAMP_STYLE_YEAR4_T:
        return parse_year4_t_datetime_text(text)
    if normalized_style == TIMESTAMP_STYLE_YEAR4_SLASH:
        return parse_year4_slash_datetime_text(text)
    if normalized_style == TIMESTAMP_STYLE_YEAR4_COMPACT:
        return parse_year4_compact_datetime_text(text)
    if normalized_style == TIMESTAMP_STYLE_YEAR2_COMPACT:
        return parse_year2_compact_datetime_text(text)
    if normalized_style == TIMESTAMP_STYLE_YEAR2_SLASH:
        return parse_year2_slash_datetime_text(text)
    if normalized_style == TIMESTAMP_STYLE_COMMON:
        return parse_flexible_datetime_text(text)
    if normalized_style == TIMESTAMP_STYLE_EXIF:
        return parse_exif_datetime_text(text)
    if normalized_style == TIMESTAMP_STYLE_EPOCH_SECONDS:
        return parse_epoch_datetime_text(text, TIMESTAMP_STYLE_EPOCH_SECONDS)
    if normalized_style == TIMESTAMP_STYLE_EPOCH_MILLISECONDS:
        return parse_epoch_datetime_text(text, TIMESTAMP_STYLE_EPOCH_MILLISECONDS)

    for parser in (
        parse_year4_dash_datetime_text,
        parse_year4_t_datetime_text,
        parse_year4_slash_datetime_text,
        parse_year4_compact_datetime_text,
        parse_year2_compact_datetime_text,
        parse_year2_slash_datetime_text,
        parse_exif_datetime_text,
        parse_flexible_datetime_text,
    ):
        parsed_value = parser(text)
        if parsed_value is not None:
            return parsed_value
    return None


def _datetime_from_filename_match(match):
    if match is None:
        return None
    try:
        fraction_text = str(match.groupdict().get("fraction") or "")
        microsecond = int(fraction_text.ljust(6, "0")[:6]) if fraction_text else 0
        return datetime(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
            int(match.group("second") or 0),
            microsecond,
        )
    except (TypeError, ValueError):
        return None


def _parse_timestamp_candidates(candidates, style):
    for candidate_text in candidates:
        parsed = parse_timestamp_text(candidate_text, style)
        if parsed is not None:
            return parsed
    return None


def _extract_filename_timestamp_candidates(stem):
    candidates = []
    seen = set()
    for pattern in (GENERIC_FILENAME_TIMESTAMP_RE, COMPACT_FILENAME_TIMESTAMP_RE):
        for match in pattern.finditer(stem):
            parsed = _datetime_from_filename_match(match)
            if parsed is None:
                continue
            candidate_text = parsed.isoformat(sep=" ", timespec="microseconds").rstrip("0").rstrip(".")
            if candidate_text and candidate_text not in seen:
                candidates.append(candidate_text)
                seen.add(candidate_text)
    for match in INLINE_EXIF_TIMESTAMP_RE.finditer(stem):
        candidate_text = str(match.group(1)).strip()
        if candidate_text and candidate_text not in seen:
            candidates.append(candidate_text)
            seen.add(candidate_text)
    for match in EPOCH_TIMESTAMP_RE.finditer(stem):
        candidate_text = str(match.group(1)).strip()
        if candidate_text and candidate_text not in seen:
            candidates.append(candidate_text)
            seen.add(candidate_text)
    normalized_stem = stem.replace("__", " ").replace("_", " ").strip()
    if normalized_stem and normalized_stem not in seen:
        candidates.append(normalized_stem)
    return candidates


def parse_generic_image_timestamp(image_name, timestamp_style=TIMESTAMP_STYLE_AUTO):
    stem = os.path.splitext(os.path.basename(str(image_name or "")))[0]
    return _parse_timestamp_candidates(
        _extract_filename_timestamp_candidates(stem),
        timestamp_style,
    )


def read_exif_timestamp_text(file_path):
    try:
        with Image.open(file_path) as image:
            exif = image.getexif()
            if not exif:
                return None
            for tag_code in (36867, 36868, 306):
                value = exif.get(tag_code)
                if value:
                    return str(value).strip()
    except Exception:
        return None
    return None


def resolve_image_timestamp(
    file_path,
    image_name,
    source=IMAGE_TIMESTAMP_SOURCE_FILENAME,
    timestamp_style=TIMESTAMP_STYLE_AUTO,
    generated_start_text="",
    frame_interval_seconds=None,
    image_index=0,
):
    normalized_source = str(source or IMAGE_TIMESTAMP_SOURCE_FILENAME).strip() or IMAGE_TIMESTAMP_SOURCE_FILENAME
    normalized_style = str(timestamp_style or TIMESTAMP_STYLE_AUTO).strip() or TIMESTAMP_STYLE_AUTO

    if normalized_source == IMAGE_TIMESTAMP_SOURCE_FILENAME:
        return parse_generic_image_timestamp(image_name, normalized_style)

    if normalized_source == IMAGE_TIMESTAMP_SOURCE_EXIF:
        exif_text = read_exif_timestamp_text(file_path)
        if not exif_text:
            return None
        return parse_timestamp_text(exif_text, normalized_style)

    if normalized_source == IMAGE_TIMESTAMP_SOURCE_CREATED:
        try:
            return datetime.fromtimestamp(os.stat(file_path).st_birthtime)
        except (AttributeError, OSError, ValueError, TypeError):
            return None

    if normalized_source == IMAGE_TIMESTAMP_SOURCE_MODIFIED:
        try:
            return datetime.fromtimestamp(os.path.getmtime(file_path))
        except (OSError, ValueError, TypeError):
            return None

    if normalized_source == IMAGE_TIMESTAMP_SOURCE_GENERATED:
        start_timestamp = parse_timestamp_text(generated_start_text, normalized_style)
        if start_timestamp is None:
            return None
        try:
            interval_seconds = float(frame_interval_seconds)
        except (TypeError, ValueError):
            return None
        if interval_seconds <= 0:
            return None
        return start_timestamp + timedelta(seconds=interval_seconds * int(image_index))

    return None


def resolve_image_timestamps(
    image_paths,
    image_names,
    source=IMAGE_TIMESTAMP_SOURCE_FILENAME,
    timestamp_style=TIMESTAMP_STYLE_AUTO,
    generated_start_text="",
    frame_interval_seconds=None,
):
    resolved_timestamps = []
    unparsed_images = []
    parsed_count = 0
    for image_index, image_path in enumerate(image_paths):
        image_name = image_names[image_index] if image_index < len(image_names) else os.path.basename(str(image_path or ""))
        resolved = resolve_image_timestamp(
            image_path,
            image_name,
            source=source,
            timestamp_style=timestamp_style,
            generated_start_text=generated_start_text,
            frame_interval_seconds=frame_interval_seconds,
            image_index=image_index,
        )
        resolved_timestamps.append(resolved)
        if resolved is None:
            unparsed_images.append(os.path.basename(str(image_name or image_path or "")))
        else:
            parsed_count += 1
    return ResolvedImageTimestamps(
        image_timestamps=resolved_timestamps,
        parsed_count=int(parsed_count),
        unparsed_images=list(unparsed_images),
    )


def parse_standard_temperature_csv(
    file_path,
    timestamp_style=TIMESTAMP_STYLE_AUTO,
    temperature_unit=TEMPERATURE_UNIT_CELSIUS,
):
    with open(file_path, "r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        raw_rows = list(reader)

    if not raw_rows:
        raise TemperatureImportError("The selected temperature CSV is empty.")

    parsed_rows = []
    for row_number, raw_row in enumerate(raw_rows, start=1):
        values = [str(value).strip() for value in raw_row]
        if not values or not any(values):
            continue
        if len(values) < 2:
            raise TemperatureImportError(
                f"Temperature CSV row {row_number} must contain at least two columns: datetime and temperature_C."
            )

        timestamp_text = values[0]
        temperature_text = values[1]
        timestamp_value = parse_timestamp_text(timestamp_text, timestamp_style)
        temperature_value = _safe_float(temperature_text)

        if row_number == 1 and timestamp_value is None and temperature_value is None:
            continue
        if timestamp_value is None:
            raise TemperatureImportError(
                f"Temperature CSV row {row_number} has an unparseable datetime value: {timestamp_text!r}."
            )
        if temperature_value is None:
            raise TemperatureImportError(
                f"Temperature CSV row {row_number} has an unparseable temperature value: {temperature_text!r}."
            )
        if str(temperature_unit or TEMPERATURE_UNIT_CELSIUS) == TEMPERATURE_UNIT_KELVIN:
            temperature_value = float(temperature_value) - 273.15
        parsed_rows.append((timestamp_value, timestamp_text, float(temperature_value), row_number))

    if len(parsed_rows) < 2:
        raise TemperatureImportError(
            "The selected temperature CSV does not contain enough valid data rows."
        )

    parsed_rows.sort(key=lambda row: row[0])
    previous_timestamp = None
    for timestamp_value, _, _, row_number in parsed_rows:
        if previous_timestamp is not None and timestamp_value == previous_timestamp:
            raise TemperatureImportError(
                f"Temperature CSV row {row_number} repeats a timestamp already present in the file."
            )
        previous_timestamp = timestamp_value

    return StandardTemperatureTimeseries(
        file_path=str(file_path),
        timeseries_datetimes=[row[0] for row in parsed_rows],
        timeseries_timestamp_texts=[row[1] for row in parsed_rows],
        temperature_values=[row[2] for row in parsed_rows],
        timeseries_row_count=len(parsed_rows),
    )


def parse_linksys32_iml(file_path):
    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as handle:
        header = handle.read(LINKSYS32_IML_MIN_HEADER_BYTES)
        if len(header) < LINKSYS32_IML_MIN_HEADER_BYTES:
            raise TemperatureImportError("The selected Linksys32 .iml file is too small to contain a valid header.")

        version = _decode_linksys32_iml_text(header[:8])
        if not version.startswith("V"):
            raise TemperatureImportError("The selected file does not look like a Linksys32 .iml data file.")

        data_record_count = struct.unpack_from("<I", header, LINKSYS32_IML_DATA_COUNT_OFFSET)[0]
        image_record_count = struct.unpack_from("<I", header, LINKSYS32_IML_IMAGE_COUNT_OFFSET)[0]
        sample_period_seconds = struct.unpack_from("<f", header, LINKSYS32_IML_SAMPLE_PERIOD_OFFSET)[0]
        start_timestamp = _parse_filetime(
            struct.unpack_from("<Q", header, LINKSYS32_IML_START_FILETIME_OFFSET)[0]
        )

        if data_record_count < 2:
            raise TemperatureImportError("The selected Linksys32 .iml file does not contain enough data records.")
        if not math.isfinite(sample_period_seconds) or sample_period_seconds <= 0:
            raise TemperatureImportError("The selected Linksys32 .iml file has an invalid data sampling interval.")
        if start_timestamp is None:
            raise TemperatureImportError("The selected Linksys32 .iml file has an invalid start timestamp.")

        image_table_bytes = int(image_record_count) * LINKSYS32_IML_IMAGE_RECORD_BYTES
        data_table_bytes = int(data_record_count) * LINKSYS32_IML_DATA_RECORD_BYTES
        metadata_bytes = image_table_bytes + data_table_bytes
        if metadata_bytes <= 0 or metadata_bytes > file_size:
            raise TemperatureImportError("The selected Linksys32 .iml file has inconsistent record counts.")

        image_table_start = file_size - metadata_bytes
        data_table_start = image_table_start + image_table_bytes
        if image_table_start < LINKSYS32_IML_MIN_HEADER_BYTES:
            raise TemperatureImportError("The selected Linksys32 .iml file has an invalid metadata table offset.")

        image_records = []
        for image_index in range(int(image_record_count)):
            handle.seek(image_table_start + image_index * LINKSYS32_IML_IMAGE_RECORD_BYTES)
            record = handle.read(LINKSYS32_IML_IMAGE_RECORD_BYTES)
            if len(record) != LINKSYS32_IML_IMAGE_RECORD_BYTES:
                raise TemperatureImportError("The selected Linksys32 .iml file has a truncated image record table.")

            image_offset, _, image_byte_count = struct.unpack_from("<III", record, 0)
            if image_byte_count <= 0 or image_offset + image_byte_count > image_table_start:
                raise TemperatureImportError(
                    f"Linksys32 .iml image record {image_index + 1} points outside the image payload."
                )
            image_timestamp = _parse_filetime(struct.unpack_from("<Q", record, 12)[0])
            if image_timestamp is None:
                raise TemperatureImportError(
                    f"Linksys32 .iml image record {image_index + 1} has an invalid timestamp."
                )

            status_start = LINKSYS32_IML_IMAGE_RECORD_HEADER_BYTES
            status_end = status_start + LINKSYS32_IML_IMAGE_TEXT_BYTES
            note_end = status_end + LINKSYS32_IML_IMAGE_NOTE_BYTES
            status_text = _decode_linksys32_iml_text(record[status_start:status_end])
            temperature_value = _parse_linksys32_iml_temperature(status_text)
            if temperature_value is None:
                raise TemperatureImportError(
                    f"Linksys32 .iml image record {image_index + 1} has an unparseable temperature value."
                )
            note_text = _decode_linksys32_iml_text(record[status_end:note_end])
            image_records.append(
                Linksys32IMLImageRecord(
                    image_index=image_index + 1,
                    image_offset=int(image_offset),
                    image_byte_count=int(image_byte_count),
                    timestamp=image_timestamp,
                    timestamp_text=image_timestamp.isoformat(timespec="milliseconds"),
                    temperature_value=float(temperature_value),
                    status_text=status_text,
                    note_text=note_text,
                )
            )

        timeseries_datetimes = []
        timeseries_seconds = []
        timeseries_timestamp_texts = []
        temperature_values = []
        status_texts = []
        for row_index in range(int(data_record_count)):
            handle.seek(data_table_start + row_index * LINKSYS32_IML_DATA_RECORD_BYTES)
            record = handle.read(LINKSYS32_IML_DATA_RECORD_BYTES)
            if len(record) != LINKSYS32_IML_DATA_RECORD_BYTES:
                raise TemperatureImportError("The selected Linksys32 .iml file has a truncated data record table.")

            status_text = _decode_linksys32_iml_text(record)
            temperature_value = _parse_linksys32_iml_temperature(status_text)
            if temperature_value is None:
                raise TemperatureImportError(
                    f"Linksys32 .iml data record {row_index + 1} has an unparseable temperature value."
                )
            timestamp = start_timestamp + timedelta(seconds=float(sample_period_seconds) * row_index)
            timeseries_seconds.append(float(sample_period_seconds) * row_index)
            timeseries_datetimes.append(timestamp)
            timeseries_timestamp_texts.append(timestamp.isoformat(timespec="microseconds"))
            temperature_values.append(float(temperature_value))
            status_texts.append(status_text)

    return Linksys32IMLTimeseries(
        file_path=str(file_path),
        version=version,
        start_timestamp=start_timestamp,
        start_timestamp_text=start_timestamp.isoformat(timespec="milliseconds"),
        sample_period_seconds=float(sample_period_seconds),
        timeseries_seconds=timeseries_seconds,
        timeseries_datetimes=timeseries_datetimes,
        timeseries_timestamp_texts=timeseries_timestamp_texts,
        temperature_values=temperature_values,
        status_texts=status_texts,
        timeseries_row_count=len(timeseries_datetimes),
        image_records=image_records,
        image_record_count=len(image_records),
    )


def write_linksys32_iml_temperature_csv(file_path, output_path):
    parsed = parse_linksys32_iml(file_path)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "temperature_C"])
        for timestamp_text, temperature_value in zip(
            parsed.timeseries_timestamp_texts,
            parsed.temperature_values,
        ):
            writer.writerow([timestamp_text, temperature_value])
    return parsed


def compute_blank_correction_by_index(blank_sample_keys, corrected_counts_by_sample, total_count):
    normalized_blank_keys = [
        str(key).strip()
        for key in (blank_sample_keys or [])
        if str(key).strip()
    ]
    if not normalized_blank_keys:
        return [None] * int(max(0, int(total_count)))
    blank_correction_values = []
    for row_index in range(int(max(0, int(total_count)))):
        blank_correction = 0
        for blank_key in normalized_blank_keys:
            sample_counts = corrected_counts_by_sample.get(blank_key, [])
            if row_index < len(sample_counts):
                blank_correction += int(sample_counts[row_index])
        blank_correction_values.append(int(blank_correction))
    return blank_correction_values


def apply_blank_correction_counts(total_cells, frozen_count, blank_correction):
    total_cells = max(0, int(total_cells))
    frozen_count = max(0, int(frozen_count))
    if blank_correction is None:
        adjusted_total = total_cells
        adjusted_frozen = frozen_count
    else:
        adjusted_total = max(0, total_cells - int(blank_correction))
        adjusted_frozen = max(0, frozen_count - int(blank_correction))
    adjusted_frozen = min(adjusted_frozen, adjusted_total)
    return adjusted_total, adjusted_frozen


def parse_tamu_image_timestamp(image_name):
    stem = os.path.splitext(os.path.basename(str(image_name or "")))[0]
    match = TAMU_IMAGE_TIMESTAMP_RE.match(stem)
    if not match:
        return None
    values = {key: int(value) for key, value in match.groupdict().items()}
    return datetime(
        values["year"],
        values["month"],
        values["day"],
        values["hour"],
        values["minute"],
        values["second"],
        values["microsecond"],
    )


def _read_xlsx_shared_strings(archive):
    shared_strings = []
    if "xl/sharedStrings.xml" not in archive.namelist():
        return shared_strings
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    for si in root.findall("main:si", XLSX_NS):
        shared_strings.append("".join(node.text or "" for node in si.findall(".//main:t", XLSX_NS)))
    return shared_strings


def _resolve_first_sheet_path(archive):
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationships = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rel_root.findall("rel:Relationship", XLSX_NS)
    }
    first_sheet = workbook_root.find("main:sheets/main:sheet", XLSX_NS)
    if first_sheet is None:
        raise TemperatureImportError("The selected TAMU workbook has no sheets.")
    rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    target = relationships.get(rel_id, "")
    if not target:
        raise TemperatureImportError("The selected TAMU workbook is missing the first worksheet target.")
    if not target.startswith("xl/"):
        target = "xl/" + target
    return target


def _read_first_sheet_rows(file_path):
    rows = []
    with zipfile.ZipFile(file_path) as archive:
        shared_strings = _read_xlsx_shared_strings(archive)
        sheet_path = _resolve_first_sheet_path(archive)
        root = ET.fromstring(archive.read(sheet_path))
        for row in root.findall(".//main:sheetData/main:row", XLSX_NS):
            row_number = int(row.attrib.get("r", "0") or 0)
            values = {}
            for cell in row.findall("main:c", XLSX_NS):
                ref = cell.attrib.get("r", "")
                column_name = "".join(character for character in ref if character.isalpha())
                if not column_name:
                    continue
                value_type = cell.attrib.get("t")
                value_element = cell.find("main:v", XLSX_NS)
                text_value = ""
                if value_type == "s" and value_element is not None and value_element.text is not None:
                    index = int(value_element.text)
                    text_value = shared_strings[index] if 0 <= index < len(shared_strings) else ""
                elif value_type == "inlineStr":
                    inline_element = cell.find("main:is/main:t", XLSX_NS)
                    text_value = inline_element.text if inline_element is not None and inline_element.text else ""
                elif value_element is not None and value_element.text is not None:
                    text_value = value_element.text
                if str(text_value).strip():
                    values[column_name] = text_value
            rows.append((row_number, values))
    return rows


def _parse_tamu_ldf_timestamp(text):
    match = TAMU_LDF_TIMESTAMP_RE.search(str(text or ""))
    if not match:
        return None
    values = {key: int(value) for key, value in match.groupdict().items()}
    return datetime(
        2000 + values["year"],
        values["month"],
        values["day"],
        values["hour"],
        values["minute"],
        values["second"],
        values["centisecond"] * 10000,
    )


def _parse_recorded_timestamp(text):
    recorded_text = str(text or "").strip()
    if ":" not in recorded_text:
        return None
    _, _, suffix = recorded_text.partition(":")
    suffix = suffix.strip()
    if not suffix:
        return None
    try:
        return datetime.strptime(suffix, "%d/%m/%Y %H:%M")
    except ValueError:
        return None


def parse_tamu_linkam_xlsx(file_path):
    rows = _read_first_sheet_rows(file_path)
    if not rows:
        raise TemperatureImportError("The selected TAMU workbook is empty.")

    metadata_values = [values.get("A", "") for _, values in rows if values.get("A")]
    ldf_text = next(
        (
            text
            for text in metadata_values
            if str(text).startswith("LDF file:") or str(text).startswith("Source:")
        ),
        "",
    )
    recorded_text = next(
        (text for text in metadata_values if str(text).startswith("Recorded:")),
        "",
    )
    sample_period_text = next(
        (text for text in metadata_values if str(text).startswith("Requested Sample Period (s):")),
        "",
    )

    start_timestamp = _parse_tamu_ldf_timestamp(ldf_text)
    if start_timestamp is None:
        start_timestamp = _parse_recorded_timestamp(recorded_text)
    start_timestamp_text = start_timestamp.isoformat(timespec="milliseconds") if start_timestamp is not None else str(recorded_text or "")

    sample_period_seconds = None
    if ":" in str(sample_period_text):
        _, _, suffix = str(sample_period_text).partition(":")
        sample_period_seconds = _safe_float(suffix)

    header_row_number = None
    for row_number, values in rows:
        if values.get("B") == "Temperature" and values.get("R") == "Image":
            header_row_number = row_number
            break
    if header_row_number is None:
        raise TemperatureImportError("The selected TAMU workbook does not contain a Linkam temperature timeseries table.")

    timeseries_seconds = []
    temperature_values = []
    data_start_row = header_row_number + 2
    for row_number, values in rows:
        if row_number < data_start_row:
            continue
        seconds_value = _safe_float(values.get("B"))
        temperature_value = _safe_float(values.get("C"))
        if seconds_value is None and temperature_value is None:
            continue
        if seconds_value is None or temperature_value is None:
            continue
        timeseries_seconds.append(float(seconds_value))
        temperature_values.append(float(temperature_value))

    if len(timeseries_seconds) < 2:
        raise TemperatureImportError("The selected TAMU workbook does not contain enough temperature timeseries rows.")

    return TAMULinkamTimeseries(
        file_path=str(file_path),
        start_timestamp=start_timestamp,
        start_timestamp_text=start_timestamp_text,
        timeseries_seconds=timeseries_seconds,
        temperature_values=temperature_values,
        sample_period_seconds=sample_period_seconds,
        timeseries_row_count=len(timeseries_seconds),
    )


def parse_ice_array_calibration_csv(file_path):
    calibration = {}
    with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise TemperatureImportError("The selected calibration CSV has no header row.")
        required_columns = {"well", "slope", "intercept"}
        missing_columns = required_columns.difference({str(value).strip() for value in reader.fieldnames})
        if missing_columns:
            raise TemperatureImportError(
                "The selected calibration CSV is missing required column(s): "
                + ", ".join(sorted(missing_columns))
            )
        for raw_row in reader:
            well_value = _safe_int(raw_row.get("well"), default=None)
            slope_value = _safe_float(raw_row.get("slope"))
            intercept_value = _safe_float(raw_row.get("intercept"))
            if well_value is None or slope_value is None or intercept_value is None:
                continue
            calibration[int(well_value)] = (float(slope_value), float(intercept_value))
    return calibration


def parse_csu_is_dat(file_path):
    with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        raw_rows = [list(row) for row in reader]

    if not raw_rows:
        raise TemperatureImportError("The selected CSU .dat file is empty.")

    header = [str(value).strip() for value in raw_rows[0]]
    if not header:
        raise TemperatureImportError("The selected CSU .dat file has no header row.")

    sample_columns = [name for name in header if name.startswith("Sample_")]
    if not sample_columns:
        raise TemperatureImportError("No CSU sample columns were found in the selected .dat file.")

    avg_temp_index = None
    picture_index = None
    for index, column_name in enumerate(header):
        if column_name == "Avg_Temp":
            avg_temp_index = index
        elif column_name == "Picture":
            picture_index = index

    if avg_temp_index is None:
        raise TemperatureImportError("The selected CSU .dat file is missing the Avg_Temp column.")
    if picture_index is None:
        raise TemperatureImportError("The selected CSU .dat file is missing the Picture column.")

    sample_indexes = {
        column_name: header.index(column_name)
        for column_name in sample_columns
    }

    rows = []
    picture_to_row = {}
    for row_index, raw_row in enumerate(raw_rows[1:]):
        row = list(raw_row)
        if len(row) < len(header):
            row.extend([""] * (len(header) - len(row)))

        timestamp, timestamp_text = _parse_csu_is_timestamp(row[0], row[1] if len(row) > 1 else "")
        avg_temp = _safe_float(row[avg_temp_index])
        picture_name = os.path.basename(str(row[picture_index] or "").strip())
        sample_counts = {
            column_name: _safe_int(row[column_index], default=0)
            for column_name, column_index in sample_indexes.items()
        }

        parsed_row = CSUISDatRow(
            row_index=row_index,
            timestamp=timestamp,
            timestamp_text=timestamp_text,
            avg_temp=avg_temp,
            picture_name=picture_name,
            sample_counts=sample_counts,
        )
        rows.append(parsed_row)

        if picture_name:
            picture_to_row[picture_name.casefold()] = row_index

    return {
        "file_path": str(file_path),
        "sample_columns": sample_columns,
        "rows": rows,
        "picture_to_row": picture_to_row,
    }


def reconcile_cumulative_counts(raw_counts, anchor_counts, maximum_count):
    raw_values = [
        max(0, min(int(maximum_count), int(value)))
        for value in raw_counts
    ]
    if not raw_values:
        return []

    max_count = max(0, int(maximum_count))
    if not anchor_counts:
        corrected = []
        running = 0
        for value in raw_values:
            running = max(running, value)
            corrected.append(min(running, max_count))
        return corrected

    anchors = []
    running_anchor = 0
    for row_index in sorted(anchor_counts.keys()):
        anchor_value = max(0, min(max_count, int(anchor_counts[row_index])))
        running_anchor = max(running_anchor, anchor_value)
        anchors.append((int(row_index), running_anchor))

    corrected = [0] * len(raw_values)

    first_index, first_value = anchors[0]
    running = 0
    for row_index in range(0, first_index + 1):
        running = max(running, min(raw_values[row_index], first_value))
        corrected[row_index] = running
    corrected[first_index] = first_value

    previous_index, previous_value = first_index, first_value
    for anchor_index, anchor_value in anchors[1:]:
        corrected[previous_index] = previous_value
        running = previous_value
        for row_index in range(previous_index + 1, anchor_index):
            bounded_value = min(max(raw_values[row_index], previous_value), anchor_value)
            running = max(running, bounded_value)
            corrected[row_index] = min(running, anchor_value)
        corrected[anchor_index] = anchor_value
        previous_index, previous_value = anchor_index, anchor_value

    corrected[previous_index] = previous_value
    running = previous_value
    for row_index in range(previous_index + 1, len(raw_values)):
        running = max(running, raw_values[row_index])
        corrected[row_index] = min(running, max_count)

    return corrected


def normalize_temperature_reset_threshold(reset_temperature):
    if reset_temperature in (None, ""):
        return None
    try:
        return float(reset_temperature)
    except (TypeError, ValueError):
        return None


def detect_cycle_start_indexes_from_temperatures(
    temperatures,
    reset_temperature,
    warmup_hysteresis_c=0.02,
):
    if temperatures is None:
        return [0]

    values = [float(value) for value in temperatures]
    if not values:
        return [0]

    threshold = normalize_temperature_reset_threshold(reset_temperature)
    if threshold is None:
        return [0]

    cycle_start_indexes = [0]
    warmup_hysteresis_c = max(0.0, float(warmup_hysteresis_c))

    first_value = values[0]
    previous_above = bool(math.isfinite(first_value) and first_value >= threshold)
    cool_segment_min = None
    if math.isfinite(first_value) and first_value < threshold:
        cool_segment_min = float(first_value)

    for index in range(1, len(values)):
        current_value = values[index]
        current_finite = bool(math.isfinite(current_value))
        current_above = bool(current_finite and current_value >= threshold)
        if current_finite and (not current_above):
            if cool_segment_min is None:
                cool_segment_min = float(current_value)
            else:
                cool_segment_min = min(cool_segment_min, float(current_value))
        if current_above and (not previous_above):
            minimum_below_threshold = cool_segment_min
            if (
                minimum_below_threshold is not None
                and (float(current_value) - float(minimum_below_threshold)) >= warmup_hysteresis_c
            ):
                cycle_start_indexes.append(index)
            cool_segment_min = None
        previous_above = current_above

    return cycle_start_indexes


def build_cycle_ids_from_start_indexes(total_count, cycle_start_indexes):
    cycle_ids = []
    if total_count <= 0:
        return cycle_ids

    normalized_starts = sorted(
        set(
            int(index)
            for index in (cycle_start_indexes or [0])
            if 0 <= int(index) < total_count
        )
    )
    if not normalized_starts or normalized_starts[0] != 0:
        normalized_starts.insert(0, 0)

    current_cycle_id = 0
    next_start_pointer = 1
    for index in range(total_count):
        while next_start_pointer < len(normalized_starts) and index >= normalized_starts[next_start_pointer]:
            current_cycle_id += 1
            next_start_pointer += 1
        cycle_ids.append(int(current_cycle_id))
    return cycle_ids


def reconcile_counts_by_cycle(raw_counts, anchor_counts, maximum_count, cycle_ids):
    raw_counts = [int(value) for value in raw_counts]
    if not raw_counts:
        return []
    if not cycle_ids or len(cycle_ids) != len(raw_counts):
        return reconcile_cumulative_counts(raw_counts, anchor_counts, maximum_count)

    corrected_counts = [0] * len(raw_counts)
    segment_start = 0
    while segment_start < len(raw_counts):
        cycle_id = cycle_ids[segment_start]
        segment_end = segment_start + 1
        while segment_end < len(raw_counts) and cycle_ids[segment_end] == cycle_id:
            segment_end += 1

        segment_raw = raw_counts[segment_start:segment_end]
        segment_anchors = {}
        for global_index, anchor_value in anchor_counts.items():
            if segment_start <= int(global_index) < segment_end:
                segment_anchors[int(global_index) - segment_start] = int(anchor_value)

        segment_corrected = reconcile_cumulative_counts(
            segment_raw,
            segment_anchors,
            maximum_count,
        )
        corrected_counts[segment_start:segment_end] = segment_corrected
        segment_start = segment_end

    return corrected_counts
