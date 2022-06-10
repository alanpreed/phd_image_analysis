import gi

from Tracking.VariableNodes import VariableNode, MappingNode, AppearanceNode, ExitNode, DivisionNode

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk, GObject


class TrackingNodeEntry(Gtk.EventBox):
    def __init__(self, node: VariableNode) -> None:
        super(TrackingNodeEntry, self).__init__()

        self.box: Gtk.Box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.box.set_homogeneous(True)
        self.node = node

        if self.node.mip_var.x == 1:
            markup = "<b>{}</b>"
        else:
            markup = "{}"

        if isinstance(node, AppearanceNode):
            self._create_label("Appear", markup)
        elif isinstance(node, ExitNode):
            self._create_label("Exit", markup)
        elif isinstance(node, MappingNode):
            self._create_label("Map {} to {}".format(node.old_segment_node.segment.seg_id,
                                                     node.new_segment_node.segment.seg_id), markup)
        elif isinstance(node, DivisionNode):
            self._create_label("Divide {} to {}, {}".format(node.old_segment_node.segment.seg_id,
                                                            node.new_segment_node_1.segment.seg_id,
                                                            node.new_segment_node_2.segment.seg_id), markup)
        else:
            print("Unknown node type: {}".format(type(node)))

        self._create_label("{:.2f}".format(node.cost), markup)
        self._create_label("{}".format(node.mip_var.x), markup)

        self.manual_select_button = Gtk.CheckButton()
        self.manual_select_button.set_halign(Gtk.Align.CENTER)
        self.box.pack_start(self.manual_select_button, True, True, 0)
        self.add(self.box)

        self.connect("button-press-event", lambda entry, event: self.manual_select_button.set_active(not self.manual_select_button.get_active()))
        self.manual_select_button.connect("toggled", lambda button: self.emit("toggle_manual_selection"))

    @GObject.Signal
    def toggle_manual_selection(self) -> None:
        pass

    def _create_label(self, text: str, markup: str) -> Gtk.Label:
        label: Gtk.Label = Gtk.Label()
        label.set_markup(markup.format(text))
        self.box.pack_start(label, True, True, 0)
        return label
