from itertools import combinations
from mip import Model, BINARY, minimize, xsum, OptimizationStatus, CBC, Constr
from typing import List, Optional, Union
from enum import Enum, auto

from Tracking.Cell import Cell, AssignmentType, SegmentAssignment
from Tracking.NodeCosts import CostParameters, CostCalculator
from Segmentation.SegmentationData import Segment, ProcessedFrame
from Tracking.TrackingSolution import TrackingSolution
from Tracking.VariableNodes import VariableNode, SegmentNode, MappingNode, AppearanceNode, ExitNode, DivisionNode

# The FactorGraphSolver class contains methods for the creation and solving of a factor graph representation of the
# joint segmentation and tracking problem, using MIP.

# Input variables:
#       - segmentations: a ProcessedFrame object for each frame, each containing one or more segmentations with
#         a collection of possible segments
#       - cost_parameters: parameters for tuning the costs associated with selecting nodes in the final solution

# The factor graph contains a variable node for each putative segment within each frame. It also contains variable nodes
# for every possible assignment of each segment between frames. There are four possible assignments:
#       - Appearance, the segment is new in this frame
#       - Exit, this is the segment's final frame
#       - Mapping, linking two segments between frames
#       - Division, linking one segment to two in the next frame
# Two constraints are implemented for the solving of the graph:
#       - Continuity, each chosen segment must have exactly one incoming and one outgoing assignment
#       - Segmentation tree conflict, each path from leaf to node in a segmentation tree must have at most one segment
#           chosen (i.e. chosen segments cannot overlap)
# The MIP solver optimises for the minimum cost of included variable nodes, where the cost of including a node is
# a measure of how improbable a given node is


class SolverStatus(Enum):
    INITIALISED = auto()
    RUNNING = auto()
    SOLVED_OPTIMAL = auto()
    SOLVED_FEASIBLE = auto()
    UNSOLVABLE = auto()
    ERROR = auto()


