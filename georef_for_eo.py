from abc import ABC, abstractmethod
import math
import numpy as np


class BaseGeoreferencer(ABC):
    @abstractmethod
    def georeference(self, my_drone, init_eo):
        """
        Georeference an image using its interior orientation and initial exterior orientation.

        A developer should implement an algorithm that adjusts initial exterior orientation.

        The following data should be returned:
            1. adjusted eo = [x, y, z, omega, phi, kappa] (unit: m, radian)

        :param my_drone: A my_drone object. See drones.py for detail.
        :return: adjusted_eo
        """
        raise NotImplementedError


class DirectGeoreferencer(BaseGeoreferencer):
    def georeference(self, my_drone, init_eo):
        if my_drone.manufacturer == 'DJI':
            direct_georeferencer = DirectGeoreferencerGimbalRPY()
        elif my_drone.manufacturer == "Sandbox2020":
            direct_georeferencer = DirectGeoreferencerSB20RPY()
        else:
            direct_georeferencer = DirectGeoreferencerFlightRPY()
        res = direct_georeferencer.georeference(my_drone, init_eo)
        return res


class DirectGeoreferencerFlightRPY(BaseGeoreferencer):
    def georeference(self, my_drone, init_eo):
        init_eo[3:] = init_eo[3:] * math.pi / 180
        R_ypr = self.__A2R_Multi(init_eo[5], init_eo[4], init_eo[3], my_drone.comb)
        R_opk = R_ypr.dot(my_drone.R_CB)
        adjusted_opk = self.__R2A_OPK(R_opk)
        adjusted_eo = np.array([init_eo[:3], adjusted_opk]).ravel()
        return adjusted_eo

    def __A2R_Multi(self, y, p, r, comb):
        #clockwise or counterclockwise
        tmp = comb[0] - 1
        option = np.zeros(3)
        for n in [0, 1, 2]:
            option[n] = np.mod(tmp, 2)  # get a remainder
            tmp = np.fix(tmp/2)         # Round Toward Zero
        if option[2] != 0:
            y = -y
        if option[1] != 0:
            p = -p
        if option[0] != 0:
            r = -r

        #angle combination
        if comb[1]-1 == 0:
            om = y
            ph = p
            kp = r
        elif comb[1]-1 == 1:
            om = y
            ph = r
            kp = p
        elif comb[1]-1 == 2:
            om = p
            ph = y
            kp = r
        elif comb[1]-1 == 3:
            om = p
            ph = r
            kp = y
        elif comb[1]-1 == 4:
            om = r
            ph = y
            kp = p
        elif comb[1]-1 == 5:
            om = r
            ph = p
            kp = y

        # matrix combination
        Rx = np.array([[1, 0, 0],
                       [0, math.cos(om), -math.sin(om)],
                       [0, math.sin(om), math.cos(om)]], dtype=float)
        Ry = np.array([[math.cos(ph), 0, math.sin(ph)],
                       [0, 1, 0],
                       [-math.sin(ph), 0, math.cos(ph)]], dtype=float)
        Rz = np.array([[math.cos(kp), -math.sin(kp), 0],
                       [math.sin(kp), math.cos(kp), 0],
                       [0, 0, 1]], dtype=float)

        if comb[2] - 1 == 0:
            Rot_ypr = np.linalg.multi_dot([Rx, Ry, Rz])
        elif comb[2] - 1 == 1:
            Rot_ypr = np.linalg.multi_dot([Rx, Rz, Ry])
        elif comb[2] - 1 == 2:
            Rot_ypr = np.linalg.multi_dot([Ry, Rx, Rz])
        elif comb[2] - 1 == 3:
            Rot_ypr = np.linalg.multi_dot([Ry, Rz, Rx])
        elif comb[2] - 1 == 4:
            Rot_ypr = np.linalg.multi_dot([Rz, Rx, Ry])
        elif comb[2] - 1 == 5:
            Rot_ypr = np.linalg.multi_dot([Rz, Ry, Rx])

        return Rot_ypr

    def __R2A_OPK(self, Rot_opk):
        s_ph = Rot_opk[0, 2]
        temp = (1 + s_ph) * (1 - s_ph)
        c_ph1 = math.sqrt(temp)
        c_ph2 = - math.sqrt(temp)

        omega = math.atan2(-Rot_opk[1, 2], Rot_opk[2, 2])
        phi = math.atan2(s_ph, c_ph1)
        kappa = math.atan2(-Rot_opk[0, 1], Rot_opk[0, 0])

        return [omega, phi, kappa]


class DirectGeoreferencerGimbalRPY(BaseGeoreferencer):
    def georeference(self, my_drone, init_eo):
        # Gimbal
        adjusted_opk = self.__rpy_to_opk(init_eo[3:])
        adjusted_eo = np.array([init_eo[:3], adjusted_opk]).ravel()
        return adjusted_eo

    def __rpy_to_opk(self, gimbal_rpy):
        roll_pitch = np.empty_like(gimbal_rpy[0:2])
        roll_pitch[0] = 90 + gimbal_rpy[1]
        if gimbal_rpy[0] < 0:
            roll_pitch[1] = 0
        else:
            roll_pitch[1] = gimbal_rpy[0]

        omega_phi = np.dot(self.rot_2d(gimbal_rpy[2] * np.pi / 180), roll_pitch.reshape(2, 1))
        kappa = -gimbal_rpy[2]
        return np.array([float(omega_phi[0, 0]), float(omega_phi[1, 0]), kappa]) * np.pi / 180

    def rot_2d(self, theta):
        # Convert the coordinate system not coordinates
        return np.array([[np.cos(theta), np.sin(theta)],
                         [-np.sin(theta), np.cos(theta)]])


class DirectGeoreferencerSB20RPY(BaseGeoreferencer):
    def georeference(self, my_drone, init_eo):
        # Gimbal
        adjusted_opk = self.__rpy_to_opk(init_eo[3:])
        adjusted_eo = np.array([init_eo[:3], adjusted_opk]).ravel()
        return adjusted_eo

    def __rpy_to_opk(self, gimbal_rpy):
        roll_pitch = np.empty_like(gimbal_rpy[0:2])
        roll_pitch[0] = gimbal_rpy[1]
        roll_pitch[1] = gimbal_rpy[0]

        yaw = gimbal_rpy[2] + 90
        omega_phi = np.dot(self.rot_2d(yaw * np.pi / 180), roll_pitch.reshape(2, 1))
        kappa = -yaw
        return np.array([float(omega_phi[0, 0]), float(omega_phi[1, 0]), kappa]) * np.pi / 180

    def rot_2d(self, theta):
        # Convert the coordinate system not coordinates
        return np.array([[np.cos(theta), np.sin(theta)],
                         [-np.sin(theta), np.cos(theta)]])
