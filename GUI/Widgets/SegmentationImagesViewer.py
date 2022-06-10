import gi
from typing import Optional, List
import numpy as np
import cv2

from Segmentation.SegmentationData import ProcessedFrame, Segment
from GUI.Widgets.SegmentOverlayImage import SegmentOverlayImage
from GUI.Widgets.SingleSegmentImage import SingleSegmentImage

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, Gdk, GObject, GdkPixbuf


def set_margins(widget, size):
    widget.set_margin_top(size)
    widget.set_margin_bottom(size)
    widget.set_margin_start(size)
    widget.set_margin_end(size)


class SegmentationImagesViewer(Gtk.Box):
    """Two-pane image viewer for segmentation editing."""
    def __init__(self, frame_segmentations: List[ProcessedFrame]) -> None:
        super(SegmentationImagesViewer, self).__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.segmentations: List[ProcessedFrame] = frame_segmentations
        self.current_segment_image: SingleSegmentImage = SingleSegmentImage(self.segmentations)
        self.segmented_image: SegmentOverlayImage = SegmentOverlayImage(self.segmentations)

        aspect_ratio: float = self.segmentations[0].frame_shape[1] / self.segmentations[0].frame_shape[0]
        self.current_box: Gtk.AspectFrame = Gtk.AspectFrame(ratio=aspect_ratio, obey_child=False, label="Current Segment")
        self.current_box.set_label_align(0.5, 0.5)
        self.segmented_box: Gtk.AspectFrame = Gtk.AspectFrame(ratio=aspect_ratio, obey_child=False, label="All Segments")
        self.segmented_box.set_label_align(0.5, 0.5)
        set_margins(self.current_segment_image, 3)
        set_margins(self.segmented_image, 3)
        self.current_box.add(self.current_segment_image)
        self.segmented_box.add(self.segmented_image)

        self.image_signal_handler_ids: List[int] = []

        self.pack_start(self.current_box, True, True, 0)
        self.pack_start(self.segmented_box, True, True, 0)
        self.set_homogeneous(True)
        self.set_spacing(5)

        self.selected_segment: Optional[Segment] = None

        self.segmented_image.connect("segment-selected", lambda overlay, segment: self.emit("segment_selected", segment))

    @GObject.Signal(arg_types=[GObject.TYPE_PYOBJECT])
    def segment_selected(self, segment: Optional[Segment]) -> None:
        self.selected_segment = segment
        self.current_segment_image.set_segment(segment)

    def set_selected_segment(self, segment: Optional[Segment]):
        if segment != self.selected_segment:
            self.segmented_image.emit("segment-selected", segment)

        # Update images
        self.set_frame_id(self.current_segment_image.frame_id)

    def set_frame_id(self, frame_id: int) -> None:
        self.segmented_image.set_frame_id(frame_id)
        self.current_segment_image.set_frame_id(frame_id)

    def enable_edit_mode(self, cursor_radius: int) -> None:
        """Disables segment selection, changes mouse cursor and enables editing signals"""
        self.segmented_image.toggle_segment_selection_on_click(False)

        # Change cursor to circular overlay, to help visualise edits
        img = np.zeros((cursor_radius * 2 + 1, cursor_radius * 2 + 1, 4), dtype=np.uint8)
        img = cv2.circle(img, (cursor_radius, cursor_radius), cursor_radius, (255, 255, 255, 255), 1)

        image_width = img.shape[1]
        image_height = img.shape[0]
        image_channels = img.shape[2]
        image_byte_data = img.tobytes()

        image_pix_buf = GdkPixbuf.Pixbuf.new_from_data(image_byte_data,
                                                       GdkPixbuf.Colorspace.RGB,
                                                       image_channels == 4, 8,
                                                       image_width, image_height,
                                                       image_width * image_channels)

        scale = self.segmented_image.image.get_scaling()
        scaled_radii = (int(cursor_radius * scale[0]), int(cursor_radius * scale[1]))
        scaled_pix_buf = image_pix_buf.scale_simple(scaled_radii[0] * 2 + 1, scaled_radii[1] * 2 + 1, GdkPixbuf.InterpType.BILINEAR)

        cursor = Gdk.Cursor(self.get_display(), scaled_pix_buf, scaled_radii[0], scaled_radii[1])
        self.get_window().set_cursor(cursor)

        self.image_signal_handler_ids.append(self.segmented_image.connect("button-press-event", lambda widget, event: self.emit("edit-begin", self.segmented_image.image.adjust_coords(event.x, event.y), event.state & Gdk.ModifierType.CONTROL_MASK)))
        self.image_signal_handler_ids.append(self.segmented_image.connect("motion-notify-event", lambda widget, event: self.emit("edit-continue", self.segmented_image.image.adjust_coords(event.x, event.y))))
        self.image_signal_handler_ids.append(self.segmented_image.connect("button-release-event", lambda widget, event: self.emit("edit-end")))

    def disable_edit_mode(self) -> None:
        """Enables segment selection, restores default mouse cursor and disables editing signals"""
        # Stop listening for mouse interaction on overlay image
        for handler_id in self.image_signal_handler_ids:
            self.segmented_image.disconnect(handler_id)
        self.image_signal_handler_ids.clear()

        # Enable segment selection
        self.segmented_image.toggle_segment_selection_on_click(True)
        self.get_window().set_cursor(None)

    @GObject.Signal(arg_types=[GObject.TYPE_PYOBJECT, GObject.TYPE_BOOLEAN])
    def edit_begin(self, location: tuple[int, int], erase: bool) -> None:
        pass

    @GObject.Signal(arg_types=[GObject.TYPE_PYOBJECT])
    def edit_continue(self, location: tuple[int, int]) -> None:
        pass

    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST)
    def edit_end(self) -> None:
        self.set_frame_id(self.current_segment_image.frame_id)
