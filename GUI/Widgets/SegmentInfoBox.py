import gi
from typing import Union, List

from Segmentation.SegmentationData import Segment

gi.require_version("Gtk", "3.0")  # noqa: E402
from gi.repository import Gtk


class SegmentInfoBox(Gtk.Frame):
    """ Simple widget for displaying general information about selected segment"""
    def __init__(self) -> None:
        super(SegmentInfoBox, self).__init__(label="Segment Information")
        self.set_label_align(0.5, 0.5)
        self.grid: Gtk.Grid = Gtk.Grid()

        # Add left and right padding to prevent text hitting frame line
        self.grid.set_margin_start(5)
        self.grid.set_margin_end(5)

        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(False)
        self.segment: Union[None, Segment] = None

        self.data_labels: List[Gtk.Label] = []
        self.label_text = ["Segment ID:",
                           "Size:",
                           "Position:",
                           "Compactness:",
                           # "Chosen?:",
                           "Intensities:"]

        for i in range(len(self.label_text)):
            text_label: Gtk.Label = Gtk.Label(self.label_text[i])
            text_label.set_justify(Gtk.Justification.RIGHT)
            text_label.set_halign(Gtk.Align.END)
            self.grid.attach(text_label, 0, i, 1, 1)

            data_label: Gtk.Label = Gtk.Label("")
            data_label.set_width_chars(20)
            self.data_labels.append(data_label)
            self.grid.attach(self.data_labels[i], 1, i, 1, 1)

        self.set_segment(None)
        self.add(self.grid)

    def set_segment(self, segment: Union[None, Segment]) -> None:
        self.segment = segment
        if segment is None:
            for label in self.data_labels:
                label.set_text("")
        else:
            self.data_labels[0].set_text("{}".format(self.segment.seg_id))
            self.data_labels[1].set_text("{}".format(self.segment.size))
            self.data_labels[2].set_text("{}, {}".format(int(self.segment.centroid[1]), int(self.segment.centroid[0])))
            self.data_labels[3].set_text("{:.03f}".format(self.segment.compactness))
            # self.data_labels[4].set_text("{}".format(self.segment.manually_chosen))
            self.data_labels[4].set_text("{}".format([round(val, 1) for val in self.segment.channel_intensities]))
