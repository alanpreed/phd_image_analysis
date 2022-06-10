import numpy as np
from scipy.signal import find_peaks
import cv2
import math
from skimage.morphology import disk
from typing import List, Union, Tuple
from Segmentation.Utilities import fill_holes, find_holes, increase_contrast


# Generate a binary image containing discrete regions, each corresponding to a unique segment in the input image.
# Segmentation is carried out by running a two-level threshold, with the threshold values identified from the image's
# histogram and modified by the supplied threshold adjustment. Identified object borders then undergo successively
# larger gap fills, followed by hole identification to find segments.

# Arguments:
# - image: array containing image to be segmented
# - blur_sd: standard deviation of the Gaussian blur to be applied to the image during pre-processing
# - threshold: the threshold adjustment value for histogram background peak detection
# - max_gap_size: maximum gap size to fill once borders have been identified
# - mask_interior: whether to use the identified cell interiors as a mask for gap filling
# - mask_holes: whether to use identified holes from smaller gap fills as a mask during larger gap fills
# - combine_gap_fills: whether to carry over the results of a gap fill as the input to the next larger gap fill
def histogram_threshold_gap_fill(raw_image: np.ndarray, blur_sd: float, threshold: float, max_gap_size: int,
                                 mask_interior: bool = True, mask_holes: bool = True,
                                 combine_gap_fills: bool = True) -> (List[np.ndarray], List[np.ndarray]):
    borders, background, interior = histogram_threshold(raw_image, blur_sd, threshold)
    background = cv2.erode(background, disk(5), iterations=1)

    # Flip to convert from (row, column) to (column, row) for cv2 (x, y) format
    background_points = np.flip(np.transpose(np.nonzero(background)), 1)
    background_tuple = tuple(background_points[0])

    return sequential_gap_fill(borders, interior, background_tuple, max_gap_size, mask_interior, mask_holes, combine_gap_fills)


def histogram_threshold(raw_image: np.ndarray, blur_sd: float, threshold: float, erode_background: bool = True) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Improve image contrast
    raw_image = increase_contrast(raw_image)

    if raw_image.dtype == np.uint16:
        raw_image = (raw_image / 256).astype(np.uint8)

    # Blur image
    if blur_sd > 0:
        gaussian_img = cv2.GaussianBlur(raw_image, (0, 0), blur_sd)
        my_image = gaussian_img
    else:
        my_image = raw_image

    # Use identified peak to perform two-level threshold on image
    # Lower threshold gives borders
    peak_lower, peak_upper = find_histogram_peak_edges(my_image, threshold)
    lower_threshold = my_image <= peak_lower
    # Mid threshold gives background
    mid_threshold = (my_image > peak_lower) & (my_image < peak_upper)
    # Upper threshold gives cell and trap interior
    upper_threshold = my_image >= peak_upper

    borders: np.ndarray = lower_threshold.astype(np.uint8)
    background: np.ndarray = mid_threshold.astype(np.uint8)
    interior: np.ndarray = upper_threshold.astype(np.uint8)

    # Identify pixels definitely in background via aggressive erosion
    if erode_background:
        background = cv2.erode(background, disk(5), iterations=1)

    return borders, background, interior


def sequential_gap_fill(borders: np.ndarray, interior: np.ndarray, background_point: Tuple,
                        max_gap_size: int, mask_interior: bool = True, mask_holes: bool = True,
                        combine_gap_fills: bool = True) -> (List[np.ndarray], List[np.ndarray]):
    to_fill = borders.copy()
    filled = []
    holes = []
    interior_eroded = cv2.erode(interior, disk(1))

    for gap_size in range(max_gap_size):
        elements = [np.ones((2 * gap_size + 1, 2 * gap_size + 1))]

        # Mask off using holes from previous fill
        if mask_holes and gap_size > 0:
            to_fill[holes[gap_size - 1] == 1] = 0

        # Use interior pixels as mask for gap fill
        if mask_interior:
            gap_filled = gap_fill_mask(to_fill, elements, mask=interior_eroded)[0]
        else:
            gap_filled = gap_fill_mask(to_fill, elements)[0]

        # Carry over filled gaps to next pass
        if combine_gap_fills:
            to_fill = gap_filled.copy().astype(np.uint8)

        filled.append(gap_filled)
        holes.append(fill_holes(find_holes(filled[gap_size].astype(np.uint8), background_point), background_point))

    return filled, holes


