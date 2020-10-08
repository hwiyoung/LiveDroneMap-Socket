import numpy as np
import uuid
import json
from struct import *
import logging
import cv2
import time


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
    if binaryHeader == b"":
        return
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
    # dumped_json = json.dumps(data, indent=4, sort_keys=True)
    # print(dumped_json)

    # jsonObject
    imageBinaryLength = c_sock.recv(4)
    imageBinaryLength = np.frombuffer(imageBinaryLength, dtype="int32")[0]

    byteBuff = b''
    while len(byteBuff) < imageBinaryLength:
        byteBuff += c_sock.recv(imageBinaryLength - len(byteBuff))
    nparr = np.frombuffer(byteBuff, dtype="uint8")
    if len(byteBuff) == 0:
        return

    # print(timeStamp, payloadLength, taskID, frameID, latitude, longitude, altitude, accuracy, jsonDataSize,
    #       data["roll"], data["pitch"], data["yaw"], data["exif"]["Model"])

    return taskID, frameID, latitude, longitude, altitude, \
           data["roll"], data["pitch"], data["yaw"], data["exif"]["Model"], nparr


def send(frame_id, task_id, name, img_type, img_boundary, objects, orthophoto, client):
    """
        Create a metadata of an orthophoto for tcp transmission
        :param frame_id: uuid of the image | string
        :param task_id: task id of the image | string
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

    # print(img_metadata)

    # Write image to memory
    orthophoto_encode = cv2.imencode('.png', orthophoto)
    orthophoto_bytes = orthophoto_encode[1].tostring()

    #############################################
    # Send object information to web map viewer #
    #############################################
    full_length = len(img_metadata_bytes) + len(orthophoto_bytes)
    fmt = '<4siii' + str(len(img_metadata_bytes)) + 's' + str(len(orthophoto_bytes)) + 's'  # s: string, i: int
    # print(fmt, b"IPOD", full_length, len(img_metadata_bytes), len(orthophoto_bytes),
    #                     img_metadata_bytes)
    data_to_send = pack(fmt, b"IPOD", full_length, len(img_metadata_bytes), len(orthophoto_bytes),
                        img_metadata_bytes, orthophoto_bytes)
    client.send(data_to_send)
