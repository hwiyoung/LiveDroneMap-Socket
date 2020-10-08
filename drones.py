from abc import *
import math
import numpy as np


class Drones:
    def __init__(self, make):
        if make == "FC220":  # DJI Mavic Pro
            self.sensor_width = 6.3  # mm
            self.focal_length = 0.0047  # m
            self.manufacturer = "DJI"
        elif make == "FC6310R":  # DJI Phantom4 RTK
            self.sensor_width = 13.2  # mm
            self.focal_length = 0.0088  # m
            # self.ground_height = 38.0  # m, Jeonju Worldcup
            self.manufacturer = "DJI"
        elif make == "FC6520":  # DJI Inspire 2
            self.sensor_width = 17.3  # mm
            self.focal_length = 0.015  # m
            self.manufacturer = "DJI"
        elif make == "DSC-RX100M4":  # Sony RX100M4
            self.sensor_width = 13.2  # mm
            self.focal_length = 0.0088  # m
            self.manufacturer = "Sandbox2020"
        elif make == "L1D-20c":  # DJI Mavic 2 Pro
            self.sensor_width = 13.2  # mm
            self.focal_length = 0.01026  # m
            self.manufacturer = "DJI"


# class SONY_ILCE_QX1:
#     def __init__(self, pre_calibrated=False):
#         self.sensor_width = 23.5  # mm
#         self.focal_length = 0.02  # m
#         self.gsd = "auto"
#         self.ground_height = 0.0  # m
#         self.R_CB = np.array([[0.994367334553110, 0.0724297138251540, -0.0773791995884510],
#                               [-0.0736697531217240, 0.997194145601333, -0.0132892232057198],
#                               [0.0761995501871716, 0.0189148759877907, 0.996913163729740]], dtype=float)
#         self.manufacturer = "Sony"
#         self.comb = [7, 4, 4]
#         self.pre_calibrated = pre_calibrated

