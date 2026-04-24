from dataclasses import dataclass, field
import re


CELL_ANALYSIS_HEADER_RE = re.compile(
    r"^cell_(\d+)_(?:grayscale|circle_x|circle_y|circle_radius)$"
)
CELL_ANALYSIS_LABEL_RE = re.compile(r"^cell_(\d+)$")


@dataclass
class CellRecord:
    """Persistent per-cell metadata and analysis payload.

    A cell ID is stable for the life of that circle. IDs are never renumbered.
    """

    cell_id: int
    sample_id: str = ""
    grayscale_timeseries: list[float] = field(default_factory=list)
    freeze_event_indices: list[int] = field(default_factory=list)
    freeze_rows: list[list[str]] = field(default_factory=list)

    def clear_analysis(self):
        self.grayscale_timeseries = []
        self.freeze_event_indices = []
        self.freeze_rows = []

    def to_dict(self):
        return {
            "cell_id": int(self.cell_id),
            "sample_id": str(self.sample_id),
            "grayscale_timeseries": [float(value) for value in self.grayscale_timeseries],
            "freeze_event_indices": [int(value) for value in self.freeze_event_indices],
            "freeze_rows": [list(row) for row in self.freeze_rows],
        }

    @classmethod
    def from_dict(cls, payload):
        record = cls(
            cell_id=int(payload.get("cell_id", 0)),
            sample_id=str(payload.get("sample_id", "")),
        )
        record.grayscale_timeseries = [float(value) for value in payload.get("grayscale_timeseries", [])]
        record.freeze_event_indices = [int(value) for value in payload.get("freeze_event_indices", [])]
        record.freeze_rows = [list(row) for row in payload.get("freeze_rows", [])]
        return record


