import socket
import selectors
import types
from socket_module import receive
import json
import numpy as np
import cv2

sel = selectors.DefaultSelector()


def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    print("accepted connection from", addr)
    # https://stackoverflow.com/questions/39145357/python-error-socket-error-errno-11-resource-temporarily-unavailable-when-s
    # conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data=data)


def service_connection(key, mask):
    sock = key.fileobj
    data = key.data
    if mask & selectors.EVENT_READ:
        try:
            print("receiving...")
            # recv_data = sock.recv(1024)
            recv_data = receive(sock)
            if recv_data:
                data.outb += recv_data
            else:
                print("closing connection to", data.addr)
                sel.unregister(sock)
                sock.close()
        ########################
        except Exception as e:
            print(e)
            print("closing connection to", data.addr)
            sel.unregister(sock)
            sock.close()
        ########################
    if mask & selectors.EVENT_WRITE:
        if data.outb:
            print("echoing data from", data.addr)


def receive(c_sock):
    tag = c_sock.recv(4)
    full_length = c_sock.recv(4)
    full_length = np.frombuffer(full_length, dtype="int32")[0]
    metadata_length = c_sock.recv(4)
    metadata_length = np.frombuffer(metadata_length, dtype="int32")[0]
    orthophoto_length = c_sock.recv(4)
    orthophoto_length = np.frombuffer(orthophoto_length, dtype="int32")[0]

    metadata = c_sock.recv(metadata_length)
    my_json = metadata.decode('utf8').replace("'", '"')
    data = json.loads(my_json)

    byteBuff = b''
    while len(byteBuff) < orthophoto_length:
        byteBuff += c_sock.recv(orthophoto_length - len(byteBuff))
    orthophoto = np.frombuffer(byteBuff, dtype="uint8")
    if len(byteBuff) == 0:
        return

    decode_img = cv2.imdecode(orthophoto, -1)
    cv2.imwrite(data["uid"] + ".png", decode_img)

    print(tag, full_length, metadata_length, orthophoto_length)

    return tag


### SERVER
SERVER_PORT = 57821
QUEUE_LIMIT = 5     # 서버 대기 큐

lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Avoid bind() exception: OSError: [Errno 48] Address already in use
lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
lsock.bind(("", SERVER_PORT))
lsock.listen()
print("listening on", ("", SERVER_PORT))
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)


try:
    while True:
        events = sel.select(timeout=None)
        for key, mask in events:
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                service_connection(key, mask)
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel.close()
