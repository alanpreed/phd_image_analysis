import gi
from typing import Optional, List

from GUI.Widgets.TrackingNodeEntry import TrackingNodeEntry
from Tracking.VariableNodes import VariableNode

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, GObject


class TrackingNodeList(Gtk.Frame):
    """Scrollable list of assignment nodes available for selected segment"""
    def __init__(self, title="Assignment Nodes") -> None:
        super(TrackingNodeList, self).__init__(label=title)
        self.set_label_align(0.5, 0.5)
        self.grid: Gtk.Grid = Gtk.Grid()
        # Add left and right padding to prevent text hitting frame line
        self.grid.set_margin_start(5)
        self.grid.set_margin_end(5)

        self.grid.set_column_homogeneous(True)

        self.scroll: Gtk.ScrolledWindow = Gtk.ScrolledWindow()
        self.grid.attach(Gtk.Label("Type"), 0, 0, 1, 1)
        self.grid.attach(Gtk.Label("Cost"), 1, 0, 1, 1)
        self.grid.attach(Gtk.Label("X"), 2, 0, 1, 1)
        self.grid.attach(Gtk.Label("Force"), 3, 0, 1, 1)
        self.grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, 1, 4, 1)
        self.grid.attach(self.scroll, 0, 2, 4, 10)
        self.add(self.grid)

        self.list_grid: Gtk.Grid = Gtk.Grid()
        self.list_grid.set_column_homogeneous(True)
        self.list_grid.set_row_spacing(0)
        self.scroll.add_with_viewport(self.list_grid)

        # Grid within scrolling window needs to expand when more entries are present, however the widget should not
        self.list_grid.set_vexpand(True)
        self.grid.set_vexpand(False)

        self.update_list(None)

    def update_list(self, assignment_nodes: Optional[List[VariableNode]]):
        for widget in self.list_grid.get_children():
            self.list_grid.remove(widget)

        if assignment_nodes is not None:
            sorted_assignments: List[VariableNode] = sorted(assignment_nodes, key=lambda node: node.cost)

            assignment_selected: bool = False
            for assignment in sorted_assignments:
                if assignment.force_inclusion:
                    assignment_selected: bool = True
                    break

            for i in range(len(sorted_assignments)):
                entry: TrackingNodeEntry = TrackingNodeEntry(sorted_assignments[i])
                self.list_grid.attach(entry, 0, i, 1, 1)

                if assignment_selected:
                    if sorted_assignments[i].force_inclusion:
                        entry.manual_select_button.set_active(True)
                    else:
                        entry.set_sensitive(False)

                # Make sure to connect signals after set_active is called, otherwise callback will fire during setup
                entry.connect("toggle_manual_selection", self._on_entry_button_toggle)

        self.list_grid.show()
        self.list_grid.show_all()

    def _on_entry_button_toggle(self, entry: TrackingNodeEntry) -> None:
        # Deactivate all other checkboxes if one is chosen - only one assignment allowed
        result = entry.manual_select_button.get_active()
        for widget in self.list_grid.get_children():
            if id(widget) != id(entry):
                widget.set_sensitive(not result)

        self.emit("manual_constraint_toggled", entry.node, result)

    @GObject.Signal(arg_types=[GObject.TYPE_PYOBJECT, GObject.TYPE_BOOLEAN])
    def manual_constraint_toggled(self, node: VariableNode, force_constraint: bool) -> None:
        node.force_inclusion = force_constraint
