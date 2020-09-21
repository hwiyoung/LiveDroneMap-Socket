from abc import ABC, abstractmethod
import time
import cv2
from osgeo.osr import SpatialReference, CoordinateTransformation
from copy import copy
import numpy as np
from numba import jit
from osgeo import gdal, osr, ogr
import logging


class BaseRectifier(ABC):
    def __init__(self, height, gsd='auto'):
        """
        Initialize rectifier.
        :param height: Average height (float) or file path of heightmap (DEM).
        :param gsd: Desired ground sampling distance in meter. If 'auto', rectifier will automatically compute gsd.
        """
        self.height = height
        self.gsd = gsd

    @abstractmethod
    def rectify(self, img, my_drone, adjusted_eo):
        """
        Rectify an image using its interior orientation, adjusted exterior orientation and digital elevation model.

        A developer should implement an algorithm that rectifies an image onto a surface.

        The following data should be returned:
            1. ortho_image (numpy array)

        :param img_fpath: A path of an image.
        :param io: Interior orientation of an image retrieved using drones.BaseDrone.extract_info
        :param adjusted_eo: Adjusted exterior orientation. See eo of drones.BaseDrone.extract_info for detail.
        :param rectified_img_fpath: A path of the project folder. The results will be saved there.
        """
        raise NotImplementedError


