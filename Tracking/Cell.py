from enum import Enum, unique, auto
from typing import List, Optional, Dict
import copy
from Segmentation.SegmentationData import Segment
import dataclasses


@unique
class AssignmentType(Enum):
    APPEAR = auto()
    MAP = auto()
    DIVIDE = auto()
    EXIT = auto()


@dataclasses.dataclass
class SegmentAssignment:
    assignment_type: AssignmentType
    cost: float

    def to_json(self) -> Dict:
        dict_class = dataclasses.asdict(self)
        dict_class["assignment_type"] = self.assignment_type.name
        return dict_class

    @classmethod
    def from_json(cls: "SegmentAssignment", data: Dict):
        assignment: SegmentAssignment = cls(**data)
        assignment.assignment_type = AssignmentType.__members__[data["assignment_type"]]
        return assignment


@dataclasses.dataclass
class Cell(object):
    cell_id: int
    parent_id: Optional[int]
    assignments: List[SegmentAssignment] = dataclasses.field(default_factory=list)
    segments: List[Segment] = dataclasses.field(default_factory=list)
    first_frame: int = 0
    lifespan: int = 0

    def to_json(self) -> Dict:
        dict_class = {}
        for entry in self.__dict__:
            if entry != "segments" and entry != "assignments":
                dict_class[entry] = copy.deepcopy(self.__dict__[entry])

        dict_class["segments"] = [seg.to_json() for seg in self.segments]
        dict_class["assignments"] = [assignment.to_json() for assignment in self.assignments]
        return dict_class

    @classmethod
    def from_json(cls: "Cell", data: Dict) -> "Cell":
        cell: Cell = cls(**data)
        cell.segments = [Segment.from_json(seg) for seg in data["segments"]]
        cell.assignments = [SegmentAssignment.from_json(assignment) for assignment in data["assignments"]]
        return cell

    def __str__(self) -> str:
        lineage = ""
        for node in self.assignments:
            if node.assignment_type == AssignmentType.APPEAR:
                lineage += "Appearance -> "
            elif node.assignment_type == AssignmentType.MAP:
                lineage += "Mapping -> "
            elif node.assignment_type == AssignmentType.DIVIDE:
                lineage += "Division -> "
            elif node.assignment_type == AssignmentType.EXIT:
                lineage += "Exit"
            else:
                lineage += "Unknown -> "
        return "Cell ID {}, parent ID {}, lineage: \r\n {}".format(self.cell_id, self.parent_id, lineage)

    def get_segment(self, frame_id: int) -> Optional[Segment]:
        if self.check_exists(frame_id):
            return self.segments[frame_id - self.first_frame]
        else:
            return None

    def get_assignment(self, frame_id: int) -> Optional[AssignmentType]:
        if self.check_exists(frame_id):
            return self.assignments[frame_id - self.first_frame].assignment_type
        else:
            return None

    def check_exists(self, frame_id: int) -> bool:
        return self.first_frame <= frame_id < self.first_frame + self.lifespan
