import json
import logging
import re
import tempfile
import time
from threading import Thread

from PIL import Image
from flask import Flask, send_from_directory
from flask import request
from flask_cors import CORS
from werkzeug.routing import BaseConverter

from utils.File import File


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


class ResourceServer(Thread):
    def __init__(self, logger, dataFolder: File, staticFolder: str, host: str, port: int, ssl, websocketEntry: str):
        super().__init__()
        self.setName("ResourceServer")
        self.setDaemon(True)

        self.logger = logger
        self.dataFolder = dataFolder
        self.staticFolder = staticFolder
        self.host = host
        self.port = port
        self.ssl = ssl
        self.websocketEntry = websocketEntry

        self.tempDir = File(tempfile.mkdtemp())
        self.tempDirClean = Thread(target=self.cleanTask, daemon=True)
        self.cleanTaskList = []

    def cleanTask(self):
        self.logger.info('ThumbnailDirectory: ' + self.tempDir.path)

        while True:
            dl = []

            for task in self.cleanTaskList:
                file: File = task[0]
                Time = task[1]
                now = time.time() * 1000

                if now >= Time:
                    dl.append(task)
                    file.delete()

            for df in dl:
                self.cleanTaskList.remove(df)

            time.sleep(10)

    def addCleanTask(self, file: File, delay):
        now = time.time() * 1000

        self.cleanTaskList.append([file, now + delay])

    def run(self):
        self.tempDirClean.start()
        td = self.tempDir

        self.logger.info(f"Flask is listening on {self.port}")

        # static_url_path: 访问前缀, static_folder: 静态资源文件夹路径
        app = Flask(__name__, static_url_path="", static_folder=self.staticFolder)

        app.url_map.converters['reg'] = RegexConverter

        CORS(app, resources=r'/*')

        @app.route("/_/<user>/<reg('.+'):path>")
        def resource(user, path):

            logger = self.logger
            dataFolder = self.dataFolder
            path = user + "/" + path

            if not dataFolder.append(user).exists:
                logger.critical(f"尝试访问未知用户: {user}")
                return "404 Not Found", 404

            target = dataFolder.append(path)
            realRelPath = target.relPath(dataFolder)

            if realRelPath.startswith(".."):
                logger.critical(f"尝试越权访问: {realRelPath}")
                return "403 Forbidden", 403

            if not re.match(r"^.+\.assets/.+$", path):
                logger.critical(f"不合法的访问: {path}")
                return "404 Not Found", 404

            file = dataFolder.append(realRelPath)

            if not file.exists:
                logger.critical(f"尝试访问不存在的文件: {file.path}")
                return "404 Not Found", 404

            isThub = request.args.get('thub') == 'true'

            if isThub:
                thubFile = td.append(file.sha1[:16] + '.png')

                if thubFile.name not in td:
                    im = Image.open(file.path)
                    im.thumbnail((64, 64))
                    im.save(thubFile.path, 'PNG')
                    self.addCleanTask(thubFile, 15*60*1000)

                return send_from_directory(td.path, thubFile.name, as_attachment=False)

            return send_from_directory(file.parent.path, file.name, as_attachment=False)

        @app.route("/default")
        def default():
            return json.dumps([self.websocketEntry])

        @app.route("/")
        def index():
            return app.send_static_file("index.html")

        app.run(host=self.host, port=self.port, ssl_context=self.ssl)
