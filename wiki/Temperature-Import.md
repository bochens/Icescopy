# Temperature Import

This page describes the temperature import workflows currently supported by Icescopy.

## Supported importers

The current application supports:

- CSU `.dat`
- TAMU Linkam `.xlsx`

These importers are not interchangeable.
Choose the importer that matches the external data format you actually have.

## CSU import

Use the CSU importer when you have the CSU `.dat` output format.

The CSU workflow supports:

- sample matching
- blank sample designation
- reset-after-warmed-to cycle splitting

## CSU blank correction

Blank correction is applied within a cycle.

In the current logic:

- the imported `.dat` series is treated as cumulative count data
- image-derived anchor points from Icescopy are used to reconcile the cumulative series
- blank samples contribute a cumulative blank correction within each cycle

The algorithm defaults to the imported cumulative series when it is consistent, but corrects it when it violates:

- monotonic accumulation
- anchor constraints
- count bounds

## TAMU Linkam import

Use the TAMU importer when you have a TAMU Linkam workbook.

This workflow uses:

- image timestamps parsed from PNG filenames
- time interpolation against the workbook timeseries
- optional calibration CSV by cell ID

## Reset After Warmed To

The reset threshold is used to split repeated cooling-warming cycles.

Use it when:

- the experiment contains repeated cycles
- counts should restart after the timeseries warms back above a chosen threshold

If the threshold is wrong, cycle boundaries will also be wrong.

## Review the output

After import, check:

- sample matching
- temperature alignment
- cycle boundaries
- whether the cumulative count shape makes sense against the image sequence

## Practical warnings

- if image timestamps are wrong, TAMU output will be wrong
- if sample assignment is wrong, grouped output will be wrong
- if freeze annotations are stale, freeze count timeseries will also be stale
