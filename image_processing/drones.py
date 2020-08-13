import re
import numpy as np
import pyexiv2
from abc import ABC, abstractmethod
import PIL.Image
import logging


def extract_info_decorator(func):
    def wrapper(*args, **kwargs):
        # Things to do before running extract_info
        self = args[0]

        # Run extract_info function
        func(*args, **kwargs)

        # Things to do after running extract_info
        self.io = {
            'focal_length': self.focal_length,
            'sensor_width': self.sensor_width,
            'R_CB': self.r_cb,
            'comb': self.comb,
            'orientation': self.orientation
        }  # Set io
        self.init_eo = np.array(
            [self.longitude, self.latitude, self.altitude, self.roll, self.pitch, self.yaw])  # Set init_eo

        # Assert if the variables are None
        try:
            for key in self.io.keys():
                assert self.io[key] is not None
        except AssertionError as err:
            logging.error('Assertion error: %s is empty!' % key)
            raise err
        try:
            for value in self.init_eo:
                assert value is not None
        except AssertionError as err:
            logging.error('Assertion error: init_eo is empty!')
            raise err
        try:
            assert self.manufacturer is not None
        except AssertionError as err:
            logging.error('Assertion error: name of the manufacturer empty!')
            raise err

        return self.io, self.init_eo
    return wrapper


class BaseDrone(ABC):
    def __init__(self):
        self.io = None
        self.init_eo = None
        self.manufacturer = None
        self.focal_length = None
        self.sensor_width = None
        self.r_cb = None
        self.comb = None
        self.orientation = 0
        self.longitude = None
        self.latitude = None
        self.altitude = None
        self.roll = None
        self.pitch = None
        self.yaw = None

    def convert_dms_to_deg(self, dms):
        def convert_fractions_to_float(fraction):
            return fraction.numerator / fraction.denominator
        d = convert_fractions_to_float(dms[0])
        m = convert_fractions_to_float(dms[1]) / 60
        s = convert_fractions_to_float(dms[2]) / 3600
        deg = d + m + s
        return deg

    def convert_dms_to_deg(self, dms):
        dms_split = dms.split(" ")
        d = self.convert_string_to_float(dms_split[0])
        m = self.convert_string_to_float(dms_split[1]) / 60
        s = self.convert_string_to_float(dms_split[2]) / 3600
        deg = d + m + s
        return deg

    def convert_string_to_float(self, string):
        str_split = string.split('/')
        return int(str_split[0]) / int(str_split[1])  # unit: mm

    @abstractmethod
    def extract_info(self, img_fpath):
        """
        Extracts interior orientation and initial exterior orientation from a given image file.

        This function should be DECORATED using @extract_info_decorator.
        Nothing need to be returned, because the decorator will assert the class variables and return them.

        Fill the following class variables out using your favorite EXIF parsing library.
            self.manufacturer (string)
            self.focal_length (float, unit: m)
            self.sensor_width (float, unit: mm)
            self.r_cb (numpy array)
            self.comb (list, len=3)
            self.orientation (int, default value is 0)
            self.latitude (float, unit: DEGREE)
            self.longitude (float, unit: DEGREE)
            self.altitude (float, unit: m)
            self.roll (float, unit: DEGREE)
            self.pitch (float, unit: DEGREE)
            self.yaw (float, unit: DEGREE)

        Again, this should be decorated using @extract_info_decorator !!!

        :param img_fpath: File path of an image file
        :return: io, init_eo
        """
        raise NotImplementedError


class DJIMavicPRO(BaseDrone):
    @extract_info_decorator
    def extract_info(self, img_fpath):
        img = pyexiv2.Image(img_fpath)
        exif = img.read_exif()
        xmp = img.read_xmp()

        # Manufacturer
        self.manufacturer = 'DJI'

        # Focal length
        self.focal_length = self.convert_string_to_float(exif['Exif.Photo.FocalLength']) / 1000    # unit: m

        # Sensor width
        self.sensor_width = 6.3

        # R_CB
        self.r_cb = np.array(
            [[0.999522908670221, -0.0306726072829229, 0.00362576969600077],
             [0.0306340504219737, 0.999478109429318, 0.0102500598212956],
             [-0.00393827350051003, -0.0101340975949394, 0.999940893287084]],
            dtype=float
        )

        # Matrix combination ID
        self.comb = [7, 4, 4]

        # Orientation
        self.orientation = int(exif['Exif.Image.Orientation'])

        # Initial EO
        self.latitude = self.convert_dms_to_deg(exif["Exif.GPSInfo.GPSLatitude"])
        self.longitude = self.convert_dms_to_deg(exif["Exif.GPSInfo.GPSLongitude"])
        self.altitude = float(xmp['Xmp.drone-dji.RelativeAltitude'])
        self.roll = float(xmp['Xmp.drone-dji.GimbalRollDegree'])
        self.pitch = float(xmp['Xmp.drone-dji.GimbalPitchDegree'])
        self.yaw = float(xmp['Xmp.drone-dji.GimbalYawDegree'])


