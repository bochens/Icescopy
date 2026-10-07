"""Native input preparation and version checks do not require Qt or the CLI."""
import copy
import unittest
from icescopy_inptk_data import prepare_source
from icescopy_inptk_state import require_toolkit_version


class SourcePreparationTests(unittest.TestCase):
    def setUp(self):
        self.headers = ['image_name', 'timestamp', 'temperature_C', 'cycle', 'A number total', 'A number frozen']
        self.rows = [['one', '2026-01-01 00:00:00', -1, '1', 10, 0],
                     ['two', '2026-01-01 00:00:10', -2, '1', 10, 2]]
        self.metadata = [{'well_volume_uL': 50, 'dilution': 1}]

    def prepare(self, rows):
        return prepare_source(self.headers, rows, self.metadata)

    def test_valid_input_hash_is_unchanged(self):
        source = self.prepare(self.rows)
        self.assertEqual(source['hash'], '0777157b1074a8bd6c6d55f67c17f9289a46caad7a287b8666a99bb378c69c14')
        self.assertEqual(source['skipped_images'], [])

    def test_rows_without_temperature_or_cycle_are_reported_and_skipped(self):
        for bad in (["after", '2026-01-01 00:00:20', '', '1', 10, 3],
                    ["before", '2025-12-31 23:59:50', '', '1', 10, 0],
                    ["unparsed", '', '', '', 10, 0],
                    ["pku", '', -3, '', 10, 0]):
            with self.subTest(image=bad[0]):
                rows = [bad, *self.rows]
                original = copy.deepcopy(rows)
                source = self.prepare(rows)
                self.assertEqual(source['skipped_images'], [bad[0]])
                self.assertEqual(source['counts']['time_s'], [0, 10])
                self.assertEqual(source['hash'], self.prepare(self.rows)['hash'])
                self.assertEqual(rows, original)

    def test_empty_source_and_invalid_counts_are_errors(self):
        with self.assertRaisesRegex(ValueError, 'No freeze-count rows'):
            self.prepare([['bad', '', '', '', 10, 0]])
        self.rows[1][-1] = 11
        with self.assertRaisesRegex(ValueError, 'whole counts'):
            self.prepare(self.rows)

    def test_sample_calibration_overrides_raw_temperature(self):
        self.headers += ['A corrected temperature_C']
        self.rows[0] += [-1.5]
        self.rows[1] += ['']
        source = self.prepare(self.rows)
        self.assertEqual(source['counts']['temperature_C'], [-1.5, -2])
        self.assertEqual([r['temperature_C'] for r in source['preview']['table']['rows']], [-1.5, -2])

    def test_toolkit_version_requirement(self):
        for value in ('0.4.4', '0.4.5', '0.4.5.dev0', '1.0.0'):
            require_toolkit_version(value)
        for value in ('0.4.3', 'unknown', None, '0.4'):
            with self.subTest(version=value), self.assertRaisesRegex(ValueError, '0.4.4 or newer'):
                require_toolkit_version(value)
