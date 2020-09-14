import sys
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
    print("accepted connection from", addr)
    # https://stackoverflow.com/questions/39145357/python-error-socket-error-errno-11-resource-temporarily-unavailable-when-s
    # conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel_server.register(conn, events, data=data)


def start_connections(host, port, num_conns):
    server_addr = (host, port)
    for i in range(0, num_conns):
        connid = i + 1
        print('starting connection', connid, 'to', server_addr)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.connect_ex(server_addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = types.SimpleNamespace(connid=connid, outb=b'')
        sel_client.register(sock, events, data=data)


def service_connection(key_s, mask_s, key_c, mask_c):
    sock_s = key_s.fileobj
    data_s = key_s.data
    sock_c = key_c.fileobj
    data_c = key_c.data
    if mask_s & selectors.EVENT_READ:
        try:
            taskID, frameID, latitude, longitude, altitude, roll, pitch, yaw, camera, img = receive(sock_s)
            if taskID is None:
                return

            start_time = time.time()
            # 1. Set IO
            my_drone = drones.Drones(make=camera, pre_calibrated=False)
            # my_drone = drones.Drones(make=camera, ground_height=38.0, pre_calibrated=True)  # Only for test - Jeonju

            # 2. System calibration & CCS converting
            init_eo = np.array([longitude, latitude, altitude, roll, pitch, yaw])
            if my_drone.pre_calibrated:
                init_eo[3:] *= np.pi / 180
                adjusted_eo = init_eo
            else:
                my_georeferencer = georeferencers.DirectGeoreferencer()
                adjusted_eo = my_georeferencer.georeference(my_drone, init_eo)

            # 3. Rectify
            my_rectifier = rectifiers.AverageOrthoplaneRectifier(height=my_drone.ground_height)
            bbox_wkt, orthophoto = my_rectifier.rectify(img, my_drone, adjusted_eo)

            send(frameID, taskID, frameID, 0, bbox_wkt, [], orthophoto, sock_c)  # 메타데이터 생성/ send to client
            print("Elapsed time:", format(time.time() - start_time, ".2f"))
        except Exception as e:
            print(e)
            print("closing connection to", data_s.addr)
            # sel_server.unregister(sock_s)
            # sock_s.close()
            sel_client.close()
            # sel_client.unregister(sock_c)
            # sock_c.close()


with open("config.json") as f:
    data = json.load(f)

### SERVER
SERVER_PORT = data["server"]["PORT"]
QUEUE_LIMIT = data["server"]["QUEUE_LIMIT"]     # 서버 대기 큐

lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Avoid bind() exception: OSError: [Errno 48] Address already in use
lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
lsock.bind(("", SERVER_PORT))
lsock.listen()
print("listening on", ("", SERVER_PORT))
lsock.setblocking(False)
sel_server.register(lsock, selectors.EVENT_READ, data=None)

### CLIENT
CLIENT_IP = data["client"]["IP"]
CLIENT_PORT = data["client"]["PORT"]
num_conn = data["client"]["NoC"]
start_connections(CLIENT_IP, CLIENT_PORT, num_conns=num_conn)

try:
    while True:
        events_servers = sel_server.select(timeout=None)
        events_clients = sel_client.select(timeout=None)
        for events_server, events_client in zip(events_servers, events_clients):
            key_server = events_server[0]
            mask_server = events_server[1]
            key_client = events_client[0]
            mask_client = events_client[1]
            if key_server.data is None:
                accept_wrapper(key_server.fileobj)
            else:
                service_connection(key_server, mask_server, key_client, mask_client)
        # Check for a socket being monitored to continue
        if not sel_client.get_map():
            sel_client = selectors.DefaultSelector()
            start_connections(CLIENT_IP, CLIENT_PORT, num_conns=num_conn)
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel_server.close()
    sel_client.close()
