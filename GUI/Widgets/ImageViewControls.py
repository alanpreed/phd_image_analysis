import gi
gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, GObject


class ImageViewControls(Gtk.Grid):
    """Widget containing Previous/Next buttons for navigating through image frames"""
    def __init__(self, num_frames: int, starting_frame: int, text: str = "Frame: ") -> None:
        super(ImageViewControls, self).__init__()

        self.num_frames: int = num_frames
        self.frame_number: int = starting_frame
        self.text = text

        self.frame_label: Gtk.Label = Gtk.Label(self.text + " {}".format(self.frame_number))
        self.left_button: Gtk.Button = Gtk.Button(label="Previous")
        self.right_button: Gtk.Button = Gtk.Button(label="Next")

        self.attach(self.frame_label, 0, 0, 2, 1)
        self.attach(self.left_button, 0, 1, 1, 1)
        self.attach(self.right_button, 1, 1, 1, 1)

        self.left_button.connect("clicked", self._on_click_prev)
        self.right_button.connect("clicked", self._on_click_next)

        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)
        self.set_valign(Gtk.Align.CENTER)

    @GObject.Signal
    def update_frame(self, frame_number: int) -> None:
        self.frame_label.set_text(self.text + " {}".format(frame_number))

    def _on_click_prev(self, button: Gtk.Button) -> None:
        self.frame_number = (self.frame_number - 1) % self.num_frames
        self.emit("update_frame", self.frame_number)

    def _on_click_next(self, button: Gtk.Button) -> None:
        self.frame_number = (self.frame_number + 1) % self.num_frames
        self.emit("update_frame", self.frame_number)

    def reset(self) -> None:
        self.frame_number = 0
        self.frame_label.set_text(self.text + " {}".format(self.frame_number))
