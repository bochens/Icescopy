from __future__ import annotations

import copy
import re
from xml.etree.ElementTree import SubElement


ALLOWED_SAMPLE_TYPES = ("air", "soil", "other")
SAMPLE_METADATA_FIELD_TYPES = ("text", "number", "datetime", "sample_type")
CUSTOM_SAMPLE_METADATA_FIELD_TYPES = ("text", "number", "datetime")
RESERVED_SAMPLE_METADATA_KEYS = ("sample_id", "cell_number")
SAMPLE_METADATA_SCHEMA_XML_TAG = "SampleMetadataFields"
SAMPLE_METADATA_FIELD_XML_TAG = "Field"
SAMPLE_METADATA_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

FIXED_SAMPLE_METADATA_KEYS = (
    "sample_name",
    "sample_long_name",
    "sampling_site",
    "collection_start",
    "collection_end",
    "sample_type",
)

LEGACY_SAMPLE_CATALOG_FIELD_NAMES = (
    "sample_name",
    "sample_long_name",
    "sampling_site",
    "collection_start",
    "collection_end",
    "sample_type",
    "dilution",
    "air_volume_L",
    "filter_fraction_used",
    "suspension_volume_mL",
    "dry_mass_g",
    "sample_note",
)

DEFAULT_SAMPLE_METADATA_SCHEMA = (
    {
        "key": "sample_name",
        "label": "Sample name",
        "type": "text",
        "fixed": True,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": (),
    },
    {
        "key": "sample_long_name",
        "label": "Sample long name",
        "type": "text",
        "fixed": True,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": (),
    },
    {
        "key": "sampling_site",
        "label": "Sampling site",
        "type": "text",
        "fixed": True,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": (),
    },
    {
        "key": "collection_start",
        "label": "Collection start",
        "type": "datetime",
        "fixed": True,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": (),
    },
    {
        "key": "collection_end",
        "label": "Collection end",
        "type": "datetime",
        "fixed": True,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": (),
    },
    {
        "key": "sample_type",
        "label": "Sample type",
        "type": "sample_type",
        "fixed": True,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": (),
    },
    {
        "key": "well_volume_uL",
        "label": "Well volume (uL)",
        "type": "number",
        "fixed": False,
        "export": True,
        "same_for_all": True,
        "required_for_sample_types": (),
    },
    {
        "key": "dilution",
        "label": "Dilution factor",
        "type": "number",
        "fixed": False,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": ("air", "soil", "other"),
    },
    {
        "key": "air_volume_L",
        "label": "Air volume (L)",
        "type": "number",
        "fixed": False,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": ("air",),
    },
    {
        "key": "filter_fraction_used",
        "label": "Filter fraction used (0-1)",
        "type": "number",
        "fixed": False,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": ("air",),
    },
    {
        "key": "suspension_volume_mL",
        "label": "Suspension volume (mL)",
        "type": "number",
        "fixed": False,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": ("air", "soil"),
    },
    {
        "key": "dry_mass_g",
        "label": "Dry mass (g)",
        "type": "number",
        "fixed": False,
        "export": True,
        "same_for_all": False,
        "required_for_sample_types": ("soil",),
    },
)


class SampleMetadataSchemaError(ValueError):
    pass


def default_sample_metadata_schema():
    return copy.deepcopy(list(DEFAULT_SAMPLE_METADATA_SCHEMA))


def _bool_text(value):
    return "true" if bool(value) else "false"


def _parse_bool(value, default=False):
    if value is None:
        return bool(default)
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def _normalize_required_sample_types(value):
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [part.strip().casefold() for part in value.split(",")]
    else:
        parts = [str(part).strip().casefold() for part in value]
    return tuple(sample_type for sample_type in parts if sample_type in ALLOWED_SAMPLE_TYPES)


def validate_sample_metadata_key(key):
    key_text = str(key or "").strip()
    if key_text in RESERVED_SAMPLE_METADATA_KEYS:
        raise SampleMetadataSchemaError(f"'{key_text}' is a system metadata key and cannot be used as a sample field.")
    built_in_keys = {field["key"] for field in DEFAULT_SAMPLE_METADATA_SCHEMA}
    if key_text in built_in_keys:
        return key_text
    if not SAMPLE_METADATA_KEY_PATTERN.fullmatch(key_text):
        raise SampleMetadataSchemaError(
            "Metadata keys must use lowercase snake_case ASCII and start with a letter."
        )
    return key_text


