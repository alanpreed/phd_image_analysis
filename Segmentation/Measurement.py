import cv2
import numpy as np
import math
from typing import Tuple, Union


def calculate_centroid(image: np.ndarray) -> Tuple[Union[float, any], ...]:
    non_zero = np.nonzero(image)
    region_size = len(non_zero[0])
    if region_size > 0:
        summed = np.sum(non_zero, 1)
        average = tuple(i / region_size for i in summed)
        return average
    else:
        return 0, 0


def calculate_compactness(image: np.ndarray) -> float:
    shape_area = np.count_nonzero(image)
    if shape_area > 1:
        contours, hierarchy = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        perimeter = cv2.arcLength(contours[0], True)
    elif shape_area == 0:
        return 0
    else:
        perimeter = 1
    circle_area = perimeter * perimeter / (4 * math.pi)
    shape_area = np.count_nonzero(image)
    isoperimetric_quotient = shape_area / circle_area
    return isoperimetric_quotient


def calculate_intensity(image: np.ndarray, region: np.ndarray) -> float:
    region_size = np.count_nonzero(region)
    if region_size > 0:
        total = np.sum(image[region != 0])
        intensity_per_pixel = total / region_size
        return intensity_per_pixel
    else:
        return 0
