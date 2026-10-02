# VCPedia 离线语料、内容对照与解析性能

本目录只整理用户已提供的本地原件，不是重新抓取全站；工具不访问网络、不发现其它 worktree、不依赖私有 tag、Git 历史或 `server/data`。以下是供项目负责人审阅的工具与证据说明，不替代人工验收。

## 范围与选材

- `candidate-ledger.json` 盘点原缓存 21 + 随机 10 个候选，保留原件哈希、来源、可证修订和每个非精选样本的代表/理由。
- `manifest.json` 只列实际随库输入，严格缺一即失败：29 页 = 原有 26 页行为归档 + 青麟雪、神孽、飞跃乌托邦；其中 28 页有同响应配对，周刊 VOCALOID 中文排行榜449仅源码，不进配对分母。
- 新恢复但没有独有断言的海王的心、惜春去、煌不复制正文/响应，只留候选台账。主工作区原材料没有改动。
- 当前默认内容精审12页，另4页保留扩展内容断言；当前性能配置选8页。工具校验所声明的样本集合、顺序和输入哈希与`benchmark-lock.json`一致，不硬编码页数。只改manifest而未同步lock会失败；明确同时修订两者可以建立新实验，但新集合不能沿用旧性能报告。
- 原26不是本轮挑出的新默认集合，而是既有回归承诺。旧行为快照与旧错误选材记录留在 `reference/historical-*`，只供追溯，不作为活动或正确性依据。
- `curation.json` 区分候选档案、默认精选和实际持有输入。依据源码 AST 的顺序、嵌套、参数槽、标签、信息框/staff、歌词候选及版本边界；不使用 Jaccard 自动淘汰，不以性能好坏/是否通过选材。

六个曾被合并的页面并非整页等价：青麟雪是普通 poem 与 group/list staff 的持平代表；神孽使用直接命名的 staff 键，保留扩展断言；飞跃乌托邦有 staff 角色与歌词后解析章节，保留扩展断言；惜春去的 center/展示色差异不新增业务边界，由青麟雪代表；海王括号和声由礼物代表、前置非歌词 poem 由青麟雪的章节选择代表；凌晨保留原基线，其下划线模板别名、ref/额外ID不被称作不存在。非精选不是宣称全文等价。

## 来源、活动与权利

`capture` 保存原响应的相对路径、原字节 SHA256、无损 gzip 字节 SHA256；`pair` 记录 `parse.wikitext.*` 与 `parse.text.*` 同响应证据。HTML 的种类是 **MediaWiki parse.text fragment，不是完整网页**。源码 sidecar 使用 UTF-8 LF，仓库哈希与原件文件哈希分开；`.gitattributes` 固定文本换行，gzip 原字节不改。未知原 capture 时间和原响应 revid 保留 null，不从目录名猜日期。

公开修订 API 元数据只查 ids/user/timestamp/sha1/size，不抓歌词。31个候选的规范化源码 SHA1 均匹配到可证修订；原响应缺 revid 时，匹配出的编号放在 `revision_editor.revid`，不冒充原响应提供了编号。该账号是该修订最后编辑者，`structure_author` 仍为 null；bot 不冒充结构作者。三页与当前最新版不同，历史元数据另保存原响应。

活动唯一依据 `https://vcpedia.cn/Special:活跃用户` 的完整官方快照，采集时间为 **2026-10-01T16:09:46.054364+00:00**。该快照40条、无分页、无用户/用户组过滤，明确过去30天活动；账号不在完整名单就是该30天不活跃。失败、反爬、截断、分页或人数与该次采集证明不符时不分类、不写数据。人数不是未来永远40的规则。`operations_30d` 是操作数，不是编辑数；保留 `groups` 和 bot 标志。Fiction Blue、小祺、这只阿皮有点皮均活跃。当前活动窗口与旧源码 capture/revision 日期分开。

