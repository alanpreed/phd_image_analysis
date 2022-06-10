from __future__ import annotations  # Allows class's type annotation to be used within class definition

import cv2
import gi
import numpy as np
from typing import Tuple
gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, Gdk, GdkPixbuf


class ResizingImage(Gtk.EventBox):
    """Resizeable image widget that can register click events"""
    def __init__(self) -> None:
        super(ResizingImage, self).__init__()
        self.image_data: np.ndarray = np.zeros((0, 0))
        self.image_pix_buf: GdkPixbuf.Pixbuf = GdkPixbuf.Pixbuf()
        self.image: Gtk.Image = Gtk.Image()
        self._reset_image()
        self.add(self.image)

        self.connect("size_allocate", _on_allocate)

    def do_get_preferred_width(self) -> Tuple[int, int]:
        return 0, 0

    def do_get_preferred_height(self) -> Tuple[int, int]:
        return 0, 0

    def set_image(self, image_data: np.ndarray, adjust_contrast: bool = False) -> None:
        if image_data.shape[0] > 0 and image_data.shape[1] > 0:
            if adjust_contrast:
                bias = np.amin(image_data) * -1
                gain = np.iinfo(image_data.dtype).max / (np.amax(image_data) + bias)
                image_data = np.minimum(np.iinfo(image_data.dtype).max,
                                        (image_data.astype(np.uint64) + bias) * gain).astype(image_data.dtype)

            # Convert to 8 bit image
            if image_data.dtype == np.uint16:
                image_data = (image_data / 256).astype(np.uint8)
            elif image_data.dtype != np.uint8:
                print("ResizingImage: unsupported datatype {}".format(image_data.dtype))
                self._reset_image()
                return

            # Convert greyscale images to RGB
            if len(image_data.shape) == 2:
                image_data = cv2.cvtColor(image_data, cv2.COLOR_GRAY2RGB)

            self.image_data = image_data

            image_width = self.image_data.shape[1]
            image_height = self.image_data.shape[0]
            image_channels = self.image_data.shape[2]
            image_byte_data = image_data.tobytes()
            self.image_pix_buf = GdkPixbuf.Pixbuf.new_from_data(image_byte_data,
                                                                GdkPixbuf.Colorspace.RGB,
                                                                image_channels == 4, 8,
                                                                image_width, image_height,
                                                                image_width * image_channels)

            box_width = self.get_allocation().width
            box_height = self.get_allocation().height
            scaled_pix_buf = self.image_pix_buf.scale_simple(box_width, box_height, GdkPixbuf.InterpType.BILINEAR)
            self.image.set_from_pixbuf(scaled_pix_buf)
        else:
            self._reset_image()

    def _reset_image(self) -> None:
        self.image = Gtk.Image()
        self.image.set_alignment(0, 0)
        self.image.set_padding(0, 0)

    def adjust_coords(self, point_x: int, point_y: int) -> Tuple[int, int]:
        image_x = int((point_x / self.get_allocation().width) * self.image_data.shape[1])
        image_y = int((point_y / self.get_allocation().height) * self.image_data.shape[0])
        return image_x, image_y

    def get_scaling(self) -> tuple[float, float]:
        return self.get_allocation().width / self.image_data.shape[1], self.get_allocation().height / self.image_data.shape[0]


def _on_allocate(resizing_image: ResizingImage, allocation: Gdk.Rectangle) -> None:
    scaled_pix_buf = resizing_image.image_pix_buf.scale_simple(allocation.width, allocation.height,
                                                               GdkPixbuf.InterpType.BILINEAR)
    resizing_image.image.set_from_pixbuf(scaled_pix_buf)
