import gi
import multiprocessing
import os
from typing import Union, Dict, Tuple

import numpy as np

from Preprocessing.ND2Frames import ND2Frames
from GUI.Widgets.CroppingControls import CroppingControls
from GUI.Widgets.ResizingImage import ResizingImage
from GUI.Widgets.ImageViewControls import ImageViewControls
from GUI.Widgets.RunningDialog import RunningDialog
from GUI.Widgets.ImagePreviewDialog import ImagePreviewDialog
from Preprocessing.ImageCropper import ImageCropper, CropParameters

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk  # noqa: E402


class CroppingTool(Gtk.Grid):
    def __init__(self, images: ND2Frames, brightfield_channel: int, defaults: CropParameters, filepath: str,
                 starting_frame: int = 0, starting_FOV: int = 0, starting_z: int = 0) -> None:
        super(CroppingTool, self).__init__()

        self.cropper: ImageCropper = ImageCropper(images, defaults)
        self.channel_id: int = brightfield_channel

        self.output_folder_chooser: Gtk.FileChooserNative = Gtk.FileChooserNative(action=Gtk.FileChooserAction.SELECT_FOLDER)
        self.running_dialog: Union[None, RunningDialog] = None
        self.output_folder_path: str = os.path.expanduser("~")

        self.frame_controls: ImageViewControls = ImageViewControls(self.cropper.frames.num_frames, starting_frame)
        self.fov_controls: ImageViewControls = ImageViewControls(self.cropper.frames.num_fovs, starting_FOV, text="FOV:")
        self.z_controls: ImageViewControls = ImageViewControls(self.cropper.frames.num_zstack, starting_z, text="Z position: ")

        control_limits: Dict[str, Tuple] = {"row_count": (0, None),
                                            "row_spacing": (0, None),
                                            "column_count": (0, None),
                                            "trap_detection_channel": (0, images.num_channels),
                                            "trap_detection_z_position": (0, images.num_zstack),
                                            "min_trap_size": (0, None),
                                            "max_trap_size": (0, None)}
        self.crop_controls: CroppingControls = CroppingControls(self.cropper.parameters, control_limits)

        self.open_folder_button: Gtk.Button = Gtk.Button(label="Choose output folder")
        self.open_folder_button.set_valign(Gtk.Align.CENTER)
        self.run_crop_button: Gtk.Button = Gtk.Button(label="Run crop")
        self.run_crop_button.set_valign(Gtk.Align.CENTER)
        self.preview_trap_button: Gtk.Button = Gtk.Button(label="View trap detection")
        self.run_crop_button.set_valign(Gtk.Align.CENTER)

        self.image: ResizingImage = ResizingImage()
        self.image_box: Gtk.AspectFrame = Gtk.AspectFrame(ratio=images.sizes['x'] / images.sizes['y'], obey_child=False)
        self.image_box.add(self.image)
        self.image_box.set_hexpand(True)
        self.image_box.set_vexpand(True)

        self.control_box: Gtk.Box = Gtk.Box()
        self.control_box.set_orientation(Gtk.Orientation.VERTICAL)
        self.control_box.set_valign(Gtk.Align.CENTER)
        self.control_box.set_halign(Gtk.Align.CENTER)

        # Pack controls into a box to prevent them spreading vertically
        self.control_box.pack_start(self.crop_controls, True, False, 0)
        self.control_box.pack_start(self.frame_controls, True, False, 0)
        self.control_box.pack_start(self.fov_controls, True, False, 0)
        self.control_box.pack_start(self.z_controls, True, False, 0)
        self.control_box.pack_start(self.preview_trap_button, True, False, 0)
        self.control_box.pack_start(self.open_folder_button, True, False, 0)
        self.control_box.pack_start(self.run_crop_button, True, False, 0)

        self.control_frame: Gtk.Frame = Gtk.Frame(label=filepath)
        self.control_frame.set_label_align(0.5, 0.5)
        self.control_frame.set_vexpand(False)
        self.control_frame.set_hexpand(False)
        self.control_frame.set_halign(Gtk.Align.CENTER)
        self.control_frame.set_valign(Gtk.Align.CENTER)
        self.control_frame.add(self.control_box)
        self.control_box.set_margin_top(10)
        self.control_box.set_margin_bottom(10)
        self.control_box.set_margin_start(10)
        self.control_box.set_margin_end(10)

        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(5)
        self.set_margin_end(5)
        self.set_column_spacing(5)
        self.set_column_homogeneous(False)
        self.attach(self.image_box, 0, 0, 1, 1)
        self.attach(self.control_frame, 1, 0, 1, 1)

        self.crop_controls.connect("update_parameters", self._change_parameters)
        self.frame_controls.connect("update_frame", self._change_frame)
        self.fov_controls.connect("update_frame", self._change_fov)
        self.z_controls.connect("update_frame", self._change_zstack)
        self.open_folder_button.connect("clicked", self._open_folder)
        self.run_crop_button.connect("clicked", self._run_crop)
        self.preview_trap_button.connect("clicked", self._view_traps)
        self.image.connect("button_press_event", self._on_click)
        self.connect("size-allocate", self._pad_label)
        self._update_image()

    def _pad_label(self, _, __):
        """Makes sure that the filepath label has a bit of padding at either end"""
        box_w = self.frame_controls.get_allocation().width
        label_w = self.control_frame.get_label_widget().get_preferred_size()[0].width
        if label_w > box_w:
            extra_padding = (label_w - box_w)/2 + 10
            self.control_box.set_margin_start(extra_padding)
            self.control_box.set_margin_end(extra_padding)

    def _on_click(self, image: ResizingImage, event: Gdk.EventButton) -> None:
        if event.type == Gdk.EventType.BUTTON_PRESS:
            image_x, image_y = image.adjust_coords(event.x, event.y)
            self.cropper.flag_region((image_y, image_x))
            self._update_image()

    def _update_image(self) -> None:
        preview: np.ndarray = self.cropper.generate_preview(self.frame_controls.frame_number,
                                                            self.fov_controls.frame_number,
                                                            self.channel_id, self.z_controls.frame_number)
        self.image.set_image(preview)

    def _change_frame(self, controls: ImageViewControls, frame_id: int) -> None:
        self._update_image()

    def _change_fov(self, controls: ImageViewControls, fov_id: int) -> None:
        self.frame_controls.reset()
        self.cropper.reset_offset()
        self._update_image()

    def _change_zstack(self, controls: ImageViewControls, zstack_id: int) -> None:
        self._update_image()

    def _change_parameters(self, controls: CroppingControls, new_settings: CropParameters) -> None:
        self.cropper.update_parameters(new_settings)
        print(self.cropper.parameters)
        self._update_image()

    def _open_folder(self, button: Gtk.Button) -> None:
        chooser_result: Gtk.ResponseType = self.output_folder_chooser.run()
        if chooser_result == Gtk.ResponseType.ACCEPT and self.output_folder_chooser.get_filename() is not None:
            self.output_folder_path = self.output_folder_chooser.get_filename()

    def _view_traps(self, button: Gtk.Button) -> None:
        print("viewing traps")
        ImagePreviewDialog("Detected Traps", self.cropper.preview_trap_image(self.frame_controls.frame_number, self.fov_controls.frame_number))

    def _run_crop(self, button: Gtk.Button) -> None:
        parent_conn, child_conn = multiprocessing.Pipe()
        crop_thread = multiprocessing.Process(target=self.cropper.crop_all, args=(self.fov_controls.frame_number,
                                                                                  self.output_folder_path,
                                                                                  parent_conn))
        self.running_dialog = RunningDialog("Running crop", child_conn, crop_thread.terminate)
        crop_thread.start()


