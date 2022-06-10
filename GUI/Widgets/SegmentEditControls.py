import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject  # noqa: E402


class SegmentEditControls(Gtk.Box):
    """Collection of buttons for controlling segmentation editor"""
    def __init__(self) -> None:
        super(SegmentEditControls, self).__init__()
        self.editing: bool = False

        self.add_button: Gtk.Button = Gtk.Button(label="Add")
        self.edit_button: Gtk.Button = Gtk.Button(label="Edit")
        self.delete_button: Gtk.Button = Gtk.Button(label="Delete")

        self.edit_button.set_sensitive(False)
        self.delete_button.set_sensitive(False)

        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.pack_start(self.add_button, True, True, 0)
        self.pack_start(self.edit_button, True, True, 0)
        self.pack_start(self.delete_button, True, True, 0)

        self.add_button.connect("clicked", lambda button: self.emit("add_segment"))
        self.edit_button.connect("clicked", lambda button: self.emit("edit_segment"))
        self.delete_button.connect("clicked", lambda button: self.emit("delete_segment"))

    def segment_selected(self) -> None:
        self.add_button.set_sensitive(False)
        self.edit_button.set_sensitive(True)
        self.delete_button.set_sensitive(True)

    def segment_deselected(self) -> None:
        self.add_button.set_sensitive(True)
        self.edit_button.set_sensitive(False)
        self.delete_button.set_sensitive(False)

    @GObject.Signal
    def add_segment(self) -> None:
        self.editing = True
        self.add_button.set_sensitive(False)
        self.edit_button.set_sensitive(True)
        self.edit_button.set_label("Done")
        pass

    @GObject.Signal
    def edit_segment(self) -> None:
        if not self.editing:
            self.editing = True
            self.edit_button.set_label("Done")
        else:
            self.editing = False
            self.edit_button.set_label("Edit")

    @GObject.Signal
    def delete_segment(self) -> None:
        pass

