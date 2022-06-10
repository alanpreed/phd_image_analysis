from Segmentation.HistogramSegmenter import *
from Segmentation.SegmentationData import save_segmentation, ProcessedFrame
import multiprocessing
import os
import psutil
import time
import cv2
import numpy as np
from typing import List

NUM_WORKERS = 4


# Returns the z index of the image with the lowest standard deviation, as a rough estimate of the best focus
def pick_z_image(image_path: str, frame_no, num_zstack: int, segmentation_channel: int) -> int:
    image_names = ["{}/frame_{}_z_{}_channel_{}.tif".format(image_path, frame_no, zstack_id, segmentation_channel) for zstack_id in range(num_zstack)]

    image_stds: List[float] = []
    for zstack_id in range(num_zstack):
        image = cv2.imread("{}/frame_{}_z_{}_channel_{}.tif".format(image_path, frame_no, zstack_id, segmentation_channel))
        image_stds.append(float(np.std(image)))

    return image_stds.index(min(image_stds))


def run_frame(image_path: str, image_no: int, num_channels: int, num_zstack: int, seg_channel: int, parameters: SegmentationParameters):
    z_index = pick_z_image(image_path, image_no, num_zstack, seg_channel)
    image_names = ["{}/frame_{}_z_{}_channel_{}.tif".format(image_path, image_no, z_index, chan) for chan in range(num_channels)]
    segmenter = HistogramSegmenter(image_names, image_no, parameters)
    segmenter.run_segmentation()

    frame_segmentation: ProcessedFrame = ProcessedFrame(image_path, image_no, image_names, (), segmenter.segmentations)
    return frame_segmentation


# Multi-thread segmentation of each region
def run_region(input_path: str, output_path: str, num_channels: int, num_zstack: int, segmentation_channel: int,  parameters: SegmentationParameters):
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        region_segmentation = pool.starmap(run_frame, [(input_path, image_no, num_channels, num_zstack, segmentation_channel, parameters) for image_no in
                                                       range(num_frames)])

    save_segmentation(region_segmentation, output_file_path)


if __name__ == '__main__':
    params = SegmentationParameters(2, [-1, -0.5, 0, 0.15, 0.3, 0.5], 10)

    input_root = "/data/cropped/2021-03-01_CMOS_cup_5'utr"
    output_root = "/data/cropped/2021-03-01_CMOS_cup_5'utr/test_seg"

    num_fovs = 10
    num_regions = 10
    num_frames = 5
    num_chan = 2
    num_z = 3
    seg_channel = 0

    for fov_id in [2]:  # range(num_fovs):
        for region_id in range(num_regions):
            input_file_path = input_root + "/fov_{}/region_{}".format(fov_id, region_id)
            output_file_path = output_root + "/fov_{}".format(fov_id, region_id)

            os.makedirs(output_file_path, exist_ok=True)
            output_file_path = output_file_path + "/region_{}".format(region_id)

            print("Mem usage: {}".format(psutil.virtual_memory().percent))
            print("Segmenting FOV {} region {}".format(fov_id, region_id))
            time_before = time.monotonic()

            # Region segmentation with worker pool is run in a separate process to avoid memory leak
            proc = multiprocessing.Process(target=run_region,
                                           args=(input_file_path, output_file_path, num_chan,
                                                 num_z, seg_channel, params))
            proc.start()
            proc.join()

            time_after = time.monotonic()
            print("FOV {} region {} runtime: {}s".format(fov_id, region_id, time_after - time_before))

#
# # IMAGE_FILENAMES = ["Input/generated_images/000.png",
# #                    "Input/generated_images/001.png",
# #                    "Input/generated_images/002.png",
# #                    "Input/generated_images/003.png",
# #                    "Input/generated_images/004.png"]
# # params = SegmentationParameters(0, [-1.2], 8)
# # segmentations = []
# #
# # for image_no in range(len(IMAGE_FILENAMES)):
# #     image_name = IMAGE_FILENAMES[image_no]
# #     print(image_name)
# #     seg = Segmentation(image_name, image_no, params)
# #     seg.run_segmentation()
# #     segmentations.append(seg)
# #
# # with open('Output/generated_images_segmentation.pickle', 'wb') as handle:
# #     pickle.dump(segmentations, handle, protocol=pickle.HIGHEST_PROTOCOL)
