# Originated from https://blog.naver.com/chandong83/221194085638
from socket import *
import cv2
import numpy as np
import uuid
from _thread import start_new_thread
import json
import pyexiv2


def write_image(img, frameID):
    img_decode = cv2.imdecode(img, cv2.IMREAD_COLOR)
    cv2.imwrite(str(frameID) + ".jpg", img_decode)
    print(str(frameID) + ".jpg")


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

    # jsonObject
    imageBinaryLength = c_sock.recv(4)
    imageBinaryLength = np.frombuffer(imageBinaryLength, dtype="int32")[0]

    byteBuff = b''
    while len(byteBuff) < imageBinaryLength:
        byteBuff += c_sock.recv(imageBinaryLength - len(byteBuff))
    nparr = np.frombuffer(byteBuff, dtype="uint8")
    if len(byteBuff) == 0:
        return

    metadata = pyexiv2.ImageData(byteBuff)
    exif = metadata.read_exif()
    xmp = metadata.read_xmp()
    print(exif)
    print(xmp)
    print(exif['Exif.Image.Orientation'])

    print(timeStamp, payloadLength, taskID, frameID, latitude, longitude, altitude, accuracy, jsonDataSize,
          data["roll"], data["pitch"], data["yaw"])

    # print('read data {}, length {}'.format(readBuf, len(readBuf)))
    # c_sock.send(readBuf)
    c_sock.send(b"Done")

    write_image(nparr, frameID)


# https://stackoverflow.com/questions/26445331/how-can-i-have-multiple-clients-on-a-tcp-python-chat-server
def client_thread(c_sock):
    c_sock.send(b"Welcome to the Server. Type messages and press enter to send.\n")

    i = 0
    while True:
        receive(c_sock)
        i += 1
        print("Connected!", i)
    c_sock.close()


ECHO_PORT = 9190    # ECHO_PORT 기본 포트
QUEUE_LIMIT = 5     # 서버 대기 큐
s = socket(AF_INET, SOCK_STREAM)    # 소켓 생성 (UDP = SOCK_DGRAM, TCP = SOCK_STREAM)
s.bind(('', ECHO_PORT))     # 포트 설정
s.listen(QUEUE_LIMIT)       # 포트 ON

print('tcp echo server ready')  # 준비 완료 화면에 표시
print('wait for client ')       # 연결 대기

while True:
    try:
        c_sock, addr = s.accept()
        print('connected from {}:{}'.format(addr[0], addr[1]))

        start_new_thread(client_thread, (c_sock, ))
        # receive(c_sock, write_image)
    except Exception:
        import traceback
        print(traceback.format_exc())

        s.listen(QUEUE_LIMIT)   # 포트 ON
        print('tcp echo server ready2')  # 준비 완료 화면에 표시
        print('wait for client2 ')   # 연결 대기

        c_sock, addr = s.accept()
        print('connected2 from {}:{}'.format(addr[0], addr[1]))

        start_new_thread(client_thread, (c_sock, ))
        # receive(c_sock, write_image)
