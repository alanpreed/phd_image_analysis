import gi
from typing import List, Optional
import os

from GUI.Widgets.SegmentInfoBox import SegmentInfoBox
from GUI.Widgets.SegmentViewControls import SegmentViewControls
from GUI.Widgets.TrackingImagesViewer import TrackingImagesViewer
from GUI.Widgets.TrackingNodeList import TrackingNodeList
from GUI.Widgets.TrackingSolverControls import TrackingSolverControls
from GUI.Widgets.CellLineageBox import CellLineageBox
from GUI.Widgets.CellInfoBox import CellInfoBox
from Segmentation.SegmentationData import ProcessedFrame, load_segmentation, Segment
from Tracking.FactorGraphSolver import FactorGraphSolver, SolverStatus
from Tracking.NodeCosts import CostParameters
from Tracking.TrackingSolution import TrackingSolution, save_tracking_solution


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk  # noqa: E402


class TrackingEditor(Gtk.Grid):
    def __init__(self, segmentations: List[ProcessedFrame], start_frame_id: int, start_segmentation_id: int) -> None:
        super(TrackingEditor, self).__init__()

        self.segmentations: List[ProcessedFrame] = segmentations
        self.tracking_solution: Optional[TrackingSolution] = None

        self.cost_params = CostParameters(1, 1, 3, 1, 3, 0.66, 20, 0, 2, 30)
        self.solver = FactorGraphSolver(segmentations, self.cost_params, True)
        self.solver.create_graph()

        self.tracking_images: TrackingImagesViewer = TrackingImagesViewer(segmentations)
        self.segment_info: SegmentInfoBox = SegmentInfoBox()
        self.cell_info: CellInfoBox = CellInfoBox()
        self.cell_lineage: CellLineageBox = CellLineageBox()
        self.view_controls: SegmentViewControls = SegmentViewControls(len(self.segmentations), start_frame_id,
                                                                      len(self.segmentations[0].segmentations),
                                                                      start_segmentation_id,
                                                                      self.segmentations[start_frame_id].segmentations[
                                                                          start_segmentation_id].name,
                                                                      self.segmentations[start_frame_id].root_directory)

        self.incoming_list: TrackingNodeList = TrackingNodeList("Incoming Assignment Nodes")
        self.outgoing_list: TrackingNodeList = TrackingNodeList("Outgoing Assignment Nodes")
        self.incoming_list.set_vexpand(True)
        self.outgoing_list.set_vexpand(True)

        self.solver_controls: TrackingSolverControls = TrackingSolverControls()

        self.controls_grid: Gtk.Grid = Gtk.Grid()
        self.controls_grid.set_column_homogeneous(True)
        self.controls_grid.set_row_spacing(5)
        self.controls_grid.set_column_spacing(5)
        #                                               x  y  w  h
        self.controls_grid.attach(self.incoming_list,   0, 0, 2, 3)
        self.controls_grid.attach(self.view_controls,   2, 0, 2, 1)
        self.controls_grid.attach(self.segment_info,    2, 1, 1, 1)
        self.controls_grid.attach(self.cell_info,       2, 2, 1, 1)
        self.controls_grid.attach(self.solver_controls, 3, 1, 1, 2)
        self.controls_grid.attach(self.cell_lineage,    4, 0, 1, 3)
        self.controls_grid.attach(self.outgoing_list,   5, 0, 2, 3)

        image_height: int = 3
        control_height: int = 2
        self.view_controls.set_vexpand(False)
        self.cell_info.set_vexpand(True)
        self.segment_info.set_vexpand(False)
        self.cell_info.set_vexpand(False)
        self.set_row_homogeneous(True)
        self.set_column_homogeneous(True)
        self.set_row_spacing(5)
        self.set_column_spacing(5)
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(5)
        self.set_margin_end(5)

        self.attach(self.tracking_images, 0, 0, 3, image_height)
        self.attach(self.controls_grid, 0, image_height, 3, control_height)

        self.tracking_images.connect("segment_selected", lambda images, segment: self._set_segment_selection(segment))
        self.view_controls.connect("update_frame", self._on_change_frame)
        self.solver_controls.connect("run_solver", self._on_run_solver)
        self.solver_controls.connect("reset_solver", self._on_reset_solver)
        self.solver_controls.connect("save_solution", self._on_save_solution)
        self.incoming_list.connect("manual_constraint_toggled", self._on_toggle_constraint)
        self.outgoing_list.connect("manual_constraint_toggled", self._on_toggle_constraint)
        self.tracking_images.set_frame(self.view_controls.frame_number)
        self.solver_controls.set_status(SolverStatus.INITIALISED)
        self.solver_controls.emit("run_solver")

    def _on_toggle_constraint(self, widget, node, force) -> None:
        self.solver.edit_constraint(node, force)
        self.solver_controls.emit("run_solver")

    def _on_change_frame(self, controls: SegmentViewControls, _frame_number: int, _segmentation_id: int):
        current = self.segmentations[self.view_controls.frame_number].segmentations[self.view_controls.segmentation_id]
        controls.set_segmentation_name(current.name)
        self.tracking_images.set_frame(self.view_controls.frame_number)

    def _set_segment_selection(self, segment: Optional[Segment]) -> None:
        cell = self.tracking_images.current_cell
        if cell is not None:
            self.segment_info.set_segment(cell.get_segment(self.view_controls.frame_number))
            self.cell_info.set_cell(cell)
            self.cell_lineage.set_cell(cell, self.view_controls.frame_number)
            self.incoming_list.update_list(cell.get_segment(self.view_controls.frame_number).incoming_assignments)
            self.outgoing_list.update_list(cell.get_segment(self.view_controls.frame_number).outgoing_assignments)
        else:
            self.segment_info.set_segment(segment)
            self.cell_info.set_cell(None)
            self.cell_lineage.set_cell(None, self.view_controls.frame_number)
            if segment is not None:
                self.incoming_list.update_list(segment.incoming_assignments)
                self.outgoing_list.update_list(segment.outgoing_assignments)
            else:
                self.incoming_list.update_list(None)
                self.outgoing_list.update_list(None)

    def _on_run_solver(self, _controls: TrackingSolverControls) -> None:
        self.solver_controls.set_status(SolverStatus.RUNNING)
        self.set_sensitive(False)

        # Wait for the UI to update before running the solver
        while Gtk.events_pending():
            Gtk.main_iteration_do(True)
        status: SolverStatus = self.solver.solve_graph()
        self.solver_controls.set_status(status)

        if status == SolverStatus.SOLVED_OPTIMAL or status == SolverStatus.SOLVED_FEASIBLE:
            self.tracking_solution = self.solver.generate_solution()
            self.tracking_images.set_cells(self.tracking_solution.cells)
        # Also wait for any interaction with inactive controls to be handles before re-enabling
        while Gtk.events_pending():
            Gtk.main_iteration_do(True)

        # Update node lists after solve
        if self.tracking_images.current_cell is not None:
            seg = self.tracking_images.current_cell.get_segment(self.view_controls.frame_number)
            self.incoming_list.update_list(seg.incoming_assignments)
            self.outgoing_list.update_list(seg.outgoing_assignments)

        self.tracking_images.set_frame(self.view_controls.frame_number)
        self.set_sensitive(True)

    def _on_reset_solver(self, _controls: TrackingSolverControls) -> None:
        self.solver = FactorGraphSolver(self.segmentations, self.cost_params, True)
        self.solver.create_graph()
        self.solver_controls.set_status(SolverStatus.INITIALISED)

        # Clear data from GUI and reset so that segments are used to draw overlay
        self.tracking_solution = None
        self.tracking_images.set_cells(None)
        self._set_segment_selection(None)

    def _on_save_solution(self, _controls: TrackingSolverControls):
        base_dir = os.path.normpath(self.segmentations[0].root_directory)
        folders = base_dir.split(os.sep)
        output_name = folders[-2] + '_' + folders[-1] + "_tracking"
        output_path = os.path.join(base_dir, output_name)
        save_tracking_solution(self.tracking_solution, output_path)
        print("Saved solution to {}".format(output_path))