def normalize_sample_metadata_field(field):
    if not isinstance(field, dict):
        raise SampleMetadataSchemaError("Each sample metadata field must be a mapping.")
    key = validate_sample_metadata_key(field.get("key", ""))
    label = str(field.get("label", "") or "").strip()
    if not label:
        label = key.replace("_", " ").title()
    field_type = str(field.get("type", "text") or "text").strip().casefold()
    if field_type not in SAMPLE_METADATA_FIELD_TYPES:
        raise SampleMetadataSchemaError(f"Unsupported sample metadata field type: {field_type}")
    fixed = _parse_bool(field.get("fixed"), key in FIXED_SAMPLE_METADATA_KEYS)
    if key in FIXED_SAMPLE_METADATA_KEYS:
        fixed = True
    if fixed and key not in FIXED_SAMPLE_METADATA_KEYS:
        raise SampleMetadataSchemaError(f"Only built-in fields can be fixed: {key}")
    if not fixed and field_type not in CUSTOM_SAMPLE_METADATA_FIELD_TYPES:
        raise SampleMetadataSchemaError(f"Custom field '{key}' must use text, number, or datetime type.")
    if key == "sample_type":
        field_type = "sample_type"
    export = _parse_bool(field.get("export"), True)
    same_for_all = _parse_bool(field.get("same_for_all"), False)
    if key == "sample_name":
        same_for_all = False
    return {
        "key": key,
        "label": label,
        "type": field_type,
        "fixed": fixed,
        "export": export,
        "same_for_all": same_for_all,
        "required_for_sample_types": _normalize_required_sample_types(
            field.get("required_for_sample_types", ())
        ),
    }


def normalize_sample_metadata_schema(schema=None):
    if schema is None:
        return default_sample_metadata_schema()
    if isinstance(schema, dict):
        fields = schema.get("fields", [])
    else:
        fields = schema
    if not fields:
        return default_sample_metadata_schema()

    normalized = []
    seen_keys = set()
    for field in fields:
        normalized_field = normalize_sample_metadata_field(field)
        key = normalized_field["key"]
        if key in seen_keys:
            raise SampleMetadataSchemaError(f"Duplicate sample metadata field key: {key}")
        seen_keys.add(key)
        normalized.append(normalized_field)

    missing_fixed_keys = [
        key for key in FIXED_SAMPLE_METADATA_KEYS if key not in seen_keys
    ]
    if missing_fixed_keys:
        raise SampleMetadataSchemaError(
            "Sample metadata schema is missing fixed field(s): "
            + ", ".join(missing_fixed_keys)
        )
    return normalized


def sample_metadata_schema_to_payload(schema=None):
    return {"fields": normalize_sample_metadata_schema(schema)}


def sample_metadata_schema_from_payload(payload):
    if payload in (None, ""):
        return default_sample_metadata_schema()
    return normalize_sample_metadata_schema(payload)


def sample_metadata_schema_from_xml(root):
    schema_element = root.find(SAMPLE_METADATA_SCHEMA_XML_TAG)
    if schema_element is None:
        return default_sample_metadata_schema()
    fields = []
    for field_element in schema_element.findall(SAMPLE_METADATA_FIELD_XML_TAG):
        fields.append(
            {
                "key": field_element.get("key", ""),
                "label": field_element.get("label", ""),
                "type": field_element.get("type", "text"),
                "fixed": _parse_bool(field_element.get("fixed"), False),
                "export": _parse_bool(field_element.get("export"), True),
                "same_for_all": _parse_bool(field_element.get("same_for_all"), False),
                "required_for_sample_types": field_element.get("required_for_sample_types", ""),
            }
        )
    return normalize_sample_metadata_schema(fields)


def append_sample_metadata_schema_xml(parent, schema=None):
    schema_element = SubElement(parent, SAMPLE_METADATA_SCHEMA_XML_TAG)
    for field in normalize_sample_metadata_schema(schema):
        field_element = SubElement(schema_element, SAMPLE_METADATA_FIELD_XML_TAG)
        field_element.set("key", field["key"])
        field_element.set("label", field["label"])
        field_element.set("type", field["type"])
        field_element.set("fixed", _bool_text(field["fixed"]))
        field_element.set("export", _bool_text(field["export"]))
        field_element.set("same_for_all", _bool_text(field.get("same_for_all", False)))
        required_text = ",".join(field.get("required_for_sample_types", ()) or ())
        if required_text:
            field_element.set("required_for_sample_types", required_text)


