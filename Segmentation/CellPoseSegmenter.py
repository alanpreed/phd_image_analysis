import subprocess
import pickle
import os
from typing import List, Tuple, Optional
import time
import shutil
import numpy as np
import cv2
from Segmentation.SegmentationData import Segment, Segmentation, ProcessedFrame, save_segmentation
from Segmentation.Measurement import calculate_centroid, calculate_compactness, calculate_intensity
from Segmentation.Utilities import find_segmented_background


class CellPoseSegmenter:
    def __init__(self, image_names: List[List[str]], image_root_path: str, segmentation_channel_id: int, cellpose_path: str) -> None:
        self.image_names = image_names
        self.image_root_path = image_root_path
        self.segmentation_channel_id = segmentation_channel_id
        self.cellpose_path = cellpose_path

    def run_segmentation(self) -> List[ProcessedFrame]:
        image_paths = self._generate_filepaths()
        pre_cellpose: float = time.time()
        cell_masks = _run_cellpose(image_paths, self.cellpose_path)
        post_cellpose: float = time.time()
        print("CellPose completed in {}s".format(post_cellpose - pre_cellpose))
        processed_frames: List[ProcessedFrame] = []

        for frame_id in range(len(cell_masks)):
            frame_images = [cv2.imread(self.image_root_path + img_name, flags=(cv2.IMREAD_GRAYSCALE + cv2.IMREAD_UNCHANGED)) for img_name in self.image_names[frame_id]]

            background_image = find_segmented_background(frame_images[self.segmentation_channel_id], cell_masks[frame_id], cell_masks[frame_id].shape)
            background_intensities = [calculate_intensity(image, background_image) for image in frame_images]

            segmentation: Segmentation = Segmentation(name="cellpose_frame_{}".format(frame_id),
                                                      segmentation_channel_id=self.segmentation_channel_id,
                                                      background_mask=background_image,
                                                      background_intensities=background_intensities,
                                                      segments=[])

            for segment_id in range(np.amax(cell_masks[frame_id])):
                segment_img = (cell_masks[frame_id] == segment_id + 1).astype(np.uint8)

                # Handle rare cases where CellPose generates a disconnected region
                num_parts, labels = cv2.connectedComponents(segment_img)

                if num_parts > 2:
                    print("Warning: segment {} in frame {} contains {} disconnected regions".format(segment_id, frame_id, num_parts - 1))

                    sizes = []
                    for i in range(num_parts):
                        sizes.append(np.count_nonzero(labels == i))

                    sorted_sizes = np.argsort(sizes)
                    print("Using largest region, size {}".format(sizes[sorted_sizes[-2]]))

                    for i in sorted_sizes[0:-2]:
                        print("Discarding region size {}".format(sizes[i]))

                    segment_img = (labels == sorted_sizes[-2]).astype(np.uint8)

                name = "f{}".format(frame_id)
                area = np.count_nonzero(segment_img)
                compactness = calculate_compactness(segment_img)
                centroid = calculate_centroid(segment_img)
                intensities: List[float] = [calculate_intensity(image, segment_img) for image in frame_images]

                new_segment = Segment(seg_id=segment_id,
                                      frame_id=frame_id,
                                      mask_image=segment_img,
                                      name=name,
                                      centroid=centroid,
                                      size=area,
                                      compactness=compactness,
                                      channel_intensities=intensities,
                                      conflicts=[])
                segmentation.segments.append(new_segment)

            processed_frame: ProcessedFrame = ProcessedFrame(root_directory=self.image_root_path,
                                                             frame_no=frame_id,
                                                             image_names=self.image_names[frame_id],
                                                             frame_shape=frame_images[0].shape,
                                                             segmentations=[segmentation])

            processed_frames.append(processed_frame)
        return processed_frames

    def _generate_filepaths(self) -> List[str]:
        image_filepaths: List[str] = []

        for frame_images in self.image_names:
            image_filepaths.append(self.image_root_path + frame_images[self.segmentation_channel_id])

        return image_filepaths


def _run_cellpose(image_filepaths: List[str], cellpose_path: str, cellpose_script_name: str = "run_cellpose.py") -> List[np.ndarray]:
    file_path = os.path.dirname(os.path.realpath(__file__)) + "/" + cellpose_script_name

    script: str = "cd {0}; source venv/bin/activate; cp {1} {2}; python {2} ".format(cellpose_path, file_path,
                                                                                     cellpose_script_name)

    for path in image_filepaths:
        script += "\"{}\" ".format(path)

    process = subprocess.run(script, shell=True, stdout=subprocess.PIPE, executable='/bin/bash')

    masks = pickle.loads(process.stdout)
    return masks


