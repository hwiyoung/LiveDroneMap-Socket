import numpy as np
import uuid
import json
import image_processing.drones as drones
import image_processing.georeferencers as georeferencers
import image_processing.rectifiers as rectifiers
import logging

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
    # dumped_json = json.dumps(data, indent=4, sort_keys=True)

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

    return taskID, frameID, latitude, longitude, altitude, data["roll"], data["pitch"], data["yaw"]


def send(c_sock, uuid, task_id, name, img_type, img_boundary, objects):
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
        "uid": uuid,  # string
        "task_id": task_id,  # string
        "img_name": name,  # string
        "img_type": img_type,  # int
        "img_boundary": img_boundary,  # WKT ... string
        "objects": objects
    }

    c_sock.send(img_metadata)

    return img_metadata



# https://stackoverflow.com/questions/26445331/how-can-i-have-multiple-clients-on-a-tcp-python-chat-server
def client_thread(c_sock):
    c_sock.send(b"Welcome to the Server. Type messages and press enter to send.\n")
    while True:
        taskID, frameID, latitude, longitude, altitude, roll, pitch, yaw = receive(c_sock)
        if not taskID or not frameID or not latitude or not longitude or not altitude \
                or not roll or not pitch or not yaw:
            break

        my_drone = drones.DJIMavicPRO()     # IO만 필요
        my_georeferencer = georeferencers.DirectGeoreferencer()     # llh -> XYZ, RPY -> OPK로 변환만 하면 됨
        my_rectifier = rectifiers.AverageOrthoplaneRectifier(height=0)  # imread 필요X, bbox_wkt와 orthphoto array

        logging.info('========================================================================================')
        logging.info('========================================================================================')
        logging.info('A new image is received.')
        logging.info('File name: %s' % frameID)
        logging.info('Current Drone: %s' % my_drone.__class__.__name__)
        logging.info('Current Georeferencer: %s' % my_georeferencer.__class__.__name__)
        logging.info('Current Rectifier: %s' % my_rectifier.__class__.__name__)
        logging.info('========================================================================================')

        logging.info('Extracting information...')
        my_drone.extract_info(fpath_dict['img_orig'])

        logging.info('Georeferencing...')
        adjusted_eo = my_georeferencer.georeference(my_drone)

        logging.info('Rectifying...')
        img_rectified_fpath, _ = my_rectifier.rectify(fpath_dict['img_orig'], my_drone.io, adjusted_eo, project_path)

        send(c_sock)    # 메타데이터 생성/ send to client
    c_sock.close()
