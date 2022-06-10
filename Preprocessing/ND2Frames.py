from pims import ND2Reader_SDK
from typing import List


# Small wrapper class to handle configuration of ND2 reader
class ND2Frames(ND2Reader_SDK):
    def __init__(self, filename) -> None:
        super(ND2Reader_SDK, self).__init__()

        super().__init__(filename)
        if 't' in self.axes:
            self.num_frames: int = self.sizes['t']
        else:
            self.num_frames: int = 1

        if 'c' in self.axes:
            self.num_channels: int = self.sizes['c']
        else:
            self.num_channels: int = 1

        if 'm' in self.axes:
            self.num_fovs: int = self.sizes['m']
        else:
            self.num_fovs: int = 1

        if 'z' in self.axes:
            self.num_zstack: int = self.sizes['z']
        else:
            self.num_zstack: int = 1

        def axes_sort(char: str):
            order_dict = {'c': 2, 't': 0, 'm': 1, 'z': 3}

            if char in order_dict:
                return order_dict[char]
            else:
                print("Warning: unknown image dimension '{}'".format(char))
                return len(order_dict)
        self.bundle_axes = 'yx'
        axes: List[str] = self.axes
        axes.remove('x')
        axes.remove('y')
        axes.sort(key=axes_sort)
        self.iter_axes = axes

    def calculate_position(self, frame_id: int, fov_id: int, channel_id: int, zstack_id: int) -> int:
        if frame_id < self.num_frames and fov_id < self.num_fovs and channel_id < self.num_channels and zstack_id < self.num_zstack:
            return (frame_id * self.num_fovs * self.num_channels * self.num_zstack) + \
                   (fov_id * self.num_channels * self.num_zstack) + \
                   (channel_id * self.num_zstack) +\
                   zstack_id
        else:
            print("Warning! ND2 position out of bounds: frame {} FOV {} channel {} z {}".format(frame_id, fov_id, channel_id, zstack_id))
            return 0