def run_editor(segmentation_file: str, starting_frame_id: int = 0, starting_segmentation_id: int = 0):
    class MyWindow(Gtk.Window):
        def __init__(self, filename: str, start_frame_id: int, start_segmentation_id: int) -> None:
            super(MyWindow, self).__init__(title="Tracking Editor")
            self.set_default_size(550, 400)

            segmentations: List[ProcessedFrame] = load_segmentation(filename)

            self.viewer: TrackingEditor = TrackingEditor(segmentations, start_frame_id, start_segmentation_id)
            self.connect("key-press-event", self.handle_keypress)
            self.add(self.viewer)

        def handle_keypress(self, _window: Gtk.Widget, event: Gdk.EventKey):
            if self.viewer.view_controls.get_sensitive():
                if event.get_keyval()[1] == Gdk.KEY_d:
                    self.viewer.view_controls.image_controls.right_button.emit("clicked")

                if event.get_keyval()[1] == Gdk.KEY_a:
                    self.viewer.view_controls.image_controls.left_button.emit("clicked")

                if event.get_keyval()[1] == Gdk.KEY_s:
                    self.viewer.solver_controls.save_button.emit("clicked")

                if event.get_keyval()[1] == Gdk.KEY_k:
                    self.destroy()

    win = MyWindow(segmentation_file, starting_frame_id, starting_segmentation_id)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == '__main__':
    segmentation_file_chooser: Gtk.FileChooserNative = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
    result = segmentation_file_chooser.run()

    if result == Gtk.ResponseType.ACCEPT and segmentation_file_chooser.get_filename() is not None:
        input_filepath = segmentation_file_chooser.get_filename()

        # fov = 5
        # region = 3

        # input_filepath = "/data/cropped/2021-04-23_CMOS_40x_broken_5'utr_EDF/fov_{0}/region_{1}/fov_{0}_region_{1}_curated.json".format(fov, region)

        if os.path.splitext(input_filepath)[-1] != '.json':
            print("Error: selected file is not a segmentation json file!")
        else:
            print("Opening {}".format(input_filepath))
            run_editor(input_filepath)
