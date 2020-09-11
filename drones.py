from abc import *
import math
import numpy as np


class Drones:
    def __init__(self, make, ground_height=0.0, pre_calibrated=False):
        if make == "FC220":  # DJI Mavic Pro
            self.sensor_width = 6.3  # mm
            self.focal_length = 0.0047  # m
            self.gsd = "auto"
            self.ground_height = ground_height  # m
            self.R_CB = np.array([[0.997391604272809, -0.0193033671589004, -0.0695511879297631],
                                  [0.0115400822765142, 0.993826984996126, -0.110339251377565],
                                  [0.0712517664845147, 0.109248816514592, 0.991457453380122]], dtype=float)
            self.manufacturer = "DJI"
            self.comb = [7, 4, 4]
            self.pre_calibrated = pre_calibrated
        elif make == "FC6310R":  # DJI Phantom4 RTK
            self.sensor_width = 13.2  # mm
            self.focal_length = 0.0088  # m
            self.gsd = "auto"
            self.ground_height = ground_height  # m
            # self.ground_height = 38.0  # m, Jeonju Worldcup
            self.R_CB = np.array([[0.992103011532570, -0.0478682839576757, -0.115932057253170],
                                  [0.0636038625107261, 0.988653550290218, 0.136083452970098],
                                  [0.108102558627082, -0.142382530141501, 0.983890772356761]], dtype=float)
            self.manufacturer = "DJI"
            self.comb = [7, 4, 4]
            self.pre_calibrated = pre_calibrated
        elif make == "FC6520":  # DJI Inspire 2
            self.sensor_width = 17.3  # mm
            self.focal_length = 0.015  # m
            self.gsd = "auto"
            self.ground_height = ground_height  # m
            self.R_CB = np.array([[0.992103011532570, -0.0478682839576757, -0.115932057253170],
                                  [0.0636038625107261, 0.988653550290218, 0.136083452970098],
                                  [0.108102558627082, -0.142382530141501, 0.983890772356761]], dtype=float)
            self.manufacturer = "DJI"
            self.comb = [7, 4, 4]
            self.pre_calibrated = pre_calibrated
        elif make == "DSC-RX100M4":  # Sony RX100M4
            self.sensor_width = 13.2  # mm
            self.focal_length = 0.0088  # m
            self.gsd = "auto"
            self.ground_height = ground_height  # m
            self.R_CB = np.array([[0.994367334553110, 0.0724297138251540, -0.0773791995884510],
                                  [-0.0736697531217240, 0.997194145601333, -0.0132892232057198],
                                  [0.0761995501871716, 0.0189148759877907, 0.996913163729740]], dtype=float)
            self.manufacturer = "Sandbox2020"
            self.comb = [7, 4, 4]
            self.pre_calibrated = pre_calibrated


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

