from typing import List, Union, Tuple
import numpy as np
import cv2
import os
from Segmentation.SegmentationData import Segment, Segmentation, ProcessedFrame
from Visualisation.Visualisation import colourise_binary_mask
from Segmentation.Measurement import calculate_intensity, calculate_centroid, calculate_compactness
from Segmentation.Utilities import fill_holes, find_segmented_background


class SegmentationEditor:
    def __init__(self, frame: ProcessedFrame, segmentation_id: int) -> None:
        self.points_buffer: List[Tuple] = []
        self.radius: int = 5
        self.erase: bool = False
        self.frame: ProcessedFrame = frame
        self.segmentation: Segmentation = frame.segmentations[segmentation_id]
        self.images: List[np.ndarray] = [cv2.imread(os.path.join(self.frame.root_directory, name), flags=(cv2.IMREAD_GRAYSCALE + cv2.IMREAD_UNCHANGED)) for name in self.frame.image_names]

    def delete_segment(self, segment_id: int) -> None:
        del(self.segmentation.segments[segment_id])

        for new_segment_id in range(len(self.segmentation.segments)):
            self.segmentation.segments[new_segment_id].seg_id = new_segment_id
        self._update_background()

    def add_segment(self) -> Segment:
        new_segment: Segment = Segment(seg_id=self.segmentation.segments[-1].seg_id + 1,
                                       frame_id=self.frame.frame_no,
                                       mask_image=np.zeros(self.segmentation.segments[-1].mask_image.shape).astype(np.uint8),
                                       name="manual_id{}".format(self.segmentation.segments[-1].seg_id + 1),
                                       centroid=(0, 0),
                                       size=0,
                                       compactness=0,
                                       channel_intensities=[],
                                       conflicts=[])

        self.segmentation.segments.append(new_segment)
        return new_segment

    def start_edit_segment(self, point: Tuple, erase: bool):
        self.points_buffer.append(point)
        self.erase = erase

    def add_point(self, point: Tuple) -> None:
        self.points_buffer.append(point)

    def finish_edit_segment(self, segment_id: int) -> None:
        segment = self.segmentation.segments[segment_id]
        new_image = np.zeros(segment.mask_image.shape).astype(np.uint8)

        for point in self.points_buffer:
            new_image = cv2.circle(new_image, (round(point[0]), round(point[1])), round(self.radius), (255, 255, 255), thickness=cv2.FILLED)

        if not self.erase:
            segment.mask_image[new_image != 0] = 1
        else:
            segment.mask_image[new_image != 0] = 0

        # Remove non-connected subregions
        label_count, labels, stats, centroids = cv2.connectedComponentsWithStats(segment.mask_image)
        areas = np.asarray(stats)[:, cv2.CC_STAT_AREA]

        if label_count > 2:
            disconnected_regions = np.argsort(areas)[:-2]
            for i in disconnected_regions:
                segment.mask_image[labels == i] = 0

        # Fill holes
        background_id: int = np.argsort(areas)[-1]
        background_point: tuple = (np.unravel_index(np.argmax(labels == background_id), labels.shape))
        segment.mask_image = fill_holes(segment.mask_image, background_point)

        segment.size = np.count_nonzero(segment.mask_image)
        segment.compactness = calculate_compactness(segment.mask_image)
        segment.centroid = calculate_centroid(segment.mask_image)
        segment.channel_intensities = [calculate_intensity(image, segment.mask_image) for image in self.images]
        self._update_background()
        self.points_buffer.clear()

    def get_raw_image(self) -> np.ndarray:
        return self.images[self.segmentation.segmentation_channel_id]

    def get_segmentation_image(self) -> Union[np.ndarray, None]:
        if len(self.segmentation.segments) > 0:
            return np.sum([colourise_binary_mask(seg.mask_image, (255, 0, 0), (0, 0, 255)) for seg in self.segmentation.segments], 0)
        else:
            return None

    def _update_background(self) -> None:
        images = [cv2.imread(os.path.join(self.frame.root_directory, img_name),
                             flags=(cv2.IMREAD_GRAYSCALE + cv2.IMREAD_UNCHANGED)) for img_name in self.frame.image_names]
        self.segmentation.background_mask = find_segmented_background(images[self.frame.segmentations[0].segmentation_channel_id], self.segmentation.segments, self.frame.frame_shape)
        self.segmentation.background_intensities = [calculate_intensity(image, self.segmentation.background_mask) for image in self.images]
