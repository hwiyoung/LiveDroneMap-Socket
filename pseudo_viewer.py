import sys
import socket
import selectors
import types
from socket_module import receive
import json
import numpy as np
import drones
import georef_for_eo as georeferencers

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
            recv_data = sock.recv(1024)
            if recv_data:
                data.outb += recv_data
                print('received', repr(data.outb), 'from', data.addr)
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
