import copy
import json
import re
import traceback
from typing import Dict

import websockets


class WsServer:
    def __init__(self, websocket, wsPath):
        self.websocket = websocket
        self.path = wsPath
        self.address = self.websocket.remote_address

        self.globalDataFolder = None

        self.context = {}
        self.dataFolder = None
        self.user = None
        self.recycleBin = None

        self.routeTable = {}
        self.logger = None

    class AuthenticationException(Exception):
        def __init__(self, message, user, password):
            Exception.__init__(self)
            self.message = message
            self.user = user
            self.password = password

    class IllegalRequestException(Exception):
        def __init__(self, path):
            Exception.__init__(self)
            self.path = path

    def addRouteRule(self, actionName: str, callback):
        self.routeTable[actionName] = callback

    def checkIllegalRequest(self, relPath: str):
        target = self.dataFolder.append(relPath)
        realRelPath = target.relPath(self.dataFolder)

        if realRelPath.startswith(".."):
            raise self.IllegalRequestException(realRelPath)

        return realRelPath

    async def showAlert(self, message: str):
        await self.sendMessage({"action": "alert", "content": message})

    async def bubble(self, message: str, duration=1500):
        await self.sendMessage({"action": "bubble", "content": message, "time": duration})

    async def sendMessage(self, message: Dict):
        await self.websocket.send(json.dumps(message))

    async def getMessage(self):
        return json.loads(await self.websocket.recv())

    async def authenticate(self):
        message = await self.getMessage()
        Pass = True

        # 验证协议
        Pass &= "action" in message
        Pass &= "user" in message
        Pass &= "password" in message
        Pass &= message["action"] == "auth"

        if not Pass:
            raise self.AuthenticationException("协议不规范", "_", "_")

        # 验证账号和密码
        user = message["user"]
        password = message["password"]

        if not re.match(r"^\w+$", user):
            raise self.AuthenticationException("用户名只能由数字、英文字母、下划线组成", user, password)

        self.dataFolder = self.globalDataFolder.append(user)

        if not self.dataFolder.exists and password != user:
            raise self.AuthenticationException("找不到这个用户!", user, password)

        userPreferences = self.dataFolder.append("preferences.json")

        # 创建用户(用户不存在且密码等于用户名时)
        if userPreferences.create(json.dumps({"password": user}, indent=4)):
            await self.bubble('用户已创建(密码为用户名)', 5000)
        else:
            preferences = json.loads(userPreferences.content)

            if ("password" not in preferences) or (preferences["password"] != password):
                raise self.AuthenticationException("密码不正确!", user, password)

        self.user = user
        self.recycleBin = self.dataFolder.append("RecycleBin")

        self.recycleBin.mkdirs()

    async def serve(self):
        self.logger.info(f"{self.address} has connected")

        message = None
        try:
            await self.authenticate()

            # 显示Welcome信息
            await self.bubble(f"已登录({self.user})", 4000)

            # 服务主循环
            while True:
                message = await self.getMessage()
                action = message["action"]

                # 打印一些信息
                if not (action == "write_file" or (action == "upload_file" and message["stage"] == "put_content")):
                    self.logger.info(message)

                # 如果是写文件，就把文件内容删掉再打印，不然会非常卡
                if action == "write_file":
                    obj = copy.copy(message)
                    del obj["content"]
                    self.logger.info(json.dumps(obj, ensure_ascii=False))

                # 如果包含'path'字段就需要检测越权访问了
                if "path" in message:
                    message["path"] = self.checkIllegalRequest(message["path"])

                if action in self.routeTable:
                    await self.routeTable[action](self, message)
        except websockets.exceptions.ConnectionClosedOK:
            self.logger.info(f"{self.address} has disconnected")
        except websockets.exceptions.ConnectionClosedError:
            self.logger.info(f"{self.address} has disconnected unexpectedly")
        except self.AuthenticationException as e:
            await self.showAlert(e.message)
            self.logger.warning(e.message + ",user: " + e.user + ", password: " + e.password)
        except self.IllegalRequestException as e:
            await self.showAlert("禁止越权访问")
            self.logger.critical(f"检测到越权访问: {e.path}")
        except:
            self.logger.error(message, exc_info=True)
            self.logger.error(traceback.format_exc(), exc_info=True)
        finally:
            await self.websocket.close()

            if 'fileObj' in self.context and not self.context["fileObj"].closed:
                self.context["fileObj"].close()
                self.context["file"].delete()
                self.logger.warning("Release of the I/O resources by force")