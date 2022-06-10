import gi
from typing import List, Union, Optional
import os
import cv2

from GUI.Widgets.SegmentInfoBox import SegmentInfoBox
from GUI.Widgets.SegmentViewControls import SegmentViewControls
from GUI.Widgets.SegmentEditControls import SegmentEditControls
from GUI.Widgets.SegmentationImagesViewer import SegmentationImagesViewer
from Segmentation.SegmentationData import ProcessedFrame, Segmentation, Segment, load_segmentation, save_segmentation
from Segmentation.SegmentationEditor import SegmentationEditor
from Segmentation.Measurement import calculate_intensity
from Segmentation.Utilities import find_segmented_background

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk  # noqa: E402


class SegmentationCurator(Gtk.Grid):
    def __init__(self, segmentations: List[ProcessedFrame], start_frame_id: int, start_segmentation_id: int, prompt_on_save: bool = False) -> None:
        super(SegmentationCurator, self).__init__()

        self.segmentations: List[ProcessedFrame] = segmentations
        self.prompt_on_save = prompt_on_save

        self.image_viewer: SegmentationImagesViewer = SegmentationImagesViewer(self.segmentations)
        self.info: SegmentInfoBox = SegmentInfoBox()
        self.view_controls: SegmentViewControls = SegmentViewControls(len(self.segmentations), start_frame_id,
                                                                      len(self.segmentations[0].segmentations),
                                                                      start_segmentation_id,
                                                                      self.segmentations[start_frame_id].segmentations[
                                                                          start_segmentation_id].name,
                                                                      self.segmentations[start_frame_id].root_directory)
        self.edit_controls: SegmentEditControls = SegmentEditControls()
        self.edge_button: Gtk.Button = Gtk.Button(label="Remove edge segments")
        self.save_button: Gtk.Button = Gtk.Button(label="Save segmentation")

        self.background_toggle: Gtk.Switch = Gtk.Switch()
        self.image_viewer.segmented_image.show_background = True
        self.background_toggle.set_state(self.image_viewer.segmented_image.show_background)
        self.background_label: Gtk.Label = Gtk.Label(label="Show background?")

        self.output_file_chooser: Gtk.FileChooserNative = Gtk.FileChooserNative(action=Gtk.FileChooserAction.SAVE)
        self.output_file_chooser.set_do_overwrite_confirmation(True)

        self.output_file_chooser.set_current_folder(self.segmentations[0].root_directory)
        self.segment_editor: SegmentationEditor = SegmentationEditor(self.segmentations[self.view_controls.frame_number], self.view_controls.segmentation_id)

        self.edit_grid: Gtk.Grid = Gtk.Grid()
        self.edit_grid.attach(self.edit_controls,           0, 0, 1, 3)
        self.edit_grid.attach(self.background_label,        2, 0, 1, 1)
        self.edit_grid.attach(self.background_toggle,       1, 0, 1, 1)
        self.edit_grid.attach(self.save_button,             1, 1, 2, 1)
        self.edit_grid.attach(self.edge_button,             1, 2, 2, 1)
        self.edit_grid.set_column_homogeneous(True)
        self.edit_grid.set_column_spacing(5)
        self.edit_grid.set_margin_start(5)
        self.edit_grid.set_margin_end(5)

        self.control_label: Gtk.Frame = Gtk.Frame(label="Editor control")
        self.control_label.add(self.edit_grid)
        self.control_label.set_label_align(0.5, 0.5)
        self.attach(self.image_viewer, 0, 0, 3, 1)
        self.attach(self.view_controls, 0, 1, 1, 1)
        self.attach(self.info, 1, 1, 1, 1)
        self.attach(self.control_label, 2, 1, 1, 1)
        self.set_row_spacing(5)
        self.set_column_spacing(5)
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(5)
        self.set_margin_end(5)

        self.view_controls.connect("update_frame", self._on_change_frame)
        self.save_button.connect("clicked", self._on_save)
        self.edge_button.connect("clicked", self.on_remove_edge_segments)
        self.edit_controls.connect("add_segment", self._on_add_segment)
        self.edit_controls.connect("delete_segment", self._on_delete_segment)

        self.image_viewer.connect("segment-selected", self._on_segment_selection)
        self.image_viewer.connect("edit-begin", lambda widget, location, erase: self.segment_editor.start_edit_segment(location, erase))
        self.image_viewer.connect("edit-continue", lambda widget, location: self.segment_editor.add_point(location))
        self.image_viewer.connect("edit-end", lambda widget: self._update_edit())

        self.edit_control_signal_handler: int = self.edit_controls.connect("edit_segment", lambda controls: self._start_edit())
        self.background_toggle.connect("state-set", self._on_toggle_background)

        self.image_viewer.set_frame_id(self.view_controls.frame_number)

    def current_segmentation(self) -> Segmentation:
        return self.segmentations[self.view_controls.frame_number].segmentations[self.view_controls.segmentation_id]

    def _start_edit(self) -> None:
        self.edit_controls.disconnect(self.edit_control_signal_handler)
        self.edit_control_signal_handler = self.edit_controls.connect("edit_segment", lambda controls: self._stop_edit())
        self.view_controls.set_sensitive(False)
        self.edit_controls.delete_button.set_sensitive(False)
        self.image_viewer.enable_edit_mode(self.segment_editor.radius)

    def _update_edit(self) -> None:
        self.segment_editor.finish_edit_segment(self.image_viewer.selected_segment.seg_id)
        self.info.set_segment(self.image_viewer.selected_segment)

    def _stop_edit(self) -> None:
        self.image_viewer.disable_edit_mode()

        # Enable navigation control and restore edit button
        self.edit_controls.disconnect(self.edit_control_signal_handler)
        self.edit_control_signal_handler = self.edit_controls.connect("edit_segment", lambda controls: self._start_edit())
        self.view_controls.set_sensitive(True)
        self.edit_controls.delete_button.set_sensitive(True)

        # Remove segment if size is 0
        if self.image_viewer.selected_segment.size == 0:
            self._on_delete_segment(None)

        self._clear_selected_segment()

    def _clear_selected_segment(self) -> None:
        self.info.set_segment(None)
        self.edit_controls.segment_deselected()
        self.segment_editor.segment = None
        self.image_viewer.set_selected_segment(None)

    def _on_change_frame(self, controls: SegmentViewControls, frame_number: int, segmentation_id: int):
        controls.set_segmentation_name(self.current_segmentation().name)
        self.segment_editor = SegmentationEditor(self.segmentations[frame_number], segmentation_id)
        self.image_viewer.set_frame_id(frame_number)
        self._clear_selected_segment()

    def _on_segment_selection(self, _segmented_img: SegmentationImagesViewer, segment: Optional[Segment]):
        if segment is not None:
            self.info.set_segment(segment)
            self.segment_editor.segment = segment
            self.edit_controls.segment_selected()
        else:
            self._clear_selected_segment()

    def _on_add_segment(self, _controls: SegmentEditControls) -> None:
        self.image_viewer.set_selected_segment(self.segment_editor.add_segment())
        self._start_edit()

    def _on_delete_segment(self, _controls: Union[None, SegmentEditControls]) -> None:
        self.segment_editor.delete_segment(self.image_viewer.selected_segment.seg_id)
        self._clear_selected_segment()

    def _on_save(self, _button: Gtk.Button):
        if self.prompt_on_save:
            self.output_file_chooser.set_current_folder(self.segmentations[0].root_directory)
            save_result = self.output_file_chooser.run()
            if save_result == Gtk.ResponseType.ACCEPT and self.output_file_chooser.get_filename() is not None:
                output_filename = self.output_file_chooser.get_filename()

                try:
                    save_segmentation(self.segmentations, output_filename)
                except IOError:
                    dialog = Gtk.MessageDialog(
                        transient_for=self,
                        flags=0,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text="Error!",
                    )
                    dialog.format_secondary_text("{}".format("Error saving file {}".format(output_filename)))
                    dialog.run()
                    dialog.destroy()
        else:
            base_dir = os.path.normpath(self.segmentations[0].root_directory)
            folders = base_dir.split(os.sep)
            output_name = folders[-2] + '_' + folders[-1] + "_curated"
            output_path = os.path.join(base_dir, output_name)

            try:
                save_segmentation(self.segmentations, output_path)
            except IOError:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Error!",
                )
                dialog.format_secondary_text("{}".format("Error saving file {}".format(output_path)))
                dialog.run()
                dialog.destroy()
            print("Saved")

    def toggle_segment_chosen_flag(self) -> None:
        if self.image_viewer.selected_segment is not None:
            current_seg = self.image_viewer.selected_segment
            current_seg.manually_chosen = not current_seg.manually_chosen
            self.info.set_segment(current_seg)

    def on_remove_edge_segments(self, _button: Gtk.Button) -> None:
        print("Removing edge segments")
        for frame in self.segmentations:
            for segmentation in frame.segmentations:
                to_remove: list[Segment] = []
                for segment in segmentation.segments:
                    seg_mask = segment.mask_image

                    mask_x0 = seg_mask[0, :].tolist()
                    mask_y0 = seg_mask[:, 0].tolist()
                    mask_x1 = seg_mask[frame.frame_shape[0] - 1, :].tolist()
                    mask_y1 = seg_mask[:, frame.frame_shape[1] - 1].tolist()

                    is_edge = any(mask_x0 + mask_x1 + mask_y0 + mask_y1)

                    if is_edge:
                        print("Frame {} seg {} is on edge".format(frame.frame_no, segment.seg_id))
                        to_remove.append(segment)

                for segment in to_remove:
                    segmentation.segments.remove(segment)

                # Recalculate correct segment IDs after removal
                for new_segment_id in range(len(segmentation.segments)):
                    segmentation.segments[new_segment_id].seg_id = new_segment_id

                # Recalculate segmentation background
                images = [cv2.imread(os.path.join(frame.root_directory, img_name), flags=(cv2.IMREAD_GRAYSCALE + cv2.IMREAD_UNCHANGED)) for img_name in frame.image_names]
                segmentation.background_mask = find_segmented_background(images[frame.segmentations[0].segmentation_channel_id], segmentation.segments, frame.frame_shape)
                segmentation.background_intensities = [calculate_intensity(image, segmentation.background_mask) for image in images]

        self._clear_selected_segment()

    def _on_toggle_background(self, switch: Gtk.Switch, state: bool):
        self.image_viewer.segmented_image.show_background = state
        self._clear_selected_segment()


