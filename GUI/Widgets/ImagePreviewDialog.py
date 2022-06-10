import gi
import numpy as np
from GUI.Widgets.ResizingImage import ResizingImage
from Segmentation.Utilities import increase_contrast

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk


class ImagePreviewDialog(Gtk.Dialog):
    """# Simple dialog box for previewing a single image"""
    def __init__(self, title: str, image: np.ndarray) -> None:
        super(ImagePreviewDialog, self).__init__(title=title)

        self.image: ResizingImage = ResizingImage()
        self.image_box: Gtk.AspectFrame = Gtk.AspectFrame(ratio=image.shape[1] / image.shape[0], obey_child=False)
        self.image_box.add(self.image)
        self.image.set_image(increase_contrast(image))

        self.close_button: Gtk.Button = Gtk.Button("Close")

        self.get_content_area().set_spacing(10)
        self.get_content_area().pack_start(self.image_box, True, True, 0)
        self.get_content_area().pack_start(self.close_button, False, False, 0)

        self.close_button.connect("clicked", self._on_click)
        self.set_modal(True)

        self.show_all()
        self.hide()
        self.resize(self.get_size()[0] + image.shape[1]/2, image.shape[0]/2)
        self.show_all()

    def _on_click(self, _) -> None:
        self.destroy()
