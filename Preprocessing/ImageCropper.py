from dataclasses import dataclass
from typing import Tuple, List, Optional
from multiprocessing.connection import Connection
import numpy as np
import cv2
import os
from Preprocessing.ND2Frames import ND2Frames
from Segmentation.Utilities import find_holes, fill_holes, find_background, increase_contrast, rotate_image


@dataclass
class CropParameters:
    angle: int
    row_count: int
    row_spacing: int
    row_offset: int
    column_count: Tuple
    column_spacing: int
    column_offset: Tuple
    correct_drift: bool
    trap_detection_channel: int
    trap_detection_z_position: int
    min_trap_size: int
    max_trap_size: int
    alternate_trap_detection: bool


@dataclass()
class CropRegion(object):
    x: int
    y: int
    width: int
    height: int
    ignored: bool = False

    def __str__(self) -> str:
        return "X: {} Y: {} W: {} H: {}".format(self.x, self.y, self.width, self.height)

    def contains_point(self, point: Tuple[int, int]) -> bool:
        if self.x < point[1] < self.x + self.width and self.y < point[0] < self.y + self.height:
            return True
        return False


class ImageCropper(object):
    def __init__(self, frames: ND2Frames, parameters: CropParameters) -> None:
        self.frames: ND2Frames = frames
        self.parameters: CropParameters = parameters
        self.current_offset: Tuple[float, float] = (0, 0)

        self.prev_frame_traps: Optional[List[Tuple[float, float]]] = None
        self.crop_regions: List[CropRegion] = self._calculate_crop_regions()

    def reset_offset(self) -> None:
        self.current_offset = (0, 0)
        self.prev_frame_traps = None
        for region in self.crop_regions:
            region.ignored = False

    def update_parameters(self, parameters: CropParameters):
        self.reset_offset()
        self.parameters = parameters
        self.crop_regions = self._calculate_crop_regions()

    # Toggle region located at point to be ignored during crop process
    def flag_region(self, point: Tuple[int, int]) -> None:
        for region in self.crop_regions:
            if region.contains_point(point):
                region.ignored = not region.ignored
                break

    # Calculates grid locations and overlays them on image
    def generate_preview(self, frame_id: int, fov_id: int, channel_id: int, zstack_id: int) -> np.ndarray:
        # Generate colour image for grid display
        frame = self.frames[self.frames.calculate_position(frame_id, fov_id, channel_id, zstack_id)]
        scaled_frame = (frame / 256).astype(np.uint8)
        output: np.ndarray = np.stack((scaled_frame, scaled_frame, scaled_frame), axis=2)

        if self.parameters.angle != 0:
            output = rotate_image(output, self.parameters.angle)
        output = increase_contrast(output)

        # Calculate offset from previous frame
        if self.parameters.correct_drift:
            new_frame = self.frames[self.frames.calculate_position(frame_id, fov_id, self.parameters.trap_detection_channel, self.parameters.trap_detection_z_position)]
            new_traps: List[Tuple[float, float]] = self._find_trap_locations(new_frame)

            if self.prev_frame_traps is not None:
                offset: Tuple[float, float] = self._calculate_xy_offset(new_traps, self.prev_frame_traps)
                print("New offset: {}".format(offset))
                self.current_offset = (self.current_offset[0] + offset[0], self.current_offset[1] + offset[1])
                print("Cumulative offset: {}".format(self.current_offset))
            self.prev_frame_traps = new_traps
        else:
            self.current_offset = (0, 0)

        # Adjust region locations by offset
        for rect in self.crop_regions:
            x = rect.x - round(self.current_offset[0])
            y = rect.y - round(self.current_offset[1])
            output = cv2.line(output, (x, y), (x + rect.width, y), (255, 0, 0), 5)
            output = cv2.line(output, (x, y), (x, y + rect.height), (255, 0, 0), 5)
            output = cv2.line(output, (x + rect.width, y), (x + rect.width, y + rect.height), (255, 0, 0), 5)
            output = cv2.line(output, (x, y + rect.height), (x + rect.width, y + rect.height), (255, 0, 0), 5)

            if rect.ignored:
                output = cv2.line(output, (x, y), (x + rect.width, y + rect.height), (255, 0, 0), 5)
                output = cv2.line(output, (x + rect.width, y), (x, y + rect.height), (255, 0, 0), 5)
        return output

    # Crop images at all timepoints, all channels and all z positions for a given FOV
    def crop_all(self, fov_id: int, output_path: str, progress_callback: Connection) -> None:
        total_images: int = self.frames.num_frames * self.frames.num_channels * self.frames.num_zstack
        images_completed: int = 0

        input_name = os.path.basename(self.frames.filename).split(".")[0]
        output_path += "/" + input_name + "/fov_{}".format(fov_id)

        cumulative_offset: Tuple[float, float] = (0, 0)

        for frame_id in range(self.frames.num_frames):
            if frame_id > 0 and self.parameters.correct_drift:
                prev_frame = self.frames[self.frames.calculate_position(frame_id - 1, fov_id, self.parameters.trap_detection_channel, self.parameters.trap_detection_z_position)]
                frame = self.frames[self.frames.calculate_position(frame_id, fov_id, self.parameters.trap_detection_channel, self.parameters.trap_detection_z_position)]

                traps_1: List[Tuple[float, float]] = self._find_trap_locations(prev_frame)
                traps_2: List[Tuple[float, float]] = self._find_trap_locations(frame)
                offset: Tuple[float, float] = self._calculate_xy_offset(traps_2, traps_1)
                cumulative_offset = (cumulative_offset[0] + offset[0], cumulative_offset[1] + offset[1])

            for zstack_id in range(self.frames.num_zstack):
                for channel_id in range(self.frames.num_channels):
                    frame = self.frames[self.frames.calculate_position(frame_id, fov_id, channel_id, zstack_id)]

                    if self.parameters.angle != 0:
                        rotated = rotate_image(frame, self.parameters.angle)
                    else:
                        rotated = frame

                    for region_id in range(len(self.crop_regions)):
                        region = self.crop_regions[region_id]

                        if not region.ignored:
                            full_output_path: str = output_path + "/region_{}/".format(region_id)

                            try:
                                os.makedirs(full_output_path, exist_ok=True)
                            except OSError:
                                progress_callback.send("Can't create output folder: {}".format(full_output_path))
                                return

                            filename: str = full_output_path + "frame_{}_z_{}_channel_{}.tif".format(frame_id, zstack_id, channel_id)
                            if not os.path.isfile(filename):
                                x = region.x - round(cumulative_offset[0])
                                y = region.y - round(cumulative_offset[1])
                                output = rotated[y: y + region.height, x:x + region.width]
                                result = cv2.imwrite(filename, output)

                                if not result:
                                    progress_callback.send("Error saving image: {}".format(filename))
                                    return
                            else:
                                progress_callback.send("Can't save image: {} already exists".format(filename))
                                return

                    images_completed += 1
                    progress_callback.send((images_completed, total_images))

    def _calculate_crop_regions(self) -> List[CropRegion]:
        img_width = self.frames.sizes['x']
        img_height = self.frames.sizes['y']
        regions = []

        for i in range(self.parameters.row_count):
            for j in range(self.parameters.column_count[i % len(self.parameters.column_count)]):
                x = self.parameters.column_offset[i % len(self.parameters.column_count)] + self.parameters.column_spacing * j
                y = self.parameters.row_offset + self.parameters.row_spacing * i

                # Cap region to within image borders
                capped_x = max(0, min(x, img_width))
                capped_y = max(0, min(y, img_height))

                if capped_x < img_width and capped_y < img_height:
                    # Smallest out of normal size, size when offset negatively, size when offset positively
                    width = min(self.parameters.column_spacing,
                                self.parameters.column_spacing - abs(x - capped_x),
                                img_width - capped_x)
                    height = min(self.parameters.row_spacing,
                                 self.parameters.row_spacing - abs(y - capped_y),
                                 img_height - capped_y)

                    new_region = CropRegion(capped_x, capped_y, width, height)
                    regions.append(new_region)
        return regions

    def _calculate_xy_offset(self, image_1_trap_centroids: List[Tuple[float, float]], image_2_trap_centroids: List[Tuple[float, float]]) -> Tuple[float, float]:
        @dataclass
        class TrapMapping:
            id_1: int
            id_2: int
            distance: float

            def __lt__(self, other) -> bool:
                return self.distance < other.distance
        trap_mappings: List[TrapMapping] = []

        # Prevent crash when no traps can be found
        if len(image_1_trap_centroids) == 0 or len(image_2_trap_centroids) == 0:
            print("Warning: no traps located in image")
            return 0, 0

        # Calculate closest object in image 2 to each object in image 1
        for id_1 in range(len(image_1_trap_centroids)):
            point_1 = image_1_trap_centroids[id_1]
            distances: List[float] = []

            for id_2 in range(len(image_2_trap_centroids)):
                point_2 = image_2_trap_centroids[id_2]
                distances.append((point_1[0] - point_2[0]) ** 2. + (point_1[1] - point_2[1]) ** 2.)

            trap_mappings.append(TrapMapping(id_1, int(np.argmin(distances)), np.min(distances)))

        # Filter out duplicate mappings to image 2 objects
        final_maps = []
        for id_2 in range(len(image_2_trap_centroids)):
            img_2_trap_maps = [mapping for mapping in trap_mappings if mapping.id_2 == id_2]
            if len(img_2_trap_maps) > 0:
                final_maps.append(min(img_2_trap_maps))

        # Calculate xy shift, excluding any maps of distance > 1 SD from average
        average_distance: float = np.average([mapping.distance for mapping in final_maps])
        sd_distance: float = float(np.std([mapping.distance for mapping in final_maps]))
        xy_shifts: List[Tuple[float, float]] = []

        for mapping in final_maps:
            if average_distance - sd_distance <= mapping.distance <= average_distance + sd_distance:
                point_1 = image_1_trap_centroids[mapping.id_1]
                point_2 = image_2_trap_centroids[mapping.id_2]

                shift = (point_2[0] - point_1[0], point_2[1] - point_1[1])
                xy_shifts.append(shift)

        return tuple(np.average(xy_shifts, axis=0))

    def _generate_trap_image(self, image: np.ndarray) -> np.ndarray:
        val, thresh = cv2.threshold(image, 0, 1, cv2.THRESH_OTSU)
        background = find_background(image, blur_image=False)
        nonzero = np.nonzero(background)
        background_point = (nonzero[1][0], nonzero[0][0])

        if self.parameters.alternate_trap_detection:
            trap_image = fill_holes(thresh.astype(np.uint8), background_point)
        else:
            inverted_thresh = np.logical_not(thresh)
            element: np.ndarray = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            dilated: np.ndarray = cv2.dilate(inverted_thresh.astype(np.uint8), element, iterations=1)
            trap_image: np.ndarray = find_holes(dilated, background_point)
        return trap_image

    def _find_trap_locations(self, image: np.ndarray) -> List[Tuple[float, float]]:
        trap_image = self._generate_trap_image(image)
        label_count, labels, stats, centroids = cv2.connectedComponentsWithStats(trap_image)
        trap_labels = np.where(np.all([stats[:, cv2.CC_STAT_AREA] > self.parameters.min_trap_size,
                                       stats[:, cv2.CC_STAT_AREA] < self.parameters.max_trap_size], axis=0))

        trap_centroids = [tuple(centroid) for centroid in centroids[trap_labels]]
        return trap_centroids

    def preview_trap_image(self, frame_id: int, fov_id: int) -> np.ndarray:
        frame = self.frames[self.frames.calculate_position(frame_id, fov_id, self.parameters.trap_detection_channel, self.parameters.trap_detection_z_position)]
        trap_image = self._generate_trap_image(frame)
        label_count, labels, stats, centroids = cv2.connectedComponentsWithStats(trap_image)

        for label in range(label_count):
            if self.parameters.min_trap_size < stats[label, cv2.CC_STAT_AREA] < self.parameters.max_trap_size:
                labels[labels == label] = 0

        trap_image = (5 * trap_image - 4 * (labels != 0)).astype(np.uint8)
        return trap_image