def run_viewer(frame_segmentations: List[ProcessedFrame],
               starting_frame_id: int = 0, starting_segmentation_id: int = 0) -> bool:
    saved: bool = False

    class MyWindow(Gtk.Window):
        def __init__(self, segmentations: List[ProcessedFrame],
                     start_frame_id: int, start_segmentation_id: int) -> None:
            super(MyWindow, self).__init__(title="Segmentation Editor")
            self.set_default_size(550, 400)
            self.maximize()
            self.viewer: SegmentationCurator = SegmentationCurator(segmentations, start_frame_id, start_segmentation_id)
            self.connect("key-press-event", self.handle_keypress)
            self.add(self.viewer)

        def handle_keypress(self, _window: Gtk.Widget, event: Gdk.EventKey):
            if self.viewer.view_controls.get_sensitive():
                if event.get_keyval()[1] == Gdk.KEY_d:
                    self.viewer.view_controls.image_controls.right_button.emit("clicked")

                if event.get_keyval()[1] == Gdk.KEY_a:
                    self.viewer.view_controls.image_controls.left_button.emit("clicked")

                if event.get_keyval()[1] == Gdk.KEY_s:
                    nonlocal saved
                    saved = True
                    self.viewer.save_button.emit("clicked")

            if event.get_keyval()[1] == Gdk.KEY_e:
                if self.viewer.edit_controls.edit_button.get_sensitive():
                    self.viewer.edit_controls.edit_button.emit("clicked")

            if event.get_keyval()[1] == Gdk.KEY_r:
                if self.viewer.edit_controls.delete_button.get_sensitive():
                    self.viewer.edit_controls.delete_button.emit("clicked")

            if event.get_keyval()[1] == Gdk.KEY_w:
                if self.viewer.edit_controls.add_button.get_sensitive():
                    self.viewer.edit_controls.add_button.emit("clicked")

            if event.get_keyval()[1] == Gdk.KEY_t:
                self.viewer.toggle_segment_chosen_flag()

            if event.get_keyval()[1] == Gdk.KEY_k:
                self.destroy()

    win = MyWindow(frame_segmentations, starting_frame_id, starting_segmentation_id)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return saved


if __name__ == '__main__':
    segmentation_file_chooser: Gtk.FileChooserNative = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
    result = segmentation_file_chooser.run()

    if result == Gtk.ResponseType.ACCEPT and segmentation_file_chooser.get_filename() is not None:
        input_filepath = segmentation_file_chooser.get_filename()

        if os.path.splitext(input_filepath)[-1] != '.json':
            print("Error: selected file is not a segmentation json file!")
            exit(1)
        else:
            print("Opening {}".format(input_filepath))
            all_segmentations: List[ProcessedFrame] = load_segmentation(input_filepath)
            run_viewer(all_segmentations)
