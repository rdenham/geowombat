import os
from collections import namedtuple

from rasterio.windows import Window


def get_file_extension(filename):

    FileNames = namedtuple('FileNames', 'd_name f_name f_base f_ext')

    d_name, f_name = os.path.splitext(filename)
    f_base, f_ext = os.path.split(f_name)

    return FileNames(d_name=d_name, f_name=f_name, f_base=f_base, f_ext=f_ext)


def n_rows_cols(pixel_index, block_size, rows_cols):

    """
    Adjusts block size for the end of image rows and columns.

    Args:
        pixel_index (int): The current pixel row or column index.
        block_size (int): The image block size.
        rows_cols (int): The total number of rows or columns in the image.

    Returns:
        Adjusted block size as int.
    """

    return block_size if (pixel_index + block_size) < rows_cols else rows_cols - pixel_index


def setup_windows(n_rows, n_cols, row_chunks, col_chunks, return_as='list'):

    if return_as == 'list':
        window_info = list()
    else:
        window_info = dict()

    i = 0

    for row_off in range(0, n_rows, row_chunks):

        height = n_rows_cols(row_off, row_chunks, n_rows)

        j = 0

        for col_off in range(0, n_cols, col_chunks):

            width = n_rows_cols(col_off, col_chunks, n_cols)

            if return_as == 'list':
                window_info.append(Window(col_off=col_off, row_off=row_off, width=width, height=height))
            else:
                window_info['{:d}{:d}'.format(i, j)] = Window(col_off=col_off, row_off=row_off, width=width, height=height)

            j += 1

        i += 1

    return window_info
