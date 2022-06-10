import numpy as np
from typing import List, Tuple
import cv2

from Segmentation.SegmentationData import Segment, ProcessedFrame


class SegmentFrameImage:
    def __init__(self, frame_segmentations: List[ProcessedFrame]) -> None:
        self.frame_segmentations: List[ProcessedFrame] = frame_segmentations
        self.frame_image: np.ndarray = np.full(tuple(self.frame_segmentations[0].frame_shape[0:2]) + (3,), 0.0)
        self.frame_id: int = 0

    def set_image(self, frame_id: int, show_background: bool = False) -> None:
        self.frame_id = frame_id
        frame_shape: Tuple[int, int] = tuple(self.frame_segmentations[frame_id].frame_shape)
        self.frame_image = np.full(frame_shape[0:2] + (3,), 0.0)

        num_regions: int = sum([len(segmentation.segments) for segmentation in self.frame_segmentations[self.frame_id].segmentations])

        if show_background:
            num_regions += 1

        colour_vals: np.ndarray = np.linspace(0, 1, num_regions, endpoint=False)
        seg_count: int = 0

        for segmentation in self.frame_segmentations[self.frame_id].segmentations:
            for segment in segmentation.segments:
                # Set hue to seg colour, saturation and value to 1, in area of segment
                self.frame_image[:, :, 0] += (segment.mask_image * colour_vals[seg_count]) * 255
                self.frame_image[:, :, 1] += segment.mask_image * 255
                self.frame_image[:, :, 2] += segment.mask_image * 255
                seg_count += 1

        if show_background:
            background_mask = self.frame_segmentations[frame_id].segmentations[0].background_mask
            self.frame_image[:, :, 0] += (background_mask * colour_vals[seg_count]) * 255
            self.frame_image[:, :, 1] += background_mask * 255
            self.frame_image[:, :, 2] += background_mask * 255

        # Convert to RGB by CV2 BGR conversion followed by flip
        self.frame_image = np.flip(cv2.cvtColor(self.frame_image.astype(np.uint8), cv2.COLOR_HSV2BGR), 2)

    def get_segments_at_point(self, point: Tuple[int, int]) -> List[Segment]:
        segs_at_point: List[Segment] = []

        for segmentation in self.frame_segmentations[self.frame_id].segmentations:
            for segment in segmentation.segments:
                if segment.mask_image[point] != 0:
                    segs_at_point.append(segment)

        return segs_at_point
