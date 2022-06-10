# Alan Reed, 2022
# A collection of functions for working with the files that make up a processed image dataset

from enum import Enum, auto
import os
import re
from multiprocessing import Pool
import progressbar
from Segmentation.SegmentationData import ProcessedFrame, load_segmentation
from Tracking.TrackingSolution import TrackingSolution, load_tracking_solution


class FileType(Enum):
    REGION = auto()
    SEGMENTATION = auto()
    CURATED_SEGMENTATION = auto()
    TRACKING = auto()


# Use regex to filter directories according to correct formatting
FOV_REGEX = "^fov_[0-9]+$"
REGION_REGEX = "^region_[0-9]+$"
IMAGE_REGEX = "^frame_[0-9]+_z_[0-9]+_channel_[0-9]+\.tif$"
SEG_REGEX = "^fov_[0-9]+_region_[0-9]+\.json$"
CURATED_REGEX = "^fov_[0-9]+_region_[0-9]+_curated\.json$"
TRACKING_REGEX = "^fov_[0-9]+_region_[0-9]+_tracking\.json$"

regex_dict = {FileType.SEGMENTATION: SEG_REGEX,
              FileType.CURATED_SEGMENTATION: CURATED_REGEX,
              FileType.TRACKING: TRACKING_REGEX}


def iterate_regions(root_directory: str, filetype: FileType):
    """Generator function that runs through all regions found within <root_directory>"""
    def sort_folders(folder: str) -> int:
        return int(folder.split('_')[1])

    fov_folders: list[str] = [folder for folder in os.listdir(root_directory) if
                              re.search(FOV_REGEX, folder) is not None]

    for fov_folder in sorted(fov_folders, key=sort_folders):
        fov_path: str = os.path.join(root_directory, fov_folder)
        region_folders: list[str] = [folder for folder in os.listdir(fov_path) if
                                     re.search(REGION_REGEX, folder) is not None]

        for region_folder in sorted(region_folders, key=sort_folders):
            region_path: str = os.path.join(fov_path, region_folder)
            if filetype == FileType.REGION:
                yield region_path
            else:
                files: list[str] = [file for file in os.listdir(region_path) if
                                    re.search(regex_dict[filetype], file) is not None]

                for file in files:
                    yield os.path.join(region_path, file)


def count_files(root_directory: str, filetype: FileType) -> int:
    """Counts all result files of the specified type within a dateset"""
    count = 0
    for _ in iterate_regions(root_directory, filetype):
        count += 1
    return count


def load_all_tracking_results(root_path: str, processes=12) -> list[TrackingSolution]:
    """Multi-threaded function that loads tracking results from every region in a dataset"""
    tracking_count = count_files(root_path, FileType.TRACKING)
    print("Total tracked regions: {}".format(tracking_count))

    results = []
    with progressbar.ProgressBar(max_value=tracking_count) as bar:
        with Pool(processes=processes) as pool:
            for res in pool.imap(load_tracking_solution, iterate_regions(root_path, FileType.TRACKING)):
                results.append(res)
                bar += 1
    return results


def load_all_segmentation_results(root_path: str, processes=12) -> list[list[ProcessedFrame]]:
    """Multi-threaded function that loads curated segmentation data from every region in a dataset"""
    segmentation_count = count_files(root_path, FileType.CURATED_SEGMENTATION)
    print("Total curated segmented regions: {}".format(segmentation_count))

    results = []
    with progressbar.ProgressBar(max_value=segmentation_count) as bar:
        with Pool(processes=processes) as pool:
            for res in pool.imap(load_segmentation, iterate_regions(root_path, FileType.CURATED_SEGMENTATION)):
                results.append(res)
                bar += 1
    return results
