import dataclasses
from typing import List, Dict
import json
import copy
import os

from Tracking.Cell import Cell


@dataclasses.dataclass
class TrackingSolution:
    total_frames: int
    root_directory: str
    image_filenames: List[List[str]]
    cells: List[Cell]

    def to_json(self) -> Dict:
        dict_class = {}
        for entry in self.__dict__:
            if entry != "cells":
                dict_class[entry] = copy.deepcopy(self.__dict__[entry])

        dict_class["cells"] = [cell.to_json() for cell in self.cells]
        return dict_class

    @classmethod
    def from_json(cls: "TrackingSolution", data: Dict) -> "TrackingSolution":
        solution: TrackingSolution = cls(**data)
        solution.cells = [Cell.from_json(cell) for cell in data["cells"]]
        return solution


def save_tracking_solution(solution: TrackingSolution, filename: str) -> None:
    with open(filename + ".json", 'w') as handle:
        solution_json: dict = solution.to_json()
        handle.write(json.dumps(solution_json))


def load_tracking_solution(filename: str) -> TrackingSolution:
    with open(filename, 'r') as handle:
        solution_json: dict = json.load(handle)

        
    solution = TrackingSolution.from_json(solution_json)
    
    root_directory: str = os.path.split(filename)[0]
    solution.root_directory = root_directory

    return solution
