import gi
from typing import Callable
from multiprocessing.connection import Connection
gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, GLib, Gdk


# Progress updates are sent through the multiprocessing pipe connection
# Tuples of the form (total, current) update the progress bar
# Strings representing errors cancel the process
class RunningDialog(Gtk.Dialog):
    def __init__(self, title: str, connection: Connection, cancel_callback: Callable[[], None]) -> None:
        super(RunningDialog, self).__init__(title=title)

        self.text: Gtk.Label = Gtk.Label("Cropping all frames")
        self.cancel_button: Gtk.Button = Gtk.Button("Cancel")
        self.progress_bar: Gtk.ProgressBar = Gtk.ProgressBar()
        self.cancel_callback = cancel_callback

        self.get_content_area().set_spacing(10)
        self.get_content_area().pack_start(self.text, True, True, 0)
        self.get_content_area().pack_start(self.progress_bar, True, True, 0)
        self.get_content_area().pack_start(self.cancel_button, True, True, 0)
        self.cancel_button.connect("clicked", self._on_cancel)
        self.connect("delete-event", self._on_close)

        self.connection = connection
        GLib.timeout_add(100, self.poll_update)

        self.set_modal(True)
        self.show_all()

    def _on_cancel(self, _) -> None:
        print("cancelled!")
        self.cancel_callback()
        self.destroy()

    def _on_close(self, _, __) -> None:
        print("closed!")
        self.cancel_callback()
        self.destroy()

    def poll_update(self) -> bool:
        try:
            if self.connection.poll():
                value = self.connection.recv()
                print(value)

                if not isinstance(value, str):
                    self.progress_bar.set_fraction(float(value[0]) / float(value[1]))

                    if value[0] == value[1]:
                        self.emit("delete-event", Gdk.Event(Gdk.EventType.DELETE))
                        return False
                else:
                    dialog = Gtk.MessageDialog(
                        transient_for=self,
                        flags=0,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text="Error!",
                    )
                    dialog.format_secondary_text("{}".format(value))
                    dialog.run()
                    dialog.destroy()
                    self._on_cancel(None)
        except EOFError:
            return False
        return True
