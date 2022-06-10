from typing import Tuple, Union, List
import cv2
import numpy as np
from Segmentation.SegmentationData import Segment


# Fills all holes in a binary image with 1
# Method: flood fill background with a 2, then set all remaining 0s to 1, then revert background to 0


def fill_holes(to_fill: np.ndarray, background_point: Tuple[int, int]) -> np.ndarray:
    mask = np.zeros((to_fill.shape[0] + 2, to_fill.shape[1] + 2), dtype=np.uint8)
    filled = cv2.floodFill(to_fill.copy(), mask, background_point, 2)[1]
    filled[filled == 0] = 1
    filled[filled == 2] = 0
    return filled


# Detect holes in an image, by flood-filling from a given background point
# Uses the image instead of the mask, to avoid altering image dimensions.
def find_holes(image: np.ndarray, background_point: Tuple[int, int]) -> np.ndarray:
    mask = np.zeros((image.shape[0] + 2, image.shape[1] + 2), dtype=np.uint8)
    return np.logical_not(cv2.floodFill(image.copy(), mask, background_point, 1)[1]).astype(np.uint8)


# Adjust the contrast of the image using the formula (pixel + bias) * gain
# If no gain and bias are supplied, scales pixel values to fill the entire
# range of the image pixel datatype (assumes unsigned type)
def increase_contrast(img, bias: Union[float, None] = None, gain: Union[float, None] = None) -> np.ndarray:
    if not bias:
        bias = np.amin(img) * -1
    if not gain:
        gain = np.iinfo(img.dtype).max / (np.amax(img) + bias)

    return cv2.addWeighted(img, gain, img, 0, bias * gain)


def find_segmented_background(image: np.ndarray, segments: Union[List[Segment], np.ndarray], frame_shape: Tuple[int],
                              erosion_size=11) -> np.ndarray:
    """Logical AND of median-based background with section of image that doesn't contain any segments """
    if isinstance(segments, np.ndarray):
        segmented_image = segments
    else:
        segmented_image = np.zeros(frame_shape)
        for seg in segments:
            segmented_image += seg.mask_image

    median_background = find_background(image)
    segment_background = segmented_image == 0

    element = cv2.getStructuringElement(cv2.MORPH_RECT, (erosion_size, erosion_size))
    segment_background = cv2.erode(segment_background.astype(np.uint8), element, iterations=1)

    background = np.logical_and(median_background, segment_background).astype(np.uint8)
    
    return background


#  Calculates image background as region_width * sd either side of the median pixel intensity,
#  then eroding and selecting the largest remaining region
def find_background(image: np.ndarray, region_width: float = 0.5, blur_image: bool = True):
    if blur_image:
        image = cv2.GaussianBlur(image, (0, 0), 2)
    img_median = np.median(image)
    std_dev = np.std(image)
    lower_bg_limit = round(img_median - region_width * std_dev)
    upper_bg_limit = round(img_median + region_width * std_dev)

    element = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    background = (image > lower_bg_limit) & (image < upper_bg_limit)
    background = cv2.erode(background.astype(np.uint8), element, iterations=1)

    label_count, labels, stats, centroids = cv2.connectedComponentsWithStats(background.astype(np.uint8), connectivity=4)

    # Sort region indexes by size
    sorted_indexes = np.argsort(stats[:, cv2.CC_STAT_AREA]).tolist()

    # All foreground regions are 0 in background image
    # connectedComponents ignores 0 so all foreground regions should still be 0 afterwards
    fg_label = 0

    # Remove foreground if it is present
    if len(sorted_indexes) > 1:
        sorted_indexes.remove(fg_label)
    else:
        print("Warning: no foreground!")

    largest_index = sorted_indexes[-1]

    if len(sorted_indexes) > 1:
        second_largest_index = sorted_indexes[-2]

        s1 = stats[largest_index, cv2.CC_STAT_AREA]
        s2 = stats[second_largest_index, cv2.CC_STAT_AREA]

        # If second and third largest areas are within 20% of each other, area likely cut in half so use both
        if s2 / s1 > 0.8:
            label_img = (labels == largest_index) + (labels == second_largest_index)
        else:
            label_img = labels == largest_index
    else:
        label_img = labels == largest_index

    return label_img


def rotate_image(image: np.ndarray, angle: float):
    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
    return result
