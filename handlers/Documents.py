import re
from typing import Dict

from server.WsServer import WsServer
from utils.File import File


class Documents:
    @staticmethod
    async def respondPath(service: WsServer, path: str):
        target = service.dataFolder.append(path)

        if not target.exists:
            await service.bubble("找不到文件: " + path)
            return

        if target.isDirectory:
            await Documents.respondFolderContents(service, target, path)
        else:
            await Documents.respondFileContent(service, target, path)

    @staticmethod
    async def respondFolderContents(service: WsServer, file: File, path: str):
        content = [
            [
                f.name,  # 文件名
                f.isFile,
                f.length if f.isFile else len(f),  # 文件大小/子文件数
            ]
            for f in file
            if f.name != 'preferences.json'
        ]

        await service.sendMessage({
            "action": "dir_content",
            "path": path,
            "contents": content
        })

    @staticmethod
    async def respondFileContent(service: WsServer, file: File, path: str):
        try:
            with open(file.path, "r", encoding="utf-8") as f:
                content = f.read()

            await service.sendMessage({
                "action": "read_file",
                "success": True,
                "path": path,
                "content": content,
            })
        except UnicodeDecodeError as e:
            await service.sendMessage({
                "action": "read_file",
                "success": False,
                "path": path,
                "reason": '服务端无法解码: ' + path,
            })

    @staticmethod
    async def onAccessPath(service: WsServer, message: Dict):
        await Documents.respondPath(service, message["path"])

    @staticmethod
    async def onWriteFile(service: WsServer, message: Dict):
        path = message["path"]
        content = message["content"]

        target = service.dataFolder.append(path)

        if not target.exists:
            await service.bubble("找不到文件: " + path)
            return

        if target.isDirectory:
            await service.bubble("这是个目录!: " + path)
            return

        target.content = content

        await service.bubble(f"已保存({target.name})", 1300)
        await Documents.respondPath(service, target.parent.relPath(service.dataFolder))
        await service.sendMessage({"action": "file_writen", "path": path})

    @staticmethod
    async def onDeleteFile(service: WsServer, message: Dict):
        path = message["path"]

        target = service.dataFolder.append(path)

        if not target.exists:
            await service.bubble("文件不存在: " + path)
            return

        if path.startswith("RecycleBin"):  # 真正的删除
            target.delete()
        else:  # 移动到回收站
            file = service.recycleBin.append(target.name)

            if file.exists:
                nameIndex = 1
                while True:
                    dotPos = file.name.rfind('.')
                    prefix = file.name[:dotPos] if dotPos != -1 else file.name
                    suffix = file.name[dotPos:]

                    newName = prefix + ' (' + str(nameIndex) + ')' + (suffix if dotPos != -1 else '')
                    newFile = service.recycleBin.append(newName)

                    if not newFile.exists:
                        file = newFile
                        break
                    nameIndex += 1

            target.moveTo(file)

            assets = target.parent.append(re.sub(r"\.md$", "", target.name) + ".assets")

            if assets.exists:
                assets.moveTo(service.recycleBin.append(assets.name))

        await Documents.respondPath(service, target.parent.relPath(service.dataFolder))

    @staticmethod
    async def onRenameFile(service: WsServer, message: Dict):
        oldFile: File = service.dataFolder[message["path"]]
        newFile: File = oldFile.parent[message["new_name"]]

        if not oldFile.exists:
            await service.bubble("文件不存在: " + message["path"])
            return

        if newFile.exists:
            await service.bubble("文件已存在: " + newFile.name)
            return

        oldFile.rename(newFile.name)

        if oldFile.name.endswith('.md'):
            oleAssets = re.sub(r"\.md$", "", oldFile.name) + ".assets"
            newAssets = re.sub(r"\.md$", "", newFile.name) + ".assets"

            assets = oldFile.parent[oleAssets]

            if assets.exists:
                assets.rename(newAssets)

            # 替换文件里的资源文件夹路径
            reg = r'(?<=\]\()' + re.escape(oleAssets) + r'(?=/)'

            newFile.content = re.sub(reg, newAssets, newFile.content)

        await Documents.respondPath(service, oldFile.parent.relPath(service.dataFolder))

    @staticmethod
    async def onCreateFolder(service: WsServer, message: Dict):
        path = message["path"]

        target = service.dataFolder.append(path)

        if target.exists:
            await service.bubble("目录已存在: " + path)
            return

        target.mkdirs()

        await Documents.respondPath(service, target.parent.relPath(service.dataFolder))

    @staticmethod
    async def onCreateFile(service: WsServer, message: Dict):
        relPath = message["path"]

        target = service.dataFolder.append(relPath)

        if target.exists:
            await service.bubble("文件已存在: " + relPath)
            return

        target.create()

        await Documents.respondPath(service, target.parent.relPath(service.dataFolder))

    @staticmethod
    async def doCopy(service: WsServer, From: File, To: File, moveMode: bool) -> bool:
        a = From.relPath(service.dataFolder)
        b = To.relPath(service.dataFolder)

        if From.parent.path == To.path:
            await service.bubble("不能原地移动/复制", 1300)
            return False

        if To[From.name].exists:
            await service.bubble("文件已存在", 1300)
            return False

        if a in b:
            await service.bubble("不能对奇怪的路径进行移动/复制", 1300)
            return False

        From.copyTo(To[From.name])

        if From.isFile:
            assets = From.parent[re.sub(r"\.md$", "", From.name) + ".assets"]
            assets2 = To[assets.name]

            if assets.exists and not assets2.exists:
                assets.copyTo(assets2)

                await service.bubble(assets2.name + ' 已被一同' + ('移动' if moveMode else '复制'), 2000)

                if moveMode:
                    assets.delete()

        if From.isDirectory and From.name.endswith('.assets'):

            docFile = From.parent[From.name[:-7] + '.md']
            docFile2 = To[docFile.name]

            if docFile.exists and not docFile2.exists:
                docFile.copyTo(docFile2)

                await service.bubble(docFile.name + ' 已被一同' + ('移动' if moveMode else '复制'), 2000)

                if moveMode:
                    docFile.delete()

        if moveMode:
            From.delete()

        return True

    @staticmethod
    async def onMoveFile(service: WsServer, message: Dict):
        From = service.dataFolder.append(message["from"])
        To = service.dataFolder.append(service.checkIllegalRequest(message["to"]))

        if await Documents.doCopy(service, From, To, True):
            await Documents.respondPath(service, To.relPath(service.dataFolder))

    @staticmethod
    async def onCopyFile(service: WsServer, message: Dict):
        From = service.dataFolder.append(message["from"])
        To = service.dataFolder.append(service.checkIllegalRequest(message["to"]))

        if await Documents.doCopy(service, From, To, False):
            await Documents.respondPath(service, To.relPath(service.dataFolder))
