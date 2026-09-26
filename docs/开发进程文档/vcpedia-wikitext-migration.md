# VCPedia 新歌采集改用站点 API 与 wikitext

## 用户故事

- 作为运维者，我希望新歌知识同步任务在站点启用反爬校验后仍能稳定取到歌曲列表与详情，以便每日新增歌曲不需要人工补录。
- 作为角色使用者，我希望天依"学会"的新歌，其歌手、UP主、简介与歌词与原实现保持一致，以便已有知识和关键词检索不因底层抓取方式变化而改变。
- 作为维护者，我希望模板结构或页面格式变化时只改配置与解析规则、不用改两套抓取代码，以便降低后续维护成本。
- 作为部署者，我希望知道升级到本次变更前需要补装哪些依赖，以便存量环境不会因为缺包导致整个 `src.world` 无法导入。

## 验收标准

### 传输

1. **状态**：任务抓取歌曲列表时；**输入**：模板页 URL（如 `https://vcpedia.cn/Template:洛天依/2026`）；**输出**：向站点 `/api.php` 发起 `action=parse&prop=wikitext&redirects=1&format=json&page=<模板标题>` 请求，请求头 `User-Agent` 为应用自述身份 `AgentLuo/1.0 (+https://github.com/SheepLiu712/Agent-LuoTianyi)`。
2. **状态**：站点返回反爬挑战（HTTP 403 或挑战页特征）；**输入**：同一请求；**输出**：改用 curl 兜底，curl 携带与请求头相同的 `--user-agent`，且不使用 shell；兜底成功时返回与直连一致的正文。
3. **状态**：直连与兜底都失败（超时、空响应、非 JSON、API 错误、缺字段、类型不符）；**输入**：上述失败响应；**输出**：列表入口向上抛出，详情入口返回 `None`；**不得**把失败当成"页面为空"的成功结果。
4. **状态**：响应是合法 JSON 且正文中包含 `Anubis` 等挑战字样；**输入**：该类响应；**输出**：按正常响应处理，不进入兜底。

### 产出等价

5. **状态**：对同一页面分别使用迁移前的 HTML 解析与新的 wikitext 解析；**输入**：人工配对的同页 HTML 与 wikitext；**输出**：两者产出的详情字典完全相同（`name`、`type`、`infobox`、`summary`、`lyrics`、`spaced_lyrics`）。
6. **状态**：既有消费方读取详情；**输入**：抓取结果；**输出**：`VCPediaFetcher.fetch_entity_description(entity_name, short_summary=True)` 的签名与返回字段不变，`fetch_song_list_from_template(url, timeout=20)` 仍返回同一批显示名（顺序、星号剥离、导航链接过滤一致）。
7. **状态**：任务收集候选；**输入**：同一次抓取；**输出**：`collect_new_song_candidates` 仍返回 `discovered` / `skipped_existing` / `fetch_failed`，`NewSongCandidate` 字段与 `content_revision` 取值口径不变。

### 部署

8. **状态**：存量环境升级到本次变更；**输入**：未安装新解析库的环境；**输出**：部署说明与依赖清单明确指出需补装 `mwparserfromhell`；否则 `src.world` 导入即失败，而不是单任务失败。

## 模块与架构

### 模块划分

改动全部落在 `server/src/world/get_new_songs`（代码地图中的"VCPedia 歌曲候选采集"）：

| 文件 | 职责 |
| --- | --- |
| `wiki_api.py`（新增） | MediaWiki API 传输：URL 与参数构造、传输身份、挑战识别、curl 兜底、响应解码与失败语义 |
| `wikitext_parser.py`（新增） | 解析 wikitext 源码：模板页显示名、详情的信息框/简介/歌词（含 `parse_details`、`parse_song_titles`） |
| `vcpedia_fetcher.py` | 详情入口；本变更后不再包含 HTML 解析，缓存、摘要与保存路径保持不变 |
| `daily_new_song_fetcher.py` | 列表入口与候选规范化；本变更后不再包含 HTML 抓取与链接解析 |

不涉及 `task.py`、`src/domain/agent`、`src/infrastructure/persistence` 与入库口径：world 仍只投递事实，落库由 Agent 侧接纳。

### 接口规范

- `fetch_wikitext(base_url: str, title: str, get: Callable[..., Response], timeout: float) -> str`
  - 成功：返回页面 wikitext 源码字符串；
  - 失败：抛出异常（HTTP 错误、挑战无法兜底、解码失败、API 错误响应、缺少字符串字段）。
- `parse_song_titles(source: str) -> List[str]`：按页面出现顺序返回显示名，过滤模板/分类等导航链接。
- `parse_details(source: str, title: str) -> Dict[str, Union[str, Dict[str, str], List[str]]]`：返回 `name`、`type`、`infobox`、`summary`、`lyrics`、`spaced_lyrics`；无歌词证据时 `type` 为 `Person`。
- `VCPediaFetcher.fetch_entity_description(entity_name, short_summary=True)`：签名不变；关闭时返回空字符串，抓取失败返回 `None`，命中缓存直接返回。

## 备注

### 关键技术选型

- 解析库使用 `mwparserfromhell`（MIT，无传递依赖），替代原先的 BeautifulSoup HTML 解析；依赖写入 `server/pyproject.toml`。
- 传输身份使用应用自述 UA。实测站点部署了 Anubis 1.27.0 校验：冒充浏览器的 UA 会被 403 拦截，自述身份的客户端可正常返回。
- curl 兜底用于站点挑战场景，携带同一 UA 且不使用 shell。

### 非目标

- 不改变世界任务的落库与事实投递边界（落库仍在 Agent 侧）。
- 不引入模板规则配置文件、缺口补提、计数统计剔除等提取行为改进，这些属于后续交付。
- 不解析远程模板或 Lua 展开，不处理未闭合或高级 LC 语法。
- 不承诺全站页面解析等价，等价范围限于验收标准中列举的行为与样例。
