import gi
from typing import Union

from Tracking.Cell import Cell

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk


class CellLineageBox(Gtk.Frame):
    """Scrollable list of chosen assignments for each frame selected cell exists in"""
    def __init__(self) -> None:
        super(CellLineageBox, self).__init__(label="Cell Lineage")
        self.set_label_align(0.5, 0.5)

        self.grid: Gtk.Grid = Gtk.Grid()
        # Add left and right padding to prevent text hitting frame line
        self.grid.set_margin_start(5)
        self.grid.set_margin_end(5)
        self.grid.set_column_homogeneous(True)

        self.scroll: Gtk.ScrolledWindow = Gtk.ScrolledWindow()
        self.list_grid: Gtk.Grid = Gtk.Grid()
        self.list_grid.set_column_homogeneous(True)
        self.list_grid.set_row_spacing(5)
        self.set_cell(None, 0)
        self.scroll.add_with_viewport(self.list_grid)

        self.grid.attach(Gtk.Label("Incoming"), 0, 0, 1, 1)
        self.grid.attach(Gtk.Label("Frame #"), 1, 0, 1, 1)
        self.grid.attach(Gtk.Label("Outgoing"), 2, 0, 1, 1)
        self.grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, 1, 3, 1)
        self.grid.attach(self.scroll, 0, 2, 3, 10)

        # Grid within scrolling window needs to expand when more entries are present, however the widget should not
        self.list_grid.set_vexpand(True)
        self.grid.set_vexpand(False)

        self.add(self.grid)

    def set_cell(self, cell: Union[Cell, None], frame_number: int):
        for widget in self.list_grid.get_children():
            self.list_grid.remove(widget)

        if cell is not None:
            for i in range(cell.lifespan):
                if frame_number == cell.first_frame + i:
                    incoming_text = "<b>{}</b>"
                    frame_text = "<b>{}</b>"
                    outgoing_text = "<b>{}</b>"
                else:
                    incoming_text = "{}"
                    frame_text = "{}"
                    outgoing_text = "{}"

                incoming_label = Gtk.Label(incoming_text.format(cell.assignments[i].assignment_type.name))
                frame_label = Gtk.Label(frame_text.format(cell.first_frame + i))
                outgoing_label = Gtk.Label(outgoing_text.format(cell.assignments[i + 1].assignment_type.name))
                incoming_label.set_use_markup(True)
                frame_label.set_use_markup(True)
                outgoing_label.set_use_markup(True)

                self.list_grid.attach(incoming_label, 0, i, 1, 1)
                self.list_grid.attach(frame_label, 1, i, 1, 1)
                self.list_grid.attach(outgoing_label, 2, i, 1, 1)

        for widget in self.list_grid.get_children():
            widget.show()
