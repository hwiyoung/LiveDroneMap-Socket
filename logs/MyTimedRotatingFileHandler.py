try:
    import codecs
except ImportError:
    codecs = None
import logging.handlers
import time
import datetime as d



class MyTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
  def __init__(self,dir_log):
   self.dir_log = dir_log
   now = d.datetime.now()
   today = now.strftime("%Y%m%d")
   filename =  self.dir_log + today
   logging.handlers.TimedRotatingFileHandler.__init__(self,dir_log, when='midnight', interval=1, backupCount=0, encoding=None)

  def doRollover(self):
   self.stream.close()

   t = self.rolloverAt - self.interval
   timeTuple = time.localtime(t)
   self.baseFilename = self.dir_log+time.strftime("%m%d%Y")
   if self.encoding:
     self.stream = codecs.open(self.baseFilename, 'w', self.encoding)
   else:
     self.stream = open(self.baseFilename, 'w')
   self.rolloverAt = self.rolloverAt + self.interval