# world 对外接口

## 模块职责

`server/src/world` 负责角色在聊天之外持续发生的世界活动，例如城市漫步、B 站事件、新歌发现和学唱任务。world 可以产生新的刺激或内容，但不应成为聊天请求的协议入口。

## 对外接口

### `WorldRuntime`

- `set_system_runtime(runtime)` / `wire_dependencies(...)`：注入系统级依赖。
- `initialize_modules()`：创建并连接已启用的世界模块。
- `start_background_services()`：启动 WorldClock 和世界后台任务。
- `await stop_background_services()`：停止调度器及其拥有的任务。
- `ensure_dependencies()`：在启动前检查配置和依赖。

### `WorldClock`

- `register_interval_action(...)`：注册按固定间隔执行的任务。
- `register_daily_action(...)`：注册每天指定时刻执行的任务。
- `start()`、`await stop()`：控制调度循环。
- `is_running()`：查询调度器状态。

### `WorldTask`

- `initialize(system_runtime)`：绑定运行环境。
- `await run_once()`：立即运行一次任务，供调度和测试调用。
- `ensure_dependencies()`：检查任务依赖。
- 任务元数据读取方法：供运行时登记名称、调度和状态。

具体任务由 `citywalk`、`bili_event_updater`、`get_new_songs`、`learn_sing_songs` 等包实现。

## MediaWiki 数据获取（新歌知识）

`server/src/world/get_new_songs/mediawiki.py` 提供基于 VCPedia MediaWiki API（`https://vcpedia.cn/api.php`）的只读获取能力，用于替代旧 HTML 抓取路径。

### `MediaWikiClient`

按页面标题获取 wikitext。

- 构造：`MediaWikiClient(base_url: str, *, timeout_seconds: int = 20)`。`base_url` 是站点根地址，如 `https://vcpedia.cn`；API 端点为 `{base_url}/api.php`。
- `get_wikitext(title: str) -> str`：通过 `action=query&prop=revisions&rvslots=main&rvprop=content&formatversion=2` 返回页面最新版本的 main-slot wikitext 文本。
  - 正常行为：页面存在时返回 wikitext 字符串；不包含任何解析后的 HTML。
  - 异常行为：网络失败、超时或非 200 响应抛出 `MediaWikiRequestError`；页面不存在（`missing`）抛出 `MediaWikiPageNotFoundError`；均不自动重试。
- 网络实现封装在 `MediaWikiClient.fetch_json(params: dict) -> dict`，通过 requests.Session 发起 GET 请求并返回 JSON；测试使用 Fake Session 替换该 seam。
- 额外副作用：无。不写文件、不写数据库、不改配置。

### `parse_song_titles_from_template(wikitext: str) -> list[str]`

从「洛天依/年份」导航模板的 wikitext 中解析歌曲名列表（按出现顺序）。

- 正常行为：解析 wikitext 中 `[[目标页面|显示名]]` 形式的内链并优先取显示名；对不以「分类/模板/媒体/帮助」为目标的普通页面内链去重后保留顺序；过滤纯数字、年份、分组标题词（如「原创曲」「殿堂曲」「传说曲」「25万以上」）和导航链接（查看/编辑/历史/刷新/简体/繁體 等）。
- 输入非法（不是字符串、为空）：返回空列表。
- 不在 spec 内的解析规则（如括号内注记、外链、管道后空白）不做额外清洗；后续切片按真实数据需要再扩展。

### `fetch_song_list_from_template(year: int, *, base_url: str, timeout_seconds: int = 20) -> list[str]`

旧的 HTML 版按模板页链接文本过滤歌曲名。本切片将其行为改为：

1. 用 `MediaWikiClient` 获取 `Template:洛天依/<year>` 的 wikitext；
2. 调用 `parse_song_titles_from_template` 返回歌曲名列表。

异常行为：模板页缺失时抛出 `MediaWikiPageNotFoundError`，网络失败抛出 `MediaWikiRequestError`；由调用方（任务）记录失败。

## 当前跨模块兼容接口

- `WishlistManager` 的愿望新增、查询、领取和状态更新方法目前被唱歌能力使用。
- QQ 音乐凭据刷新、歌曲和歌词下载等函数目前被 system 管理接口调用。

这些接口是当前事实，但它们把 world 的内部实现暴露给 capabilities/system。后续应由 `WorldRuntime` 或专用的窄服务接口承接，新增调用不要继续扩大这组接口。

## 正常与异常行为

- `start_background_services()` 只负责安排任务；单个世界任务的成功或失败应独立记录，不能让一次网络失败终止整个时钟。
- 世界任务可能访问外部网络、模型、数据库、文件和第三方平台，具有明显副作用。
- `stop_background_services()` 应取消本运行时创建的任务并等待退出，不能遗留跨测试的后台协程。
- 未配置密钥、外部服务不可用或数据不完整时，任务可报告跳过/失败，但不得伪报已发布或已学会。

## 使用示例

每天的新歌任务由 `WorldClock` 触发 `run_once()`，查询新歌并形成待学习记录；如果后来需要通知用户，应生成内部事件交给正常交互链，而不是直接操作某个用户的 WebSocket。

## 应覆盖的契约场景

- 一个周期任务失败不会停止其他已登记任务，失败原因可从日志/观测中读取。
- `stop_background_services()` 后时钟和所有归属任务均退出，不再触发外部写入。
- 外部凭据缺失或网络超时时，任务报告跳过/失败，不生成“已发布”“已学会”的成功记录。
