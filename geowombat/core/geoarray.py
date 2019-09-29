from __future__ import division

import os
from copy import copy

from .properties import GeoProperties
from .moving import MovingWindow

from mpglue import raster_tools
from mpglue import vector_tools

import numpy as np
from osgeo import gdal, osr
import rasterio
from skimage.exposure import rescale_intensity

# import matplotlib.pyplot as plt
# from cartopy import crs as ccrs
# from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER


def _wrap_rasterio(src):

    """
    Wraps attributes from a `rasterio` object
    """

    geo_src = src.meta.copy()

    left = src.bounds.left + src.j*src.res[0]
    right = left + src.ccols*src.res[0]
    top = src.bounds.top - src.i*src.res[0]
    bottom = top - src.rrows*src.res[0]

    width = right - left
    height = top - bottom

    transform = rasterio.transform.from_bounds(left,
                                               bottom,
                                               right,
                                               top,
                                               width,
                                               height)

    geo_src.update({'width': width,
                    'height': height,
                    'transform': transform})

    geo_src._create = raster_tools.create_raster
    geo_src._warp = raster_tools.warp
    geo_src._transform = vector_tools.Transform
    geo_src._get_xy_offsets = vector_tools.get_xy_offsets
    geo_src._nd_to_rgb = raster_tools.nd_to_rgb

    return geo_src


def _wrap_mpglue(src):

    """
    Wraps attributes from a `MpGlue` object
    """

    # Wrap the array as a GeoArray
    geo_src = src.copy()

    geo_src.update_info(left=src.left+(src.j*src.cellY),
                        top=src.top-(src.i*src.cellY))

    geo_src.update_info(right=geo_src.left+(src.ccols*src.cellY),
                        bottom=geo_src.top-(src.rrows*src.cellY))

    geo_src._create = raster_tools.create_raster
    geo_src._warp = raster_tools.warp
    geo_src._transform = vector_tools.Transform
    geo_src._get_xy_offsets = vector_tools.get_xy_offsets
    geo_src._nd_to_rgb = raster_tools.nd_to_rgb

    return geo_src


def _wrap_gdal(src):

    """
    Wraps attributes from a `GDAL` object
    """

    with raster_tools.ropen(file_name=src.GetFileList()[0]) as glsrc:

        __ = glsrc.read()
        geo_src = _wrap_mpglue(glsrc)

    return geo_src


