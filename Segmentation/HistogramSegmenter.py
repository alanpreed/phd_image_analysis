import numpy as np
import cv2
from dataclasses import dataclass
from typing import List

from Segmentation.HistogramGapFill import histogram_threshold_gap_fill, find_background
from Segmentation.Measurement import calculate_centroid, calculate_compactness, calculate_intensity
from Segmentation.SegmentationData import Segment, Segmentation


@dataclass
class SegmentationParameters:
    blur_sd: float
    histogram_threshold_adjustments: List[float]
    max_gap_fill: int
    mask_interior: bool = True
    mask_holes: bool = True
    combine_gap_fills: bool = True
    filter_small_segments: bool = True
    minimum_segment_size: int = 20


# Calculate segmentation of an image, using a two-level histogram-determined threshold followed by
# successively larger border gap filling and hole identification
class HistogramSegmenter:
    def __init__(self, channel_image_names: List[str], frame_no: int, parameters: SegmentationParameters, segmentation_channel: int = 0):
        self.frame_no = frame_no
        self.image_names = channel_image_names
        self.images: List[np.ndarray] = [cv2.imread(name, flags=(cv2.IMREAD_GRAYSCALE + cv2.IMREAD_UNCHANGED)) for name in channel_image_names]

        self.parameters: SegmentationParameters = parameters
        self.segmentation_channel_id = segmentation_channel

        self.background: np.ndarray = find_background(self.images[segmentation_channel], self.parameters.blur_sd, max(self.parameters.histogram_threshold_adjustments))
        self.background_intensities = [calculate_intensity(image, self.background) for image in self.images]

        self.segmented_images: List[List[np.ndarray]] = []
        self.segmentations: List[Segmentation] = []

    def run_segmentation(self) -> None:
        self.segmentations = []
        # print("Segmenting image")
        self.segmented_images = self._segment_image()
        # print("Labelling segments")
        labelled_segments = self._label_segments(self.segmented_images)
        # print("Calculating segment conflicts")
        labelled_segments = self._calculate_conflicts(labelled_segments)
        # print("Flattening segment array")
        self.segmentations = self._flatten_segments(labelled_segments)
        # print("Segmentation complete")

    def _segment_image(self) -> List[List[np.ndarray]]:
        # Run segmentation for each threshold and gap size
        segmented_images = []

        for threshold in self.parameters.histogram_threshold_adjustments:
            filled, holes = histogram_threshold_gap_fill(self.images[self.segmentation_channel_id],
                                                         self.parameters.blur_sd,
                                                         threshold,
                                                         self.parameters.max_gap_fill)
            filtered_segments = []

            for hole_img in holes:
                # Filter out small regions
                label_count, labels, stats, centroids = cv2.connectedComponentsWithStats(hole_img.astype(np.uint8),
                                                                                         connectivity=4)
                if self.parameters.filter_small_segments:
                    for label in range(label_count):
                        if stats[label, cv2.CC_STAT_AREA] < self.parameters.minimum_segment_size:
                            labels[labels == label] = 0

                    # Relabel to fill in numbering gaps
                    label_count, labels = cv2.connectedComponents(labels.astype(np.uint8), connectivity=4)
                filtered_segments.append(labels)
            segmented_images.append(filtered_segments)
        return segmented_images

    def _label_segments(self, segmented_images: List[List[np.ndarray]]) -> List[List[List[Segment]]]:
        labelled_segments = []
        segment_count = 0

        # For every possible segmentation generated for image
        for threshold_id in range(len(self.parameters.histogram_threshold_adjustments)):
            threshold_segments = []

            for gap_id in range(self.parameters.max_gap_fill):
                segments = segmented_images[threshold_id][gap_id]
                num_segments = np.amax(segments)
                gap_segments = []

                for segment_id in range(1, num_segments + 1):
                    segment_img = (segments == segment_id).astype(np.uint8)

                    name = "f{}_t{}_g{}_s{}".format(self.frame_no,
                                                    self.parameters.histogram_threshold_adjustments[threshold_id],
                                                    gap_id,
                                                    segment_count)
                    area = np.count_nonzero(segment_img)
                    compactness = calculate_compactness(segment_img)
                    centroid = calculate_centroid(segment_img)
                    intensities: List[float] = [calculate_intensity(image, segment_img) for image in self.images]

                    new_segment = Segment(seg_id=segment_count,
                                          mask_image=segment_img,
                                          frame_id=self.frame_no,
                                          name=name,
                                          centroid=centroid,
                                          size=area,
                                          compactness=compactness,
                                          channel_intensities=intensities,
                                          conflicts=[])

                    gap_segments.append(new_segment)
                    segment_count += 1
                threshold_segments.append(gap_segments)
            labelled_segments.append(threshold_segments)
        return labelled_segments

    def _calculate_conflicts(self, labelled_segments: List[List[List[Segment]]]) -> List[List[List[Segment]]]:
        # For every possible segmentation generated for image
        for threshold_id in range(len(self.parameters.histogram_threshold_adjustments)):
            for gap_id in range(self.parameters.max_gap_fill):
                segments = labelled_segments[threshold_id][gap_id]
                for segment in segments:
                    # Segments conflict with themselves
                    segment.conflicts.append(segment.seg_id)
                    # For each threshold, including current one
                    for other_threshold_id in range(threshold_id, len(self.parameters.histogram_threshold_adjustments)):
                        # For each gap size larger than current one
                        # Don't want to compare segments from the same image, or duplicate comparisons
                        if threshold_id == other_threshold_id:
                            gap_range = range(gap_id, self.parameters.max_gap_fill)
                        else:
                            gap_range = range(0, self.parameters.max_gap_fill)

                        for other_gap_id in gap_range:
                            if threshold_id != other_threshold_id or gap_id != other_gap_id:
                                other_segments = labelled_segments[other_threshold_id][other_gap_id]

                                for other_segment in other_segments:
                                    intersect_img = np.logical_and(segment.mask_image, other_segment.mask_image)
                                    intersect = np.any(intersect_img)

                                    if intersect:
                                        segment.conflicts.append(other_segment.seg_id)
                                        other_segment.conflicts.append(segment.seg_id)
        return labelled_segments

    def _flatten_segments(self, labelled_segments: List[List[List[Segment]]]) -> List[Segmentation]:
        segmentations: List[Segmentation] = []

        for threshold_id in range(len(self.parameters.histogram_threshold_adjustments)):
            for gap_id in range(self.parameters.max_gap_fill):
                segments: List[Segment] = labelled_segments[threshold_id][gap_id]

                segmentation: Segmentation = Segmentation(name="hist_threshold_{}_gap_{}".format(threshold_id, gap_id),
                                                          segmentation_channel_id=self.segmentation_channel_id,
                                                          background_mask=self.background,
                                                          background_intensities=self.background_intensities,
                                                          segments=segments)

                segmentations.append(segmentation)
        return segmentations
