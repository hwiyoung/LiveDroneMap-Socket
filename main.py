from socket import *
from _thread import start_new_thread
import json
from server_func import client_thread

with open("config.json") as f:
    data = json.load(f)

SERVER_PORT = data["server"]["PORT"]
QUEUE_LIMIT = data["server"]["QUEUE_LIMIT"]     # 서버 대기 큐

CLIENT_IP = data["client"]["IP"]
CLIENT_PORT = data["client"]["PORT"]

s = socket(AF_INET, SOCK_STREAM)    # 소켓 생성 (UDP = SOCK_DGRAM, TCP = SOCK_STREAM)
s.bind(('', SERVER_PORT))           # 포트 설정
s.listen(QUEUE_LIMIT)               # 포트 ON

print('tcp echo server ready')  # 준비 완료 화면에 표시
print('wait for client ')       # 연결 대기

while True:
    try:
        c_sock, addr = s.accept()
        print('connected from {}:{}'.format(addr[0], addr[1]))

        start_new_thread(client_thread, (c_sock, ))
    except Exception:
        import traceback
        print(traceback.format_exc())

        s.listen(QUEUE_LIMIT)   # 포트 ON
        print('Re: tcp echo server ready')  # 준비 완료 화면에 표시
        print('Re: wait for client')   # 연결 대기

        c_sock, addr = s.accept()
        print('Re: connected from {}:{}'.format(addr[0], addr[1]))

        start_new_thread(client_thread, (c_sock, ))
