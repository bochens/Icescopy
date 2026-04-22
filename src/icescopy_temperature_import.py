from __future__ import annotations

import csv
import math
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
import xml.etree.ElementTree as ET


CSU_IS_TIMESTAMP_RE = re.compile(r":\.(\d+)$")
TAMU_IMAGE_TIMESTAMP_RE = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})-"
    r"(?P<hour>\d{2})-(?P<minute>\d{2})-(?P<second>\d{2})-"
    r"(?P<microsecond>\d{6})$"
)
TAMU_LDF_TIMESTAMP_RE = re.compile(
    r"(?P<day>\d{2})-(?P<month>\d{2})-(?P<year>\d{2})\s+"
    r"(?P<hour>\d{2})-(?P<minute>\d{2})-(?P<second>\d{2})-(?P<centisecond>\d{2})"
)
XLSX_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


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
class TAMULinkamTrace:
    file_path: str
    start_timestamp: datetime | None
    start_timestamp_text: str
    trace_seconds: list[float]
    trace_temperatures: list[float]
    sample_period_seconds: float | None
    trace_row_count: int


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
        raise TemperatureImportError("The selected TAMU workbook does not contain a Linkam temperature trace table.")

    trace_seconds = []
    trace_temperatures = []
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
        trace_seconds.append(float(seconds_value))
        trace_temperatures.append(float(temperature_value))

    if len(trace_seconds) < 2:
        raise TemperatureImportError("The selected TAMU workbook does not contain enough temperature trace rows.")

    return TAMULinkamTrace(
        file_path=str(file_path),
        start_timestamp=start_timestamp,
        start_timestamp_text=start_timestamp_text,
        trace_seconds=trace_seconds,
        trace_temperatures=trace_temperatures,
        sample_period_seconds=sample_period_seconds,
        trace_row_count=len(trace_seconds),
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
