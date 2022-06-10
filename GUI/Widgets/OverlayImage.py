import gi
import numpy as np
import cv2
from typing import Union

from GUI.Widgets.ResizingImage import ResizingImage
gi.require_version("Gtk", "3.0")  # noqa: E402


class OverlayImage(ResizingImage):
    """Two-layer resizeable image widget, combining a base image and a transparent overlay"""
    def __init__(self) -> None:
        super(OverlayImage, self).__init__()

        self.raw_image: Union[None, np.ndarray] = None
        self.set_hexpand(True)
        self.set_vexpand(True)

    def set_overlay(self, overlay_image: Union[None, np.ndarray], alpha: float = 0.6) -> None:
        if self.raw_image is not None:
            if overlay_image is not None:
                # Construct RGB version of grey-level image and overlay
                base_colour = np.dstack((self.raw_image, self.raw_image, self.raw_image))
                if len(overlay_image.shape) == 2:
                    overlay_colour = np.dstack((overlay_image, np.zeros(overlay_image.shape), np.zeros(overlay_image.shape)))
                else:
                    overlay_colour = overlay_image

                # Convert both to HSV
                base_hsv = cv2.cvtColor(base_colour.astype(np.uint8), cv2.COLOR_RGB2HSV)
                overlay_hsv = cv2.cvtColor(overlay_colour.astype(np.uint8), cv2.COLOR_RGB2HSV)

                base_hsv[..., 0] = overlay_hsv[..., 0]
                base_hsv[..., 1] = overlay_hsv[..., 1] * alpha

                result = cv2.cvtColor(base_hsv, cv2.COLOR_HSV2RGB)
                super().set_image(result)
            else:
                super().set_image(self.raw_image)

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
                print("OverlayImage: unsupported datatype {}".format(image_data.dtype))
                return

        self.raw_image = image_data
        super().set_image(image_data, adjust_contrast)