class FactorGraphSolver(object):
    def __init__(self, segmentations: List[ProcessedFrame], cost_parameters: CostParameters, include_all_segments: bool) -> None:
        self.segmentations: List[ProcessedFrame] = segmentations
        self.include_all_segments = include_all_segments
        self.factor_model: Model = Model('SegTrack', solver_name=CBC)
        self.factor_model.verbose = 0
        self.cost_calculator: CostCalculator = CostCalculator(cost_parameters)

        # Make sure that assignment lists are empty
        for frame_segmentation in self.segmentations:
            for segmentation in frame_segmentation.segmentations:
                for segment in segmentation.segments:
                    segment.incoming_assignments = []
                    segment.outgoing_assignments = []

        # Lists storing all types of variable node for MIP factor graph
        self.node_segments: List[SegmentNode] = []
        self.node_mappings: List[MappingNode] = []
        self.node_divisions: List[DivisionNode] = []
        self.node_appearances: List[AppearanceNode] = []
        self.node_exits: List[ExitNode] = []

    def edit_constraint(self, node: VariableNode, force_assignment: bool):
        if force_assignment:
            self.factor_model += node.mip_var == 1, "manual_{}".format(node.mip_var.name)
        else:
            constraint: Optional[Constr] = self.factor_model.constr_by_name("manual_{}".format(node.mip_var.name))
            self.factor_model.remove(constraint)

    def create_graph(self) -> None:
        num_frames = len(self.segmentations)
        previous_segment_nodes: List[SegmentNode] = []

        # Create all variable nodes
        print("Creating frame nodes")
        for frame_id in range(num_frames):
            new_segments: List[Segment] = []
            for segmentation in self.segmentations[frame_id].segmentations:
                new_segments += segmentation.segments

            # Keep track of all segments in the current frame, for use when the next frame is considered
            new_segment_nodes: List[SegmentNode] = []

            # Every segment has a segment node, plus appearance and exit assignment nodes
            for segment in new_segments:
                segment_node = SegmentNode(segment,
                                           self.cost_calculator.calculate_segment_cost(segment),
                                           self.factor_model.add_var(var_type=BINARY,
                                                                     name='segment_{}_{}'.format(segment.name, segment.seg_id)))

                appearance_node = AppearanceNode(segment_node,
                                                 self.cost_calculator.calculate_appearance_cost(segment),
                                                 self.factor_model.add_var(var_type=BINARY,
                                                                           name='appear_{}_{}'.format(segment.name, segment.seg_id)))

                exit_node = ExitNode(segment_node,
                                     self.cost_calculator.calculate_exit_cost(segment),
                                     self.factor_model.add_var(var_type=BINARY,
                                                               name='exit_{}_{}'.format(segment.name, segment.seg_id)))

                # Keep lists of assignment nodes for each segment, for continuity constraint generation later
                segment.incoming_assignments.append(appearance_node)
                segment.outgoing_assignments.append(exit_node)

                # # Save MIP references in the segmentation tree for tree constraint generation later
                # segment.factor_graph_node = segment_node

                self.node_appearances.append(appearance_node)
                self.node_exits.append(exit_node)
                self.node_segments.append(segment_node)
                new_segment_nodes.append(segment_node)

            # From the second frame onwards division and mapping can also be considered
            if frame_id > 0:
                # Create variable nodes for every possible mapping between previous frame and this one
                for prev_segment_node in previous_segment_nodes:
                    for new_segment_node in new_segment_nodes:
                        mapping_cost = self.cost_calculator.calculate_mapping_cost(prev_segment_node.segment,
                                                                                   new_segment_node.segment)
                        mapping_name: str = 'map_{}_{}_to_{}_{}'.format(prev_segment_node.segment.name,
                                                                        prev_segment_node.segment.seg_id,
                                                                        new_segment_node.segment.name,
                                                                        new_segment_node.segment.seg_id)
                        # Temporarily disabled mapping cost limiting
                        # if mapping_cost < self.cost_calculator.cost_parameters.max_cost:
                        mapping_node = MappingNode(prev_segment_node,
                                                   new_segment_node,
                                                   mapping_cost,
                                                   self.factor_model.add_var(var_type=BINARY, name=mapping_name))

                        prev_segment_node.segment.outgoing_assignments.append(mapping_node)
                        new_segment_node.segment.incoming_assignments.append(mapping_node)
                        self.node_mappings.append(mapping_node)

                # Create nodes for every possible combination of two new segs, for each seg in the previous frame
                # Do not create division nodes for traps
                # Itertools used to generate combinations for us
                for prev_segment_node in previous_segment_nodes:
                    if not prev_segment_node.segment.manually_chosen:
                        for seg_node_pair in combinations(new_segment_nodes, 2):
                            if not seg_node_pair[0].segment.manually_chosen and not seg_node_pair[1].segment.manually_chosen:
                                division_cost = self.cost_calculator.calculate_division_cost(prev_segment_node.segment,
                                                                                             seg_node_pair[0].segment,
                                                                                             seg_node_pair[1].segment)

                                division_name: str = 'divide_{}_{}_to_{}_{}_and_{}_{}'.format(prev_segment_node.segment.name, prev_segment_node.segment.seg_id,
                                                                                              seg_node_pair[0].segment.name, seg_node_pair[0].segment.seg_id,
                                                                                              seg_node_pair[1].segment.name, seg_node_pair[0].segment.seg_id)

                                if division_cost < self.cost_calculator.cost_parameters.max_cost:
                                    division_node = DivisionNode(prev_segment_node,
                                                                 seg_node_pair[0],
                                                                 seg_node_pair[1],
                                                                 division_cost,
                                                                 self.factor_model.add_var(var_type=BINARY,
                                                                                           name=division_name))

                                    prev_segment_node.segment.outgoing_assignments.append(division_node)
                                    seg_node_pair[0].segment.incoming_assignments.append(division_node)
                                    seg_node_pair[1].segment.incoming_assignments.append(division_node)
                                    self.node_divisions.append(division_node)

            previous_segment_nodes = new_segment_nodes

            # Add conflict constraints for each segment
            for seg_id in range(len(new_segments)):
                conflict_nodes = [new_segment_nodes[i] for i in new_segments[seg_id].conflicts]

                # Have to check length, otherwise bugged constraints are added even when no conflicts are present
                if len(conflict_nodes) > 0:
                    self.factor_model += xsum(new_segment_node.mip_var for new_segment_node in conflict_nodes) <= 1

        # Add continuity constraints for every segment
        for node in self.node_segments:
            # Must be exactly one incoming and outgoing assignment if a segment is chosen
            self.factor_model += xsum(incoming_node.mip_var
                                      for incoming_node in node.segment.incoming_assignments) == node.mip_var
            self.factor_model += xsum(outgoing_node.mip_var
                                      for outgoing_node in node.segment.outgoing_assignments) == node.mip_var

        # Do not allow segments to divide in consecutive frames
        for node in self.node_segments:
            incoming_divisions = [incoming for incoming in node.segment.incoming_assignments if isinstance(incoming, DivisionNode)]
            outgoing_divisions = [outgoing for outgoing in node.segment.outgoing_assignments if isinstance(outgoing, DivisionNode)]

            self.factor_model += xsum(div_node.mip_var for div_node in incoming_divisions + outgoing_divisions) <= 1

        if self.include_all_segments:
            for node in self.node_segments:
                self.factor_model += node.mip_var == 1

        print("Frame nodes created.")

        # Calculate total cost function and set as model objective
        self.factor_model.objective = minimize(xsum(node.mip_var * node.cost for node in (self.node_segments +
                                                                                          self.node_mappings +
                                                                                          self.node_divisions +
                                                                                          self.node_appearances +
                                                                                          self.node_exits)))

    def solve_graph(self, max_run_time=300, print_solution=False) -> SolverStatus:
        print('Model has {} vars, {} constraints and {} nzs'.format(self.factor_model.num_cols,
                                                                    self.factor_model.num_rows,
                                                                    self.factor_model.num_nz))
        self.factor_model.threads = -1
        status = self.factor_model.optimize(max_seconds=max_run_time)

        if status == OptimizationStatus.OPTIMAL:
            print('Optimal solution with cost {} found'.format(self.factor_model.objective_value))
            return SolverStatus.SOLVED_OPTIMAL
        elif status == OptimizationStatus.FEASIBLE:
            print('sol.cost {} found, best possible: {}'.format(self.factor_model.objective_value,
                                                                self.factor_model.objective_bound))
            return SolverStatus.SOLVED_FEASBILE
        elif status == OptimizationStatus.NO_SOLUTION_FOUND or status == OptimizationStatus.INFEASIBLE:
            print('No feasible solution found, lower bound is: {}'.format(self.factor_model.objective_bound))
            return SolverStatus.UNSOLVABLE

        # if status == OptimizationStatus.OPTIMAL or status == OptimizationStatus.FEASIBLE:
        #     if print_solution:
        #         print('Solution:')
        #         for v in self.factor_model.vars:
        #             if abs(v.x) > 1e-6:  # only printing non-zeros
        #                 print('{} : {}'.format(v.name, v.x))

        else:
            return SolverStatus.ERROR

    def generate_solution(self) -> TrackingSolution:
        # Node classes cannot be pickled due to MIP C data types. This is a temporary class to allow cell lineage to be
        # calculated from the selected factor graph nodes, before the useful data is extracted into a final Cell class
        class _Cell(object):
            def __init__(self, cell_id: int, parent_id: Optional[int], first_node: Union[AppearanceNode, DivisionNode]):
                self.cell_id: int = cell_id
                self.parent_id: int = parent_id
                self.nodes: List[VariableNode] = [first_node]
                self.segments: List[Segment] = []

        cell_data: List[_Cell] = []
        cell_count: int = 0
        chosen_appearances = [node for node in self.node_appearances if node.mip_var.x == 1]

        for appearance in chosen_appearances:
            cell_data.append(_Cell(cell_count, None, appearance))
            cell_count += 1

        # Compile lists of segments and assignment nodes to generate lineage for each cell
        for cell in cell_data:
            while not isinstance(cell.nodes[-1], ExitNode):
                current_node = cell.nodes[-1]

                if isinstance(current_node, AppearanceNode):
                    segment_node = current_node.segment_node

                elif isinstance(current_node, MappingNode):
                    segment_node = current_node.new_segment_node

                elif isinstance(current_node, DivisionNode):
                    daughter_1 = current_node.new_segment_node_1
                    daughter_2 = current_node.new_segment_node_2

                    # If this cell was spawned by a division, track lineage using the smaller cell
                    if len(cell.nodes) == 1:
                        if daughter_1.segment.size < daughter_2.segment.size:
                            segment_node = daughter_1
                        else:
                            segment_node = daughter_2
                    else:
                        # Otherwise, track lineage using larger cell and add smaller as a new cell
                        if daughter_1.segment.size > daughter_2.segment.size:
                            segment_node = daughter_1
                        else:
                            segment_node = daughter_2
                        cell_data.append(_Cell(cell_count, cell.cell_id, current_node))
                        cell_count += 1
                else:
                    segment_node = []
                    print("Unknown node type: {}".format(type(current_node)))

                new_node = [node for node in segment_node.segment.outgoing_assignments if node.mip_var.x == 1]

                if len(new_node) == 1:
                    cell.nodes += new_node
                    cell.segments.append(segment_node.segment)
                else:
                    print("Error! segment does not have exactly one outgoing assignment selected.")

        final_cells: List[Cell] = []

        for cell in cell_data:
            new_cell = Cell(cell.cell_id, cell.parent_id)
            new_cell.segments = cell.segments
            new_cell.first_frame = cell.segments[0].frame_id
            new_cell.lifespan = len(cell.segments)

            for node in cell.nodes:
                if isinstance(node, AppearanceNode):
                    node_type = AssignmentType.APPEAR
                elif isinstance(node, MappingNode):
                    node_type = AssignmentType.MAP
                elif isinstance(node, DivisionNode):
                    node_type = AssignmentType.DIVIDE
                elif isinstance(node, ExitNode):
                    node_type = AssignmentType.EXIT
                else:
                    node_type = AssignmentType.EXIT
                    print("Error! Unknown node type")
                new_cell.assignments.append(SegmentAssignment(node_type, node.cost))

            final_cells.append(new_cell)

        solution: TrackingSolution = TrackingSolution(total_frames=len(self.segmentations),
                                                      root_directory=self.segmentations[0].root_directory,
                                                      image_filenames=[frame.image_names for frame in self.segmentations],
                                                      cells=final_cells)
        return solution