def sample_metadata_field_keys(schema=None):
    return tuple(field["key"] for field in normalize_sample_metadata_schema(schema))


def export_sample_metadata_field_keys(schema=None):
    return tuple(
        field["key"]
        for field in normalize_sample_metadata_schema(schema)
        if bool(field.get("export", True))
    )


def same_for_all_sample_metadata_field_keys(schema=None):
    return tuple(
        field["key"]
        for field in normalize_sample_metadata_schema(schema)
        if bool(field.get("same_for_all", False))
    )


def sample_metadata_field_for_key(schema, key):
    key_text = str(key or "")
    for field in normalize_sample_metadata_schema(schema):
        if field["key"] == key_text:
            return field
    return None


def sample_metadata_field_type(schema, key):
    field = sample_metadata_field_for_key(schema, key)
    return "" if field is None else str(field.get("type", "text") or "text")


def sample_metadata_field_label(schema, key):
    field = sample_metadata_field_for_key(schema, key)
    return str(key or "") if field is None else str(field.get("label", key) or key)


def sample_metadata_field_same_for_all(schema, key):
    field = sample_metadata_field_for_key(schema, key)
    return False if field is None else bool(field.get("same_for_all", False))


def sample_metadata_field_is_relevant(schema, field_key, sample_record):
    field = sample_metadata_field_for_key(schema, field_key)
    if field is None:
        return False
    if field.get("fixed", False):
        return True
    required_types = tuple(field.get("required_for_sample_types", ()) or ())
    if not required_types:
        return True
    sample_type = str(sample_record.get("sample_type", "") or "").strip().casefold()
    return bool(sample_type) and sample_type in required_types


def normalize_sample_catalog_record(value, schema=None):
    active_schema = normalize_sample_metadata_schema(schema)
    record = {field["key"]: "" for field in active_schema}
    if not isinstance(value, dict):
        return record
    for field in active_schema:
        field_key = field["key"]
        raw_value = value.get(field_key, "")
        if field_key == "sample_type":
            normalized_type = str(raw_value or "").strip().casefold()
            record[field_key] = (
                normalized_type if normalized_type in ALLOWED_SAMPLE_TYPES else ""
            )
        else:
            record[field_key] = str(raw_value or "").strip()
    return record


def same_for_all_sample_metadata_values(catalog, schema=None):
    active_schema = normalize_sample_metadata_schema(schema)
    shared_values = {}
    if not isinstance(catalog, dict):
        return shared_values
    for field_key in same_for_all_sample_metadata_field_keys(active_schema):
        for _sample_id, sample_record in sorted(catalog.items(), key=lambda pair: int(pair[0])):
            normalized_record = normalize_sample_catalog_record(sample_record, active_schema)
            value = str(normalized_record.get(field_key, "") or "").strip()
            if value:
                shared_values[field_key] = value
                break
    return shared_values


def migrate_sample_catalog_for_schema(catalog, old_schema, new_schema, rename_map=None):
    old_schema = normalize_sample_metadata_schema(old_schema)
    new_schema = normalize_sample_metadata_schema(new_schema)
    rename_map = {
        str(old_key): str(new_key)
        for old_key, new_key in (rename_map or {}).items()
        if str(old_key) and str(new_key) and str(old_key) != str(new_key)
    }
    output = {}
    if not isinstance(catalog, dict):
        return output
    old_keys = set(sample_metadata_field_keys(old_schema))
    new_keys = set(sample_metadata_field_keys(new_schema))
    for sample_id, sample_record in catalog.items():
        normalized_old_record = {
            key: str(sample_record.get(key, "") or "").strip()
            for key in old_keys
            if isinstance(sample_record, dict)
        }
        migrated = {}
        for old_key, value in normalized_old_record.items():
            target_key = rename_map.get(old_key, old_key)
            if target_key in new_keys:
                migrated[target_key] = value
        output[int(sample_id)] = normalize_sample_catalog_record(migrated, new_schema)
    return output


def dropped_sample_metadata_keys(old_schema, new_schema, rename_map=None):
    rename_map = dict(rename_map or {})
    old_keys = set(sample_metadata_field_keys(old_schema))
    new_keys = set(sample_metadata_field_keys(new_schema))
    return sorted(
        old_key
        for old_key in old_keys
        if rename_map.get(old_key, old_key) not in new_keys
    )
