"""Prepare native toolkit input from Icescopy's in-memory count table.

This maps stored fields and calculates observed fractions, never concentrations
or blank corrections. The external toolkit validates every uploaded experiment.
"""
import hashlib
import json
import math
from collections import defaultdict

import pandas as pd
from icescopy_inptk_state import curve_specs
from icescopy_sample_metadata import WATER_BLANK_SAMPLE_TYPE


NORMALIZATION_FIELDS = ('air_volume_L', 'suspension_volume_mL', 'filter_fraction_used', 'dry_mass_g')
PLOT_COLUMNS = ('temperature_C', 'concentration', 'lower_error', 'upper_error', 'unit',
                'basis', 'segment_id', 'point_order', 'contributor_count', 'qc_flag', 'reporting_status')


def prepare_source(headers, rows, metadata):
    positions = {name: i for i, name in enumerate(headers)}
    if len(positions) != len(headers): raise ValueError('Freeze-count column names must be unique.')
    pairs = [(name[:-len(' number total')], i, positions.get(name[:-len('total')]+'frozen'))
             for i, name in enumerate(headers) if name.endswith(' number total')]
    if not pairs or any(frozen is None for _, _, frozen in pairs):
        raise ValueError('Freeze counts need paired total and frozen columns for every sample.')
    if any(len(row) != len(headers) for row in rows): raise ValueError('Freeze-count rows have inconsistent lengths.')
    temperature = positions.get('temperature_C')
    if temperature is None: raise ValueError('Freeze counts need temperature_C.')
    cycle_col = positions.get('cycle')
    cycles = [str(row[cycle_col]).strip() if cycle_col is not None else '' for row in rows]
    if any(cycles) and not all(cycles): raise ValueError('Some freezing cycle labels are missing.')
    if not any(cycles): cycles = ['1'] * len(rows)
    time_values = None
    if 'time_s' in positions:
        time_values = [float(row[positions['time_s']]) for row in rows]
    elif 'timestamp' in positions:
        timestamps = pd.to_datetime([row[positions['timestamp']] for row in rows], errors='raise')
        if timestamps.isna().any(): raise ValueError('Freeze counts have missing timestamps.')
        time_values = (timestamps-timestamps[0]).total_seconds().tolist()
    picture_col = positions.get('picture', positions.get('image_name'))
    counts, records, measurements, missing = [], [], [], {}
    for sample_index, (key, total_col, frozen_col) in enumerate(pairs):
        original = metadata[sample_index] if sample_index < len(metadata) else {}
        record = {'measurement_id': key, 'sample_id': key, 'run_id': '1',
                  'sample_type': original.get('sample_type') or 'other'}
        for destination, source in (('dilution', 'dilution'), ('droplet_volume_uL', 'well_volume_uL'),
                                    *((field, field) for field in NORMALIZATION_FIELDS)):
            value = original.get(source)
            try: parsed = float(value) if value not in (None, '', 'NA') else None
            except (TypeError, ValueError): parsed = None
            record[destination] = parsed if parsed is None or math.isfinite(parsed) else None
        required_fields = ('droplet_volume_uL',) if record['sample_type'] == WATER_BLANK_SAMPLE_TYPE else ('dilution', 'droplet_volume_uL')
        required = [field for field in required_fields if record[field] is None]
        sample_rows, observation_number = [], defaultdict(int)
        for index, row in enumerate(rows):
            if row[total_col] in ('', None) or row[frozen_col] in ('', None): continue
            total, frozen, temp = float(row[total_col]), float(row[frozen_col]), float(row[temperature])
            if not all(math.isfinite(v) for v in (total, frozen, temp)):
                raise ValueError(f'{key}: counts and temperatures must be finite.')
            if total <= 0 or frozen < 0 or frozen > total or total % 1 or frozen % 1:
                raise ValueError(f'{key}: require whole counts, 0 ≤ frozen ≤ total, and total > 0.')
            cycle = cycles[index]
            count = dict(measurement_id=key, run_id='1', cycle_id=cycle, temperature_C=temp,
                         observation_id=str(observation_number[cycle]), n_total=int(total), n_frozen=int(frozen))
            observation_number[cycle] += 1
            if time_values is not None:
                if not math.isfinite(time_values[index]): raise ValueError('Observation times must be finite.')
                count['time_s'] = time_values[index]
            if picture_col is not None: count['picture_id'] = str(row[picture_col] or '')
            counts.append(count)
            sample_rows.append(dict(count, sample_id=key, fraction_frozen=frozen/total))
        if not sample_rows: continue
        if required: missing[key] = required
        records.append(record)
        measurements.append(dict(measurement_id=key, run_id='1', sample_id=key,
            cycle_ids=list(dict.fromkeys(r['cycle_id'] for r in sample_rows)), observation_count=len(sample_rows),
            temperature_min_C=min(r['temperature_C'] for r in sample_rows),
            temperature_max_C=max(r['temperature_C'] for r in sample_rows)))
    if not counts: raise ValueError('No count observations found.')
    # Counts remain previewable before physical concentration metadata is complete.
    preview_rows = [dict(row, sample_id=row['measurement_id'], fraction_frozen=row['n_frozen']/row['n_total']) for row in counts]
    columns = {key: [row[key] for row in counts] for key in counts[0]}
    digest = hashlib.sha256(json.dumps([columns, records], allow_nan=False, separators=(',', ':')).encode()).hexdigest()
    error = ('Missing concentration metadata: '+ '; '.join(f"{key}: {', '.join(fields)}" for key, fields in missing.items())) if missing else None
    preview = {'measurements': measurements, 'measurement_metadata': records,
               'table': {'columns': list(preview_rows[0]), 'rows': preview_rows},
               'suspension_metadata': {'valid': not missing, 'error': error, 'missing_fields': missing},
               'analysis_performed': False}
    return {'counts': columns, 'metadata': records, 'hash': digest, 'preview': preview}


def upload_scope(settings, *, selected=None):
    """Only requested physical samples and their explicitly assigned blanks."""
    specs = curve_specs(settings, selected=selected)
    targets = {member['measurement_id'] for spec in specs.values() for member in spec['inputs']}
    blanks = {blank for key in targets for blank in settings['inputs'][key]['blanks']}
    return {key: (settings['inputs'][key]['group'],
                  tuple(settings['inputs'][key]['blanks']) if key in targets else ())
            for key in sorted(targets | blanks)}


def upload_choices(source, settings, *, selected=None):
    """Snapshot requested counts, grouping and blanks into a new experiment.

    Keep the complete source for raw plots; unrelated inputs must not become
    analysis samples or impose metadata/blank requirements on this experiment.
    """
    scope = upload_scope(settings, selected=selected)
    records = []
    for original in source['metadata']:
        record = dict(original)
        key = record['measurement_id']
        if key not in scope: continue
        record['sample_id'] = scope[key][0]
        if settings['inputs'][key]['blank']:
            # Preserve the catalog role. The toolkit supplies the neutral blank
            # dilution; only the actual well volume and counts affect correction.
            record['sample_type'] = WATER_BLANK_SAMPLE_TYPE
            record.pop('dilution', None)
            for field in NORMALIZATION_FIELDS:
                record.pop(field, None)
        records.append({key: value for key, value in record.items() if value is not None})
    blank_map = {key: list(blanks) for key, (_group, blanks) in scope.items() if blanks}
    indices = [i for i, key in enumerate(source['counts']['measurement_id']) if key in scope]
    counts = {column: [values[i] for i in indices] for column, values in source['counts'].items()}
    return {'counts': counts, 'metadata': records, 'water_blank_map': blank_map, 'run_id': '1'}
