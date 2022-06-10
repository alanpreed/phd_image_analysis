"""Script for running and curating the tracking of all curated segmentations for regions in input_path"""

import os
from typing import List, Tuple
import re
import time
import shutil
from GUI.TrackingEditor import run_editor

input_path = "/smalldata/2022-01-25_wafer9_lo_fluo_3out_1h30cycle_air_edf"  # 5'UTR 1
# input_path = "/ramdisk/2022-02-09_wafer9_lo_fluo_3out_1h30mcycle_air_edf"  # 5'UTR 2
# input_path = "/ramdisk/2022-02-10_wafer9_lo_fluo_3out_1h30mcycle_air_ser51_edf"  # Ser51Ala 1
# input_path = "/ramdisk/2022-02-24_wafer7_lo_fluo_gcn4_edf" # No switching 1
# input_path = "/ramdisk/2022-02-14_wafer9_lo_fluo_3out_1h30mcycle_air_ser51_edf"  # Ser51Ala 2
# input_path = "/ramdisk/2022-02-16_wafer9_lo_fluo_3out_1h30mcycle_air_gcn4_edf"  # 5'UTR 3

second_output_path = os.path.join("/smalldata", os.path.split(input_path)[1])

# Use regex to filter directories according to correct formatting
FOV_REGEX = "^fov_[0-9]+$"
REGION_REGEX = "^region_[0-9]+$"
IMAGE_REGEX = "^frame_[0-9]+_z_[0-9]+_channel_[0-9]+\.tif$"
SEG_REGEX = "^fov_[0-9]+_region_[0-9]+\.json$"
CURATED_REGEX = "^fov_[0-9]+_region_[0-9]+_curated\.json$"

# Data positions within filenames
FRAME_POS = 1
Z_POS = 3
CHAN_POS = 5


def sort_files(filename: str) -> Tuple[int, int]:
    filename = os.path.splitext(filename)[0]
    parts = filename.split('_')
    return int(parts[FRAME_POS]), int(parts[CHAN_POS])


def sort_folders(folder: str) -> int:
    return int(folder.split('_')[1])


fov_folders: List[str] = [folder for folder in os.listdir(input_path) if re.search(FOV_REGEX, folder) is not None]

# Count total segmented regions
curated_seg_filepaths: List[str] = []
region_count: int = 0
for fov_folder in sorted(fov_folders, key=sort_folders):
    fov_path: str = input_path + '/' + fov_folder + '/'
    region_folders: List[str] = [folder for folder in os.listdir(fov_path) if re.search(REGION_REGEX, folder) is not None]

    for region_folder in sorted(region_folders, key=sort_folders):
        region_path: str = fov_path + region_folder + '/'
        seg_files: List[str] = [file for file in os.listdir(region_path) if re.search(CURATED_REGEX, file) is not None]
        if len(seg_files) == 1:
            segmentation_filepath = os.path.join(region_path, seg_files[0])
            curated_seg_filepaths.append(segmentation_filepath)
            region_count += 1

print("Total curated regions: {}".format(len(curated_seg_filepaths)))


# Run tracking editing tool for all regions, skipping any that have been tracked
current_region: int = 0
for fov_folder in sorted(fov_folders, key=sort_folders):
    fov_path: str = input_path + '/' + fov_folder + '/'
    region_folders: List[str] = [folder for folder in os.listdir(fov_path) if re.search(REGION_REGEX, folder) is not None]

    fov_id: int = int(fov_folder.split('_')[1])
    print("FOV {}".format(fov_id))
    for region_folder in sorted(region_folders, key=sort_folders):

        region_id = int(region_folder.split('_')[1])

        tracking_filename = "_".join([fov_folder, region_folder, "tracking.json"])
        tracking_filepath = os.path.join(input_path, fov_folder, region_folder, tracking_filename)

        if os.path.exists(tracking_filepath):
            print(print("FOV {} Region {} already tracked".format(fov_folder.split('_')[1], region_folder.split('_')[1])))
            current_region += 1
            print("Completed {} out of {} regions".format(current_region, region_count))
            continue
        else:
            region_path: str = fov_path + region_folder + '/'
            seg_files: List[str] = [file for file in os.listdir(region_path) if re.search(CURATED_REGEX, file) is not None]

            if len(seg_files) == 1:
                print("FOV {} Region {}".format(fov_folder.split('_')[1], region_folder.split('_')[1]))
                pre_curate: float = time.time()

                curation_filepath = os.path.join(region_path, seg_files[0])

                run_editor(curation_filepath)

                # Copy file out of RAM after curation completed
                root_path, ext = os.path.splitext(curation_filepath)
                tracking_filename = "_".join([fov_folder, region_folder, "tracking.json"])
                tracking_filepath = os.path.join(input_path, fov_folder, region_folder, tracking_filename)

                if os.path.exists(tracking_filepath):
                    out_path = os.path.join(second_output_path, fov_folder, region_folder, tracking_filename)
                    print("Copying \n {} \n to \n {}".format(tracking_filepath, out_path))
                    shutil.copy2(tracking_filepath, out_path)
                current_region += 1
                print("Completed {} out of {} regions in {}".format(current_region, region_count, time.time() - pre_curate))
            else:
                print("Warning: no segmentation data found for {} {}".format(fov_folder, region_folder))
