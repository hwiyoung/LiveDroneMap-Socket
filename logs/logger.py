#-*- coding: utf-8 -*-

import os
import os.path
import logging
import re
from logging.handlers import TimedRotatingFileHandler
from logs.MyTimedRotatingFileHandler import MyTimedRotatingFileHandler
from logs.file_check import file_check


# Loging Level
##########################################################################################################
# DEBUG < INFO < WARNING < ERROR < CRITICAL
# DEBUG	상세한 정보. 보통 문제를 진단할 때만 사용
# INFO	예상대로 작동하는 지에 대한 확인
# WARNING	예상치 못한 일이 발생했거나 가까운 미래에 발생할 문제(예를 들어 ‘디스크 공간 부족’)에 대한 표시.
#        소프트웨어는 여전히 예상대로 작동
# ERROR	더욱 심각한 문제로 인해, 소프트웨어가 일부 기능을 수행하지 못함
# CRITICAL	심각한 에러. 프로그램 자체가 계속 실행되지 않을 수 있음을 나타냄
##########################################################################################################

# home_dir = os.path.expanduser('~')
home_dir = os.getcwd()
# 디렉토리 경로 & 파일명 설정
# file_check.py에 설정한거랑 동일해야함!
# 폴더명앞에 .을 붙여 숨김폴더로 생성
log_dir = home_dir + '/.log'
filename = log_dir + '/logs.log'

# 폴더가 없을시 생성
if not os.path.exists(log_dir):
    os.mkdir(log_dir)
# 파일 체크
file_check()
# 기본 로거
logger = logging.getLogger(__name__)
# 2020-09-16 13:46:42,443 [    INFO] test logging 이런식으로 찍히게 해줌
formatter = logging.Formatter(u'%(asctime)s [%(levelname)s|%(filename)s:%(lineno)s] %(message)s')
# setLevel을 이용하여 특정 Login Level의 경우에만 기록되도록 할수있다.
logger.setLevel(logging.DEBUG)


#fileHandler = TimedRotatingFileHandler(filename=log_dir + '/test.log', when='midnight', interval=1, encoding='utf-8')
fileHandler = MyTimedRotatingFileHandler(filename)
fileHandler.setFormatter(formatter)
fileHandler.suffix = '%Y%m%d'
fileHandler.extMatch = re.compile(r"^\d{8}$")
fileHandler.setLevel(logging.DEBUG)
logger.addHandler(fileHandler)

# Console에 log 남기기
streamHandler = logging.StreamHandler()
streamHandler.setFormatter(formatter)
streamHandler.setLevel(logging.INFO)
logger.addHandler(streamHandler)