def run_full_segmentation(input_path: str, cellpose_location: str = "/home/alan/Programming/cellpose", z_position: int = 1, seg_channel_id: int = 0, start_fov: int = 0, start_region: int = 0, output_root: Optional[str] = None) -> None:
    NUM_FILENAME_PARTS = 6
    FRAME_POS = 1
    Z_POS = 3
    CHAN_POS = 5

    def split_filename(filename: str) -> List[str]:
        ext_removed = os.path.splitext(filename)[0]
        return ext_removed.split('_')

    def sort_files(filename: str) -> Tuple[int, int]:
        parts = split_filename(filename)
        return int(parts[FRAME_POS]), int(parts[CHAN_POS])

    def sort_folders(folder: str) -> int:
        return int(folder.split('_')[1])

    fov_count: int = 0
    region_count: int = 0
    for fov_folder in sorted(os.listdir(input_path), key=sort_folders):
        fov_count += 1
        for region_folder in sorted(os.listdir(input_path + '/' + fov_folder), key=sort_folders):
            region_count += 1

    print("Total {} FOVs, {} regions".format(fov_count, region_count))

    for fov_folder in sorted(os.listdir(input_path), key=sort_folders):
        fov_id: int = int(fov_folder.split('_')[1])
        print("FOV {}".format(fov_id))
        if fov_id >= start_fov:
            for region_folder in sorted(os.listdir(input_path + '/' + fov_folder), key=sort_folders):
                region_id = int(region_folder.split('_')[1])

                if fov_id == start_fov and region_id < start_region:
                    continue

                print("FOV {} Region {}".format(fov_id, region_id))

                region_dir = input_path + '/' + fov_folder + '/' + region_folder + '/'
                files = os.listdir(region_dir)

                start_time: float = time.time()

                # Remove all z positions other than the one chosen for segmentation, as well as invalid filenames
                filtered_files: List[str] = []
                for file in files:
                    split_name = split_filename(file)
                    if len(split_name) != NUM_FILENAME_PARTS:
                        print("Warning: file {} does not fit naming convention".format(file))
                        continue
                    elif int(split_name[Z_POS]) != z_position:
                        continue
                    else:
                        filtered_files.append(file)

                filtered_files.sort(key=sort_files)

                if len(filtered_files) > 0:
                    filenames = [split_filename(file) for file in filtered_files]

                    num_frames = len(np.unique([file[FRAME_POS] for file in filenames]))
                    num_channels = len(np.unique([file[CHAN_POS] for file in filenames]))

                    # Group image names by frame:
                    # List[ List[frame_x_channel_1, frame_x_channel_2], List[frame_x+1_channel_1, frame_x+1_channel_2], ...]
                    image_filenames = []
                    for frame_no in range(num_frames):
                        frame_image_names = []
                        for channel_id in range(num_channels):
                            frame_image_names.append(filtered_files[frame_no * num_channels + channel_id])
                        image_filenames.append(frame_image_names)

                    segmenter = CellPoseSegmenter(image_filenames, region_dir, seg_channel_id, cellpose_location)

                    region_segmentation: List[ProcessedFrame] = segmenter.run_segmentation()
                    output_path = region_dir + fov_folder + '_' + region_folder
                    save_segmentation(region_segmentation, output_path)

                    # Save a copy to disk as well as RAM
                    if output_root is not None:
                        src_file = output_path + ".json"
                        if os.path.exists(src_file):
                            dest_file = os.path.join(output_root, fov_folder, region_folder, os.path.split(src_file)[-1])
                            print("Copying \n {} \n to \n {}".format(src_file, dest_file))
                            shutil.copy2(src_file, dest_file)
                        else:
                            print("File copy failed - no segmentation saved!")
                else:
                    print("Warning: no suitable image files found")

                end_time: float = time.time()
                print("Region completed in {}s".format(end_time - start_time))


if __name__ == '__main__':
    # root_input_path = "/ramdisk/2022-01-25_wafer9_lo_fluo_3out_1h30cycle_air_edf"  # 5'UTR 1
    # root_input_path = "/ramdisk/2022-02-09_wafer9_lo_fluo_3out_1h30mcycle_air_edf"  # 5'UTR 2
    # root_input_path = "/ramdisk/2022-02-10_wafer9_lo_fluo_3out_1h30mcycle_air_ser51_edf"  # Ser51Ala 1
    # root_input_path = "/ramdisk/2022-02-24_wafer7_lo_fluo_gcn4_edf"  # Non-switching 1
    # root_input_path = "/ramdisk/2022-02-14_wafer9_lo_fluo_3out_1h30mcycle_air_ser51_edf"  # Ser51Ala 2
    root_input_path = "/ramdisk/2022-02-16_wafer9_lo_fluo_3out_1h30mcycle_air_gcn4_edf"  # 5'UTR 3

    second_output_path = os.path.join("/smalldata", os.path.split(root_input_path)[1])

    run_full_segmentation(root_input_path, z_position=0, start_fov=0, start_region=0, output_root=second_output_path)
