import os
import asyncio
import aiohttp
import aiofiles
import asyncio
import subprocess



class DownloadHandle:
    def __init__(self):
        self.url = None
        self.filename = None
        self.content_length = 0
        self.written = 0
        self.coroutine = None

    def progress(self):
        return int(100 * self.written / self.content_length if self.content_length > 0 else 0)

    def __repr__(self):
        return f"DownloadHandle(url={self.url}, filename={self.filename}, content_length={self.content_length}, written={self.written})"

async def download(handle: DownloadHandle):
    async with aiohttp.ClientSession() as session:
        async with session.get(handle.url) as response:
            handle.content_length = int(response.headers.get('content-length', 0))
            handle.written = 0
            async with aiofiles.open(handle.filename, 'wb') as file:
                async for data in response.content.iter_chunked(1024):
                    await file.write(data)
                    handle.written += len(data)

async def update_tqdm(pbar, handle: DownloadHandle):
    while handle.progress() < 100:
        # We don't know the total size until the download starts, so we update it here
        pbar.total = handle.content_length / 1024
        pbar.update(handle.written / 1024 - pbar.n)
        await asyncio.sleep(0.1)

class RunHandle:
    def __init__(self):
        self.filename = None
        self.args = []
        self.process = None

    def __repr__(self):
        return f"RunHandle(filename={self.filename}, args={self.args}, process={self.process})"

class LlamafileManager:
    def __init__(self, llamafiles_dir: str):
        self.llamafiles_dir = llamafiles_dir
        self.download_handles = []
        self.run_handles = []

    def list_llamafiles(self):
        return [f for f in os.listdir(self.llamafiles_dir) if f.endswith('.llamafile')]

    def has_llamafile(self, name):
        return name in self.list_llamafiles()

    def download_llamafile(self, url, name):
        handle = DownloadHandle()
        self.download_handles.append(handle)
        handle.url = url
        handle.filename = os.path.join(self.llamafiles_dir, name)
        handle.coroutine = download(handle)
        return handle

    def run_llamafile(self, name: str, args: list):
        if not self.has_llamafile(name):
            raise ValueError(f"llamafile {name} is not available")
        handle = RunHandle()
        self.run_handles.append(handle)
        handle.filename = os.path.join(self.llamafiles_dir, name)
        # Print the file path, and check if the file exists
        print(handle.filename)
        if not os.path.isfile(handle.filename):
            raise FileNotFoundError(f"{name} not found in {self.llamafiles_dir}")
        if os.name == 'posix' or os.name == 'darwin':
            if not os.access(handle.filename, os.X_OK):
                os.chmod(handle.filename, 0o755)
        handle.args = args
        # print(["sh", "-c", handle.filename, *args ])
        # handle.process = subprocess.Popen(["sh", "-c", handle.filename, *args ])

        cmd = f"{handle.filename} {' '.join(args)}"
        handle.process = subprocess.Popen(["sh", "-c", cmd])

        return handle

    def stop_llamafile(self, handle: RunHandle):
        if handle.process.poll() is None:
            handle.process.terminate()
            handle.process.wait()
            self.run_handles.remove(handle)