if __name__ == '__main__':
    class MyWindow(Gtk.Window):
        def __init__(self, images: ND2Frames, filepath: str) -> None:
            super(MyWindow, self).__init__(title="Cropping Tool")
            # 60x defaults
            # defaults: CropParameters = CropParameters(angle=0,
            #                                           row_count=8,
            #                                           column_count=(7, 6),
            #                                           row_spacing=241,
            #                                           column_spacing=297,
            #                                           row_offset=120,
            #                                           column_offset=(-30, 125),
            #                                           correct_drift=True,
            #                                           trap_detection_channel=0,
            #                                           trap_detection_z_position=0,
            #                                           min_trap_size=1900,
            #                                           max_trap_size=3000,
            #                                           alternate_trap_detection=False)
            # 40x defaults
            defaults: CropParameters = CropParameters(angle=0,
                                                      row_count=12,
                                                      column_count=(7, 6),
                                                      row_spacing=161,
                                                      column_spacing=197,
                                                      row_offset=120,
                                                      column_offset=(65, 165),
                                                      correct_drift=True,
                                                      trap_detection_channel=0,
                                                      trap_detection_z_position=0,
                                                      min_trap_size=700,
                                                      max_trap_size=2000,
                                                      alternate_trap_detection=False)

            brightfield_channel_id: int = 0
            self.crop: CroppingTool = CroppingTool(images, brightfield_channel_id, defaults, filepath)
            self.add(self.crop)
            self.connect("key-press-event", self.handle_keypress)

        def handle_keypress(self, _window: Gtk.Widget, event: Gdk.EventKey):
            if event.get_keyval()[1] == Gdk.KEY_Right:
                self.crop.frame_controls.right_button.emit("clicked")

            if event.get_keyval()[1] == Gdk.KEY_Left:
                self.crop.frame_controls.left_button.emit("clicked")

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
