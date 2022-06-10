import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import hsv_to_rgb
import imageio
from typing import List, Tuple
import cv2

from Tracking.Cell import Cell


# Convert a binary image into a coloured area with a coloured border
def colourise_binary_mask(image: np.ndarray, area_colour: Tuple, border_colour: Tuple) -> np.ndarray:
    border = cv2.findContours(image.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    border_image = np.zeros(image.shape).astype(np.uint8)
    cv2.drawContours(border_image, border[0], -1, (1, 0, 0))

    image_rgb = np.dstack(tuple([(image != 0) * colour_channel for colour_channel in area_colour]))
    image_rgb[border_image != 0] = border_colour

    return image_rgb


def generate_border_mask(image: np.ndarray, thickness: int) -> np.ndarray:
    border = cv2.findContours(image.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    border_image = np.zeros(image.shape).astype(np.uint8)
    cv2.drawContours(border_image, border[0], -1, (1, 0, 0), thickness)
    return border_image


def plot_frame(cell_data: List[Cell], frame_id: int, label_cells: bool = True):
    colour_vals = np.linspace(0, 1, len(cell_data), endpoint=False)

    frame_cell_list = [cell for cell in cell_data if
                       cell.first_frame <= frame_id < cell.lifespan + cell.first_frame]

    frame_shape = cell_data[0].segments[0].mask_image.shape
    frame_image = np.full(frame_shape[0:2] + (3,), 0.0)

    for cell in frame_cell_list:
        segment = cell.segments[frame_id - cell.first_frame]

        # Set hue to seg colour, saturation and value to 1, in area of segment
        frame_image[:, :, 0] += (segment.mask_image * colour_vals[cell.cell_id])
        frame_image[:, :, 1] += segment.mask_image
        frame_image[:, :, 2] += segment.mask_image

    fig, ax = plt.subplots()
    ax.imshow(hsv_to_rgb(frame_image), cmap='rainbow')

    if label_cells:
        for cell in frame_cell_list:
            segment = cell.segments[frame_id - cell.first_frame]
            # For some reason centre_of_mass swaps x and y
            ax.text(segment.centroid[1], segment.centroid[0], cell.cell_id,
                    fontsize=5, color='white', horizontalalignment='center', verticalalignment='center')
    plt.show()


def generate_gif(cell_data: List[Cell], first_frame: int, num_frames: int, output_filename: str,
                 label_cells: bool = True, fps=1):
    colour_vals = np.linspace(0, 1, len(cell_data), endpoint=False)
    images = []

    for frame in range(first_frame, first_frame + num_frames):
        frame_cell_list = [cell for cell in cell_data if
                           cell.first_frame <= frame < cell.lifespan + cell.first_frame]

        frame_shape = cell_data[0].segments[0].mask_image.shape
        frame_image = np.full(frame_shape[0:2] + (3,), 0.0)

        for cell in frame_cell_list:
            segment = cell.segments[frame - cell.first_frame]

            # Set hue to seg colour, saturation and value to 1, in area of segment
            frame_image[:, :, 0] += (segment.mask_image * colour_vals[cell.cell_id])
            frame_image[:, :, 1] += segment.mask_image
            frame_image[:, :, 2] += segment.mask_image

        plt.figure()
        fig, ax = plt.subplots()
        ax.imshow(hsv_to_rgb(frame_image), cmap='rainbow')

        if label_cells:
            for cell in frame_cell_list:
                segment = cell.segments[frame - cell.first_frame]
                ax.text(segment.centroid[1], segment.centroid[0], cell.cell_id, fontsize=5, color='white',
                        horizontalalignment='center', verticalalignment='center')
        fig.canvas.draw()
        image = np.frombuffer(fig.canvas.tostring_rgb(), dtype='uint8')
        image = image.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        images.append(image)
        plt.close()

    imageio.mimsave(output_filename + '.gif', images, fps=fps)
