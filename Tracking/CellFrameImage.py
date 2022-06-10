import numpy as np
from typing import List, Tuple
import cv2

from Tracking.Cell import Cell
from Segmentation.SegmentationData import Segment


class CellFrameImage:
    def __init__(self, cell_data: List[Cell]) -> None:
        self.frame_id: int = 0
        self.all_cells = cell_data
        self.current_frame_cells: List[Cell] = []
        self.cell_colours: np.ndarray = np.linspace(0, 1, len(self.all_cells), endpoint=False)

        # Find frame shape by looking up the size of the first cell segment image to be included in this image
        frame_shape: Tuple[int, int] = cell_data[0].segments[0].mask_image.shape
        self.frame_image: np.ndarray = np.full(frame_shape[0:2] + (3,), 0.0)

    def set_image(self, frame_id: int) -> None:
        self.current_frame_cells = [cell for cell in self.all_cells if cell.check_exists(frame_id)]
        frame_shape: Tuple[int, int] = self.current_frame_cells[0].get_segment(frame_id).mask_image.shape
        self.frame_image = np.full(frame_shape[0:2] + (3,), 0.0)
        self.frame_id = frame_id

        for cell in self.current_frame_cells:
            segment = cell.get_segment(frame_id)

            # Set hue to seg colour, saturation and value to 1, in area of segment
            self.frame_image[:, :, 0] += (segment.mask_image * self.cell_colours[cell.cell_id]) * 255
            self.frame_image[:, :, 1] += segment.mask_image * 255
            self.frame_image[:, :, 2] += segment.mask_image * 255

        # Convert to RGB by CV2 BGR conversion followed by flip
        self.frame_image = np.flip(cv2.cvtColor(self.frame_image.astype(np.uint8), cv2.COLOR_HSV2BGR), 2)

    def get_segments_at_point(self, point: Tuple[int, int]) -> List[Segment]:
        segs_at_point: List[Segment] = []
        for cell in self.current_frame_cells:
            segment = cell.get_segment(self.frame_id)
            if segment.mask_image[point] != 0:
                segs_at_point.append(segment)
        return segs_at_point

    def get_cells_at_point(self, point: Tuple[int, int]) -> List[Cell]:
        cells_at_point: List[Cell] = []
        for cell in self.current_frame_cells:
            segment = cell.get_segment(self.frame_id)
            if segment.mask_image[point] != 0:
                cells_at_point.append(cell)
        return cells_at_point