权利依据为 [浏览前必读](https://vcpedia.cn/VCPedia:%E6%B5%8F%E8%A7%88%E5%89%8D%E5%BF%85%E8%AF%BB)（取证 oldid 585010），原页保存在 `evidence/site-terms.html`：站点编辑文本适用对应版本的许可，2026-09-16后为 CC BY-NC-SA 4.0，之前历史部分可能仍为 CC BY-NC-SA 3.0 CN。**歌词、引文和媒体并不因此获得站点整体 CC 授权，权利归原权利人，本目录不宣称已取得歌词授权，也不将第三方内容改为项目 MIT。** 保留已有原件的版权提示、页面来源与历史参考。整理修改仅无损压缩、LF sidecar和标明选择依据的测试摘取；许可范围仍需维护者核验。

## 独立内容预期，不是新解析器输出快照

`oracle.json` 来源于历史 `manual_oracle.json`、随机 `lyrics-verdict.json` 与对应源码/HTML人工选块审查，未调用 `parse_details` 生成 expected。

- 每页记录具体 `.poem` 序号或首 `LyricsKai[/hover].original` 槽及选择范围。不拼接所有 poem；山塘多版本不作一个分母。
- `lyrics_exact` 指 **zh-cn 字形归一、去Unicode空白后的所选文本精确一致**，不是原始字形/空白/段落格式保真。歌词全文、代表行及顺序、明确的信息框键值、首简介事实分别计分。
- 长平受保护传统字形、达拉空白 ruby 的 `啦啦`、礼物括号和声另有不归一化的字面断言。生产已有的 nowiki/LC 单元测试仍负责其它保护语义。
- 横竖的早期黄龄二创 poem 不属于歌词章节首候选；I LOVE YOU只审第一候选及可见摩斯码；Estrus只审遮罩 original，不宣称解遮罩或所有版本完整。
- `reviewed_outcomes.json`记录各布尔检查的已审满足/未满足状态，不是expected正文，也不声称这些槽位互相独立。新增不符或判定变化须失败并审阅；不自动更新，不用skip/xfail隐藏。
- 来源存在性测试只证明简介事实在整页可见文本中出现，以及人工来源描述字段齐备、歌词预期非空；它不自动证明事实来自约定简介章节或歌词预期完整对应指定容器。`selection`中的poem序号/模板槽位是人工核对记录，不能把“存在该记录”当作机器已经重建并验证该来源。
- `meta.json` 仅是行为快照。16页仅因已解释的 mark_counts 修复删除纯再生计数项而将 `infobox_n` 减一；歌词、needed等不变，旧快照保留。`needed=False` 和“有歌词”均不是内容完整证明。

这份历史对照在12页上设了78个布尔检查槽位：旧58项满足/20项未满足，新67项满足/11项未满足；扩展16页共104槽，旧77项满足、新93项满足。槽位并不独立：歌词全文匹配与从同一全文派生的代表行顺序有重叠。因此不能把67/78称为准确率，也不能把11个未满足槽位称为11个独立缺陷。另按页单列归一化歌词精确匹配：旧2/12、新9/12。逐页、逐字段结果比总槽位数更能说明差异。

明确保留反向/已知问题：Foxy旧正确、新空；Sharing两侧都不匹配首英文候选（新误取后候选）；社畜旧重复但代表行完整，新空；山塘新歌词恢复但首简介的日期/项目号事实丢失；唱给新歌词恢复但丢“压线”。**回归稳定不等于效果已达标；历史当日24首“不回退”宣称仍未验证。** 本目录没有改变或收窄 A1 补提行为。

## 命令

在`server`目录使用已安装项目依赖的Python解释器执行。脚本通过`__file__`定位导入，直接使用脚本绝对路径亦可，不依赖pytest的PYTHONPATH；Python及依赖版本记录在实验报告中，不要求作者的本机解释器路径。

```text
python scripts/vcpedia_freeze_corpus.py --manifest tests/support/vcpedia_corpus/manifest.json --output data/test_outputs/corpus-reproduced-UNIQUE --offline
python tests/support/vcpedia_corpus/oracle_support.py --manifest tests/support/vcpedia_corpus/manifest.json --output data/test_outputs/effect-UNIQUE.json --check
python scripts/vcpedia_perf_baseline.py --manifest tests/support/vcpedia_corpus/manifest.json --output data/test_outputs/performance-UNIQUE.json --check
python -m pytest tests/unit/world/test_vcpedia_corpus_baseline.py tests/unit/world/test_vcpedia_corpus_tools.py tests/unit/world/test_vcpedia_perf_baseline.py -q -p no:cacheprovider --basetemp=data/test_outputs/pytest-corpus-UNIQUE
```

必须换唯一输出/临时目录。**不要把 pytest basetemp 放进 corpus：测试会复制输入。** 已增加结果目录排除以及 freeze 拒绝输出位于源目录内的保护。

冻结命令先验证全部材料，再写新目录；已存在输出一律拒绝，不覆写已有语料或 oracle。它只重组输入及元数据，不生成或复制批准的 oracle/行为baseline；批准预期必须单独审阅迁移。导入材料不等于批准新预期。校验失败返回非0。

效果`--check`是“与已审判定一致”的回归门禁；即使返回0，也必须读`effect_complete`和未满足槽位，不能宣称全正确。性能`--check`对本次声明且与lock一致的集合独立运行3组，每组新侧中位耗时总和必须小于旧侧，任一组失败返回非0。这是方向性判定，没有最低改善幅度或统计显著性保证；不追加未经约定的保守裕量。普通CI仅跑假时钟统计、顺序及失败码测试。

## 真实性能的范围

旧侧是 commit `910af449680091e339e0e6fd517d08c1f5222923` 的 `_parse_page` / `_get_data_from_infobox`，blob `3208aae7a2f2dc74f9c77f2c8b7bcee680b596a5`，与 `79ae2c0` 同blob。`reference/vcpedia_fetcher.py.txt` 固定原字节；测试只装载这两个方法，隔离构造/网络/LLM。`../vcpedia_legacy_html.py` 是按职责拆分的等价适配，28真实配对及边界夹具比较全部六字段，不是简化poem模拟。

新旧都测完整字段抽取，所有读取/验证/导入/初始化在计时外；每页2 warmups + 9 rounds，按页/轮交替先后。新报告包含原始samples、每页median、配对加速比的median、sum medians group ratio、样本输入hash、依赖版本，以及基准脚本、输入校验器、旧适配、新解析器、模板规则加载器、文本转换器和规则文件的本地源码hash；不是整个Python环境的递归依赖指纹。文件大小仅本地文件字节比的median，**不是网络传输比**。

`5b7b932`批次的历史干净导出运行（不是本次N6/N8–N15验证，也不包含后来新增的完整九文件指纹；Python3.10.20，BeautifulSoup4 4.15.0、mwparserfromhell0.7.2、zhconv1.4.3）：median配对加速比约7.208/6.974/7.382；sum-medians组比约5.869/4.898/5.429，三组新均小于旧；文件字节比median约30.475。原始samples与实现/规则/manifest指纹见[性能结果](../vcpedia_review/results/performance.json)，完整验证范围和失败见[核验记录](../vcpedia_review/README.md)。只说明这组离线解析，不承诺旧文档中的数值、不承诺端到端性能，换机须重测，结果不随源码自动刷新。
