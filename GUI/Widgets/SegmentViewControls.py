import gi
from GUI.Widgets.ImageViewControls import ImageViewControls

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, GObject


class SegmentViewControls(Gtk.Frame):
    """Pair of ImageViewControls, for navigating frame number and segmentation number"""
    def __init__(self, num_frames: int, starting_frame: int, num_segmentations: int, starting_segmentation: int, seg_name: str, file_name: str) -> None:
        super(SegmentViewControls, self).__init__(label=file_name)
        self.set_label_align(0.5, 0.5)
        self.grid: Gtk.Grid = Gtk.Grid()
        self.grid.set_margin_top(3)
        self.grid.set_margin_bottom(3)

        # Add left and right padding to prevent text hitting frame line
        self.grid.set_margin_start(5)
        self.grid.set_margin_end(5)

        self.segmentation_id: int = starting_segmentation
        self.frame_number: int = starting_frame

        self.image_controls: ImageViewControls = ImageViewControls(num_frames, starting_frame)
        self.segmentation_controls: ImageViewControls = ImageViewControls(num_segmentations, self.segmentation_id, text="Segmentation: ")
        self.segmentation_label: Gtk.Label = Gtk.Label()
        self.set_segmentation_name(seg_name)

        self.grid.attach(self.segmentation_label, 0, 0, 2, 1)
        self.grid.attach(self.image_controls, 0, 1, 1, 2)
        self.grid.attach(self.segmentation_controls, 1, 1, 1, 2)
        self.add(self.grid)

        self.image_controls.connect("update_frame", lambda img_con, new_frame: self.emit("update_frame", new_frame, self.segmentation_id))
        self.segmentation_controls.connect("update_frame", lambda img_con, new_segmentation: self.emit("update_frame", self.frame_number, new_segmentation))

        self.grid.set_column_homogeneous(True)
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_spacing(10)

    def set_segmentation_name(self, name: str):
        self.segmentation_label.set_text("Segmentation name:     {}".format(name))

    @GObject.Signal
    def update_frame(self, frame_number: int, segmentation_id: int) -> None:
        self.frame_number = frame_number
        self.segmentation_id = segmentation_id
