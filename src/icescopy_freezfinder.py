from PySide6.QtWidgets import (QPushButton, QFileDialog, QVBoxLayout, QLineEdit, QLabel,
                              QSizePolicy, QHBoxLayout,QDialog, QSpacerItem, QFrame, QRadioButton)
from PySide6.QtGui import Qt
import os
import platform
import numpy as np
import pandas as pd
from scipy import signal
import re

DEFAULT_FREEZE_RESULT_HEADERS = [
    'cell',
    'image_index',
    'image_name',
]

DEFAULT_FREEZE_FINDER_WIDTH = 10.0
DEFAULT_FREEZE_FINDER_PROMINENCE = 100.0
DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS = 5
DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS = 0
DEFAULT_CONVOLUTION_RAMP_POINTS = 0
DEFAULT_ONSET_DIFF_FRACTION = 0.5
DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING = False


def build_image_datetime_array(datetime_array, filename_array):
    datetime_array = np.asarray(datetime_array, dtype=object)
    filename_array = np.asarray(filename_array, dtype=object)

    if datetime_array.size == 0:
        return np.array([], dtype='datetime64[us]')

    first_value = datetime_array[0]
    if first_value in (None, '', 'None'):
        datetime_strs = []
        for fname in filename_array:
            parts = str(fname).split('-')
            if len(parts) >= 6:
                datetime_strs.append(
                    parts[0] + '-' + parts[1] + '-' + parts[2] + 'T' +
                    parts[3] + ':' + parts[4] + ':' + parts[5]
                )
            else:
                datetime_strs.append('NaT')
        return np.array(datetime_strs, dtype='datetime64[us]')

    return np.array(datetime_array, dtype='datetime64[us]')


def read_grayscale_csv(gsm_file_path):
    str_array = np.loadtxt(gsm_file_path, delimiter=",", dtype=str, skiprows=2)
    if str_array.ndim == 1:
        str_array = np.expand_dims(str_array, axis=0)

    filename_array = str_array[:, 0]
    datetime_array = str_array[:, 1]
    flag_array = str_array[:, 2] == 'flagged'
    circle_data = str_array[:, 3:].astype(float) if str_array.shape[1] > 3 else np.empty((len(str_array), 0))
    image_grayscale_data = circle_data[:, ::4] if circle_data.size else np.empty((len(str_array), 0))
    image_datetime_array = build_image_datetime_array(datetime_array, filename_array)

    return {
        'filename_array': filename_array,
        'datetime_array': datetime_array,
        'image_datetime_array': image_datetime_array,
        'flag_array': flag_array,
        'circle_data': circle_data,
        'image_grayscale_data': image_grayscale_data,
    }


def compute_freeze_result_rows(
    filename_array,
    image_datetime_array,
    image_grayscale_data,
    width=DEFAULT_FREEZE_FINDER_WIDTH,
    prominence=DEFAULT_FREEZE_FINDER_PROMINENCE,
    tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
    convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
    detect_brightening=DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING,
    cell_ids=None,
    interpolated_image_temps=None,
    correction_func=None,
):
    freeze_result_rows = []
    peak_indexes_by_cell = []

    image_grayscale_data = np.asarray(image_grayscale_data, dtype=float)
    if image_grayscale_data.ndim == 1 and image_grayscale_data.size:
        image_grayscale_data = image_grayscale_data.reshape(-1, 1)

    if image_grayscale_data.size == 0:
        return freeze_result_rows, peak_indexes_by_cell

    resolved_cell_ids = None
    if cell_ids is not None:
        resolved_cell_ids = [int(value) for value in cell_ids]

    for cell_index in np.arange(image_grayscale_data.shape[1]):
        raw_grayscale = np.asarray(image_grayscale_data[:, cell_index], dtype=float)
        cell_id = (
            int(resolved_cell_ids[cell_index])
            if resolved_cell_ids is not None and cell_index < len(resolved_cell_ids)
            else int(cell_index)
        )
        extend_count = int(max(0, tail_extend_points))
        _, g_array_step = compute_convolution_timeseries(
            raw_grayscale,
            tail_extend_points=tail_extend_points,
            convolution_half_window_points=convolution_half_window_points,
            convolution_ramp_points=convolution_ramp_points,
        )
        center_offset = compute_convolution_center_offset(
            len(raw_grayscale) + extend_count,
            convolution_half_window_points=convolution_half_window_points,
            convolution_ramp_points=convolution_ramp_points,
        )

        peaks, peak_properties = signal.find_peaks(
            g_array_step if detect_brightening else -g_array_step,
            width=width,
            prominence=prominence,
        )
        left_ips = peak_properties.get("left_ips", peaks.astype(float))
        right_ips = peak_properties.get("right_ips", peaks.astype(float))
        event_indexes = []
        max_frame_index = len(filename_array) - 1
        for peak_index, left_ip, right_ip in zip(peaks, left_ips, right_ips):
            event_indexes.append(
                refine_event_index_from_raw_timeseries(
                    raw_grayscale,
                    peak_index,
                    left_ip,
                    right_ip,
                    center_offset,
                    max_frame_index,
                    detect_brightening=detect_brightening,
                )
            )

        event_indexes = np.asarray(event_indexes, dtype=int)
        peak_indexes_by_cell.append(event_indexes)

        for peak_index in event_indexes:
            refined_index = int(peak_index)
            row = [
                f'cell_{cell_id}',
                str(refined_index),
                str(filename_array[refined_index]),
            ]
            freeze_result_rows.append(row)

    return freeze_result_rows, peak_indexes_by_cell


