# Classes for each type of variable node used in the factor graph representation of the segmentation and tracking
# problem.
from mip import Var
from Segmentation.HistogramSegmenter import Segment


class VariableNode(object):
    def __init__(self, cost: float, mip_var: Var) -> None:
        self.mip_var: Var = mip_var
        self.cost: float = cost
        self.force_inclusion: bool = False


class SegmentNode(VariableNode):
    def __init__(self, segment: Segment, cost: float, mip_var: Var) -> None:
        self.segment: Segment = segment
        super(SegmentNode, self).__init__(cost, mip_var)


class AppearanceNode(VariableNode):
    def __init__(self, segment_node: SegmentNode, cost: float, mip_var: Var) -> None:
        self.segment_node: SegmentNode = segment_node
        super(AppearanceNode, self).__init__(cost, mip_var)


class MappingNode(VariableNode):
    def __init__(self, old_segment_node: SegmentNode, new_segment_node: SegmentNode,
                 cost: float, mip_var: Var) -> None:
        self.old_segment_node: SegmentNode = old_segment_node
        self.new_segment_node: SegmentNode = new_segment_node
        super(MappingNode, self).__init__(cost, mip_var)


class ExitNode(VariableNode):
    def __init__(self, segment_node: SegmentNode, cost: float, mip_var: Var):
        self.segment_node: SegmentNode = segment_node
        super(ExitNode, self).__init__(cost, mip_var)


class DivisionNode(VariableNode):
    def __init__(self, old_segment_node: SegmentNode, new_segment_node_1: SegmentNode, new_segment_node_2: SegmentNode,
                 cost: float, mip_var: Var) -> None:
        self.old_segment_node: SegmentNode = old_segment_node
        self.new_segment_node_1: SegmentNode = new_segment_node_1
        self.new_segment_node_2: SegmentNode = new_segment_node_2
        super(DivisionNode, self).__init__(cost, mip_var)
