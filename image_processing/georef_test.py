import numpy as np
from osgeo import ogr
from osgeo.osr import SpatialReference, CoordinateTransformation

def Rot3D(eo):
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


def projection(vertices, eo, rotation_matrix, dem):
    coord_GCS = np.dot(rotation_matrix, vertices)
    scale = (dem - eo[2]) / coord_GCS[2]

    plane_coord_GCS = scale * coord_GCS[0:2] + [[eo[0]], [eo[1]]]

    return plane_coord_GCS


def pcs2ccs(bbox_px, rows, cols, pixel_size, focal_length):
    """
    Convert pixel coordinate system to camera coordinate system
    :param bbox_px: Bounding box in pixel coordinate system, px - shape: 2 x n
    :param rows: The length of rows in pixel, px
    :param cols: The length of columns in pixel, px
    :param pixel_size: mm/px
    :param focal_length: mm
    :return: Bounding box in camera coordinate system, mm
    """
    bbox_camera = np.empty(shape=(3, bbox_px.shape[1]))

    bbox_camera[0, :] = (bbox_px[0, :] - cols / 2) * pixel_size
    bbox_camera[1, :] = -(bbox_px[1, :] - rows / 2) * pixel_size
    bbox_camera[2, :] = -focal_length

    return bbox_camera


def georef_inference(bbox_coords, rows, cols, pixel_size, focal_length, tm_eo, R_CG, ground_height):
    bbox_px = np.array(bbox_coords).reshape(len(bbox_coords)//2, 2).T

    # Convert pixel coordinate system to camera coordinate system
    # input params unit: px, px, px, mm/px, mm
    bbox_camera = pcs2ccs(bbox_px, rows, cols, pixel_size, focal_length * 1000)  # shape: 3 x bbox_point

    # Project camera coordinates to ground coordinates
    proj_coordinates = projection(bbox_camera, tm_eo, R_CG, ground_height)

    return proj_coordinates


def create_inference_metadata(object_type, boundary_image, boundary_world):
    """
    Create a metadata of **each** detected object
    :param object_type: Type of the object | int
    :param boundary: Boundary of the object in GCS - shape: 2(x, y) x points | np.array
    :return: JSON object of each detected object ... python dictionary
    """
    obj_metadata = {
        "obj_type": object_type,
        "obj_boundary_image": boundary_image
    }

    object_boundary = "POLYGON (("
    for i in range(boundary_world.shape[1]):
        object_boundary = object_boundary + str(boundary_world[0, i]) + " " + str(boundary_world[1, i]) + ", "
    object_boundary = object_boundary + str(boundary_world[0, 0]) + " " + str(boundary_world[1, 0]) + "))"
    # print("object_boundary: ", object_boundary)

    obj_metadata["obj_boundary_world"] = object_boundary  # string in wkt
    # print("obj_metadata: " ,obj_metadata)

    return obj_metadata


def geographic2plane(eo, epsg):
    # Define the Plane Coordinate System (EPSG 5186)
    plane = SpatialReference()
    plane.ImportFromEPSG(epsg)

    # Define the wgs84 system (EPSG 4326)
    geographic = SpatialReference()
    geographic.ImportFromEPSG(4326)

    coord_transformation = CoordinateTransformation(geographic, plane)

    # Check the transformation for a point close to the centre of the projected grid
    xy = coord_transformation.TransformPoint(float(eo[0]), float(eo[1]))  # The order: Lon, Lat
    return xy[0:2]
