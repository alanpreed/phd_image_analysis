import gi
from typing import Union

from Tracking.Cell import Cell, AssignmentType

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk


class CellInfoBox(Gtk.Frame):
    """Simple widget for displaying general information about selected cell"""
    def __init__(self) -> None:
        super(CellInfoBox, self).__init__(label="Cell Information")
        self.set_label_align(0.5, 0.5)
        self.grid: Gtk.Grid = Gtk.Grid()
        # Add left and right padding to prevent text hitting frame line
        self.grid.set_margin_start(5)
        self.grid.set_margin_end(5)
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_spacing(5)
        self.cell: Union[None, Cell] = None

        self.id_label: Gtk.Label = Gtk.Label("")
        self.parent_label: Gtk.Label = Gtk.Label("")
        self.lifespan_label: Gtk.Label = Gtk.Label("")
        self.division_label: Gtk.Label = Gtk.Label("")

        self.grid.attach(Gtk.Label("Cell ID:"), 0, 0, 1, 1)
        self.grid.attach(self.id_label, 1, 0, 1, 1)
        self.grid.attach(Gtk.Label("Parent ID:"), 0, 1, 1, 1)
        self.grid.attach(self.parent_label, 1, 1, 1, 1)
        self.grid.attach(Gtk.Label("Lifespan:"), 0, 2, 1, 1)
        self.grid.attach(self.lifespan_label, 1, 2, 1, 1)
        self.grid.attach(Gtk.Label("Divisions:"), 0, 3, 1, 1)
        self.grid.attach(self.division_label, 1, 3, 1, 1)

        self.add(self.grid)

        self.set_cell(None)

    def set_cell(self, cell: Union[None, Cell]) -> None:

        if cell is None:
            self.id_label.set_text("")
            self.parent_label.set_text("")
            self.lifespan_label.set_text("")
            self.division_label.set_text("")
        else:
            self.id_label.set_text("{}".format(cell.cell_id))
            self.parent_label.set_text("{}".format(cell.parent_id))
            self.lifespan_label.set_text("{}".format(cell.lifespan))

            div_count = 0
            for i in range(1, len(cell.assignments)):
                if cell.assignments[i].assignment_type == AssignmentType.DIVIDE:
                    div_count += 1

            self.division_label.set_text("{}".format(div_count))