class CellStateManager:
    """Owns cell bookkeeping and analysis-table synchronization logic."""

    def __init__(self, main_window):
        self.main_window = main_window

    def extract_cell_id_from_analysis_header(self, header_text):
        header = str(header_text or "")
        match = CELL_ANALYSIS_HEADER_RE.match(header)
        if not match:
            return None
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None

    def extract_cell_id_from_label(self, label_text):
        match = CELL_ANALYSIS_LABEL_RE.match(str(label_text or ""))
        if not match:
            return None
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None

    def serialize_cell_records(self):
        records = getattr(self.main_window, "cell_records_by_id", {})
        return {
            str(int(cell_id)): record.to_dict()
            for cell_id, record in sorted(records.items(), key=lambda pair: int(pair[0]))
        }

    def deserialize_cell_records(self, payload):
        records = {}
        if not isinstance(payload, dict):
            return records
        for key, raw_record in payload.items():
            try:
                cell_id = int(key)
            except (TypeError, ValueError):
                continue
            if isinstance(raw_record, dict):
                record = CellRecord.from_dict(raw_record)
                record.cell_id = cell_id
            else:
                record = CellRecord(cell_id=cell_id)
            records[cell_id] = record
        return records

    def ensure_cell_record(self, cell_id):
        try:
            cell_id = int(cell_id)
        except (TypeError, ValueError):
            return None
        record = self.main_window.cell_records_by_id.get(cell_id)
        if record is None:
            record = CellRecord(cell_id=cell_id)
            self.main_window.cell_records_by_id[cell_id] = record
        return record

    def ensure_cell_registry_matches_scene_cells(self):
        active_ids = {
            int(item.cell_id)
            for item in self.main_window.cell_items
        }
        for cell_id in active_ids:
            self.ensure_cell_record(cell_id)
        for stale_id in list(self.main_window.cell_records_by_id.keys()):
            if stale_id not in active_ids:
                self.main_window.cell_records_by_id.pop(stale_id, None)

    def _used_cell_ids(self):
        used_ids = set()
        for item in self.main_window.cell_items:
            try:
                used_ids.add(int(item.cell_id))
            except (TypeError, ValueError):
                continue
        for keyframe_items in self.main_window.keyframe_cell_items_dict.values():
            for item in keyframe_items:
                try:
                    used_ids.add(int(item.cell_id))
                except (TypeError, ValueError):
                    continue
        for cell_id in self.main_window.cell_records_by_id.keys():
            try:
                used_ids.add(int(cell_id))
            except (TypeError, ValueError):
                continue
        return used_ids

    def _lowest_available_cell_id(self):
        used_ids = self._used_cell_ids()
        next_id = 0
        while next_id in used_ids:
            next_id += 1
        return next_id

    def recompute_next_cell_id(self, preserve_if_larger=True):
        derived_next = self._lowest_available_cell_id()
        if preserve_if_larger:
            current_next = int(getattr(self.main_window, "next_cell_id", 0))
            self.main_window.next_cell_id = max(current_next, derived_next)
        else:
            self.main_window.next_cell_id = derived_next
        if self.main_window.next_cell_id < 0:
            self.main_window.next_cell_id = 0
        return self.main_window.next_cell_id

    def allocate_cell_id(self):
        cell_id = int(self.recompute_next_cell_id(preserve_if_larger=False))
        self.ensure_cell_record(cell_id)
        self.recompute_next_cell_id(preserve_if_larger=False)
        return cell_id

    def cell_id_exists(self, cell_id, exclude_cell_id=None):
        try:
            cell_id = int(cell_id)
        except (TypeError, ValueError):
            return False

        try:
            exclude_cell_id = None if exclude_cell_id is None else int(exclude_cell_id)
        except (TypeError, ValueError):
            exclude_cell_id = None

        if cell_id == exclude_cell_id:
            return False

        for item in self.main_window.cell_items:
            try:
                item_id = int(item.cell_id)
            except (TypeError, ValueError):
                continue
            if item_id == cell_id:
                return True

        for keyframe_items in self.main_window.keyframe_cell_items_dict.values():
            for item in keyframe_items:
                try:
                    item_id = int(item.cell_id)
                except (TypeError, ValueError):
                    continue
                if item_id == cell_id:
                    return True

        return int(cell_id) in self.main_window.cell_records_by_id

    def rename_cell_id(self, old_cell_id, new_cell_id):
        try:
            old_cell_id = int(old_cell_id)
            new_cell_id = int(new_cell_id)
        except (TypeError, ValueError):
            return False, "Cell ID must be an integer."

        if old_cell_id == new_cell_id:
            return True, ""

        if new_cell_id < 0:
            return False, "Cell ID must be 0 or greater."

        if self.cell_id_exists(new_cell_id, exclude_cell_id=old_cell_id):
            return False, f"Cell {new_cell_id} already exists."

        def update_item_cell_id(item):
            if item is None:
                return
            try:
                item_id = int(item.cell_id)
            except (TypeError, ValueError):
                return
            if item_id != old_cell_id:
                return
            if hasattr(item, "sync_from_data"):
                item.sync_from_data(
                    item.circle_positions,
                    item.circle_sizes,
                    item.circle_pixel_positions,
                    new_cell_id,
                    edit_chosen=getattr(item, "edit_chosen", False),
                    hover=getattr(item, "hover", False),
                    pressed=getattr(item, "pressed", False),
                )
            else:
                item.cell_id = new_cell_id

        for item in self.main_window.cell_items:
            update_item_cell_id(item)

        for keyframe_items in self.main_window.keyframe_cell_items_dict.values():
            for item in keyframe_items:
                update_item_cell_id(item)

        existing_record = self.main_window.cell_records_by_id.pop(old_cell_id, None)
        if existing_record is not None:
            existing_record.cell_id = new_cell_id
            self.main_window.cell_records_by_id[new_cell_id] = existing_record

        old_prefix = f"cell_{old_cell_id}_"
        new_prefix = f"cell_{new_cell_id}_"
        self.main_window.grayscale_results_headers = [
            header.replace(old_prefix, new_prefix, 1)
            if str(header).startswith(old_prefix)
            else header
            for header in self.main_window.grayscale_results_headers
        ]

        old_label = f"cell_{old_cell_id}"
        new_label = f"cell_{new_cell_id}"
        updated_freeze_rows = []
        for row in self.main_window.freeze_results_rows:
            copied_row = list(row)
            if copied_row and str(copied_row[0]) == old_label:
                copied_row[0] = new_label
            updated_freeze_rows.append(copied_row)
        self.main_window.freeze_results_rows = updated_freeze_rows

        if hasattr(self.main_window, "cell_controller"):
            controller = self.main_window.cell_controller
            controller.group_cell_ids = [
                new_cell_id if int(cell_id) == old_cell_id else int(cell_id)
                for cell_id in controller.group_cell_ids
            ]
            controller.group_ordered_cell_ids = [
                new_cell_id if int(cell_id) == old_cell_id else int(cell_id)
                for cell_id in controller.group_ordered_cell_ids
            ]

        self.recompute_next_cell_id(preserve_if_larger=True)
        self.ensure_cell_registry_matches_scene_cells()
        self.main_window.last_grayscale_output_path = None
        self.main_window.last_freeze_output_path = None
        self.sync_cell_analysis_from_results()
        self.main_window.update_results_tables()
        return True, ""

    def clear_cell_analysis(self):
        for record in self.main_window.cell_records_by_id.values():
            record.clear_analysis()

    def sync_cell_analysis_from_results(self):
        self.clear_cell_analysis()
        has_grayscale = bool(
            self.main_window.grayscale_results_headers and self.main_window.grayscale_results_rows
        )
        has_freeze = bool(self.main_window.freeze_results_rows)
        if not has_grayscale and not has_freeze:
            return

        grayscale_col_by_id = {}
        if has_grayscale:
            for column_index, header in enumerate(self.main_window.grayscale_results_headers):
                cell_id = self.extract_cell_id_from_analysis_header(header)
                if cell_id is None:
                    continue
                if not str(header).endswith("_grayscale"):
                    continue
                grayscale_col_by_id[cell_id] = column_index

        freeze_rows_by_cell = {}
        freeze_indices_by_cell = {}
        for row in self.main_window.freeze_results_rows:
            if not row:
                continue
            cell_id = self.extract_cell_id_from_label(row[0])
            if cell_id is None:
                continue
            freeze_rows_by_cell.setdefault(cell_id, []).append(list(row))
            if len(row) > 1:
                try:
                    event_index = int(float(row[1]))
                except (TypeError, ValueError):
                    continue
                freeze_indices_by_cell.setdefault(cell_id, []).append(event_index)

        cell_ids = set(grayscale_col_by_id.keys()) | set(freeze_rows_by_cell.keys())
        if not cell_ids:
            return

        for cell_id in sorted(cell_ids):
            grayscale_timeseries = []
            column_index = grayscale_col_by_id.get(cell_id)
            if column_index is not None:
                for row in self.main_window.grayscale_results_rows:
                    try:
                        grayscale_timeseries.append(float(row[column_index]))
                    except (IndexError, TypeError, ValueError):
                        grayscale_timeseries.append(float("nan"))

            record = self.ensure_cell_record(cell_id)
            if record is None:
                continue
            record.grayscale_timeseries = grayscale_timeseries
            record.freeze_event_indices = list(freeze_indices_by_cell.get(cell_id, []))
            record.freeze_rows = [list(row) for row in freeze_rows_by_cell.get(cell_id, [])]

    def prune_analysis_results_for_deleted_cells(self, deleted_cell_ids):
        if not deleted_cell_ids:
            return False
        deleted_set = {int(cell_id) for cell_id in deleted_cell_ids}
        changed = False

        for cell_id in deleted_set:
            self.main_window.cell_records_by_id.pop(cell_id, None)

        if self.main_window.grayscale_results_headers:
            kept_indices = []
            kept_headers = []
            for index, header in enumerate(self.main_window.grayscale_results_headers):
                cell_id = self.extract_cell_id_from_analysis_header(header)
                if cell_id is not None and cell_id in deleted_set:
                    changed = True
                    continue
                kept_indices.append(index)
                kept_headers.append(header)

            if len(kept_indices) != len(self.main_window.grayscale_results_headers):
                self.main_window.grayscale_results_headers = kept_headers
                self.main_window.grayscale_results_rows = [
                    [row[index] if index < len(row) else "" for index in kept_indices]
                    for row in self.main_window.grayscale_results_rows
                ]

        if self.main_window.freeze_results_rows:
            kept_freeze_rows = []
            for row in self.main_window.freeze_results_rows:
                cell_id = self.extract_cell_id_from_label(row[0] if row else None)
                if cell_id is not None and cell_id in deleted_set:
                    changed = True
                    continue
                kept_freeze_rows.append(row)
            self.main_window.freeze_results_rows = kept_freeze_rows

        if changed:
            self.main_window.last_grayscale_output_path = None
            self.main_window.last_freeze_output_path = None
            self.sync_cell_analysis_from_results()
            self.main_window.update_results_tables()
        return changed