class AIMIFYFLIRDuoProRVisible(BaseDrone):
    @extract_info_decorator
    def extract_info(self, img_fpath):
        # FLIR DPR image
        img_obj = PIL.Image.open(img_fpath)
        exifmeta = img_obj.getexif()

        self.manufacturer = 'AIMIFY'

        # Interior Orientation parameters
        self.focal_length = exifmeta.get(37386)[0] / exifmeta.get(37386)[1] / 1000
        self.r_cb = np.array(
            [[0.998462934306642, -0.0551774433308000, -0.00521714129071994],
             [-0.00597304747229945, -0.0135435197840377, -0.999890441886386],
             [0.0551007397379077, 0.998384706823645, -0.0138522799928253]],
            dtype=float
        )
        self.comb = [5, 4, 5]
        self.sensor_width = 10.88

        # Exterior Orientation parameters
        # Location Parsing : FLIR DPR key LOCATION KEY = 34853
        GPS_key = 34853
        GPS_Lati_meta = exifmeta.get(GPS_key)[2]
        GPS_Long_meta = exifmeta.get(GPS_key)[4]
        GPS_Alti_meta = exifmeta.get(GPS_key)[6]
        self.latitude = GPS_Lati_meta[0][0] / GPS_Lati_meta[0][1] + \
                   GPS_Lati_meta[1][0] / GPS_Lati_meta[1][1] / 60 + \
                   GPS_Lati_meta[2][0] / GPS_Lati_meta[2][1] / 3600
        self.longitude = GPS_Long_meta[0][0] / GPS_Long_meta[0][1] + \
                   GPS_Long_meta[1][0] / GPS_Long_meta[1][1] / 60 + \
                   GPS_Long_meta[2][0] / GPS_Long_meta[2][1] / 3600
        self.altitude = GPS_Alti_meta[0] / GPS_Alti_meta[1]

        # Position Parsing : FLIR DPR key POSE KEY = 700
        YPR_key = 700
        YPR_meta = exifmeta.get(YPR_key)
        for yrp in ["Yaw", "Roll", "Pitch"]:
            target = "<Camera:" + yrp + ">(.*?)/100"
            m = re.search(target, str(YPR_meta))
            if yrp == "Yaw":
                self.yaw = eval(m.group()[12:])
            elif yrp == "Roll":
                self.roll = eval(m.group()[13:])
            elif yrp == "Pitch":
                self.pitch = eval(m.group()[14:])


class AIMIFYFLIRDuoProRThermal(BaseDrone):
    @extract_info_decorator
    def extract_info(self, img_fpath):
        # TODO: [minpkang] FLIR Duo Pro R 메타데이터 파싱 - 열영상
        self.manufacturer = None
        self.focal_length = None
        self.sensor_width = None
        self.r_cb = None
        self.comb = None
        self.orientation = 0
        self.longitude = None
        self.latitude = None
        self.altitude = None
        self.roll = None
        self.pitch = None
        self.yaw = None
        raise NotImplementedError  # TODO: [minpkang] 구현 완료 후 예외 발생 지울 것!


if __name__ == '__main__':
    my_drone = DJIMavicPRO()
    my_drone.extract_info('test_data/DJIMavicPRO.JPG')
    print(my_drone.io)
    print(my_drone.init_eo)

    my_drone = AIMIFYFLIRDuoProRVisible()
    my_drone.extract_info('test_data/FLIRDuoProR.JPG')
    print(my_drone.io)
    print(my_drone.init_eo)
