import datetime as d
import os
import os.path

# home_dir = os.path.expanduser('~')
home_dir = os.getcwd()
# 디렉토리 경로 & 파일명 설정
# logger.py에 설정한거랑 동일해야함!
# 폴더명앞에 .을 붙여 숨김폴더로 생성
log_dir = home_dir + '/.log'
filename = log_dir + '/logs.log'


dir_log = filename
check = None
now = d.datetime.now()
today = now.strftime('%Y%m%d')
yesterday = int(today) - 1
filename_yesterday = dir_log + str(yesterday)
filename = dir_log + now.strftime('%Y%m%d')
filename_search = dir_log + str(yesterday)
filename_split = filename_search.split('/')
filename_check = filename_split[-1]

# log_dir = './log'

def file_check():
    for file in os.listdir(log_dir):
        if file == filename_check:
            check = 'exist'
        else:
            check = 'nonexistent'

    if check == 'exist':
        pass
    else:
        os.rename(dir_log, filename_yesterday)

