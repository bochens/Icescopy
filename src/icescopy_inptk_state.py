"""Session choices and CLI argument construction for the INP panel."""
import copy
import hashlib
import json
import math


def new_settings():
    return {
        "inputs": {}, "curves": [], "ranges": {}, "method": "mle",
        "blank_correction": True, "basis": "suspension", "fit_step": "",
        "grid_step": "", "grid_start": "", "grid_end": "", "grid_method": "latest",
        "grid_window": "", "decrease_policy": "stop_at_decrease", "z": "1.96",
        "min_frozen": 3, "min_unfrozen": 3, "suggestion": None,
    }


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def number(value):
    if isinstance(value, dict) and "$nonfinite" in value:
        return float(value["$nonfinite"])
    try:
        return float(value)
    except (ValueError, TypeError):
        return float("nan")


def reconcile_inputs(settings, preview):
    """Keep explicit choices only for exact known input identities; never infer blanks."""
    result = copy.deepcopy(settings)
    known = result["inputs"]
    result["inputs"] = {}
    for measurement in preview.get("measurements", []):
        key = measurement["measurement_id"]
        cycles = [str(c) for c in measurement["cycle_ids"]]
        value = copy.deepcopy(known.get(key, {
            "group": key, "blank": False, "blanks": [],
            "cycle": cycles[0] if len(cycles) == 1 else "",
        }))
        if value["cycle"] not in cycles:
            value["cycle"] = cycles[0] if len(cycles) == 1 else ""
        result["inputs"][key] = value
    return result


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


def cli_choices(settings, *, suggest=False, selected=None):
    specs = curve_specs(settings, selected=selected)
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
    if not settings["blank_correction"]:
        args.append("--no-water-blank-correction")
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
        if settings["method"] == "mle":
            numeric["fit_step"] = "--fit-step-C"
        ranges = {key: value for key, value in settings["ranges"].items() if key in used and value}
        for key, limits in ranges.items():
            if any(not math.isfinite(float(v)) for v in limits.values()):
                raise ValueError(f"{key}: limits must be finite temperatures.")
            if limits.get("min_C", -math.inf) > limits.get("max_C", math.inf):
                raise ValueError(f"{key}: the cold limit must not exceed the warm limit.")
        args += ["--temperature-ranges", json.dumps(ranges)]
    for key, flag in numeric.items():
        text = settings[key].strip()
        if not text:
            continue
        value = float(text)
        if not math.isfinite(value) or (key in {"z", "fit_step", "grid_step", "grid_window"} and value <= 0):
            raise ValueError(f"Enter a valid value for {key.replace('_', ' ')}.")
        args += [flag, text]
    return args
