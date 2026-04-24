# API Module: `icescopy_image_edit`

Image-adjustment helpers and overlay widgets for crop and histogram workflows.

## Source

- File: `src/icescopy_image_edit.py`

## Classes

| Class | Purpose | Page |
| --- | --- | --- |
| `ImageHistogramWidget` | Histogram display widget for image-edit review. | [ImageHistogramWidget](API-Class-ImageHistogramWidget) |
| `ImageRectOverlayItem` | Interactive rectangular overlay used for image-edit reference-area workflows. | [ImageRectOverlayItem](API-Class-ImageRectOverlayItem) |
| `ImageCropOverlayItem` | Interactive crop overlay used to define rotated crop state. | [ImageCropOverlayItem](API-Class-ImageCropOverlayItem) |

## Module Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `IMAGE_EDIT_HISTOGRAM_BIN_COUNT` | 371 | Count value for image edit histogram bin count. |

## Top-level Functions

| Function | Line | Explanation |
| --- | --- | --- |
| `exposure_gain(exposure_stops)` | 18 | Implements exposure gain. |
| `contrast_gain(contrast_percent)` | 22 | Implements contrast gain. |
| `normalize_angle_degrees(angle_degrees)` | 27 | Normalizes angle degrees. |
| `rotated_crop_corners(crop_state)` | 36 | Implements rotated crop corners. |
| `fit_rotated_crop_state_to_bounds(image_width, image_height, crop_state)` | 63 | Implements fit rotated crop state to bounds. |
| `normalize_rotated_crop_state(image_width, image_height, crop_state=None)` | 123 | Normalizes rotated crop state. |
| `crop_state_is_identity(image_width, image_height, crop_state=None, tolerance=1e-06)` | 178 | Implements crop state is identity. |
| `build_rotated_crop_affine(image_width, image_height, crop_state=None)` | 189 | Builds rotated crop affine. |
| `apply_affine_to_point(matrix, x_value, y_value)` | 203 | Applies affine to point. |
| `invert_affine_matrix(matrix)` | 208 | Implements invert affine matrix. |
| `normalize_rect_area_state(image_width, image_height, area_state=None, min_size=16.0)` | 212 | Normalizes rect area state. |
| `qimage_buffer_array(q_image, dtype=np.uint8)` | 256 | Implements qimage buffer array. |
| `apply_exposure_to_uint8(image_array, exposure_stops)` | 261 | Applies exposure to uint8. |
| `apply_contrast_to_uint8(image_array, contrast_percent)` | 274 | Applies contrast to uint8. |
| `_warp_border_value(image_array)` | 288 | Implements warp border value. |
| `apply_rotated_crop_to_uint8(image_array, crop_state=None)` | 294 | Applies rotated crop to uint8. |
| `apply_image_adjustments_to_uint8(image_array, exposure_stops=0.0, contrast_percent=0.0, crop_state=None, apply_crop=True)` | 313 | Applies image adjustments to uint8. |
| `apply_image_adjustments_to_qimage(q_image, exposure_stops=0.0, contrast_percent=0.0, crop_state=None, apply_crop=True)` | 330 | Applies image adjustments to qimage. |
| `qimage_to_grayscale_array(q_image)` | 358 | Implements qimage to grayscale array. |
| `compute_histogram_bins(image_gray, bin_count=IMAGE_EDIT_HISTOGRAM_BIN_COUNT)` | 374 | Computes histogram bins. |
