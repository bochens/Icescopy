"""Small CSV layouts for exact toolkit results; no fitting or resampling."""
import csv
import json
import math
from pathlib import Path

from icescopy_inptk_state import number


UNITS = {"INP_per_mL_suspension": "INP/mL suspension", "INP_per_L_air": "INP/L air",
         "INP_per_g_dry_soil": "INP/g dry soil"}


def concentration_csv(tables, curves):
    """One temperature column, then one concentration column per curve.

    Temperatures and estimates come directly from the saved calculation. Missing
    temperatures stay empty; zero estimates remain zero. No rounding,
    interpolation or extrapolation changes the toolkit values.
    """
    headers = ["temperature_C"]
    series = []
    temperatures = set()
    if not curves or len({label for label, _ in curves}) != len(curves):
        raise ValueError("Choose distinct calculated curves to export.")
    units = set()
    for label, name in curves:
        table = tables.get(name, {}).get("cumulative")
        if table is None:
            raise ValueError(f"Concentration for {label} is unavailable. Recalculate before exporting.")
        points = {}
        for row in table["rows"]:
            temperature = number(row.get("temperature_C"))
            if not math.isfinite(temperature):
                raise ValueError(f"{label}: cannot export a nonfinite temperature.")
            if temperature in points:
                # A wide table cannot silently collapse separate observations.
                raise ValueError(f"{label}: repeated temperature {temperature:g} °C. Enable a temperature grid and recalculate before exporting.")
            value = number(row.get("concentration"))
            points[temperature] = "" if math.isnan(value) else value
            units.add(str(row.get("unit", "")))
        temperatures.update(points)
        series.append((label, points))
    if len(units) != 1 or not next(iter(units), ""):
        raise ValueError("Concentration curves must have one common saved unit.")
    unit = UNITS.get(next(iter(units)), next(iter(units)))
    for label, _ in series:
        headers.append(f"{label} concentration ({unit})")
    rows = [[temperature, *(points.get(temperature, "") for _, points in series)]
            for temperature in sorted(temperatures, reverse=True)]
    if not rows:
        raise ValueError("No calculated concentration points are available to export.")
    return headers, rows


def frozen_fraction_csv(table, choices, selected=None):
    """Use the toolkit's chosen observation IDs for gridded fractions.

    This joins already calculated fractions to already selected observations;
    it does not select, interpolate or correct the original counts.
    """
    used = {(key, str(choices["inputs"][key]["cycle"]))
            for curve in choices["curves"] for key in curve["inputs"]}
    used.update((blank, cycle) for key, cycle in tuple(used) for blank in choices["inputs"][key]["blanks"])
    if selected is not None:
        identity = lambda row: tuple(str(row[field]) for field in
                                     ('measurement_id', 'run_id', 'cycle_id', 'observation_id'))
        fractions = {identity(row): row['fraction_frozen'] for row in table['rows']}
        points = {}
        for point in selected:
            records = point.get('source_observations') or []
            if isinstance(records, str): records = json.loads(records)
            for record in records:
                key = record['measurement_id']
                if (key, str(record['cycle_id'])) not in used: continue
                value = fractions[identity(record)]
                values = points.setdefault(number(point['temperature_C']), {})
                if key in values and values[key] != value:
                    raise ValueError(f'{key}: conflicting selected fractions at one temperature.')
                values[key] = value
        names = [key for key in choices['inputs'] if any(member == key for member, _ in used)]
        rows = [[t, *(points[t].get(key, '') for key in names)] for t in sorted(points, reverse=True)]
        if not rows: raise ValueError('No selected frozen fractions are available to export.')
        return ['temperature_C', *(key + ' fraction_frozen' for key in names)], rows
    rows = [[row["temperature_C"], row["measurement_id"], row["cycle_id"], row["fraction_frozen"]]
            for row in table["rows"] if (row["measurement_id"], str(row["cycle_id"])) in used]
    if not rows:
        raise ValueError("No measured frozen fractions are available to export.")
    return ["temperature_C", "sample", "cycle", "fraction_frozen"], rows


def write_csv(path, headers, rows):
    """Never overwrite a file; remove only our newly created incomplete file."""
    target = Path(path)
    created = False
    try:
        with target.open("x", encoding="utf-8", newline="") as handle:
            created = True
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