class GeoMethods(GeoProperties, MovingWindow):

    def _get_shape(self):

        self.layers_ = 1
        self.rows_ = 0
        self.cols_ = 0

        if len(self.shape) == 2:
            self.rows_, self.cols_ = self.shape
        else:
            self.layers_, self.rows_, self.cols_ = self.shape

    def set_names(self, names):

        """
        Sets array layer names

        Example:
            >>> garray.set_names(['blue', 'green', 'red', 'nir'])

        Returns:
            None, sets names in place
        """

        self.layer_names = names

        for i in range(0, len(names)):
            setattr(self, names[i], self[i])

    def set_no_data(self, value):

        """
        Sets array 'no data' value

        Example:
            >>> garray.set_no_data(0)

        Returns:
            None, sets `no data` value in place
        """

        self.no_data_ = value

    def extract(self,
                row_start=None,
                rows=None,
                col_start=None,
                cols=None,
                layer_start=None,
                layers=None):

        """
        Slices an array

        Example:
            >>> # rows 1-10
            >>> # columns 0-20
            >>> print(geoarray.left, geoarray.top)
            >>>
            >>> # Use the `extract` method to maintain geo-coordinates
            >>> new_array = geoarray.extract(row_start=1, rows=10, cols=20)
            >>>
            >>> # The extent is updated
            >>> print(new_array.left, new_array.top)
        """

        if not isinstance(layer_start, int):
            layer_start = 0

        if not isinstance(layers, int):
            layers = self.layers

        if not isinstance(row_start, int):
            row_start = 0

        if not isinstance(rows, int):
            rows = self.rows

        if not isinstance(col_start, int):
            col_start = 0

        if not isinstance(cols, int):
            cols = self.columns

        src = self.src.copy()

        src.left = self.src.left + (self.src.cellY * col_start)
        src.right = self.src.left + (self.src.cellY * (col_start+cols))
        src.top = self.src.top - (self.src.cellY * row_start)
        src.bottom = self.src.top - (self.src.cellY * (row_start+rows))

        # if inplace:
        #
        #     if self.layers == 1:
        #         self = self[row_start:row_start+rows, col_start:col_start+cols]
        #     else:
        #
        #         self = self[layer_start:layer_start+layers,
        #                     row_start:row_start+rows,
        #                     col_start:col_start+cols]
        #
        #     # new_geo = GeoArray(array, src)
        #     # self.__class__ = new_geo.__class__
        #     # self = super(GeoArray, self).__init__(array, src)
        #     # self = self.reinit(array, src)
        #     # self = GeoArray(array, src)
        #
        #     # self.src = src
        #     # self._update_inplace(self)

        if self.layers == 1:
            sub_array = self[row_start:row_start+rows, col_start:col_start+cols]
        else:

            sub_array = self[layer_start:layer_start+layers,
                             row_start:row_start+rows,
                             col_start:col_start+cols]

        sub_array.src = src
        sub_array.set_no_data(self.no_data)

        return sub_array

    def to_crs(self, crs=None, **kwargs):

        """
        Warps the array projection

        Args:
            crs (Optional[int or str])
            kwargs (Optional[dict])

        Example:
            >>> print(geoarray.left, geoarray.top, geoarray.projection)
            >>>
            >>> geoarray = geoarray.to_crs(crs=102033)
            >>>
            >>> print(geoarray.left, geoarray.top, geoarray.projection)
            >>>
            >>> # Create a new array with warped bounds
            >>> geoarray_warp = geoarray.to_crs(crs=102033)
        """

        if isinstance(self.crs, int):
            in_epsg = self.crs
            in_proj = None
            in_crs = in_epsg
        else:
            in_epsg = None
            in_proj = self.crs
            in_crs = in_proj

        if isinstance(crs, int):
            out_epsg = crs
            out_proj = None
            out_crs = out_epsg
        elif isinstance(crs, str):
            out_epsg = None
            out_proj = crs
            out_crs = out_proj
        else:
            out_epsg = None
            out_proj = self.crs
            out_crs = out_proj

        n_layers = copy(self.layers)

        if 'outputBounds' not in kwargs:

            ptr = self.src._transform(self.left, self.top, in_crs, out_crs)
            tleft, ttop = ptr.x_transform, ptr.y_transform

            ptr = self.src._transform(self.right, self.bottom, in_crs, out_crs)
            tright, tbottom = ptr.x_transform, ptr.y_transform

            kwargs['outputBounds'] = [tleft, tbottom, tright, ttop]

        # Warp the array
        src = self.src._warp(self.src.datasource,
                             'memory.mem',
                             in_epsg=in_epsg,
                             in_proj=in_proj,
                             out_epsg=out_epsg,
                             out_proj=out_proj,
                             return_datasource=True,
                             overwrite=True,
                             srcNodata=self.no_data,
                             **kwargs)

        # TODO: update MpGlue `bands2open` to `bands`
        # TODO: handle backend dependency when not using MpGlue
        self_cp = GeoArray(src.read(bands2open=list(range(1, n_layers+1))), src)
        self_cp.src = src.copy()

        if os.path.isfile(src.output_image):
            os.remove(src.output_image)

        self_cp = self._attach_funcs(self_cp)
        self_cp.set_no_data(self.no_data)

        try:
            gdal.Unlink(src.output_image)
        except:
            pass

        src = None

        return self_cp

    def _attach_funcs(self, self_cp):

        self_cp.src._create = self.src._create
        self_cp.src._warp = self.src._warp
        self_cp.src._transform = self.src._transform
        self_cp.src._nd_to_rgb = self.src._nd_to_rgb
        self_cp.src._get_xy_offsets = self.src._get_xy_offsets

        return self_cp

    def _get_min_overlap(self, extent):

        """
        Gets the minimum overlap extent
        """

        left = max(self.extent[0], extent[0])
        right = min(self.extent[1], extent[1])
        top = min(self.extent[2], extent[2])
        bottom = max(self.extent[3], extent[3])

        return left, right, top, bottom

    @staticmethod
    def _do_slice(slice_a, slice_b, operator):

        # Force to NumPy arrays to avoid recursion
        if operator == 'add':
            result = np.array(slice_a) + np.array(slice_b)
        elif operator == 'subtract':
            result = np.array(slice_a) - np.array(slice_b)
        elif operator == 'multiply':
            result = np.array(slice_a) * np.array(slice_b)

        return result

    def _get_slices(self, garray, operator, how):

        """
        Gets union slice of two arrays

        Args:
            garray (GeoArray)
            operator (str)
            how (str)
        """

        # Find the overlap
        left, right, top, bottom = self._get_min_overlap(garray.extent)

        nrows = int((top - bottom) / self.cell_y)
        ncols = int((right - left) / self.cell_y)

        extent_list = [left, top, right, bottom, self.cell_x, self.cell_y]

        l_a, t_a = self.src._get_xy_offsets(image_list=extent_list,
                                            x=self.left,
                                            y=self.top,
                                            check_position=False)[2:]

        l_b, t_b = self.src._get_xy_offsets(image_list=extent_list,
                                            x=garray.left,
                                            y=garray.top,
                                            check_position=False)[2:]

        if self.layers > 1:

            slice_a = self[:, t_a:t_a + nrows, l_a:l_a + ncols]
            slice_b = garray[:, t_b:t_b + nrows, l_b:l_b + ncols]

            result = self._do_slice(slice_a, slice_b, operator)

            if how == 'extent':
                self[:, t_a:t_a+nrows, l_a:l_a+ncols] = result
                result = self
            elif how == 'union':
                
                # TODO: combine both extents
                pass
                
            elif how == 'intersection':
                pass

        else:

            slice_a = self[t_a:t_a + nrows, l_a:l_a + ncols]
            slice_b = garray[t_b:t_b + nrows, l_b:l_b + ncols]

            result = self._do_slice(slice_a, slice_b, operator)

            if how == 'extent':
                self[t_a:t_a+nrows, l_a:l_a+ncols] = result
                result = self
            elif how == 'union':
                pass
            elif how == 'intersection':
                pass

        src = self.src.copy()

        src.left = left
        src.right = right
        src.top = top
        src.bottom = bottom

        result = GeoArray(result, src)
        result.set_no_data(self.no_data)

        return result

    def geo_add(self, garray, how='extent'):

        """
        Adds GeoArrays
        
        Example:
            >>> result = garray.geo_add(other_garray)

        Args:
            garray (GeoArray)
            how (Optional[str]): Choices are ['extent', 'intersection', 'union'].

                'extent': Use the extent of `self`.
                'intersection': Use the intersection between `self` and `garray`.
                'union': Use the union (extent of `self` + extent of `garray`) between `self` and `garray`.

        Returns:
            GeoArray
        """

        return self._get_slices(garray, 'add', how)

    def geo_subtract(self, garray, how='extent'):

        """
        Subtracts GeoArrays

        Args:
            garray (GeoArray)
            how (Optional[str]): Choices are ['extent', 'intersection', 'union'].

                'extent': Use the extent of `self`.
                'intersection': Use the intersection between `self` and `garray`.
                'union': Use the union (extent of `self` + extent of `garray`) between `self` and `garray`.

        Returns:
            GeoArray
        """

        return self._get_slices(garray, 'subtract', how)

    def geo_multiply(self, garray, how='extent'):

        """
        Multiplies GeoArrays
        
        Args:
            garray (GeoArray)
            how (Optional[str]): Choices are ['extent', 'intersection', 'union'].

                'extent': Use the extent of `self`.
                'intersection': Use the intersection between `self` and `garray`.
                'union': Use the union (extent of `self` + extent of `garray`) between `self` and `garray`.

        Returns:
            GeoArray
        """

        return self._get_slices(garray, 'multiply', how)

    def mask(self, mask_array):

        """
        Masks the GeoArray with a secondary geo-array

        Args:
            mask_array (GeoArray)
            
        Example:
            >>> garray.set_no_data(0)
            >>> masked = garray.mask(mask_array)
            
        Returns:
            GeoArray, where `mask_array` locations == `no data`.
        """

        left, right, top, bottom = self._get_min_overlap(mask_array.extent)

        extent_list = [left, top, right, bottom, self.cell_x, self.cell_y]

        x_offset, y_offset = self.src._get_xy_offsets(image_list=extent_list,
                                                      x=self.left,
                                                      y=self.top,
                                                      check_position=False)[2:]

        if self.layers > 1:
            self[:, y_offset:y_offset+mask_array.rows, x_offset:x_offset+mask_array.columns] = self.no_data
        else:
            self[y_offset:y_offset+mask_array.rows, x_offset:x_offset+mask_array.columns] = self.no_data

        return self

    def to_coordinates(self):

        """
        Creates x,y coordinate indices

        Example:
            >>> x, y = geoarray.to_coordinates()
            
        Returns:
            x (GeoArray), y (GeoArray)
        """

        # Create the longitudes
        x_coordinates = np.arange(self.left, self.right, self.cell_y)
        x_coordinates = np.tile(x_coordinates, self.rows).reshape(self.rows, self.columns)

        # Create latitudes
        y_coordinates = np.arange(self.top, self.bottom, self.cell_x).reshape(self.rows, 1)
        y_coordinates = np.tile(y_coordinates, self.columns)

        return x_coordinates, y_coordinates

    def to_raster(self, file_name, **kwargs):

        """
        Writes an array to a raster file

        Args:
            file_name (str)
            kwargs (dict)

        Example:
            >>> geoarray.to_raster('image.tif')
            
        Returns:
            None
        """

        self.src.update_info(bands=self.layers,
                             rows=self.rows,
                             cols=self.columns,
                             left=self.left,
                             top=self.top)

        out_rst = self.src._create(file_name,
                                   self.src,
                                   **kwargs)

        if self.layers == 1:
            out_rst.write_array(self, band=1)
        else:

            for n_band in range(1, self.layers+1):
                out_rst.write_array(self[n_band-1], band=n_band)

        out_rst.close_file()
        out_rst = None

    def _transform_plot_coords(self):

        in_sr = osr.SpatialReference()
        in_sr.ImportFromWkt(self.crs)
        in_proj = in_sr.ExportToProj4()

        out_sr = osr.SpatialReference()
        out_sr.ImportFromEPSG(4326)
        out_proj = out_sr.ExportToProj4()

        ptr = self.src._transform(self.left, self.top, in_proj, out_proj)
        im_left_crs, im_top_crs = ptr.x_transform, ptr.y_transform

        ptr = self.src._transform(self.right, self.bottom, in_proj, out_proj)
        im_right_crs, im_bottom_crs = ptr.x_transform, ptr.y_transform

        return [im_left_crs, im_right_crs, im_top_crs, im_bottom_crs]

    def show(self, bands=None, scale_factor=1.0, cmap=None, percentiles=(5, 95)):

        """
        Plots the array

        Args:
            bands (Optional[int or list])
            scale_factor (Optional[float])
            cmap (Optional[str])
            percentiles (Optional[tuple])
            
        Returns:
            None
        """

        plt.rcParams['figure.figsize'] = 3, 3
        plt.rcParams['axes.titlesize'] = 5
        plt.rcParams['axes.titlepad'] = 5
        plt.rcParams['axes.grid'] = False
        plt.rcParams['axes.spines.left'] = False
        plt.rcParams['axes.spines.top'] = False
        plt.rcParams['axes.spines.right'] = False
        plt.rcParams['axes.spines.bottom'] = False
        plt.rcParams['xtick.top'] = True
        plt.rcParams['ytick.right'] = True
        plt.rcParams['xtick.direction'] = 'in'
        plt.rcParams['ytick.direction'] = 'in'
        plt.rcParams['xtick.color'] = 'none'
        plt.rcParams['ytick.color'] = 'none'
        plt.rcParams['figure.dpi'] = 300
        plt.rcParams['savefig.bbox'] = 'tight'
        plt.rcParams['savefig.pad_inches'] = 0.5

        extent = self._transform_plot_coords()

        crs = ccrs.PlateCarree()

        fig = plt.figure()
        ax = fig.add_subplot(111, projection=crs)

        gkwargs = dict(color='white',
                       linewidth=0.1,
                       linestyle='--',
                       draw_labels=True)

        crskwargs = dict(origin='upper',
                         extent=extent,
                         transform=crs)

        if isinstance(bands, list):
            rgb = self[np.array(bands, dtype='int64')-1]
        elif isinstance(bands, int):
            rgb = self[bands-1]
        else:
            rgb = self.copy()

        rgb = self._scale_array(rgb, scale_factor, percentiles)

        rgb = np.ma.masked_where(rgb == 0, rgb)

        if (self.layers == 3) or isinstance(bands, list):
            cmap = None

        ax.imshow(rgb,
                  interpolation='nearest',
                  cmap=cmap,
                  **crskwargs)

        ax.outline_patch.set_linewidth(0)
        ax = self._set_grids(ax, **gkwargs)

        plt.tight_layout(pad=0.5)

        plt.show()

    def _scale_array(self, rgb, scale_factor, percentiles):

        """
        Scales and adjusts values for display

        Args:
            rgb (ndarray)
            scale_factor (float)
            percentiles (tuple)
        """

        pmin, pmax = percentiles

        rgb = np.float32(rgb)

        rgb[(rgb == self.no_data) | (rgb == 0)] = np.nan

        rgb[~np.isnan(rgb)] *= scale_factor

        if len(rgb.shape) == 2:

            rgb = rescale_intensity(rgb,
                                    in_range=(np.nanpercentile(rgb, pmin),
                                              np.nanpercentile(rgb, pmax)),
                                    out_range=(0, 1))

        else:

            for lidx, layer in enumerate(rgb):

                rgb[lidx] = rescale_intensity(layer,
                                              in_range=(np.nanpercentile(layer, pmin),
                                                        np.nanpercentile(layer, pmax)),
                                              out_range=(0, 1))

            rgb = self.src._nd_to_rgb(rgb)

        rgb[np.isnan(rgb)] = 0

        return rgb

    @staticmethod
    def _set_grids(ax, **gkwargs):

        """
        Args:
            ax (object)
            kwargs (dict)
        """

        grids = ax.gridlines(**gkwargs)

        grids.xformatter = LONGITUDE_FORMATTER
        grids.yformatter = LATITUDE_FORMATTER

        grids.ylabel_style = {'size': 3, 'color': 'gray'}
        grids.xlabel_style = {'size': 2, 'color': 'gray', 'rotation': 45}

        grids.ylabels_left = True
        grids.ylabels_right = False
        grids.xlabels_top = False
        grids.xlabels_bottom = True

        return ax


