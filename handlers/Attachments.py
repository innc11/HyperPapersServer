import base64
import re
from typing import Dict

from server.WsServer import WsServer
from utils.File import File


class AttachmentsHandler:
    @staticmethod
    async def respondAttachmentList(service: WsServer, path: str):
        target: File = service.dataFolder.append(path)
        attchDir = target.parent.append(re.sub(r"\.md$", "", target.name) + ".assets")

        attachments = []

        if attchDir.exists:
            attachments = [(f.name, f.length) for f in attchDir]

        await service.sendMessage({
            "action": "attachment_list",
            "path": path,
            "attachments": attachments
        })

    @staticmethod
    async def onRequestAttachmentList(service: WsServer, message: Dict):
        await AttachmentsHandler.respondAttachmentList(service, message["path"])

    @staticmethod
    async def onUploadAttachment(service: WsServer, message: Dict):
        ctx = service.context
        stage = message['stage']

        if stage == "open_file":
            if 'fileObj' not in ctx or ctx["fileObj"].closed:
                fileName = message['attachment']
                target = service.dataFolder.append(message["path"])

                attachDir = target.parent.append(re.sub(r"\.md$", "", target.name) + ".assets")
                attachDir.mkdirs()

                file = attachDir.append(fileName)

                ctx["path"] = message["path"]
                ctx["file"] = file
                ctx["fileObj"] = open(file.path, "wb", buffering=0)

                await service.sendMessage({
                    "action": "file_transfer",
                    "sub_state": "opened"
                })
        elif stage == "put_content":
            if 'fileObj' in ctx:
                ctx["fileObj"].write(base64.decodebytes(message['content'].encode()))

                await service.sendMessage({
                    "action": "file_transfer",
                    "sub_state": "wrote"
                })
        elif stage == "close_file":
            if 'fileObj' in ctx:
                ctx["fileObj"].close()
                await service.bubble(f"已上传({ctx['file'].name})", 1800)
                await AttachmentsHandler.respondAttachmentList(service, ctx["path"])

    @staticmethod
    async def onRemoveAttachment(service: WsServer, message: Dict):
        path = message["path"]
        fileName = message['attachment']

        target = service.dataFolder.append(path)
        file = target.parent.append(re.sub(r"\.md$", "", target.name) + ".assets").append(fileName)

        if not file.exists:
            await service.bubble("找不到文件: " + path)
            return

        file.delete()

        await AttachmentsHandler.respondAttachmentList(service, path)

