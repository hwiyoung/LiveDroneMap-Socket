# Usage: main.py --config [config_file]

from argparse import ArgumentParser
from logs.logger import logger
import socket
import selectors
import types
from socket_module import receive, send
import json
import numpy as np
import drones
import georef_for_eo as georeferencers
import rectifiers
import time

sel_server = selectors.DefaultSelector()
sel_client = selectors.DefaultSelector()


def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    logger.info("accepted connection from (%s, %i)" % (addr[0], addr[1]))
    # https://stackoverflow.com/questions/39145357/python-error-socket-error-errno-11-resource-temporarily-unavailable-when-s
    # conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel_server.register(conn, events, data=data)


def start_connections(host, port, num_conns):
    server_addr = (host, port)
    for i in range(0, num_conns):
        connid = i + 1
        logger.info('starting connection', connid, 'to', server_addr)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.connect_ex(server_addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = types.SimpleNamespace(connid=connid, outb=b'')
        sel_client.register(sock, events, data=data)


def service_connection(key_s, mask_s, sock_c, pre_calibrated, angle_threshold, ground_height, gsd):
    sock_s = key_s.fileobj
    data_s = key_s.data
    if mask_s & selectors.EVENT_READ:
        try:
            taskID, frameID, latitude, longitude, altitude, roll, pitch, yaw, camera, img = receive(sock_s)
            if taskID is None:
                logger.debug("No received data!!!")
                return

            start_time = time.time()
            # 1. Set IO
            my_drone = drones.Drones(make=camera, pre_calibrated=pre_calibrated)

            # 2. System calibration & CCS converting
            init_eo = np.array([longitude, latitude, altitude, roll, pitch, yaw])
            if pre_calibrated:
                init_eo[3:] *= np.pi / 180
                adjusted_eo = init_eo
            else:
                my_georeferencer = georeferencers.DirectGeoreferencer()
                adjusted_eo = my_georeferencer.georeference(my_drone, init_eo)

            if abs(adjusted_eo[3]) > angle_threshold or abs(adjusted_eo[4]) > angle_threshold:
                logger.debug("Omega: %.2f, Phi: %.2f" % (adjusted_eo[3] * 180 / np.pi, adjusted_eo[3] * 180 / np.pi))
                return

            # 3. Rectify
            my_rectifier = rectifiers.AverageOrthoplaneRectifier(height=ground_height, gsd=gsd)
            bbox_wkt, orthophoto = my_rectifier.rectify(img, my_drone, adjusted_eo)
            logger.info("Processing time: %.2f s" % (time.time() - start_time))

            send(frameID, taskID, frameID, 0, bbox_wkt, [], orthophoto, sock_c)  # send to client
            logger.info("Elapsed time: %.2f s" % (time.time() - start_time))
        except Exception as e:
            print(e)
            logger.info("closing connection to (%s, %i)" % (data_s.addr[0], data_s.addr[1]))
            sock_c.close()
            global client_connection
            client_connection = 0
            sel_server.unregister(sock_s)
            sock_s.close()


"""
Start of the code
1. Parse arguments
2. Server
3. Client
4. Processing
"""
print('Usage: python main.py --config [config_file]')
parser = ArgumentParser(description="Configuration")
parser.add_argument("--config", help="the name of config file", type=str, default="config_ndmi.json")
args = parser.parse_args()
config = args.config

with open(config) as f:
    data = json.load(f)

# SERVER
SERVER_PORT = data["server"]["PORT"]
QUEUE_LIMIT = data["server"]["QUEUE_LIMIT"]  # 서버 대기 큐

lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Avoid bind() exception: OSError: [Errno 48] Address already in use
lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
lsock.bind(("", SERVER_PORT))
lsock.listen()
logger.info("listening on (\"\", %i)" % SERVER_PORT)
lsock.setblocking(False)
sel_server.register(lsock, selectors.EVENT_READ, data=None)

# CLIENT
CLIENT_IP = data["client"]["IP"]
CLIENT_PORT = data["client"]["PORT"]
num_conn = data["client"]["NoC"]
logger.info("starting connection...")
sock_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_client.connect_ex((CLIENT_IP, CLIENT_PORT))
client_connection = 1
logger.info("connected!")

# PROCESSING
pre_calibrated = eval(data["processing"]["pre_calibrated"])  # bool
angle_threshold = data["processing"]["threshold_angle"]  # deg
ground_height = data["processing"]["ground_height"]  # m
gsd = data["processing"]["gsd"]  # m/px
logger.info("Pre-calibrated: %s" % pre_calibrated)
logger.info("Threshold for angle: %.2f deg" % angle_threshold)
logger.info("Ground height: %.2f m" % ground_height)
logger.info("Ground Sampling Distance: %.2f m/px" % gsd)

try:
    while True:
        events_servers = sel_server.select(timeout=None)
        for key, mask in events_servers:
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                service_connection(key, mask, sock_client,
                                   pre_calibrated, angle_threshold * np.pi / 180, ground_height, gsd)
        # Check for a socket being monitored to continue
        if client_connection == 0:
            logger.info("starting connection...")
            sock_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_client.connect_ex((CLIENT_IP, CLIENT_PORT))
            client_connection = 1
            logger.info("connected!")
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel_server.close()
    sel_client.close()
