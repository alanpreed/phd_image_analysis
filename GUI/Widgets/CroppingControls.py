import gi
from typing import List, Optional, Dict, Tuple
from dataclasses import asdict

from Preprocessing.ImageCropper import CropParameters
gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, GObject


class ParameterEntry(Gtk.Entry):
    """ Wrapper class for Entry to add min/max values, and key variables to link controls back to CropParameter class"""
    def __init__(self, cropparameter_key: str, cropparameter_subkey: Optional[int], initial_value: float, min_val: Optional[float], max_val: Optional[float]):
        super(ParameterEntry, self).__init__()
        self.cropparameter_key: str = cropparameter_key
        self.cropparameter_subkey: Optional[int] = cropparameter_subkey
        self.min_val: float = min_val
        self.max_val: float = max_val
        self.set_text(str(initial_value))

        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_max_length(12)
        self.set_width_chars(12)


class ParameterToggle(Gtk.Switch):
    """Wrapper class for Switchm adding key for linking back to CropParameter class"""
    def __init__(self, cropparameter_key: str, initial_value: bool):
        super(ParameterToggle, self).__init__()
        self.set_state(initial_value)
        self.cropparameter_key = cropparameter_key


class CroppingControls(Gtk.Grid):
    """Widget containing all editable parameters used for cropping images"""
    def __init__(self, defaults: CropParameters, limits: Dict[str, Tuple]) -> None:
        super(CroppingControls, self).__init__()

        self.crop_parameters = defaults
        self.control_labels: List[Gtk.Label] = []
        self.control_entries: List[Gtk.Entry] = []
        self.set_valign(Gtk.Align.CENTER)
        self.set_row_spacing(10)
        self.set_column_spacing(5)

        fields = asdict(self.crop_parameters)

        for i in range(len(fields)):
            key = list(fields.keys())[i]
            val = list(fields.values())[i]

            if isinstance(val, bool):
                control: ParameterToggle = ParameterToggle(key, val)
                control.connect("state-set", self._on_toggle)

            elif isinstance(val, (float, int)):
                if key in limits:
                    control = ParameterEntry(key, None, val, limits[key][0], limits[key][1])
                else:
                    control = ParameterEntry(key, None, val, None, None)
                control.connect("activate", self._on_edit)

            elif isinstance(val, tuple):
                control: Gtk.Box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

                for val_id in range(len(val)):
                    if key in limits:
                        subcontrol = ParameterEntry(key, val_id, val[val_id], limits[key][0], limits[key][1])
                    else:
                        subcontrol = ParameterEntry(key, val_id, val[val_id], None, None)
                    subcontrol.cropparameter_subkey = val_id
                    subcontrol.connect("activate", self._on_edit)
                    control.pack_start(subcontrol, False, False, 0)

            else:
                print("Warning: unhandled parameter type {} for parameter {}".format(type(val), key))
                control: Gtk.Box = Gtk.Box()

            label: Gtk.Label = Gtk.Label("{}".format(key.capitalize().replace("_", " ")))
            label.set_halign(Gtk.Align.END)
            self.control_entries.append(control)
            self.control_labels.append(label)
            self.attach(label, 0, i, 1, 1)
            self.attach(control, 1, i, 1, 1)

    @GObject.Signal(arg_types=[GObject.TYPE_PYOBJECT])
    def update_parameters(self, crop_parameters: CropParameters) -> None:
        pass

    def _on_toggle(self, switch: Gtk.Switch, state: bool):
        setattr(self.crop_parameters, switch.cropparameter_key, state)
        self.emit("update_parameters", self.crop_parameters)

    def _on_edit(self, entry: ParameterEntry) -> None:
        text = entry.get_text()

        try:
            if text == "":
                value = 0
            else:
                if (entry.min_val is None or int(text) >= entry.min_val) and (entry.max_val is None or int(text) < entry.max_val):
                    value = int(text)
                else:
                    raise ValueError

            if isinstance(getattr(self.crop_parameters, entry.cropparameter_key), tuple):
                old_tuple = getattr(self.crop_parameters, entry.cropparameter_key)
                value = (*old_tuple[:entry.cropparameter_subkey], value, *old_tuple[entry.cropparameter_subkey + 1:])

            setattr(self.crop_parameters, entry.cropparameter_key, value)

            self.emit("update_parameters", self.crop_parameters)
        except (ValueError, SyntaxError):
            print("error")
            GObject.signal_stop_emission_by_name(entry, "activate")

        if isinstance(getattr(self.crop_parameters, entry.cropparameter_key), tuple):
            entry.set_text(str(getattr(self.crop_parameters, entry.cropparameter_key)[entry.cropparameter_subkey]))
        else:
            entry.set_text(str(getattr(self.crop_parameters, entry.cropparameter_key)))