class GeoArray(GeoMethods, np.ndarray):

    """
    A class for geo-aware NumPy arrays

    Args:
        array (ndarray)
        src (object)

    Example:
        >>> import mpglue as gl
        >>> import geowombat as gwb
        >>>
        >>> with raster_tools.ropen('image.tif') as src:
        >>>
        >>>     array = src.read()
        >>>     garray = gwb.GeoArray(array, src)
    """

    def __new__(cls, array, src, info=None):

        obj = np.asarray(array).view(cls)

        if isinstance(src, raster_tools.ropen):

            obj.lib = 'mpglue'
            obj.src = _wrap_mpglue(src)

        elif isinstance(src, rasterio.io.DatasetReader):

            obj.lib = 'rasterio'
            obj.src = _wrap_rasterio(src)

        elif isinstance(src, gdal.Dataset):

            obj.lib = 'gdal'
            obj.src = _wrap_gdal(src)

        obj.original_layers = 1

        if len(array.shape) == 2:
            obj.original_rows, obj.original_columns = array.shape
        else:
            obj.original_layers, obj.original_rows, obj.original_columns = array.shape

        obj.no_data_ = 0
        obj.info = info
        obj.layer_names = map(str, list(range(1, obj.original_layers+1)))

        return obj

    def __add__(self, other):

        if isinstance(other, GeoArray):
            return self.geo_add(other)
        else:
            return np.add(self, other)

    def __sub__(self, other):

        if isinstance(other, GeoArray):
            return self.geo_subtract(other)
        else:
            return np.subtract(self, other)

    def __mul__(self, other):

        if isinstance(other, GeoArray):
            return self.geo_multiply(other)
        else:
            return np.multiply(self, other)

    def __array_finalize__(self, obj):

        if obj is None:
            return

        self.lib = getattr(obj, 'lib', None)
        self.no_data_ = getattr(obj, 'no_data_', None)
        self.layer_names = getattr(obj, 'layer_names', None)
        self.src = getattr(obj, 'src', None)
        self.original_layers = getattr(obj, 'original_layers', None)
        self.original_rows = getattr(obj, 'original_rows', None)
        self.original_columns = getattr(obj, 'original_columns', None)


