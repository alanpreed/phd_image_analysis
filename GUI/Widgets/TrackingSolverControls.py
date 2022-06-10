import gi

from Tracking.FactorGraphSolver import SolverStatus

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, GObject


class TrackingSolverControls(Gtk.Frame):
    """Collection of buttons and status indicator for controlling factor graph tracking solver"""
    def __init__(self) -> None:
        super(TrackingSolverControls, self).__init__(label="Solver Control")
        self.set_label_align(0.5, 0.5)

        self.status_header: Gtk.Label = Gtk.Label(label="Status: ")
        self.status_info: Gtk.Label = Gtk.Label(label=" ")
        self.run_button: Gtk.Button = Gtk.Button(label="Run solver")
        self.reset_button: Gtk.Button = Gtk.Button(label="Reset solver")
        self.save_button: Gtk.Button = Gtk.Button(label="Save tracking results")

        self.run_button.set_halign(Gtk.Align.CENTER)
        self.run_button.set_valign(Gtk.Align.CENTER)
        self.reset_button.set_halign(Gtk.Align.CENTER)
        self.reset_button.set_valign(Gtk.Align.CENTER)
        self.save_button.set_halign(Gtk.Align.CENTER)
        self.save_button.set_valign(Gtk.Align.CENTER)

        self.grid: Gtk.Grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
        self.grid.set_margin_start(5)
        self.grid.set_margin_end(5)
        # self.grid.set_column_homogeneous(True)
        self.grid.set_row_homogeneous(True)
        self.grid.set_halign(Gtk.Align.CENTER)
        self.grid.attach(self.status_header, 0, 0, 1, 1)
        self.grid.attach(self.status_info, 1, 0, 1, 1)
        self.grid.attach(self.run_button, 0, 1, 2, 1)
        self.grid.attach(self.reset_button, 0, 2, 2, 1)
        self.grid.attach(self.save_button, 0, 3, 2, 1)
        self.add(self.grid)

        self.run_button.connect("clicked", lambda button: self.emit("run_solver"))
        self.reset_button.connect("clicked", lambda button: self.emit("reset_solver"))
        self.save_button.connect("clicked", lambda button: self.emit("save_solution"))

    def set_status(self, status: SolverStatus) -> None:
        if status == SolverStatus.INITIALISED:
            self.status_info.set_text("Initialised")
            self.save_button.set_sensitive(False)
        elif status == SolverStatus.RUNNING:
            self.status_info.set_text("Running")
        elif status == SolverStatus.SOLVED_OPTIMAL:
            self.status_info.set_text("Optimal solve")
            self.save_button.set_sensitive(True)
        elif status == SolverStatus.SOLVED_FEASIBLE:
            self.status_info.set_text("Feasible solve")
            self.save_button.set_sensitive(True)
        elif status == SolverStatus.UNSOLVABLE:
            self.status_info.set_text("Unsolvable")
            self.save_button.set_sensitive(False)
        else:
            print("Unknown solver status")
            self.status_info.set_text("Error")

    @GObject.Signal
    def run_solver(self) -> None:
        pass

    @GObject.Signal
    def reset_solver(self) -> None:
        pass

    @GObject.Signal
    def save_solution(self) -> None:
        pass
