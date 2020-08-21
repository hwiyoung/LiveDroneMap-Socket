import numpy as np
import uuid
import json
from socket import *
from struct import *
import image_processing.drones_socket as drones
import image_processing.georeferencers_socket as georeferencers
import image_processing.rectifiers_socket as rectifiers
import logging
import cv2
import time


with open("config.json") as f:
    data = json.load(f)

SERVER_PORT = data["server"]["PORT"]
QUEUE_LIMIT = data["server"]["QUEUE_LIMIT"]     # 서버 대기 큐

CLIENT_IP = data["client"]["IP"]
CLIENT_PORT = data["client"]["PORT"]

client = socket(AF_INET, SOCK_STREAM)
client.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
client.connect((CLIENT_IP, CLIENT_PORT))


# https://stackoverflow.com/questions/55014710/zero-fill-right-shift-in-python
def zero_fill_right_shift(val, n):
    return (val >> n) if val >= 0 else ((val + 0x100000000) >> n)


def parse_header(binary_header):
    domains = [{"name": "version", "offset": 0, "length": 2, "type": "int16"},
               {"name": "messageType", "offset": 2, "length": 4, "type": "int16"},
               {"name": "ping", "offset": 6, "length": 1, "type": "boolean"},
               {"name": "pong", "offset": 7, "length": 1, "type": "boolean"},
               {"name": "countOfImages", "offset": 8, "length": 4, "type": "int16"},
               {"name": "reservation", "offset": 12, "length": 4, "type": "int16"}]
    result = []
    for domain in domains:
        dt = np.dtype(np.uint16)
        dt = dt.newbyteorder('<')
        value = zero_fill_right_shift(np.frombuffer(binary_header, dtype=dt)[0] << (16 + domain["offset"]),
                                      32 - domain["length"])
        result.append(value)

    return result


def receive(c_sock):
    binaryHeader = c_sock.recv(2)  # Read the length of header
    packetHeader = parse_header(binaryHeader)
    timeStamp = c_sock.recv(8)
    timeStamp = np.frombuffer(timeStamp, dtype="int64")[0]
    payloadLength = c_sock.recv(4)
    payloadLength = np.frombuffer(payloadLength, dtype="int32")[0]

    # https://docs.python.org/ko/3/library/uuid.html
    taskID = c_sock.recv(16)
    taskID = uuid.UUID(bytes=taskID)
    frameID = c_sock.recv(16)
    frameID = uuid.UUID(bytes=frameID)
    latitude = c_sock.recv(8)
    latitude = np.frombuffer(latitude, dtype="double")[0]
    longitude = c_sock.recv(8)
    longitude = np.frombuffer(longitude, dtype="double")[0]
    altitude = c_sock.recv(4)
    altitude = np.frombuffer(altitude, dtype="float32")[0]
    accuracy = c_sock.recv(4)
    accuracy = np.frombuffer(accuracy, dtype="float32")[0]
    jsonDataSize = c_sock.recv(4)
    jsonDataSize = np.frombuffer(jsonDataSize, dtype="int32")[0]

    jsonData = c_sock.recv(jsonDataSize)    # binary
    # https://stackoverflow.com/questions/40059654/python-convert-a-bytes-array-into-json-format
    my_json = jsonData.decode('utf8').replace("'", '"')
    # Load the JSON to a Python list & dump it back out as formatted JSON
    data = json.loads(my_json)
    dumped_json = json.dumps(data, indent=4, sort_keys=True)
    print(dumped_json)

    # jsonObject
    imageBinaryLength = c_sock.recv(4)
    imageBinaryLength = np.frombuffer(imageBinaryLength, dtype="int32")[0]

    byteBuff = b''
    while len(byteBuff) < imageBinaryLength:
        byteBuff += c_sock.recv(imageBinaryLength - len(byteBuff))
    nparr = np.frombuffer(byteBuff, dtype="uint8")
    if len(byteBuff) == 0:
        return

    print(timeStamp, payloadLength, taskID, frameID, latitude, longitude, altitude, accuracy, jsonDataSize,
          data["roll"], data["pitch"], data["yaw"])
    c_sock.send(b"Done")

    return taskID, frameID, latitude, longitude, altitude, data["roll"], data["pitch"], data["yaw"], nparr


