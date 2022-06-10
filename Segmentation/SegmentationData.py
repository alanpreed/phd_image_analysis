import numpy as np
from typing import List, Tuple, Any, Dict
import json
import dataclasses
import copy
import os


@dataclasses.dataclass
class Segment:
    seg_id: int
    frame_id: int
    mask_image: np.ndarray
    name: str
    centroid: tuple
    size: int
    compactness: float
    channel_intensities: List[float]
    conflicts: List[int]
    manually_chosen: bool = False
    incoming_assignments: List[Any] = dataclasses.field(default_factory=list)
    outgoing_assignments: List[Any] = dataclasses.field(default_factory=list)

    def to_json(self) -> Dict:
        # dataclasses.asdict doesn't work, as assignments are unpickleable and it doesn't seem to use __getstate__
        dict_class = {}
        for entry in self.__dict__:
            if entry != "mask_image" and entry != "centroid" and entry != "incoming_assignments" and entry != "outgoing_assignments":
                dict_class[entry] = copy.deepcopy(self.__dict__[entry])
        dict_class["mask_image"] = self.mask_image.tolist()
        dict_class["centroid"] = list(self.centroid)
        dict_class["incoming_assignments"] = []
        dict_class["outgoing_assignments"] = []
        return dict_class

    @classmethod
    def from_json(cls: "Segment", data: Dict) -> "Segment":
        seg: Segment = cls(**data)
        seg.mask_image = np.array(data["mask_image"]).astype(np.uint8)
        seg.centroid = tuple(seg.centroid)
        return seg

    # Clear incoming/outgoing assignment lists to allow pickling
    def __getstate__(self) -> Dict:
        state = self.__dict__.copy()
        state["incoming_assignments"] = []
        state["outgoing_assignments"] = []
        return state


@dataclasses.dataclass
class Segmentation:
    name: str
    segmentation_channel_id: int
    background_mask: np.ndarray
    background_intensities: List[float]
    segments: List[Segment]


@dataclasses.dataclass
class ProcessedFrame:
    root_directory: str
    frame_no: int
    image_names: List[str]
    frame_shape: Tuple
    segmentations: List[Segmentation]


def save_segmentation(segmentations: List[ProcessedFrame], filename: str) -> None:
    class SegmentationEncoder(json.JSONEncoder):
        def default(self, obj: Any) -> Any:
            if dataclasses.is_dataclass(obj):
                dict_class = dataclasses.asdict(obj)
                dict_class.update({"dataclass_type": type(obj).__name__})

                return dict_class

            if isinstance(obj, np.ndarray):
                return obj.tolist()

            return super().default(obj)

    with open(filename + ".json", 'w') as handle:
        datastr = json.dumps(segmentations, cls=SegmentationEncoder)
        handle.write(datastr)


def load_segmentation(filename: str) -> List[ProcessedFrame]:
    def decode_segmentation(dict_class: dict):
        if "dataclass_type" in dict_class:
            if dict_class["dataclass_type"] == "ProcessedFrame":
                del dict_class["dataclass_type"]
                output = ProcessedFrame(**dict_class)

                # Encoding doesn't handle nested dataclasses, so segmentation and segments have to be manually decoded
                segmentations = []
                for dict_segmentation in dict_class["segmentations"]:
                    segmentation = Segmentation(**dict_segmentation)
                    segmentation.background_mask = np.array(segmentation.background_mask).astype(np.uint8)

                    segments = []
                    for dict_segment in segmentation.segments:
                        segment = Segment(**dict_segment) # noqa, suppress type error as dict_segment will be dict not Segment due to json decoding
                        segment.mask_image = np.array(segment.mask_image).astype(np.uint8)
                        segments.append(segment)
                    segmentation.segments = segments

                    segmentations.append(segmentation)
                output.segmentations = segmentations
                return output

            if dict_class["dataclass_type"] == "Segmentation":
                del dict_class["dataclass_type"]
                output = Segmentation(**dict_class)

                segments = []
                for dict_segment in dict_class["segments"]:
                    segment = Segment(**dict_segment)
                    segment.mask_image = np.array(segment.mask_image).astype(np.uint8)
                    segments.append(segment)

                output.segments = segments
                return output
            else:
                print("Unknown dataclass type: {}".format(dict_class["dataclass_type"]))
        return dict_class

    with open(filename, 'r') as handle:
        loaded_segmentations: List[ProcessedFrame] = json.load(handle, object_hook=decode_segmentation)

    # File structure: <nd2_name>/<fov_no>/<region_no>/segmentation.json
    root_directory: str = os.path.split(filename)[0]
    for segmentation in loaded_segmentations:
        segmentation.root_directory = root_directory
    return loaded_segmentations