# Determines the upper and lower edges of the largest peak in the histogram of the supplied image, adjusted by the
# threshold value.
def find_histogram_peak_edges(image: np.ndarray, threshold: float, smoothing: int = 10) -> (int, int):
    if len(image.shape) != 2:
        print("Error! image is not greyscale")
        return
    if image.dtype != np.uint8:
        print("Error! image datatype is not uint8")
        return

    # Calculate histogram for uint8 image
    n = cv2.calcHist([image], [0], None, [256], [0, 256]).flatten()

    # Smooth bins using moving box average via convolution from:
    # https://stackoverflow.com/questions/20618804/how-to-smooth-a-curve-in-the-right-way
    def smooth(y, box_pts):
        box = np.ones(box_pts) / box_pts
        y_smooth = np.convolve(y, box, mode='same')
        return y_smooth

    smoothed_n = smooth(n, smoothing)

    # Calculate first and second derivative to find max of gradient
    grad = np.gradient(smoothed_n)
    smoothed_grad = smooth(grad, smoothing)
    grad2 = np.gradient(smoothed_grad)

    # Use scikit's find_peaks to spot the maxima of the second derivative.
    # Constrained minimum height to half of the highest peak (arbitrary choice) to avoid identifying noise
    peaks = find_peaks(grad2, height=0.5 * max(grad2))

    # Find highest peaks on the left and right of the minimum of the second derivative
    lowest_point_index = np.argmin(grad2)
    lh_peak_indices = peaks[0][peaks[0] < lowest_point_index]
    rh_peak_indices = peaks[0][peaks[0] > lowest_point_index]

    lh_peaks_sorted = np.argsort(grad2[lh_peak_indices])
    rh_peaks_sorted = np.argsort(grad2[rh_peak_indices])

    lh_max_peak_index = lh_peak_indices[lh_peaks_sorted[-1]]
    rh_max_peak_index = rh_peak_indices[rh_peaks_sorted[-1]]

    # Adjust lower and upper bounds of histogram peak according to threshold
    peak_separation = rh_max_peak_index - lh_max_peak_index
    peak_lower = math.floor(lh_max_peak_index + (0.5 * threshold * peak_separation))
    peak_upper = math.ceil(rh_max_peak_index - (0.5 * threshold * peak_separation))

    return peak_lower, peak_upper


def clamp(x: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(x, maximum))


# Fills gaps in an image as detected using supplied structuring element. Optional mask can be supplied, preventing
# gap fills that intersect with the mask. Accepts an array of structuring elements to calculate different gap fills in
# paralle;, returning results in an array.
def gap_fill_mask(image: np.ndarray, struct_elements: List[np.ndarray],
                  mask: Union[None, np.ndarray] = None) -> np.ndarray:
    contours, hierarchy = cv2.findContours(image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    num_contours = len(hierarchy[0])

    output_images = np.zeros((len(struct_elements),) + image.shape)

    for contour_id in range(num_contours):
        contour_img = np.zeros(image.shape)
        contour_img = cv2.drawContours(contour_img, contours, contour_id, 1)
        points = np.transpose(np.nonzero(contour_img))

        for point in points:
            for element_id in range(len(struct_elements)):
                element_image = np.zeros(image.shape)

                im_y, im_x = element_image.shape
                el_y, el_x = struct_elements[element_id].shape

                el_centre_x = math.floor((el_x - 1) / 2)
                el_centre_y = math.floor((el_y - 1) / 2)

                y_min = clamp(point[0] - el_centre_y, 0, im_y)
                y_max = clamp(point[0] - el_centre_y + el_y, 0, im_y)
                x_min = clamp(point[1] - el_centre_x, 0, im_x)
                x_max = clamp(point[1] - el_centre_x + el_x, 0, im_x)

                el_x_max = x_max - x_min
                el_y_max = y_max - y_min

                element_image[y_min:y_max, x_min:x_max] = struct_elements[element_id][0:el_y_max, 0:el_x_max]

                # Use image instead of contours for AND, to avoid "filling gap" between borders of solids
                # Only look at pixels overlapping with element to reduce computational load
                and_img = np.logical_and(struct_elements[element_id][0:el_y_max, 0:el_x_max],
                                         image[y_min:y_max, x_min:x_max])
                ret, labels, stats, centroids = cv2.connectedComponentsWithStats(and_img.astype(np.uint8))

                # If there's more than 2 regions then a gap has been crossed.
                if ret > 2:
                    cv2.line(labels, tuple(np.round(centroids[1]).astype(np.int)),
                             tuple(np.round(centroids[2]).astype(np.int)), 1, 1)

                    if mask is None:
                        output_images[element_id][y_min:y_max, x_min:x_max] = np.logical_or(
                            output_images[element_id][y_min:y_max, x_min:x_max], labels)
                    else:
                        if not np.any(labels[mask[y_min:y_max, x_min:x_max] == 1]):
                            output_images[element_id][y_min:y_max, x_min:x_max] = np.logical_or(
                                output_images[element_id][y_min:y_max, x_min:x_max], labels)

    return np.logical_or(output_images, image)


def find_background(raw_image: np.ndarray, blur_sd: float, threshold: float, min_region_size=1500) -> np.ndarray:
    borders, background, interior = histogram_threshold(raw_image, blur_sd, threshold)
    background = cv2.erode(background, disk(5), iterations=1)

    label_count, labels, stats, centroids = cv2.connectedComponentsWithStats(background.astype(np.uint8), connectivity=4)

    for label in range(label_count):
        if stats[label, cv2.CC_STAT_AREA] < min_region_size:
            labels[labels == label] = 0

    return labels != 0