def send(frame_id, task_id, name, img_type, img_boundary, objects, orthophoto):
    """
        Create a metadata of an orthophoto for tcp transmission
        :param uuid: uuid of the image | string
        :param uuid: task id of the image | string
        :param name: A name of the original image | string
        :param img_type: A type of the image - optical(0)/thermal(1) | int
        :param img_boundary: Boundary of the orthophoto | string in wkt
        :param objects: JSON object? array? of the detected object ... from create_obj_metadata
        :return: JSON object of the orthophoto ... python dictionary
    """
    img_metadata = {
        "uid": str(frame_id),  # string
        "task_id": str(task_id),  # string
        "img_name": str(name),  # string
        "img_type": img_type,  # int
        "img_boundary": img_boundary,  # WKT ... string
        "objects": objects
    }
    img_metadata_bytes = json.dumps(img_metadata).encode()

    print(img_metadata)

    # Write image to memory
    orthophoto_encode = cv2.imencode('.png', orthophoto)
    orthophoto_bytes = orthophoto_encode[1].tostring()

    #############################################
    # Send object information to web map viewer #
    #############################################
    full_length = len(img_metadata_bytes) + len(orthophoto_bytes)
    fmt = '<4siii' + str(len(img_metadata_bytes)) + 's' + str(len(orthophoto_bytes)) + 's'  # s: string, i: int
    data_to_send = pack(fmt, b"IPOD", full_length, len(img_metadata_bytes), len(orthophoto_bytes),
                        img_metadata_bytes, orthophoto_bytes)
    client.send(data_to_send)


# https://stackoverflow.com/questions/26445331/how-can-i-have-multiple-clients-on-a-tcp-python-chat-server
def client_thread(s_sock):
    s_sock.send(b"Welcome to the Server. Type messages and press enter to send.\n")
    while True:
        start_time = time.time()
        taskID, frameID, latitude, longitude, altitude, roll, pitch, yaw, img = receive(s_sock)
        if not taskID or not frameID or not latitude or not longitude or not altitude \
                or not roll or not pitch or not yaw:
            break

        # 1. Set IO
        my_drone = drones.DJIPhantom4RTK(pre_calibrated=True)
        # sensor_width = my_drone.sensor_width
        # focal_length = my_drone.focal_length
        # gsd = my_drone.gsd
        # ground_height = my_drone.ground_height
        # R_CB = my_drone.R_CB
        # comb = my_drone.comb
        # manufacturer = my_drone.manufacturer

        # 2. System calibration & CCS converting
        init_eo = np.array([longitude, latitude, altitude, roll, pitch, yaw])
        if my_drone.pre_calibrated:
            init_eo[3:] = init_eo[3:] * np.pi / 180
            adjusted_eo = init_eo
        else:
            my_georeferencer = georeferencers.DirectGeoreferencer()
            adjusted_eo = my_georeferencer.georeference(my_drone, init_eo)

        # 3. Rectify
        my_rectifier = rectifiers.AverageOrthoplaneRectifier(height=my_drone.ground_height)
        bbox_wkt, orthophoto = my_rectifier.rectify(img, my_drone, adjusted_eo)

        logging.info('========================================================================================')
        logging.info('========================================================================================')
        logging.info('A new image is received.')
        logging.info('File name: %s' % frameID)
        logging.info('Current Drone: %s' % my_drone.__class__.__name__)
        logging.info('========================================================================================')

        send(frameID, taskID, frameID, 0, bbox_wkt, [], orthophoto)    # 메타데이터 생성/ send to client
        print(time.time() - start_time)
    s_sock.close()