def refine_event_index_from_raw_timeseries(
    raw_grayscale,
    peak_index,
    left_ip,
    right_ip,
    center_offset,
    max_frame_index,
    onset_diff_fraction=DEFAULT_ONSET_DIFF_FRACTION,
    detect_brightening=DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING,
):
    search_start = max(0, int(np.floor(float(left_ip) + center_offset)) - 1)
    search_end = min(max_frame_index, int(np.ceil(float(right_ip) + center_offset)) + 1)

    if search_end <= search_start:
        event_position = float(peak_index) + center_offset
        return int(np.clip(np.floor(event_position), 0, max_frame_index))

    raw_window = np.asarray(raw_grayscale[search_start : search_end + 1], dtype=float)
    if raw_window.size < 2:
        event_position = float(peak_index) + center_offset
        return int(np.clip(np.floor(event_position), 0, max_frame_index))

    raw_diffs = np.diff(raw_window)
    candidate_indexes = np.where(raw_diffs > 0)[0] if detect_brightening else np.where(raw_diffs < 0)[0]
    if candidate_indexes.size == 0:
        event_position = float(peak_index) + center_offset
        return int(np.clip(np.floor(event_position), 0, max_frame_index))

    candidate_magnitudes = raw_diffs[candidate_indexes] if detect_brightening else -raw_diffs[candidate_indexes]
    if candidate_magnitudes.size == 1:
        onset_local_index = int(candidate_indexes[0])
    else:
        # Split the candidate derivative magnitudes into two groups
        # (small changes vs large freezing steps) using a simple 1D 2-means
        # fit, then choose the first derivative in time that belongs to the
        # larger-change cluster.
        centers = np.array(
            [float(np.min(candidate_magnitudes)), float(np.max(candidate_magnitudes))],
            dtype=float,
        )
        if np.isclose(centers[0], centers[1]):
            onset_local_index = int(candidate_indexes[0])
        else:
            labels = np.zeros_like(candidate_magnitudes, dtype=int)
            for _ in range(16):
                distances = np.abs(candidate_magnitudes[:, None] - centers[None, :])
                new_labels = np.argmin(distances, axis=1)
                if np.array_equal(new_labels, labels):
                    break
                labels = new_labels
                for cluster_index in (0, 1):
                    cluster_values = candidate_magnitudes[labels == cluster_index]
                    if cluster_values.size:
                        centers[cluster_index] = float(np.mean(cluster_values))

            large_drop_cluster = int(np.argmax(centers))
            onset_candidates = candidate_indexes[labels == large_drop_cluster]
            if onset_candidates.size == 0:
                onset_local_index = int(candidate_indexes[np.argmax(candidate_magnitudes)])
            else:
                onset_local_index = int(onset_candidates[0])

    # diff[i] is the change from frame i to frame i+1; the first picture after
    # onset is therefore the frame on the right side of that diff.
    return min(max_frame_index, search_start + onset_local_index + 1)


