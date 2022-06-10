from math import pi
import numpy as np
import cv2
import math
from dataclasses import dataclass
from typing import Tuple

from Segmentation.HistogramSegmenter import Segment

# A class encapsulating functions for calculating the costs associated with each type of variable node in our
# factor graph, as well as parameters for calculating said costs. Currently, cost calculations for each type of node
# have an order of magnitude of around 1, if they are somewhat feasible.


@dataclass()
class CostParameters:
    max_conflicts: int
    conflict_min_cost: float
    conflict_max_cost: float
    compactness_min_cost: float
    compactness_max_cost: float
    compactness_mid_point: float
    compactness_slope: float
    exit_cost: int
    appearance_cost_scale: float
    max_cost: float


class CostCalculator:
    def __init__(self, cost_parameters: CostParameters) -> None:
        self.cost_parameters = cost_parameters

    def _distance_squared(self, point_1: Tuple[float], point_2: Tuple[float]) -> float:
        return ((point_2[0] - point_1[0]) ** 2) + ((point_2[1] - point_1[1]) ** 2)

    def calculate_segment_cost(self, segment: Segment) -> float:
        # Segment costs are negative, to encourage inclusion
        # Better compactness makes it more likely to be a cell. Range of values is tight, use sigmoid
        # More conflicts implies a more likely segment. Scale linearly
        conflict_scale = ((self.cost_parameters.conflict_max_cost - self.cost_parameters.conflict_min_cost) /
                          self.cost_parameters.max_conflicts)

        conflict_benefit = conflict_scale * len(segment.conflicts) + self.cost_parameters.conflict_min_cost

        compactness_benefit = (((self.cost_parameters.compactness_max_cost - self.cost_parameters.compactness_min_cost) /
                               (1 + math.exp(-self.cost_parameters.compactness_slope *
                                             (segment.compactness - self.cost_parameters.compactness_mid_point))))
                               + self.cost_parameters.compactness_min_cost)

        segment_cost = (compactness_benefit + conflict_benefit) * -1
        return segment_cost

    def calculate_mapping_cost(self, old_segment: Segment, new_segment: Segment) -> float:
        separation_squared = self._distance_squared(old_segment.centroid, new_segment.centroid)
        radius_squared = old_segment.size / pi

        # Separation ratio ranges from 0 (on top of each other) through 1 (one radius away) and above
        separation_ratio = separation_squared / radius_squared

        # Sum both size ratios, so that the total increases if either segment is larger
        # Size ratio is near 2 for similarly sized segments
        size_ratio = old_segment.size / new_segment.size + new_segment.size / old_segment.size

        # Square separation cost to increase impact for high separation
        # Square size difference, then subtract 2^2 such that identical sizes incur no cost
        return (separation_ratio ** 2) + size_ratio ** 2 - 4

    def calculate_division_cost(self, old_segment: Segment, new_segment_1: Segment, new_segment_2: Segment) -> float:
        # Division cost is based on the cost of map (mother) + appear (daughter), scaled based on size and separation
        # If mother+daughter are close, daughter is small and mother is sufficiently large, then division should be
        # lower cost than map + appear. Otherwise, cost should be larger to discourage selection.

        if new_segment_1.size < new_segment_2.size:
            mother = new_segment_2
            daughter = new_segment_1
        else:
            mother = new_segment_1
            daughter = new_segment_2

        mother_daughter_separation = calculate_pixel_separation(mother, daughter)

        base_cost_offset = 0.8
        min_cost = 0
        max_cost = 0.25
        threshold_cost = max_cost / 2
        size_slope = 10
        max_daughter_size = 230
        min_mother_ratio = 2
        separation_slope = 2
        max_separation = 1

        separation_mid_point = find_midpoint(min_cost, max_cost, separation_slope, max_separation, threshold_cost)
        separation_cost_mult = sigmoid(min_cost, max_cost, separation_slope, separation_mid_point,
                                       mother_daughter_separation)

        daughter_midpoint = find_midpoint(min_cost, max_cost, size_slope, 1, threshold_cost)
        daughter_cost_mult = sigmoid(min_cost, max_cost, size_slope, daughter_midpoint, daughter.size / max_daughter_size)

        mother_midpoint = find_midpoint(min_cost, max_cost, size_slope, min_mother_ratio, threshold_cost)
        mother_cost_mult = sigmoid(min_cost, max_cost, size_slope, mother_midpoint, 2 * mother_midpoint - (mother.size / daughter.size))

        base_cost = self.calculate_mapping_cost(old_segment, mother) + self.calculate_appearance_cost(daughter)

        total_cost = base_cost * (base_cost_offset + mother_cost_mult + daughter_cost_mult + separation_cost_mult)

        return total_cost

    def calculate_appearance_cost(self, segment: Segment) -> float:
        # No easily applicable precedent in literature;
        # Make appearance a multiple of the segment's benefit, to encourage persistence for multiple frames
        segment_cost = self.calculate_segment_cost(segment)
        return segment_cost * self.cost_parameters.appearance_cost_scale * -1

    def calculate_exit_cost(self, segment: Segment) -> float:
        # From Jug: exit cost 0 due to losing segment benefit
        return self.cost_parameters.exit_cost


def sigmoid(min_val: float, max_val: float, slope: float, mid_point: float, x: float) -> float:
    val: float = min_val + ((max_val - min_val) / (1 + math.exp(-slope * (x - mid_point))))
    return val


def find_midpoint(min_val, max_val, slope, x, y) -> float:
    val = (1 / slope) * math.log((max_val - min_val) / (y - min_val) - 1) + x
    return val


def calculate_pixel_separation(segment_1: Segment, segment_2: Segment) -> float:
    combined_image = segment_1.mask_image + segment_2.mask_image
    if np.amax(combined_image) < 2:
        inverted_combined = np.logical_not(combined_image)
        seg_2_zeroed = inverted_combined + 2 * segment_1.mask_image
        dist_transformed = cv2.distanceTransform(seg_2_zeroed, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)

        # Adjust separation by 1 so that it is zero when objects have no gap between them
        min_dist = np.amin(dist_transformed[segment_1.mask_image != 0]) - 1
        return min_dist
    else:
        return 0
