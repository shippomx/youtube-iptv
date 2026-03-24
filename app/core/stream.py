import asyncio
import os


async def resolve_stream(source_url: str, timeout: int = 30, cookies_path: str = "") -> str | None:
    """调用 yt-dlp 提取真实流地址，超时或失败返回 None。"""
    cmd = ["yt-dlp", "--no-update", "-g", "-f", "b",
           "--extractor-args", "youtube:player_client=android"]
    if cookies_path and os.path.isfile(cookies_path):
        cmd += ["--cookies", cookies_path]
    cmd.append(source_url)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode().strip() or None
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return None
