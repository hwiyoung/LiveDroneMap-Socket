#-*- coding: utf-8 -*-

from logger import logger

logger.info("test logging")
logger.info(' %s test string' % 'ddd')

connection = 'connction success!'
logger.debug(' {}'.format(connection))

def test_log(num):
    cnt = num

    if cnt > 0:
        logger.critical('{}update success!.'.format(num))
    else:
        logger.error('{}update fail!.'.format(num))

test_log(3)
test_log(-2)