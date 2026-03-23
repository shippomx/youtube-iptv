# IPTV SaaS 设计规格

**日期**：2026-03-23
**状态**：已批准
**目标用户**：个人 NAS 自用

---

## 一、概述

构建一个运行在 NAS 上的动态 IPTV 聚合服务。通过 `yt-dlp` 从 YouTube Live 等平台提取真实流地址，动态生成标准 M3U 播放列表，供 VLC、Jellyfin、IPTV App 等客户端直接使用。提供简单 Web 管理面板进行频道管理。

---

## 二、架构（单体 FastAPI）

```
iptv-saas/
├── app/
│   ├── main.py              # FastAPI 入口，挂载路由 + 启动调度器
│   ├── api/
│   │   ├── channels.py      # GET/POST/PATCH/DELETE /channels
│   │   ├── m3u.py           # GET /m3u
│   │   └── health.py        # GET /health
│   ├── core/
│   │   ├── scheduler.py     # APScheduler，定时刷新所有频道
│   │   ├── stream.py        # yt-dlp asyncio subprocess 封装
│   │   └── checker.py       # 流地址健康检测（HEAD 请求）
│   ├── db/
│   │   ├── database.py      # SQLite 连接（SQLAlchemy，启用 WAL 模式）
│   │   └── models.py        # Channel 表结构
│   └── static/
│       └── index.html       # 前端面板（Alpine.js，无构建步骤）
├── Dockerfile
├── docker-compose.yml
└── data/
    └── channels.db          # SQLite 数据文件（挂载到 NAS 卷）
```

### 数据流

```
用户访问 /m3u
    ↓
FastAPI 从 SQLite 读取所有启用频道及其缓存的流地址
    ↓
直接返回 M3U 文本（无等待，毫秒级响应）

后台 APScheduler（每 30 分钟，可配置）
    ↓
asyncio 并发调用 yt-dlp 解析各频道（最多 5 个并发）
    ↓
将新流地址 + 状态写回 SQLite
```

---

## 三、数据库设计

### channels 表

```sql
CREATE TABLE channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    source_url  TEXT NOT NULL,
    stream_url  TEXT,
    logo_url    TEXT,
    group_name  TEXT DEFAULT 'default',
    enabled     BOOLEAN DEFAULT TRUE,
    last_check  DATETIME,
    status      TEXT DEFAULT 'unknown',  -- ok / dead / pending / unknown
    fail_count  INTEGER DEFAULT 0
);
```

- `source_url`：YouTube Live / 其他平台原始 URL
- `stream_url`：yt-dlp 解析出的真实 HLS/RTMP 地址（缓存）
- `status`：连续 3 次解析失败后标记为 `dead`
- `fail_count`：连续失败次数计数器

---

## 四、API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/m3u` | 返回完整 M3U 播放列表 |
| `GET` | `/channels` | 获取所有频道列表（JSON） |
| `POST` | `/channels` | 添加新频道 |
| `PATCH` | `/channels/{id}` | 更新频道信息（名称/分组/logo/启用状态） |
| `DELETE` | `/channels/{id}` | 删除频道 |
| `POST` | `/channels/{id}/refresh` | 手动触发单个频道流地址刷新（异步，返回 `202 Accepted`） |
| `POST` | `/channels/refresh-all` | 手动触发全量刷新（异步，返回 `202 Accepted`，受并发限制） |
| `GET` | `/health` | 服务状态 + 各频道最新状态汇总 |

### M3U 输出格式

```m3u
#EXTM3U
#EXTINF:-1 tvg-logo="https://..." group-title="新闻",TVBS
https://...real-stream-url...
#EXTINF:-1 tvg-logo="https://..." group-title="体育",Sky Sports
https://...real-stream-url...
```

支持 `tvg-logo` 和 `group-title`，兼容 Jellyfin、VLC、IPTV Smarters 等主流客户端。

### M3U 过滤规则

- **默认**：仅输出 `enabled = TRUE` 且 `stream_url IS NOT NULL` 且 `status != 'dead'` 的频道
- **查询参数** `?include_dead=true`：包含 `dead` 状态频道（用于调试）
- 服务刚启动、首次刷新前 `stream_url` 为 NULL 的频道会被跳过，不影响 M3U 解析

### 手动刷新语义

`POST /channels/{id}/refresh` 和 `POST /channels/refresh-all` 均为**异步触发**，立即返回 `202 Accepted`。客户端可刷新频道列表查看最新状态，无需长轮询。

手动触发与 APScheduler 定时任务**共享同一 `asyncio.Semaphore`**，不会绕过并发限制。两者可能同时运行（无互斥），极端情况下同一频道的两个写入会竞争数据库，但最终结果均为有效流地址，可接受（个人用途下此场景概率极低）。

---

## 五、Stream 解析与调度

### yt-dlp 调用

