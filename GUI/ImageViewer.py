import gi
import numpy as np
from GUI.Widgets.ResizingImage import ResizingImage
from GUI.Widgets.ImageViewControls import ImageViewControls
from Preprocessing.ND2Frames import ND2Frames
from Segmentation.Utilities import increase_contrast
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk  # noqa: E402


class ImageViewer(Gtk.Grid):
    def __init__(self, frames: ND2Frames, filepath: str) -> None:
        super(ImageViewer, self).__init__()

        self.frames = frames
        self.frame_id = 0
        self.fov_id = 0
        self.channel_id = 0
        self.zstack_id = 0

        self.frame_controls: ImageViewControls = ImageViewControls(self.frames.num_frames, self.frame_id)
        self.fov_controls: ImageViewControls = ImageViewControls(self.frames.num_fovs, self.fov_id, text="FOV:")
        self.channel_controls: ImageViewControls = ImageViewControls(self.frames.num_channels, self.channel_id, text="Channel: ")
        self.z_controls: ImageViewControls = ImageViewControls(self.frames.num_zstack, self.zstack_id, text="Z position: ")

        aspect_ratio: float = frames.sizes['x'] / frames.sizes['y']
        self.image: ResizingImage = ResizingImage()
        self.image_box: Gtk.AspectFrame = Gtk.AspectFrame(ratio=aspect_ratio, obey_child=False)
        self.image_box.add(self.image)
        self.image_box.set_hexpand(True)
        self.image_box.set_vexpand(True)

        self.control_frame: Gtk.Frame = Gtk.Frame(label=filepath)
        self.control_box: Gtk.Box = Gtk.Box()
        self.control_box.set_orientation(Gtk.Orientation.VERTICAL)
        self.control_box.set_valign(Gtk.Align.CENTER)
        self.control_box.set_halign(Gtk.Align.CENTER)
        self.control_frame.add(self.control_box)

        # Pack controls into a box to prevent them spreading vertically
        self.control_box.pack_start(self.frame_controls, True, False, 0)
        self.control_box.pack_start(self.fov_controls, True, False, 0)
        self.control_box.pack_start(self.channel_controls, True, False, 0)
        self.control_box.pack_start(self.z_controls, True, False, 0)

        self.attach(self.image_box, 0, 0, 1, 1)
        self.attach(self.control_frame, 1, 0, 1, 1)
        self.control_frame.set_vexpand(False)
        self.control_frame.set_hexpand(False)
        self.control_frame.set_halign(Gtk.Align.CENTER)
        self.control_frame.set_valign(Gtk.Align.CENTER)

        self.control_box.set_margin_top(10)
        self.control_box.set_margin_bottom(10)
        self.control_box.set_margin_start(10)
        self.control_box.set_margin_end(10)
        self.control_frame.set_label_align(0.5, 0.5)

        self.frame_controls.connect("update_frame", self._change_frame)
        self.fov_controls.connect("update_frame", self._change_fov)
        self.channel_controls.connect("update_frame", self._change_channel)
        self.z_controls.connect("update_frame", self._change_zstack)

        self.connect("size-allocate", self.pad_label)
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(5)
        self.set_margin_end(5)
        self.set_column_homogeneous(False)
        self.set_column_spacing(5)
        self._update_images()

    def pad_label(self, _, __):
        """Makes sure that the filepath label has a bit of padding at either end"""
        box_w = self.frame_controls.get_allocation().width
        label_w = self.control_frame.get_label_widget().get_preferred_size()[0].width

        if label_w > box_w:
            extra_padding = (label_w - box_w)/2 + 10
            self.control_box.set_margin_start(extra_padding)
            self.control_box.set_margin_end(extra_padding)


    def _change_frame(self, controls: ImageViewControls, frame_id: int) -> None:
        self.frame_id = frame_id
        self._update_images()
        print(self.control_box.get_preferred_size()[0].width)

    def _change_fov(self, controls: ImageViewControls, fov_id: int) -> None:
        self.fov_id = fov_id
        self._update_images()

    def _change_channel(self, controls: ImageViewControls, channel_id: int) -> None:
        self.channel_id = channel_id
        self._update_images()

    def _change_zstack(self, controls: ImageViewControls, zstack_id: int) -> None:
        self.zstack_id = zstack_id
        self._update_images()

    def _update_images(self) -> None:
        self.image.set_image(self._lookup_image(self.frame_id, self.fov_id, self.channel_id, self.zstack_id), True)

    def _lookup_image(self, frame_id: int, fov_id: int, channel_id: int, zstack_id: int) -> np.ndarray:
        # Frame axis iteration order: t m c z
        pos = (frame_id * self.frames.num_fovs * self.frames.num_channels * self.frames.num_zstack) + \
              (fov_id * self.frames.num_channels * self.frames.num_zstack) + \
              (channel_id * self.frames.num_zstack) +\
              zstack_id
        image = increase_contrast(self.frames[pos])
        return image


if __name__ == '__main__':
    class MyWindow(Gtk.Window):
        def __init__(self, images: ND2Frames, path: str) -> None:
            super(MyWindow, self).__init__(title="Image Viewer")

            self.viewer: ImageViewer = ImageViewer(images, path)
            self.connect("key-press-event", self.handle_keypress)

            self.add(self.viewer)

        # Some global keyboard shortcuts to improve usability
        def handle_keypress(self, window: Gtk.Widget, event: Gdk.EventKey):
            if event.get_keyval()[1] == Gdk.KEY_d:
                self.viewer.frame_controls.right_button.emit("clicked")

            if event.get_keyval()[1] == Gdk.KEY_a:
                self.viewer.frame_controls.left_button.emit("clicked")

            if event.get_keyval()[1] == Gdk.KEY_w:
                self.viewer.z_controls.right_button.emit("clicked")

            if event.get_keyval()[1] == Gdk.KEY_s:
                self.viewer.z_controls.left_button.emit("clicked")

    image_file_chooser: Gtk.FileChooserNative = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
    result = image_file_chooser.run()

    if result == Gtk.ResponseType.ACCEPT and image_file_chooser.get_filename() is not None:
        input_filepath = image_file_chooser.get_filename()

        if os.path.splitext(input_filepath)[-1] != '.nd2':
            print("Error: selected file is not  an nd2 image file!")
        else:
            with ND2Frames(input_filepath) as nd2_images:
                win = MyWindow(nd2_images, input_filepath)
                win.connect("destroy", Gtk.main_quit)

                # Show to get window size updated, then hide so that we can resize
                win.show_all()
                win.hide()
                win.resize(win.get_size()[0] + 750, 750)
                win.show_all()
                Gtk.main()
