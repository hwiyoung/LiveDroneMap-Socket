from socket import *
from _thread import start_new_thread
import json
from server_func_inference_test import client_thread

with open("config.json") as f:
    data = json.load(f)

SERVER_PORT = data["server"]["PORT"]
QUEUE_LIMIT = data["server"]["QUEUE_LIMIT"]     # 서버 대기 큐

CLIENT_IP = data["client"]["IP"]
CLIENT_PORT = data["client"]["PORT"]

server = socket(AF_INET, SOCK_STREAM)    # 소켓 생성 (UDP = SOCK_DGRAM, TCP = SOCK_STREAM)
server.bind(('', SERVER_PORT))           # 포트 설정
server.listen(QUEUE_LIMIT)               # 포트 ON

print('tcp server ready')  # 준비 완료 화면에 표시
print('wait for client ')       # 연결 대기

while True:
    try:
        s_sock, s_addr = server.accept()
        print('connected from {}:{}'.format(s_addr[0], s_addr[1]))

        start_new_thread(client_thread, (s_sock, ))
    except Exception:
        import traceback
        print(traceback.format_exc())

        server.listen(QUEUE_LIMIT)   # 포트 ON
        print('Re: tcp echo server ready')  # 준비 완료 화면에 표시
        print('Re: wait for client')   # 연결 대기

        s_sock, s_addr = server.accept()
        print('Re: connected from {}:{}'.format(s_addr[0], s_addr[1]))

        start_new_thread(client_thread, (s_sock, ))