class AverageOrthoplaneRectifier(BaseRectifier):
    def __restoreOrientation(self, image, orientation):
        if orientation == 8:
            restored_image = self.__rotate(image, -90)
        elif orientation == 6:
            restored_image = self.__rotate(image, 90)
        elif orientation == 3:
            restored_image = self.__rotate(image, 180)
        else:
            restored_image = image

        return restored_image

    def __rotate(self, image, angle):
        # https://www.pyimagesearch.com/2017/01/02/rotate-images-correctly-with-opencv-and-python/

        height = image.shape[0]
        width = image.shape[1]
        center = (width / 2, height / 2)

        # grab the rotation matrix (applying the negative of the
        # angle to rotate clockwise), then grab the sine and cosine
        # (i.e., the rotation components of the matrix)
        rotation_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        abs_cos = abs(rotation_mat[0, 0])
        abs_sin = abs(rotation_mat[0, 1])

        # compute the new bounding dimensions of the image
        bound_w = int(height * abs_sin + width * abs_cos)
        bound_h = int(height * abs_cos + width * abs_sin)

        # adjust the rotation matrix to take into account translation
        rotation_mat[0, 2] += bound_w / 2 - center[0]
        rotation_mat[1, 2] += bound_h / 2 - center[1]

        # perform the actual rotation and return the image
        rotated_mat = cv2.warpAffine(image, rotation_mat, (bound_w, bound_h))
        return rotated_mat

    def __geographic2plane(self, eo, epsg):
        # Define the Plane Coordinate System (EPSG 5186)
        plane = SpatialReference()
        plane.ImportFromEPSG(epsg)

        # Define the wgs84 system (EPSG 4326)
        geographic = SpatialReference()
        geographic.ImportFromEPSG(4326)

        coord_transformation = CoordinateTransformation(geographic, plane)

        # Check the transformation for a point close to the centre of the projected grid
        xy = coord_transformation.TransformPoint(float(eo[0]), float(eo[1]))  # The order: Lon, Lat
        eo_conv = copy(eo)
        eo_conv[0:2] = xy[0:2]
        return eo_conv

    def __Rot3D(self, eo):
        om = eo[3]
        ph = eo[4]
        kp = eo[5]

        #      | 1       0        0    |
        # Rx = | 0    cos(om)  sin(om) |
        #      | 0   -sin(om)  cos(om) |

        Rx = np.zeros(shape=(3, 3))
        cos, sin = np.cos(om), np.sin(om)

        Rx[0, 0] = 1
        Rx[1, 1] = cos
        Rx[1, 2] = sin
        Rx[2, 1] = -sin
        Rx[2, 2] = cos

        #      | cos(ph)   0  -sin(ph) |
        # Ry = |    0      1      0    |
        #      | sin(ph)   0   cos(ph) |

        Ry = np.zeros(shape=(3, 3))
        cos, sin = np.cos(ph), np.sin(ph)

        Ry[0, 0] = cos
        Ry[0, 2] = -sin
        Ry[1, 1] = 1
        Ry[2, 0] = sin
        Ry[2, 2] = cos

        #      | cos(kp)   sin(kp)   0 |
        # Rz = | -sin(kp)  cos(kp)   0 |
        #      |    0         0      1 |

        Rz = np.zeros(shape=(3, 3))
        cos, sin = np.cos(kp), np.sin(kp)

        Rz[0, 0] = cos
        Rz[0, 1] = sin
        Rz[1, 0] = -sin
        Rz[1, 1] = cos
        Rz[2, 2] = 1

        # R = Rz * Ry * Rx
        R = np.linalg.multi_dot([Rz, Ry, Rx])
        return R

    def __boundary(self, image, eo, R, dem, pixel_size, focal_length):
        inverse_R = R.transpose()

        image_vertex = self.__getVertices(image, pixel_size, focal_length)  # shape: 3 x 4

        proj_coordinates = self.__projection(image_vertex, eo, inverse_R, dem)

        bbox = np.empty(shape=(4, 1))
        bbox[0] = min(proj_coordinates[0, :])  # X min
        bbox[1] = max(proj_coordinates[0, :])  # X max
        bbox[2] = min(proj_coordinates[1, :])  # Y min
        bbox[3] = max(proj_coordinates[1, :])  # Y max

        return bbox, proj_coordinates.T

    def __getVertices(self, image, pixel_size, focal_length):
        rows = image.shape[0]
        cols = image.shape[1]

        # (1) ------------ (2)
        #  |     image      |
        #  |                |
        # (4) ------------ (3)

        vertices = np.empty(shape=(3, 4))

        vertices[0, 0] = -cols * pixel_size / 2
        vertices[1, 0] = rows * pixel_size / 2

        vertices[0, 1] = cols * pixel_size / 2
        vertices[1, 1] = rows * pixel_size / 2

        vertices[0, 2] = cols * pixel_size / 2
        vertices[1, 2] = -rows * pixel_size / 2

        vertices[0, 3] = -cols * pixel_size / 2
        vertices[1, 3] = -rows * pixel_size / 2

        vertices[2, :] = -focal_length

        return vertices

    def __projection(self, vertices, eo, rotation_matrix, dem):
        coord_GCS = np.dot(rotation_matrix, vertices)
        scale = (dem - eo[2]) / coord_GCS[2]

        plane_coord_GCS = scale * coord_GCS[0:2] + [[eo[0]], [eo[1]]]

        return plane_coord_GCS

    @staticmethod
    @jit(nopython=True)
    def __projectedCoord(boundary, boundary_rows, boundary_cols, gsd, eo, ground_height):
        proj_coords = np.empty(shape=(3, boundary_rows * boundary_cols))
        i = 0
        for row in range(boundary_rows):
            for col in range(boundary_cols):
                proj_coords[0, i] = boundary[0, 0] + col * gsd - eo[0]
                proj_coords[1, i] = boundary[3, 0] - row * gsd - eo[1]
                i += 1
        proj_coords[2, :] = ground_height - eo[2]
        return proj_coords

    def __backProjection(self, coord, R, focal_length, pixel_size, image_size):
        coord_CCS_m = np.dot(R, coord)  # unit: m     3 x (row x col)
        scale = (coord_CCS_m[2]) / (-focal_length)  # 1 x (row x col)
        plane_coord_CCS = coord_CCS_m[0:2] / scale  # 2 x (row x col)
        logging.debug(plane_coord_CCS.shape)
        logging.debug(pixel_size)
        # Convert CCS to Pixel Coordinate System
        coord_CCS_px = plane_coord_CCS / pixel_size  # unit: px
        coord_CCS_px[1] = -coord_CCS_px[1]

        coord_out = image_size[::-1] / 2 + coord_CCS_px  # 2 x (row x col)

        return coord_out

    @staticmethod
    @jit(nopython=True)
    def __resample(coord, boundary_rows, boundary_cols, image):
        # Define channels of an orthophoto
        b = np.zeros(shape=(boundary_rows, boundary_cols), dtype=np.uint8)
        g = np.zeros(shape=(boundary_rows, boundary_cols), dtype=np.uint8)
        r = np.zeros(shape=(boundary_rows, boundary_cols), dtype=np.uint8)
        a = np.zeros(shape=(boundary_rows, boundary_cols), dtype=np.uint8)

        rows = np.reshape(coord[1], (boundary_rows, boundary_cols))
        cols = np.reshape(coord[0], (boundary_rows, boundary_cols))

        rows = rows.astype(np.int16)
        # rows = np.int16(rows)
        cols = cols.astype(np.int16)

        for row in range(boundary_rows):
            for col in range(boundary_cols):
                if cols[row, col] < 0 or cols[row, col] >= image.shape[1]:
                    continue
                elif rows[row, col] < 0 or rows[row, col] >= image.shape[0]:
                    continue
                else:
                    b[row, col] = image[rows[row, col], cols[row, col]][0]
                    g[row, col] = image[rows[row, col], cols[row, col]][1]
                    r[row, col] = image[rows[row, col], cols[row, col]][2]
                    a[row, col] = 255

        return b, g, r, a

    def __createGeoTiff(self, b, g, r, a, boundary, gsd, rows, cols, dst):
        # https://stackoverflow.com/questions/33537599/how-do-i-write-create-a-geotiff-rgb-image-file-in-python
        geotransform = (boundary[0], gsd, 0, boundary[3], 0, -gsd)

        # create the 4-band(RGB+Alpha) raster file
        dst_ds = gdal.GetDriverByName('GTiff').Create(dst, cols, rows, 4, gdal.GDT_Byte)
        dst_ds.SetGeoTransform(geotransform)  # specify coords

        # Define the TM central coordinate system (EPSG 5186)
        srs = osr.SpatialReference()  # establish encoding
        srs.ImportFromEPSG(5186)

        dst_ds.SetProjection(srs.ExportToWkt())  # export coords to file
        dst_ds.GetRasterBand(1).WriteArray(r)  # write r-band to the raster
        dst_ds.GetRasterBand(2).WriteArray(g)  # write g-band to the raster
        dst_ds.GetRasterBand(3).WriteArray(b)  # write b-band to the raster
        dst_ds.GetRasterBand(4).WriteArray(a)  # write a-band to the raster

        dst_ds.FlushCache()  # write to disk
        dst_ds = None

    def __export_bbox_to_wkt(self, bbox):
        res = "POLYGON ((" + \
              str(bbox[0, 0]) + " " + str(bbox[0, 1]) + ", " + \
              str(bbox[1, 0]) + " " + str(bbox[1, 1]) + ", " + \
              str(bbox[2, 0]) + " " + str(bbox[2, 1]) + ", " + \
              str(bbox[3, 0]) + " " + str(bbox[3, 1]) + ", " + \
              str(bbox[0, 0]) + " " + str(bbox[0, 1]) + "))"
        return res

    def rectify(self, img, my_drone, adjusted_eo):
        img = cv2.imdecode(img, cv2.IMREAD_COLOR)

        # 1. Restore the image based on orientation information
        # restored_image = self.__restoreOrientation(img, io['orientation'])
        restored_image = img

        image_rows = restored_image.shape[0]
        image_cols = restored_image.shape[1]

        pixel_size = my_drone.sensor_width / image_cols  # unit: mm/px
        pixel_size = pixel_size / 1000  # unit: m/px

        logging.debug('Easting | Northing | Height | Omega | Phi | Kappa')
        converted_eo = self.__geographic2plane(adjusted_eo, 3857)
        R = self.__Rot3D(converted_eo)

        # 2. Extract a projected boundary of the image
        bbox, proj_bbox = self.__boundary(restored_image, converted_eo, R, self.height, pixel_size, my_drone.focal_length)

        if self.gsd == 'auto':
            self.gsd = (pixel_size * (converted_eo[2] - self.height)) / my_drone.focal_length  # unit: m/px
            self.gsd *= 2

        # Boundary size
        boundary_cols = int((bbox[1, 0] - bbox[0, 0]) / self.gsd)
        boundary_rows = int((bbox[3, 0] - bbox[2, 0]) / self.gsd)

        proj_coords = self.__projectedCoord(bbox, boundary_rows, boundary_cols, self.gsd, converted_eo, self.height)

        # Image size
        image_size = np.reshape(restored_image.shape[0:2], (2, 1))

        backProj_coords = self.__backProjection(proj_coords, R, my_drone.focal_length, pixel_size, image_size)

        b, g, r, a = self.__resample(backProj_coords, boundary_rows, boundary_cols, img)

        orthophoto_array = cv2.merge((b, g, r, a))

        bbox_wkt = self.__export_bbox_to_wkt(proj_bbox)

        return bbox_wkt, orthophoto_array