def build_convolution_kernel(
    signal_length,
    convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
):
    signal_length = int(max(1, signal_length))
    half_window_points = int(convolution_half_window_points)
    if half_window_points <= 0:
        half_window_points = signal_length
    half_window_points = min(half_window_points, signal_length)

    total_length = half_window_points * 2
    ramp_points = int(max(0, min(convolution_ramp_points, total_length - 2)))

    if ramp_points <= 0:
        return np.concatenate((
            np.ones(half_window_points, dtype=float),
            -1.0 * np.ones(half_window_points, dtype=float),
        ))

    left_length = max(1, (total_length - ramp_points) // 2)
    right_length = max(1, total_length - ramp_points - left_length)

    kernel_parts = [np.ones(left_length, dtype=float)]
    transition = np.linspace(1.0, -1.0, ramp_points + 2, dtype=float)[1:-1]
    kernel_parts.append(transition)
    kernel_parts.append(-1.0 * np.ones(right_length, dtype=float))
    kernel = np.concatenate(kernel_parts)

    abs_sum = np.sum(np.abs(kernel))
    if abs_sum > 0:
        kernel *= float(total_length) / float(abs_sum)
    return kernel


def compute_convolution_center_offset(
    signal_length,
    convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
):
    kernel = build_convolution_kernel(
        signal_length,
        convolution_half_window_points=convolution_half_window_points,
        convolution_ramp_points=convolution_ramp_points,
    )
    return 0.5 * (len(kernel) - 1)


def compute_convolution_timeseries(
    grayscale_values,
    tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
    convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
):
    g_array = np.asarray(grayscale_values, dtype=float)
    if g_array.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    extend_count = int(max(0, tail_extend_points))
    if extend_count > 0:
        tail_value = float(g_array[-1])
        g_array = np.concatenate((g_array, np.full(extend_count, tail_value, dtype=float)))

    centered = g_array - np.average(g_array)
    kernel = build_convolution_kernel(
        len(centered),
        convolution_half_window_points=convolution_half_window_points,
        convolution_ramp_points=convolution_ramp_points,
    )
    convolved = np.convolve(centered, kernel, mode='valid')
    return centered, convolved


def write_freeze_results_csv(output_csv_path, headers, rows):
    with open(output_csv_path, 'w') as the_file:
        the_file.write(','.join(headers))
        the_file.write("\n")
        for row in rows:
            the_file.write(",".join(row))
            the_file.write("\n")


def build_freeze_output_path(grayscale_csv_path):
    base_path, _ = os.path.splitext(grayscale_csv_path)
    return base_path + "_freeze.csv"


class FreezeFinderDialog(QDialog):
    def __init__(
        self,
        default_grayscale_path=None,
        default_output_dir=None,
        default_width=DEFAULT_FREEZE_FINDER_WIDTH,
        default_prominence=DEFAULT_FREEZE_FINDER_PROMINENCE,
        default_tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
        default_convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
        default_convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
    ):
        super(FreezeFinderDialog, self).__init__()

        self.freeze_result_headers = list(DEFAULT_FREEZE_RESULT_HEADERS)
        self.freeze_result_rows = []
        self.output_csv_path = None

        self.setWindowTitle('Convolution freeze finder script')
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        # Set a fixed height
        self.setFixedHeight(350)

        # Set the vertical size policy to fixed
        sizePolicy = self.sizePolicy()
        sizePolicy.setVerticalPolicy(QSizePolicy.Fixed)
        self.setSizePolicy(sizePolicy)

        # Input File 1 Image grayscale file
        file1_layout = QHBoxLayout()
        self.input_file1_edit = QLineEdit()
        self.input_file1_button = QPushButton('Select')
        self.input_file1_button.clicked.connect(self.select_input_file1)
        file1_layout.addWidget(QLabel('Image grayscale file*:'))
        file1_layout.addWidget(self.input_file1_edit)
        file1_layout.addWidget(self.input_file1_button)
        layout.addLayout(file1_layout)
        self.input_file1_button.setFocusPolicy(Qt.NoFocus)

        # Input File 2 Linkam data file
        file2_layout = QHBoxLayout()
        self.input_file2_edit = QLineEdit()
        self.input_file2_button = QPushButton('Select')
        self.input_file2_button.clicked.connect(self.select_input_file2)
        file2_layout.addWidget(QLabel('Linkam data file*:'))
        file2_layout.addWidget(self.input_file2_edit)
        file2_layout.addWidget(self.input_file2_button)
        layout.addLayout(file2_layout)
        self.input_file2_button.setFocusPolicy(Qt.NoFocus)

        # Input File 3
        file3_layout = QHBoxLayout()
        self.input_file3_edit = QLineEdit()
        self.input_file3_button = QPushButton('Select')
        self.input_file3_button.clicked.connect(self.select_input_file3)
        file3_layout.addWidget(QLabel('Temperature correction file:'))
        file3_layout.addWidget(self.input_file3_edit)
        file3_layout.addWidget(self.input_file3_button)
        layout.addLayout(file3_layout)
        self.input_file3_button.setFocusPolicy(Qt.NoFocus)

        # Output File
        file_output_layout = QHBoxLayout()
        self.output_file_edit = QLineEdit()
        self.output_file_button = QPushButton('Select')
        self.output_file_button.clicked.connect(self.select_output_file)
        file_output_layout.addWidget(QLabel('Output File*:'))
        file_output_layout.addWidget(self.output_file_edit)
        file_output_layout.addWidget(self.output_file_button)
        layout.addLayout(file_output_layout)
        self.output_file_button.setFocusPolicy(Qt.NoFocus)

         # --- Spacer and Separator Line between Output File and Other Inputs ---
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        hline2 = QFrame()
        hline2.setFrameShape(QFrame.HLine)
        hline2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(hline2)

        # Additional Input Boxes for Width and Prominence
        additional_inputs_layout = QHBoxLayout()

        # Width Input
        self.width_edit = QLineEdit()
        additional_inputs_layout.addWidget(QLabel('Peak finding width:'))
        additional_inputs_layout.addWidget(self.width_edit)
        self.width_edit.setText(f"{float(default_width):g}")

        # Prominence Input
        self.prominence_edit = QLineEdit()
        additional_inputs_layout.addWidget(QLabel('Peak finding Prominence:'))
        additional_inputs_layout.addWidget(self.prominence_edit)
        self.prominence_edit.setText(f"{float(default_prominence):g}")

        self.tail_extend_points_edit = QLineEdit()
        additional_inputs_layout.addWidget(QLabel('Tail extension points:'))
        additional_inputs_layout.addWidget(self.tail_extend_points_edit)
        self.tail_extend_points_edit.setText(str(int(default_tail_extend_points)))

        self.convolution_half_window_points_edit = QLineEdit()
        additional_inputs_layout.addWidget(QLabel('Convolution half window points:'))
        additional_inputs_layout.addWidget(self.convolution_half_window_points_edit)
        self.convolution_half_window_points_edit.setText(str(int(default_convolution_half_window_points)))

        self.convolution_ramp_points_edit = QLineEdit()
        additional_inputs_layout.addWidget(QLabel('Convolution ramp points:'))
        additional_inputs_layout.addWidget(self.convolution_ramp_points_edit)
        self.convolution_ramp_points_edit.setText(str(int(default_convolution_ramp_points)))

        layout.addLayout(additional_inputs_layout)

        # OK and Cancel buttons
        self.ok_button = QPushButton('OK')
        self.ok_button.clicked.connect(self.run_freeze_finder_script)

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.ok_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

        if default_grayscale_path:
            self.input_file1_edit.setText(default_grayscale_path)
        if default_output_dir:
            self.output_file_edit.setText(default_output_dir)
        

    def select_input_file1(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            'Select image grayscale file',
            "",
            "",
            options=self.file_dialog_options(),
        )
        if file_name:
            self.input_file1_edit.setText(file_name)

    def select_input_file2(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            'Select Linkam data file',
            "",
            "",
            options=self.file_dialog_options(),
        )
        if file_name:
            self.input_file2_edit.setText(file_name)
    
    def select_input_file3(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            'Select temperature correction file',
            "",
            "",
            options=self.file_dialog_options(),
        )
        if file_name:
            self.input_file3_edit.setText(file_name)

    def select_output_file(self):
        file_name = QFileDialog.getExistingDirectory(
            self,
            'Select Output Path',
            "",
            options=self.file_dialog_options(),
        )
        if file_name:
            self.output_file_edit.setText(file_name)

    def run_freeze_finder_script(self):

        try:
            self.freeze_result_rows = []

            gsm_file_path           = self.input_file1_edit.text()
            linkam_file_path        = self.input_file2_edit.text()
            correction_file_path    = self.input_file3_edit.text()
            output_dir              = self.output_file_edit.text()
            width                   = float(self.width_edit.text())
            prominence              = float(self.prominence_edit.text())
            tail_extend_points      = int(float(self.tail_extend_points_edit.text()))
            convolution_half_window_points = int(float(self.convolution_half_window_points_edit.text()))
            convolution_ramp_points = int(float(self.convolution_ramp_points_edit.text()))

            grayscale_data = read_grayscale_csv(gsm_file_path)
            filename_array = grayscale_data['filename_array']
            image_datetime_array = grayscale_data['image_datetime_array']
            image_grayscale_data = grayscale_data['image_grayscale_data']


            # Read Excel file
            df = pd.read_excel(linkam_file_path)
            linkam_headers = df[:104].to_numpy()[:,0]

            LDF_file_string = linkam_headers[1]
            match = re.search(r'(\d{2}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}-\d{2})', LDF_file_string)
            date_str = match.group(1)
            formatted_date_str = '20' + date_str[6:8] + '-' + date_str[3:5] + '-' + date_str[:2] + 'T' + date_str[9:11] + ':' + date_str[12:14] + ':' + date_str[15:17] + '.' + date_str[18:]

            first_datetime = np.datetime64(formatted_date_str, 'us')

            sample_period = float(re.search(r'([\d.]+)', linkam_headers[6]).group(1)) # in seconds

            linkam_temperature_ramp = linkam_headers = df[104:].to_numpy()[:,2].astype('float')
            linkam_indexes = np.arange(len(linkam_temperature_ramp))
            linkam_time_passed = linkam_indexes * np.timedelta64(int(sample_period*1E6), 'us')
            linkam_time_array = first_datetime + linkam_time_passed

            linkam_time_stamps = linkam_time_array.astype('datetime64[ms]').astype('int')
            image_time_stamps = image_datetime_array.astype('datetime64[ms]').astype('int')

            interpolated_image_temps = np.interp(image_time_stamps, linkam_time_stamps, linkam_temperature_ramp, left = np.nan, right = np.nan)

            # Read temperature correction file
            correction_func = None
            if correction_file_path: # if user input the correction_file_path
                correction_data = np.loadtxt(correction_file_path, delimiter = ",", skiprows=1)

                well_num = correction_data[:,0]
                slope_val = correction_data[:,1]
                intercept_val = correction_data[:,2]

                def correct_for_actural_temp(measured_temp, the_well_num):
                    the_slope_val = slope_val[the_well_num]
                    the_intercept_val = intercept_val[the_well_num]

                    return (measured_temp - the_intercept_val)/the_slope_val
                correction_func = correct_for_actural_temp

            self.output_csv_path = os.path.join(output_dir, "freezing_output.csv")
            self.freeze_result_rows, peak_indexes_by_cell = compute_freeze_result_rows(
                filename_array,
                image_datetime_array,
                image_grayscale_data,
                width=width,
                prominence=prominence,
                tail_extend_points=tail_extend_points,
                convolution_half_window_points=convolution_half_window_points,
                convolution_ramp_points=convolution_ramp_points,
                interpolated_image_temps=interpolated_image_temps,
                correction_func=correction_func,
            )
            write_freeze_results_csv(self.output_csv_path, self.freeze_result_headers, self.freeze_result_rows)

        except Exception as err:
            print(err)
            self.reject()
        else:
            self.accept()

        
    def file_dialog_options(self):
        return QFileDialog.Options()