```python
# core/stream.py
async def resolve_stream(source_url: str, timeout: int = 30) -> str | None:
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "-g", "-f", "best", source_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode().strip() or None
    except asyncio.TimeoutError:
        proc.kill()
        return None
```

使用 `asyncio` 异步子进程，不阻塞 FastAPI 主事件循环。`asyncio.wait_for` 控制超时，防止子进程挂起导致调度器阻塞。超时时长由 `RESOLVE_TIMEOUT_SECONDS` 环境变量配置，默认 30s。

### 调度策略

- **调度间隔**：默认 30 分钟，通过 `REFRESH_INTERVAL_MINUTES` 环境变量配置
- **并发限制**：`asyncio.Semaphore(MAX_CONCURRENT_RESOLVES)`，默认 5，防止 YouTube 限速
- **失败处理**：单次失败保留旧流地址，`fail_count` 递增；连续 3 次失败（`FAIL_THRESHOLD`）标记 `dead`
- **成功恢复**：解析成功后 `fail_count` 重置为 0，状态恢复 `ok`
- **启动刷新**：服务启动后延迟 10s 执行首次全量刷新
- **调度器集成**：使用 APScheduler 3.x `AsyncIOScheduler`，通过 FastAPI `lifespan` (`@asynccontextmanager`) 挂载，确保应用关闭时调度器正确停止

### 每次调度执行顺序

1. 并发调用 `resolve_stream` 更新所有启用频道的 `stream_url`
2. 解析完成后，对 `stream_url IS NOT NULL` 的频道执行 HEAD 健康检测
3. 将最终 `status` 和 `last_check` 写回数据库

健康检测基于最新解析结果，确保检测的是有效地址。

### 健康检测

对最新缓存的 `stream_url` 发送 `HEAD` 请求，超时时长由 `HEALTH_CHECK_TIMEOUT_SECONDS` 环境变量配置，默认 5s。与流解析在同一调度周期内串行执行（先解析后检测），结果写入 `status` 字段。

单次调度的最坏时间上界约为：`ceil(N / MAX_CONCURRENT_RESOLVES) × RESOLVE_TIMEOUT_SECONDS + N × HEALTH_CHECK_TIMEOUT_SECONDS`。NAS 网络不稳定时建议适当降低 `MAX_CONCURRENT_RESOLVES` 或增大 `REFRESH_INTERVAL_MINUTES`。

---

## 六、前端面板

**技术栈**：原生 HTML + Alpine.js（~15KB CDN，无构建步骤）

**功能：**
- 添加频道（名称、源地址、分组、Logo URL）
- 频道列表展示：名称、分组、状态（ok/dead/pending）、最后检测时间
- 启用/禁用频道（点击状态图标切换）
- 单频道手动刷新
- 全量刷新触发
- 一键复制 M3U 链接 / 导出 M3U 文件

---

## 七、Docker 部署

### Dockerfile

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi uvicorn sqlalchemy "apscheduler>=3,<4" "yt-dlp==2024.12.13"
# yt-dlp 版本锁定：与平台反爬机制强绑定，升级需手动测试后 bump 版本号

WORKDIR /app
COPY . .

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

注：yt-dlp 固定版本由 `pip install` 管理，不在构建时执行 `yt-dlp -U`（构建阶段更新无效，且易因网络问题导致构建失败）。

### docker-compose.yml

```yaml
services:
  iptv:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - /volume1/docker/iptv:/app/data
    environment:
      - DB_PATH=/app/data/channels.db
      - REFRESH_INTERVAL_MINUTES=30
      - MAX_CONCURRENT_RESOLVES=5
      - FAIL_THRESHOLD=3
      - RESOLVE_TIMEOUT_SECONDS=30
      - HEALTH_CHECK_TIMEOUT_SECONDS=5
    restart: unless-stopped
```

- SQLite 数据库挂载到 NAS 持久卷，重建容器不丢数据
- NAS 路径 `/volume1/docker/iptv` 适用于 Synology，TrueNAS 可相应调整
- `data/channels.db` 通过 `.gitignore` 排除，不进入代码仓库

---

## 八、关键决策说明

| 决策 | 选择 | 理由 |
|------|------|------|
| 后端框架 | FastAPI | 异步支持好，yt-dlp 原生 Python |
| 数据库 | SQLite（WAL 模式） | NAS 单文件，WAL 允许读写并发 |
| 调度器 | APScheduler 3.x AsyncIOScheduler | 内嵌进程，与 FastAPI lifespan 集成 |
| 前端 | Alpine.js 单文件 | 无构建步骤，NAS 部署零依赖 |
| 部署 | 单 Docker 容器 | NAS 上最简单的管理方式 |
| 流解析 | asyncio subprocess + wait_for | 不阻塞事件循环，有超时保护 |

---

## 九、不在范围内（YAGNI）

- 用户系统 / 多租户
- API Key 认证
- 商业化功能（订阅、限速）
- 多平台自动发现
- 代理池
- 独立前端构建（React/Vue）
