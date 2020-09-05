import logging
import sys
import time

from utils.File import File


class ALogger(logging.Logger):
    def __init__(self, logsFolder: File):
        super().__init__(__name__)

        logsFolder.mkdirs()

        filename = self.getFileName()
        formatter = self.getFormatter()

        self.fileHandler = logging.FileHandler(logsFolder[filename].path, encoding="utf-8")
        self.fileHandler.setLevel(logging.INFO)
        self.fileHandler.setFormatter(formatter)

        self.streamHandler = logging.StreamHandler(sys.stdout)
        self.streamHandler.setLevel(logging.INFO)
        self.streamHandler.setFormatter(formatter)

        self.addHandler(self.fileHandler)
        self.addHandler(self.streamHandler)

    @staticmethod
    def getFormatter():
        lineFormat = '[%(asctime)s %(levelname)s]: %(message)s'
        dateFormat = '%m-%d %H:%M:%S'
        return logging.Formatter(fmt=lineFormat, datefmt=dateFormat)

    @staticmethod
    def getFileName():
        currentTime = time.strftime('%Y-%m-%d-%H-%M', time.localtime(time.time()))
        return currentTime + ".log"
