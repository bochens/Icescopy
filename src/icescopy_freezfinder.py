import os
import numpy as np
from scipy import signal
from icescopy_preferences import DEFAULT_PREFERENCE_VALUES

DEFAULT_FREEZE_RESULT_HEADERS = [
    'cell',
    'image_index',
    'image_name',
]

DEFAULT_FREEZE_FINDER_WIDTH = DEFAULT_PREFERENCE_VALUES["FreezeFinderWidth"]
DEFAULT_FREEZE_FINDER_PROMINENCE = DEFAULT_PREFERENCE_VALUES["FreezeFinderProminence"]
DEFAULT_FREEZE_FINDER_HEAD_EXTEND_POINTS = DEFAULT_PREFERENCE_VALUES["FreezeFinderHeadExtendPoints"]
DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS = DEFAULT_PREFERENCE_VALUES["FreezeFinderTailExtendPoints"]
DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS = DEFAULT_PREFERENCE_VALUES["ConvolutionHalfWindowPoints"]
DEFAULT_CONVOLUTION_RAMP_POINTS = DEFAULT_PREFERENCE_VALUES["ConvolutionRampPoints"]
DEFAULT_ONSET_DIFF_FRACTION = 0.5
DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING = DEFAULT_PREFERENCE_VALUES["FreezeFinderDetectBrightening"]


def compute_freeze_result_rows(
    filename_array,
    image_datetime_array,
    image_grayscale_data,
    width=DEFAULT_FREEZE_FINDER_WIDTH,
    prominence=DEFAULT_FREEZE_FINDER_PROMINENCE,
    head_extend_points=DEFAULT_FREEZE_FINDER_HEAD_EXTEND_POINTS,
    tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
    convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
    detect_brightening=DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING,
    cell_ids=None,
    interpolated_image_temps=None,
    correction_func=None,
    frame_indexes=None,
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
    if frame_indexes is None:
        resolved_frame_indexes = list(range(len(filename_array)))
    else:
        resolved_frame_indexes = [int(value) for value in frame_indexes]

    for cell_index in np.arange(image_grayscale_data.shape[1]):
        raw_grayscale = np.asarray(image_grayscale_data[:, cell_index], dtype=float)
        cell_id = (
            int(resolved_cell_ids[cell_index])
            if resolved_cell_ids is not None and cell_index < len(resolved_cell_ids)
            else int(cell_index)
        )
        event_indexes = []
        for run_start, run_end in contiguous_finite_runs(raw_grayscale):
            run_event_indexes = compute_freeze_event_indexes(
                raw_grayscale[run_start:run_end],
                width=width,
                prominence=prominence,
                head_extend_points=head_extend_points,
                tail_extend_points=tail_extend_points,
                convolution_half_window_points=convolution_half_window_points,
                convolution_ramp_points=convolution_ramp_points,
                detect_brightening=detect_brightening,
            )
            event_indexes.extend(
                run_start + int(run_event_index)
                for run_event_index in run_event_indexes
            )

        event_indexes = np.asarray(event_indexes, dtype=int)
        peak_indexes_by_cell.append(event_indexes)

        for peak_index in event_indexes:
            refined_index = int(peak_index)
            output_frame_index = (
                int(resolved_frame_indexes[refined_index])
                if 0 <= refined_index < len(resolved_frame_indexes)
                else refined_index
            )
            row = [
                f'cell_{cell_id}',
                str(output_frame_index),
                str(filename_array[refined_index]),
            ]
            freeze_result_rows.append(row)

    return freeze_result_rows, peak_indexes_by_cell


def contiguous_finite_runs(values):
    """Return half-open index ranges that contain only finite measurements.

    Missing cell measurements are represented by NaN. Treating a NaN as part
    of the convolution poisons the full series, while interpolating across it
    can invent a freezing transition. Splitting the signal preserves every
    measured transition without bridging an unmeasured gap.
    """
    finite_indexes = np.flatnonzero(np.isfinite(np.asarray(values, dtype=float)))
    if finite_indexes.size == 0:
        return []

    split_points = np.flatnonzero(np.diff(finite_indexes) > 1) + 1
    index_groups = np.split(finite_indexes, split_points)
    return [
        (int(index_group[0]), int(index_group[-1]) + 1)
        for index_group in index_groups
        if index_group.size
    ]


def compute_freeze_event_indexes(
    raw_grayscale,
    width=DEFAULT_FREEZE_FINDER_WIDTH,
    prominence=DEFAULT_FREEZE_FINDER_PROMINENCE,
    head_extend_points=DEFAULT_FREEZE_FINDER_HEAD_EXTEND_POINTS,
    tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
    convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
    detect_brightening=DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING,
):
    raw_grayscale = np.asarray(raw_grayscale, dtype=float)
    if raw_grayscale.size == 0:
        return np.array([], dtype=int)

    head_extend_count = int(max(0, head_extend_points))
    tail_extend_count = int(max(0, tail_extend_points))
    _, g_array_step = compute_convolution_timeseries(
        raw_grayscale,
        head_extend_points=head_extend_points,
        tail_extend_points=tail_extend_points,
        convolution_half_window_points=convolution_half_window_points,
        convolution_ramp_points=convolution_ramp_points,
    )
    center_offset = compute_convolution_center_offset(
        len(raw_grayscale) + head_extend_count + tail_extend_count,
        convolution_half_window_points=convolution_half_window_points,
        convolution_ramp_points=convolution_ramp_points,
    ) - head_extend_count

    peaks, peak_properties = signal.find_peaks(
        g_array_step if detect_brightening else -g_array_step,
        width=width,
        prominence=prominence,
    )
    left_ips = peak_properties.get("left_ips", peaks.astype(float))
    right_ips = peak_properties.get("right_ips", peaks.astype(float))
    max_frame_index = len(raw_grayscale) - 1
    event_indexes = [
        refine_event_index_from_raw_timeseries(
            raw_grayscale,
            peak_index,
            left_ip,
            right_ip,
            center_offset,
            max_frame_index,
            detect_brightening=detect_brightening,
        )
        for peak_index, left_ip, right_ip in zip(peaks, left_ips, right_ips)
    ]
    return np.asarray(event_indexes, dtype=int)


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
    """Map the first valid-convolution sample to the pattern's signal center."""
    kernel = build_convolution_kernel(
        signal_length,
        convolution_half_window_points=convolution_half_window_points,
        convolution_ramp_points=convolution_ramp_points,
    )
    # In a full convolution, output index j is centered at j - (M-1)/2
    # for a pattern of length M. NumPy's 'valid' slice starts at min(N,M)-1,
    # including when the pattern is longer than the N-point signal (window 0).
    # Using (M-1)/2 alone is correct only when N >= M.
    valid_start = min(int(signal_length), len(kernel)) - 1
    return valid_start - 0.5 * (len(kernel) - 1)


def compute_convolution_timeseries(
    grayscale_values,
    head_extend_points=DEFAULT_FREEZE_FINDER_HEAD_EXTEND_POINTS,
    tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS,
    convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS,
    convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS,
):
    g_array = np.asarray(grayscale_values, dtype=float)
    if g_array.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    head_extend_count = int(max(0, head_extend_points))
    if head_extend_count > 0:
        head_value = float(g_array[0])
        g_array = np.concatenate((np.full(head_extend_count, head_value, dtype=float), g_array))

    tail_extend_count = int(max(0, tail_extend_points))
    if tail_extend_count > 0:
        tail_value = float(g_array[-1])
        g_array = np.concatenate((g_array, np.full(tail_extend_count, tail_value, dtype=float)))

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
