import asyncio
import json
import os
import ssl
import sys
import threading

import websockets

from forwarder.Forwarder import Forwarder
from server.ResServer import ResourceServer
from server.WsServer import WsServer
from handlers.Attachments import AttachmentsHandler
from handlers.Documents import Documents
from utils.ALogger import ALogger
from utils.File import File


async def handler(websocket, wsPath):
    userData.mkdirs()

    ser = WsServer(websocket, wsPath)

    ser.globalDataFolder = userData
    ser.logger = logger

    ser.addRouteRule("upload_file", AttachmentsHandler.onUploadAttachment)
    ser.addRouteRule("attachment_list", AttachmentsHandler.onRequestAttachmentList)
    ser.addRouteRule("remove_attachment", AttachmentsHandler.onRemoveAttachment)

    ser.addRouteRule("access_path", Documents.onAccessPath)
    ser.addRouteRule("write_file", Documents.onWriteFile)
    ser.addRouteRule("delete_file", Documents.onDeleteFile)
    ser.addRouteRule("rename_file", Documents.onRenameFile)
    ser.addRouteRule("create_folder", Documents.onCreateFolder)
    ser.addRouteRule("create_file", Documents.onCreateFile)
    ser.addRouteRule("move_file", Documents.onMoveFile)
    ser.addRouteRule("copy_file", Documents.onCopyFile)

    await ser.serve()


appDir = File(os.path.split(os.path.abspath(sys.argv[0]))[0])
configs = {
    'logs_directory': 'logs',
    'forwarder_port': 800,
    'websocket_port': 58010,
    'flask_port': 58011,
    'forwarder_host': '127.0.0.1',
    'websocket_host': '0.0.0.0',
    'flask_host': '0.0.0.0',
    'data_directory': 'users',
    'frontend_directory': 'htdocs',
    'ssl_cert_file': 'domain.pem',
    'ssl_key_file': 'domain.key',

    'websocket_entry': 'ws://127.0.0.1:800'
}

configFile = File('config.json')

if configFile.exists:
    print('Load configs from '+configFile.name)
    configs = json.loads(configFile.content)

logger = ALogger(appDir[configs['logs_directory']])
forwarderPort = configs['forwarder_port']
websocketPort = configs['websocket_port']
flaskPort = configs['flask_port']
userData = appDir[configs['data_directory']]
sslCertFile = appDir[configs['ssl_cert_file']]
sslKeyFile = appDir[configs['ssl_key_file']]
frontendDir = appDir[configs['frontend_directory']]
forwarderHost = configs['forwarder_host']
flaskHost = configs['flask_host']
websocketHost = configs['websocket_host']
websocketEntry = configs['websocket_entry']

# 加载SSL证书
ssl_context = None

if sslCertFile.exists and sslKeyFile.exists:
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=sslCertFile.path, keyfile=sslKeyFile.path)
    logger.info(f"The SSL certificate has been loaded")

# 转发器
fwder = Forwarder(forwarderPort, forwarderHost, websocketPort, flaskPort, ssl_context, logger)

# Flask
rs = ResourceServer(logger, userData, staticFolder=frontendDir.path, host=flaskHost, port=flaskPort, ssl=None, websocketEntry=websocketEntry)

# WS服务器
wsServer = websockets.serve(handler, websocketHost, websocketPort, ssl=None)
eventLoop = asyncio.get_event_loop()


def websocketServerRun():
    logger.info(f"Websocket Server is listening on {websocketPort}")

    eventLoop.run_until_complete(wsServer)
    eventLoop.run_forever()


th = threading.Thread(target=websocketServerRun, daemon=True)

fwder.start()
th.start()
rs.start()

fwder.join()
