import gi
from typing import List, Optional
import os
import cv2

from GUI.Widgets.OverlayImage import OverlayImage
from Segmentation.SegmentationData import Segment, ProcessedFrame
from Visualisation.Visualisation import colourise_binary_mask
from Segmentation.Utilities import increase_contrast

gi.require_version("Gtk", "3.0")  # noqa: E402


class SingleSegmentImage(OverlayImage):
    """Display a single segment overlaid on the raw image"""
    def __init__(self, frame_segmentations: List[ProcessedFrame]) -> None:
        super(SingleSegmentImage, self).__init__()
        self.frame_id: int = 0
        self.segment: Optional[Segment] = None
        self.frame_segmentations: List[ProcessedFrame] = frame_segmentations

        self.set_hexpand(True)
        self.set_vexpand(True)

    def set_segment(self, segment: Optional[Segment]) -> None:
        self.segment = segment
        if segment is not None:
            self.set_overlay(colourise_binary_mask(segment.mask_image, (255, 0, 0), (255, 0, 0)))
        else:
            self.set_overlay(None)

    def set_frame_id(self, frame_id: int) -> None:
        """Update raw image with new frame"""
        self.frame_id = frame_id

        frame_segmentation = self.frame_segmentations[frame_id]

        file_path = os.path.join(frame_segmentation.root_directory, frame_segmentation.image_names[frame_segmentation.segmentations[0].segmentation_channel_id])
        image = cv2.imread(file_path, flags=cv2.IMREAD_UNCHANGED)
        self.set_image(increase_contrast(image))
        self.set_segment(self.segment)