class open(GeoMethods):

    """
    A class to open and read GeoWombat GeoArrays

    Args:
        file_name (str)
        backend (Optional[str])

    Attributes:
        read
        file_name
        backend

    Example:
        >>> import geowombat as gwb
        >>>
        >>> with gwb.open('image.tif') as src:
        >>>     garray = src.read(bands=-1)
        >>>
        >>> # Set band names
        >>> with gwb.open('image.tif') as src:
        >>>     garray = src.read(names=['red', 'green', 'blue', 'nir'], bands=-1)
    """

    def __init__(self, file_name, backend='rasterio'):

        self.file_name = file_name
        self.backend = backend

    def read(self, names=None, **kwargs):

        """
        Reads an image from file

        Args:
            names (Optional[list]): A list of band names. Default is None.
            kwargs (Optional[dict]): Keyword arguments to pass to the backend I/O manager.
            
        Returns:
            GeoArray
        """

        if self.backend == 'mpglue':

            with raster_tools.ropen(self.file_name) as src:
                garray = GeoArray(src.read(**kwargs), src)

        elif self.backend == 'rasterio':

            with rasterio.open(self.file_name) as src:

                if 'window' in kwargs:

                    src.i = kwargs['window'][0][0]
                    src.j = kwargs['window'][1][0]
                    src.rrows = kwargs['window'][0][1]
                    src.ccols = kwargs['window'][1][1]

                else:

                    src.i = 0
                    src.j = 0
                    src.rrows = src.shape[0]
                    src.ccols = src.shape[1]

                garray = GeoArray(src.read(**kwargs), src)

        src = None

        if names:
            garray.set_names(names)

        return garray

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.src = None

    def __del__(self):
        self.__exit__(None, None, None)