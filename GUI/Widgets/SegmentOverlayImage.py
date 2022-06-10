import gi
import cv2
import os
import numpy as np
from typing import Optional, Tuple, List

from Segmentation.SegmentFrameImage import SegmentFrameImage
from Segmentation.Utilities import increase_contrast
from GUI.Widgets.OverlayImage import OverlayImage
from Segmentation.SegmentationData import ProcessedFrame, Segment
from Visualisation.Visualisation import generate_border_mask
from Tracking.CellFrameImage import CellFrameImage
from Tracking.Cell import Cell

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, Gdk, GObject


class SegmentOverlayImage(Gtk.Overlay):
    """ Image overlay of segments over brightfield image. Segments are selectable if interactive; selected segment
        is drawn with a white border."""
    def __init__(self, frame_segmentations: List[ProcessedFrame], interactive: bool = True) -> None:
        super(SegmentOverlayImage, self).__init__()
        self.frame_segmentations = frame_segmentations
        self.frame_id: Optional[int] = None
        self.show_background: bool = False

        self.segment_image: SegmentFrameImage = SegmentFrameImage(self.frame_segmentations)
        self.cell_image: Optional[CellFrameImage] = None

        self.selected_segment: Optional[Segment] = None
        self.image: OverlayImage = OverlayImage()
        self.add(self.image)
        self.connect("get_child_position", _handle_label_position)
        self.labels: List[Gtk.Label] = []

        self.on_click_signal_handler: Optional[int] = None

        if interactive:
            self.on_click_signal_handler = self.connect("button_press_event", _on_click)

    def set_frame_id(self, frame_id: Optional[int]) -> None:
        """Update image frame and overlay using segments (or cells if available) present in the given frame number"""
        self.frame_id = frame_id
        self.label_segments(frame_id)
        if frame_id is not None:
            frame_segmentation = self.frame_segmentations[frame_id]
            file_path = os.path.join(frame_segmentation.root_directory, frame_segmentation.image_names[0])
            image = cv2.imread(file_path, flags=cv2.IMREAD_UNCHANGED)
            self.image.set_image(increase_contrast(image))

            if self.cell_image is not None:
                self.cell_image.set_image(frame_id)
                self.image.set_overlay(self.cell_image.frame_image, alpha=1)
            else:
                self.segment_image.set_image(frame_id, self.show_background)
                self.image.set_overlay(self.segment_image.frame_image, alpha=1)

            if self.selected_segment is not None:
                self.draw_border(self.selected_segment, (255, 255, 255))
        else:
            self.image.set_image(np.zeros((1, 1)).astype(np.uint8))

    def set_cells(self, cells: Optional[List[Cell]]) -> None:
        """Provide cell data to use instead of segments"""
        if cells is not None:
            self.cell_image = CellFrameImage(cells)
        else:
            self.cell_image = None

        if self.frame_id is not None:
            self.set_frame_id(self.frame_id)

    def get_cell(self) -> Optional[Cell]:
        if self.cell_image is not None and self.selected_segment is not None:
            for cell in self.cell_image.current_frame_cells:
                seg: Segment = cell.get_segment(self.frame_id)
                if seg is not None and seg.seg_id == self.selected_segment.seg_id:
                    return cell
        return None

    @GObject.Signal(arg_types=[GObject.TYPE_PYOBJECT])
    def segment_selected(self, segment: Optional[Segment], colour: Tuple[int, int, int] = (255, 255, 255), thickness: int = 1) -> None:
        if self.frame_id is not None:
            if self.cell_image is not None:
                self.image.set_overlay(self.cell_image.frame_image, alpha=1)
            else:
                self.image.set_overlay(self.segment_image.frame_image, alpha=1)
            if segment is not None:
                self.selected_segment = segment

                self.draw_border(segment, colour, thickness)
            else:
                self.selected_segment = None

    def draw_border(self, segment: Segment, colour: Tuple[int, int, int], thickness: int = 1) -> None:
        """Draw a 1-pixel border around the provided segment"""
        border_img = generate_border_mask(segment.mask_image, thickness)
        result = self.image.image_data
        result[border_img != 0] = colour
        super(OverlayImage, self.image).set_image(result)

    def label_segments(self, frame_id: Optional[int]) -> None:
        for label in self.labels:
            self.remove(label)
        self.labels = []

        if frame_id is not None:
            for segmentation in self.frame_segmentations[frame_id].segmentations:
                for segment in segmentation.segments:
                    seg_label: Gtk.Label = Gtk.Label(label=segment.seg_id)
                    seg_label.centroid = segment.centroid
                    seg_label.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 1, 1))
                    self.add_overlay(seg_label)
                    seg_label.show()
                    self.labels.append(seg_label)
                    self.set_overlay_pass_through(seg_label, True)

    def scale_label_centroid(self, centroid: Tuple[float, float]) -> Tuple[float, float]:
        shape = self.image.image_data.shape
        return (centroid[0] / shape[0]) * self.get_allocated_height(), (centroid[1] / shape[1]) * self.get_allocated_width()

    def toggle_segment_selection_on_click(self, sensitive: bool):
        """Enable/disable segment selection functionality"""
        if sensitive and self.on_click_signal_handler is None:
            self.on_click_signal_handler = self.connect("button_press_event", _on_click)
        elif not sensitive and self.on_click_signal_handler is not None:
            self.disconnect(self.on_click_signal_handler)
            self.on_click_signal_handler = None


# Connected to get-child-position signal, allowing overlays at custom positions
def _handle_label_position(overlay: SegmentOverlayImage, widget: Gtk.Widget, rect: Gdk.Rectangle) -> bool:
    rect.height = widget.get_preferred_height().natural_height
    rect.width = widget.get_preferred_width().natural_width

    coords = overlay.scale_label_centroid(widget.centroid)
    rect.x = coords[1]
    rect.y = coords[0] - rect.height / 2
    return True


def _on_click(segment_overlay_image: SegmentOverlayImage, event: Gdk.EventButton) -> None:
    if event.type == Gdk.EventType.BUTTON_PRESS:
        image_x, image_y = segment_overlay_image.image.adjust_coords(event.x, event.y)

        if segment_overlay_image.cell_image is not None:
            segments = segment_overlay_image.cell_image.get_segments_at_point((image_y, image_x))
        else:
            segments = segment_overlay_image.segment_image.get_segments_at_point((image_y, image_x))

        if len(segments) > 0:
            index = 0
            for i in range(len(segments)):
                if segment_overlay_image.selected_segment is not None and segments[i].seg_id == segment_overlay_image.selected_segment.seg_id:
                    index = (i + 1) % len(segments)
                    break

            segment_overlay_image.selected_segment = segments[index]
            segment_overlay_image.emit("segment_selected", segments[index])

        else:
            segment_overlay_image.emit("segment_selected", None)
