import asyncio


async def resolve_stream(source_url: str, timeout: int = 30) -> str | None:
    """调用 yt-dlp 提取真实流地址，超时或失败返回 None。"""
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "-g", "-f", "best", source_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode().strip() or None
    except asyncio.TimeoutError:
        proc.kill()
        return None
