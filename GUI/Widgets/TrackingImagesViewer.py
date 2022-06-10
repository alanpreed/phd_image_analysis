import gi
from typing import Optional, List

from Segmentation.SegmentationData import ProcessedFrame, Segment
from GUI.Widgets.SegmentOverlayImage import SegmentOverlayImage
from Tracking.Cell import Cell, AssignmentType

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, GObject

selection_border_colour: tuple[int, int, int] = (255, 255, 255)
appear_border_colour: tuple[int, int, int] = (255, 0, 0)
division_border_colour: tuple[int, int, int] = (0, 255, 0)
border_thickness: int = 1
overlap_border_thickness: int = 2


def set_margins(widget, size):
    widget.set_margin_top(size)
    widget.set_margin_bottom(size)
    widget.set_margin_start(size)
    widget.set_margin_end(size)


class TrackingImagesViewer(Gtk.Box):
    """Three-pane image viewer for tracking editing"""
    def __init__(self, frame_segmentations: List[ProcessedFrame]) -> None:
        super(TrackingImagesViewer, self).__init__(orientation=Gtk.Orientation.HORIZONTAL)

        self.segmentations: List[ProcessedFrame] = frame_segmentations
        self.current_cell: Optional[Cell] = None
        self.cells_available: bool = False
        self.frame_id: int = 0

        aspect_ratio: float = self.segmentations[0].frame_shape[1] / self.segmentations[0].frame_shape[0]
        self.previous_frame: SegmentOverlayImage = SegmentOverlayImage(self.segmentations, False)
        self.previous_box: Gtk.AspectFrame = Gtk.AspectFrame(ratio=aspect_ratio, obey_child=False, label="Previous Frame")
        self.previous_box.set_label_align(0.5, 0.5)
        self.previous_box.add(self.previous_frame)

        self.current_frame: SegmentOverlayImage = SegmentOverlayImage(self.segmentations)
        self.current_box: Gtk.AspectFrame = Gtk.AspectFrame(ratio=aspect_ratio, obey_child=False, label="Current Frame")
        self.current_box.set_label_align(0.5, 0.5)
        self.current_box.add(self.current_frame)

        self.next_frame: SegmentOverlayImage = SegmentOverlayImage(self.segmentations, False)
        self.next_box: Gtk.AspectFrame = Gtk.AspectFrame(ratio=aspect_ratio, obey_child=False, label="Next Frame")
        self.next_box.set_label_align(0.5, 0.5)
        self.next_box.add(self.next_frame)

        set_margins(self.previous_frame, 3)
        set_margins(self.current_frame, 3)
        set_margins(self.next_frame, 3)

        self.set_homogeneous(True)
        self.pack_start(self.previous_box, True, True, 0)
        self.pack_start(self.current_box, True, True, 0)
        self.pack_start(self.next_box, True, True, 0)

        self.current_frame.connect("segment-selected", lambda overlay, segment: self.emit("segment_selected", segment))

    def set_frame(self, frame_id: int):
        self.frame_id = frame_id
        if frame_id > 0:
            self.previous_frame.set_frame_id(frame_id - 1)
        else:
            self.previous_frame.set_frame_id(None)
        if frame_id < len(self.segmentations) - 1:
            self.next_frame.set_frame_id(frame_id + 1)
        else:
            self.next_frame.set_frame_id(None)
        self.current_frame.set_frame_id(frame_id)

        # If a cell had been selected and exists in the new frame, keep it selected
        if self.current_cell is not None and self.current_cell.check_exists(frame_id):
            self.current_frame.emit("segment_selected", self.current_cell.get_segment(frame_id))
        else:
            self.current_cell = None
            self.current_frame.emit("segment_selected", None)

        self.show_assignment_borders()

    def set_cells(self, cells: Optional[List[Cell]]):
        self.previous_frame.set_cells(cells)
        self.current_frame.set_cells(cells)
        self.next_frame.set_cells(cells)

    @GObject.Signal(arg_types=[GObject.TYPE_PYOBJECT])
    def segment_selected(self, _segment: Optional[Segment]) -> None:
        self.current_cell = self.current_frame.get_cell()

        # Clear borders in previous and next frames
        self.previous_frame.segment_selected(None)
        self.next_frame.segment_selected(None)

        # Handle highlighting of incoming and outgoing cell assignments in prev/next frame images
        if self.current_cell is not None:
            previous_assigment = self.current_cell.get_assignment(self.frame_id - 1)
            current_assignment = self.current_cell.get_assignment(self.frame_id)
            next_assignment = self.current_cell.get_assignment(self.frame_id + 1)

            # Thicker border for selected appearances and divisions in previous frame
            if previous_assigment == AssignmentType.APPEAR or previous_assigment ==  AssignmentType.DIVIDE:
                self.previous_frame.draw_border(self.current_cell.get_segment(self.frame_id - 1), selection_border_colour, overlap_border_thickness)

            # Border for mapping from previous frame or division from previous frame
            if current_assignment == AssignmentType.MAP:
                self.previous_frame.draw_border(self.current_cell.get_segment(self.frame_id - 1), selection_border_colour)
            elif current_assignment == AssignmentType.DIVIDE:
                if self.current_cell.first_frame != self.frame_id:
                    self.previous_frame.draw_border(self.current_cell.get_segment(self.frame_id - 1), selection_border_colour)

                # Thicker border for mother+daughter division in current frame
                assignment = [ass for ass in self.current_cell.get_segment(self.frame_id).incoming_assignments if ass.mip_var.x == 1][0]
                self.current_frame.draw_border(assignment.new_segment_node_1.segment, selection_border_colour, overlap_border_thickness)
                self.current_frame.draw_border(assignment.new_segment_node_2.segment, selection_border_colour, overlap_border_thickness)

            # Thicker border for appearance in current frame
            elif current_assignment == AssignmentType.APPEAR:
                self.current_frame.draw_border(self.current_cell.get_segment(self.frame_id), selection_border_colour, overlap_border_thickness)

            # Border for mapping to next frame
            if next_assignment == AssignmentType.MAP:
                self.next_frame.draw_border(self.current_cell.get_segment(self.frame_id + 1), selection_border_colour)
            # Thicker border for divisions in next frame
            elif next_assignment == AssignmentType.DIVIDE:
                assignment = [ass for ass in self.current_cell.get_segment(self.frame_id).outgoing_assignments if ass.mip_var.x == 1][0]
                self.next_frame.draw_border(assignment.new_segment_node_1.segment, selection_border_colour, overlap_border_thickness)
                self.next_frame.draw_border(assignment.new_segment_node_2.segment, selection_border_colour, overlap_border_thickness)

        self.show_assignment_borders()

    def show_assignment_borders(self) -> None:
        """ Draw borders around cells that appeared or divided"""
        _show_assignment_borders(self.current_frame)
        _show_assignment_borders(self.previous_frame)
        _show_assignment_borders(self.next_frame)


def _show_assignment_borders(seg_image: SegmentOverlayImage) -> None:
    """ Draw borders around cells that appeared or divided"""
    if seg_image.cell_image is not None and seg_image.frame_id is not None:
        for cell in seg_image.cell_image.current_frame_cells:
            assignment: AssignmentType = cell.assignments[seg_image.frame_id - cell.first_frame].assignment_type
            if assignment == AssignmentType.APPEAR:
                seg_image.draw_border(cell.get_segment(seg_image.frame_id), appear_border_colour, border_thickness)
            elif assignment == AssignmentType.DIVIDE:
                seg_image.draw_border(cell.get_segment(seg_image.frame_id), division_border_colour, border_thickness)

