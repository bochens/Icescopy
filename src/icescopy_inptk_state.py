"""Session choices and CLI argument construction for the INP panel."""
import copy
import hashlib
import json
import math
import re

from icescopy_sample_metadata import WATER_BLANK_SAMPLE_TYPE


MIN_INPTK_VERSION = (0, 4, 4)


def require_toolkit_version(value):
    """Reject versions missing the temperature-range result contract."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:[.\-+]|$)', str(value))
    if match is None or tuple(map(int, match.groups())) < MIN_INPTK_VERSION:
        raise ValueError(f'This Icescopy needs INP-toolkit 0.4.4 or newer (found {value}). '
                         'Install the matching INP-toolkit release.')


# External-toolkit options; the client enables them only when advertised.
BLANK_ONSET_FLAG = "--water-blank-after-first-freeze"
BLANK_RANGE_FLAG = "--water-blank-temperature-range"


def new_settings():
    return {
        "inputs": {}, "curves": [], "ranges": {}, "blank_range": {}, "method": "mle",
        "blank_correction": True, "blank_after_first_freeze": False, "basis": "suspension",
        "grid_step": "0.5", "grid_start": "0", "grid_end": "-35", "grid_method": "latest",
        "grid_window": "", "decrease_policy": "stop_at_decrease", "z": "1.96",
        "min_frozen": 3, "min_unfrozen": 3, "suggestion": None,
    }


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def copy_choices(settings):
    """Copy editable choices, sharing the immutable CLI suggestion report.

    A report may contain thousands of original observations. No control edits
    that report; keeping it out of deep copies makes normal editing inexpensive.
    """
    result = copy.deepcopy({k: v for k, v in settings.items() if k != "suggestion"})
    result["suggestion"] = settings.get("suggestion")
    return result


def individual_choices(settings):
    """Direct full-range sample/blank calculations, independent of combination."""
    result = copy_choices(settings)
    keys = list(dict.fromkeys(k for c in settings["curves"] for k in c["inputs"]))
    result["curves"] = [{"name": key, "inputs": [key]} for key in keys]
    result["ranges"] = {}
    result["suggestion"] = None
    result["method"] = "average"
    return result


def number(value):
    if isinstance(value, dict) and "$nonfinite" in value:
        return float(value["$nonfinite"])
    try:
        return float(value)
    except (ValueError, TypeError):
        return float("nan")


def automatic_blank_assignments(settings):
    """Apply the selected catalog water blanks to each non-blank sample."""
    state = copy_choices(settings)
    blanks = [key for key, value in state["inputs"].items() if value["blank"] and value.get("use_blank", True)]
    for value in state["inputs"].values():
        value["blanks"] = [] if value["blank"] else list(blanks)
    return state


def available_concentration_bases(settings, metadata):
    """Offer normalization shared by all samples included in calculation."""
    used = {key for curve in settings["curves"] for key in curve["inputs"]
            if key in settings["inputs"] and not settings["inputs"][key]["blank"]}
    if not used:
        used = {key for key, value in settings["inputs"].items() if not value["blank"]}
    catalog = {row["measurement_id"]: row for row in metadata}
    types = {catalog.get(key, {}).get("sample_type", "other") for key in used}
    if types == {"air"}:
        return ("suspension", "sampled_air")
    if types == {"soil"}:
        return ("suspension", "dry_soil")
    return ("suspension",)


def reconcile_inputs(settings, preview):
    """Take blank roles from catalog types, preserving exact input selections."""
    result = copy_choices(settings)
    known = result["inputs"]
    result["inputs"] = {}
    metadata = {row["measurement_id"]: row for row in preview.get("measurement_metadata", [])}
    for measurement in preview.get("measurements", []):
        key = measurement["measurement_id"]
        cycles = [str(c) for c in measurement["cycle_ids"]]
        value = copy.deepcopy(known.get(key, {
            "group": key, "blank": False, "blanks": [],
            "cycle": cycles[0] if len(cycles) == 1 else "",
        }))
        value["blank"] = metadata.get(key, {}).get("sample_type") == WATER_BLANK_SAMPLE_TYPE
        value.setdefault("use_blank", True)
        if value["blank"]:
            value["group"] = key
        if value["cycle"] not in cycles:
            value["cycle"] = cycles[0] if len(cycles) == 1 else ""
        result["inputs"][key] = value
    # A catalog water blank cannot also be an analysis sample. Preserve empty
    # groups created by the user, but remove groups emptied by a role change.
    curves = []
    for curve in result["curves"]:
        previous = curve["inputs"]
        curve["inputs"] = [key for key in previous if key in result["inputs"] and not result["inputs"][key]["blank"]]
        if curve["inputs"] or not previous:
            curves.append(curve)
    result["curves"] = curves
    assigned = {key for curve in curves for key in curve["inputs"]}
    for key, value in result["inputs"].items():
        if not value["blank"] and known.get(key, {}).get("blank") and key not in assigned:
            name, suffix = key, 2
            while name in {curve["name"] for curve in curves}:
                name = f"{key} ({suffix})"; suffix += 1
            value["group"] = name
            curves.append({"name": name, "inputs": [key]})
    return automatic_blank_assignments(result)


def curve_specs(settings, *, selected=None):
    curves = {}
    inputs = settings["inputs"]
    for curve in settings["curves"]:
        if selected is not None and curve["name"] != selected:
            continue
        name = curve["name"].strip()
        if not name or name in curves:
            raise ValueError("Each output curve needs a unique, nonempty name.")
        if not curve["inputs"] or len(set(curve["inputs"])) != len(curve["inputs"]):
            raise ValueError(f"Choose distinct inputs for {name}.")
        chosen, groups = [], set()
        for key in curve["inputs"]:
            if key not in inputs:
                raise ValueError(f"{name}: input {key} is no longer available. Edit its inputs.")
            value = inputs[key]
            if value["blank"]:
                raise ValueError(f"{key} is a blank; remove it from {name}.")
            if not value["cycle"]:
                raise ValueError(f"Select a cycle for {key}.")
            if not value["group"].strip():
                raise ValueError(f"Enter an original-sample group for {key}.")
            groups.add(value["group"])
            chosen.append({"measurement_id": key, "cycle_id": value["cycle"]})
        if len(groups) != 1:
            raise ValueError(f"{name}: combined inputs must belong to the same original sample.")
        curves[name] = {"inputs": chosen}
    if not curves:
        raise ValueError("Add an output curve and choose its inputs.")
    return curves


def concentration_curves(settings):
    """Request group outputs and each physical member once, without regrouping it."""
    specs = curve_specs(settings)
    individual = {}
    singles = {tuple((i['measurement_id'], i['cycle_id']) for i in spec['inputs']): name
               for name, spec in specs.items() if len(spec['inputs']) == 1}
    for group_name, spec in list(specs.items()):
        if len(spec['inputs']) < 2: continue
        for member in spec['inputs']:
            identity = ((member['measurement_id'], member['cycle_id']),)
            name = singles.get(identity)
            if name is None:
                base = f"{group_name} / {member['measurement_id']}"
                name, suffix = base, 2
                while name in specs:
                    name = f"{base} ({suffix})"; suffix += 1
                specs[name] = {'inputs': [copy.deepcopy(member)]}
                singles[identity] = name
            individual[name] = member['measurement_id']
    return specs, individual


def temperature_range(settings, key):
    """Forward only user limits; an empty range means toolkit Full range."""
    return dict(settings["ranges"].get(key, {}))


def cli_choices(settings, *, suggest=False, selected=None, include_individual=False, saved=False):
    specs = curve_specs(settings, selected=selected)
    if include_individual and not suggest: specs, _ = concentration_curves(settings)
    inputs = settings["inputs"]
    blank_map = {}
    used = {i["measurement_id"] for curve in specs.values() for i in curve["inputs"]}
    for key in used:
        blanks = inputs[key]["blanks"]
        for blank in blanks:
            if blank not in inputs or not inputs[blank]["blank"]:
                raise ValueError(f"{key}: assigned blank {blank} is no longer marked as a blank.")
        if blanks:
            blank_map[key] = blanks
    args = ["--sample-map", json.dumps({k: v["group"] for k, v in inputs.items()}),
            "--curves", json.dumps(specs), "--water-blank-map", json.dumps(blank_map)]
    if saved: args = ['--curves', json.dumps(specs)]
    if not settings["blank_correction"]:
        args.append("--no-water-blank-correction")
    elif settings["blank_after_first_freeze"]:
        args.append(BLANK_ONSET_FLAG)
    blank_range = dict(settings["blank_range"])
    if settings["blank_after_first_freeze"]:
        blank_range.pop("max_C", None)
    if settings["blank_correction"] and blank_map and blank_range:
        if any(not math.isfinite(float(v)) for v in blank_range.values()):
            raise ValueError("Water-blank limits must be finite temperatures.")
        if blank_range.get("min_C", -math.inf) > blank_range.get("max_C", math.inf):
            raise ValueError("The water-blank cold limit must not exceed the warm limit.")
        args += [BLANK_RANGE_FLAG, json.dumps(blank_range)]
    numeric = {"z": "--z"}
    if settings["grid_step"].strip():
        numeric.update(grid_step="--temperature-step-C", grid_start="--temperature-start-C",
                       grid_end="--temperature-end-C")
        args += ["--temperature-method", settings["grid_method"]]
        if settings["grid_method"] == "window":
            if not settings["grid_window"].strip():
                raise ValueError("Enter the full count-selection window width in °C.")
            numeric["grid_window"] = "--temperature-window-C"
    if suggest:
        args += ["--min-frozen", str(settings["min_frozen"]),
                 "--min-unfrozen", str(settings["min_unfrozen"])]
    else:
        args += ["--method", settings["method"], "--output-basis", settings["basis"],
                 "--decrease-policy", settings["decrease_policy"]]
        ranges = {key: temperature_range(settings, key) for key in sorted(used)
                  if settings["ranges"].get(key)}
        for key, limits in ranges.items():
            if any(not math.isfinite(float(v)) for v in limits.values()):
                raise ValueError(f"{key}: limits must be finite temperatures.")
            if limits.get("min_C", -math.inf) > limits.get("max_C", math.inf):
                raise ValueError(f"{key}: the cold limit must not exceed the warm limit.")
        args += ["--temperature-ranges", json.dumps(ranges)]
    for key, flag in numeric.items():
        text = settings[key].strip()
        # Blank endpoint fields mean the same defaults displayed in the client,
        # including sessions saved before these endpoints were explicit.
        if key in {"grid_start", "grid_end"} and not text:
            text = {"grid_start": "0", "grid_end": "-35"}[key]
        if not text:
            continue
        label = {"z": "Uncertainty z",
                 "grid_step": "Count step (°C)", "grid_start": "Warm end (°C)",
                 "grid_end": "Cold end (°C)", "grid_window": "Window width (°C)"}[key]
        try: value = float(text)
        except (ValueError, TypeError): value = math.nan
        if not math.isfinite(value) or (key in {"z", "grid_step", "grid_window"} and value <= 0):
            raise ValueError(f"Enter a valid number for {label}.")
        args += [flag, text]
    return args


def set_group_inputs(settings, index, members):
    """Assign selected physical inputs to one group, moving them from others.

    Unchecking an input leaves its data available as an individual group. The
    client never invents an additional independent replicate of a physical input.
    """
    result = copy_choices(settings)
    target = result['curves'][index]
    members = list(dict.fromkeys(members))
    removed = set(target['inputs']) - set(members)
    target['inputs'] = members
    for curve in result['curves']:
        if curve is not target:
            curve['inputs'] = [key for key in curve['inputs'] if key not in members]
    result['curves'] = [c for c in result['curves'] if c is target or c['inputs']]
    assigned = {key for c in result['curves'] for key in c['inputs']}
    for key in sorted(removed - assigned):
        if result['inputs'][key]['blank']: continue
        name, suffix = key, 2
        while name in {c['name'] for c in result['curves']}:
            name = f'{key} ({suffix})'; suffix += 1
        result['curves'].append({'name': name, 'inputs': [key]})
    for curve in result['curves']:
        for key in curve['inputs']:
            result['inputs'][key]['group'] = curve['name']
    return result
