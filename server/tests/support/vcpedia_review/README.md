# PR #195 全范围文档、工单与验证核验

本记录服务于 [PR #195](https://github.com/SheepLiu712/Agent-LuoTianyi/pull/195) 和 [Issue #196](https://github.com/SheepLiu712/Agent-LuoTianyi/issues/196)。权威产品契约为进行中的 [VCPedia spec](../../../../docs/开发进程文档/vcpedia-wikitext-migration.md)。本文件是证据与承接台账，不是第二份 spec，也不以记录当前实现替代独立内容预期。

## 核验边界

- 原审查 head：`b0d0a8ee10ad441bd19937959ba885d26299772c`。
- merge-base：`910af449680091e339e0e6fd517d08c1f5222923`。
- 文档范围包括原18个提交中的新增、修订、合并、删除；并纳入本轮所有新增说明。不是只检查最后两个提交或本轮修改过的Markdown。
- `.wikitext` 是外部来源材料，JSON配置/提示词/元数据及源码、测试、工具的docstring也是契约与证据检查对象。
- 当前客户端分支、#194/#197的独立外部测试修复不属于本PR修改范围。#123/#124/#125为已关闭未合并的旧PR栈，仅提供历史背景。
- 原始文档及范围清单见 [document_inventory.json](document_inventory.json)。该文件记录审查版本的历史；本轮新增文件另在最终验证中登记。

## 一、三份历史文档的去向

| 原路径（仓库根相对） | 历史 | 本轮承接 |
| --- | --- | --- |
| `docs/开发进程文档/vcpedia-wikitext-migration.md` | `b6969eb`新增，`1caa2d0`/`159f4bf`修订，`93c3218`删除 | 恢复为统一进行中spec，保留原1–19编号并明确边界 |
| `docs/开发进程文档/vcpedia-extraction-rules.md` | `ed6795b`新增，`159f4bf`合并删除 | 不复活平行spec；count策略、Ruby回退、字形保护、唯一材料入口由VCP-07/12/13/14/15/20/21承接 |
| `docs/开发进程文档/vcpedia-keyword-baseline.md` | `d48af59`新增，后有多次数字/口径修订，`93c3218`删除 | 不将混杂样本的旧数字重写为新事实；范围决定由VCP-16/17/19承接，历史证据限制记在本文件 |

原全文可在Git固定版本复查：迁移spec与关键词记录取`0f9a758`，提取规则取`159f4bf^`。非代码参考`server/tests/support/legacy_vcpedia_parser.py`在`954cdfb`新增、`2ccf061`删除；最终原测试是内联期望而非运行时执行旧HTML实现，本轮真实旧算法比较另在语料说明标明来源。

### 生命周期纠正

此前“开发进程目录已废弃”不符合[开发守则](../../../../docs/开发守则.md)。其中第36、59行所述流程是：进行中spec留存；实现审核合入dev且验收有证据后，关闭功能工单、另开清理Issue、在dev独立删除。`93c3218`提前删除进行中spec与此不同。

PR评审确认“文件已删除、Issue链接已同步”，不等于明确豁免这一流程。当前恢复一份统一spec，不再维护PR附录/Issue正文各自一份拷贝。#196保持开放直至完成条件满足；#197不是清理Issue。

## 二、全PR仍有效的说明覆盖

| 类别 | 核查对象 | 检查要点 |
| --- | --- | --- |
| 工具 | `scripts/vcpedia_freeze_corpus.py`、`vcpedia_perf_baseline.py`、`vcpedia_prompt_lab.py`及本轮检查入口 | 默认行为、实际输入、示例、网络/写盘、失败退出、统计定义一致 |
| 业务源码 | `wiki_api`、`wikitext_parser`、`template_rules`、`text_conversion`、`source_extraction`与修改的`vcpedia_fetcher`、`daily_new_song_fetcher`、`task` | 返回值、状态范围、转换顺序、开关、边界不因重构失真 |
| 配置与提示词 | 源码/包内`vcpedia_templates.json`、`config.json.template`、提取prompt、`pyproject.toml` | 两份规则一致；provider闭合；依赖/包资源可用；缺省与显式关闭区分；模型职责分离 |
| 原9个新增测试说明 | transport、wikitext_equivalence、material_counts、infobox_staff_scope、lyrics_recovery、keyword_contract、rules_packaging、supplement_switches、corpus_baseline | 人工样例/真实响应、快照/独立oracle、规则/真实模型证据不混称 |
| 语料 | manifest、meta、curation、源码、HTML、独立预期、活动统计 | 样本身份、hash、配对版本、活动来源、编辑归属、第三方权利、选材理由 |
| 长期入口 | `server/README.md`、`server/tests/README.md`、`server/tests/unit/world/README.md`、代码地图/守则/spec模板 | 本PR导致的新断链和部署/命令缺口；不以内部新增文件强迫重写全仓库地图 |
| 线上 | #195正文/评论/review、#196正文/评论、旧PR替代关系 | 对应最终head、声明与证据一致、无重复标准或遗漏条款 |

原`tests/INVARIANTS.md`中Agent旧文档断链在merge-base已存在，不计作本PR新引入问题。

## 三、文档 ↔ 工单 ↔ 证据矩阵

Issue #196引用同一组稳定ID。表中“验收方式”不是已经通过；当前运行状态见第六节，历史或未验证项不得混入通过数。

| spec ID | 交付契约 | 仓库证据入口（server相对） | 证据范围/边界 |
| --- | --- | --- | --- |
| VCP-01–04 | API身份/请求形状/挑战与失败 | `tests/unit/world/test_vcpedia_transport_contract.py` | Fake传输契约，不保证某个UA永远200/403 |
| VCP-05 | 首框归集、字段优先级、有效页级容器 | `tests/unit/world/test_vcpedia_infobox_staff_scope.py` | 使用真实制作人员模板、有效角色参数；不把无效嵌套的特殊结果立为验收 |
| VCP-06–07 | 展示项、独立简介/歌词、首候选、Ruby | `tests/unit/world/test_vcpedia_wikitext_equivalence.py`及解析定向回归 | 人工样例不是全站等价证明；新增用例绑定具体语义 |
| VCP-08 | 真实结构内容质量 | `tests/support/vcpedia_corpus/README.md`及独立内容预期测试 | 按选定候选的内容比较，保留反向案例，非空率只辅助 |
| VCP-09 | 原24首新旧比较 | 历史`0f9a758`关键词记录 | 待原输入/版本补证；不由新的精选语料代替 |
| VCP-10 | 两首当前歌词/关键词可用 | `tests/unit/world/test_vcpedia_lyrics_recovery.py`、`tests/support/vcpedia_lyrics_recovery.json` | 不加载旧HTML，不单独证明“迁移前为空” |
| VCP-11 | 刹那芳华64→723 | 原PR/历史基线人工记录 | 本轮未重新取得同批输入，历史观察待补证 |
| VCP-12–13 | 规则加载/形状/查询/冻结 | `tests/unit/world/test_vcpedia_rules_packaging.py`及规则校验回归 | 错误需定位；不存在与损坏两种情况不混淆 |
| VCP-14–15 | 缺口、双开关、注册/调用、先补后总结 | `tests/unit/world/test_vcpedia_supplement_switches.py`、`test_world_task_vcpedia_new_songs.py` | 两个Fake模型有不同职责；不据此声称真实模型保真 |
| VCP-16–17 | 索引安全与非目标 | `tests/unit/world/test_vcpedia_keyword_contract.py` | 6–50及`=>`规则；不外推小样本英文结论 |
| VCP-18 | 依赖/配置/provider/wheel资源 | `tests/integration/packaging/test_pyproject_installation.py`及配置回归 | 隔离加载，不宣称wheel包含所有部署资源 |
| VCP-19 | 存量不迁移、World仅投递 | `tests/integration/world`、`test_world_task_vcpedia_new_songs.py` | 不访问生产库；历史3320首全量数据未重新核验 |
| VCP-20–21 | count清理、保护与转换顺序 | `tests/unit/world/test_vcpedia_material_counts.py`及资料字段内容回归 | 同时测材料与最终字段，不能仅数infobox条目 |
| VCP-22 | 提示词实验安全默认与契约 | `scripts/vcpedia_prompt_lab.py`及离线CLI测试 | 默认不联网，实验不启用片段POST，不等同完整生产链 |
| VCP-23 | 离线效果/成本与真实旧算法 | `scripts/vcpedia_perf_baseline.py`及工具测试 | 固定集合，统计准确，真实计时在受控任务单列 |
| VCP-24 | 活动统计/配对/去重/独立预期 | `scripts/vcpedia_freeze_corpus.py`及语料工具测试 | 完整官方30天名单；不自行统计recentchanges |
| VCP-25 | 全变更文件项目lint | `scripts/check_pr_python.py`及门禁测试 | 显式文件与实际集合一致，不能只依赖目录返回0 |
| VCP-26 | 本文件、inventory和Issue双向核验 | 本文件及`document_inventory.json` | 每项承接或标待验；删除文档不删除承诺 |

## 四、撤回或限定的历史声明

### Ruff与测试

- `b0d0a8e`的N1已独立复现：22个变更Python文件，4个F401＋3个E501。旧目录命令只选中打包测试1个文件，其“全绿”不能承载整个PR的门禁声明。
- 旧复跑的242 world、1014全量通过/1个401失败、26个world集成及wheel成员检查是旧head结果。不能复制到新head，也不能把“1失败”简写为全量全绿。

### 页面数量与活动统计

- 缓存21＋随机10是历史配对候选集；另批browser-fixed、tag fixture和24首在线列表不能直接相加，必须按页面/内容身份去重。
- 旧35候选包含`page1/2/3`伪标题；旧26页数字不是新选材目标。
- 旧“最近500次编辑”方法错误判定Fiction Blue、小祺、这只阿皮有点皮不活跃。官方特殊页完整名单明确最近30天活跃定义，三者在本轮名单中；纠正后按结构与独有边界重新决定页面价值，不机械恢复所有页面。
- 活动统计操作数不是编辑次数；当前最后编辑者不是该历史版本结构作者；bot的最后操作不能替代人工归属证据。

### 内容与真实模型

- 将所有HTML `.poem` 字符数累加，再与首个歌词候选比较，不能推出“山塘恋雨只抽到18%”。多版本、原译或旁注须分别识别。
- `lyrics`非空不代表完整，`needed=true`不代表模型调用一定必要。保留非空字段的补全设计，不实施一刀切禁补提，也不按某一模型的单次表现加包含性守卫。
- 历史prompt lab发送`materials.raw`，而生产发送经过转换/计数剔除的`materials.text`。旧几次真实模型输出是当时提示词实验，不是本轮生产补提质量证明。
- “某模型本次逐字照抄”不是零损害保证；“某变体一次没输出null”不能证明所有无变化设计无效。

### 性能与网络

- 原26.7由平均值计算，却标成中位数；旧侧简化poem提取与新侧完整解析不对称。旧53.0→5.6或63.1→7.0不能作为新基准的通过阈值。
- 冻结HTML通常是API `parse.text`，文件字节比不是HTTP传输量；离线解析耗时不是端到端速度。
- 历史UA探针既出现过403，也出现过两种UA均200。仅以一次记录称“UA造成必然失败”不成立；应用身份与挑战兜底仍是明确传输契约。

### 关键词旧记录

- 原关键词文档混用了12/20/24首及不同时间库内统计；不把这些数字合为一个样本总体。
- “全部在6–50内”与同表“>50有2条”矛盾；“本次无关键词代码改动”又被后来的`=>`过滤修复改变。
- 两首未出现纯拉丁片段，不等于所有英文歌词都会被窗口过滤；“保留行结构”可能改变新采集关键词粒度，不影响旧索引是另一条存量不迁移约束。

## 五、线上工单双向检查

实施前已经保存并核对#195/#196正文、维护者评论和`b0d0a8ee`审查，区分这些内容与提交说明。

正向：本文登记的全PR文档条款 → 统一spec ID → #196验收 → 代码/测试/固定材料证据。

反向：#196/#195每项“完成/通过/可复现/默认/不变”声明 → 相同spec ID → 实際命令结果与适用版本。孤立链接、粗指标与历史观察不能替代验收。

需同步纠正的旧正文包括：仍写未跑锁定版、补提默认关闭、26页承接24首、mean称median、双关零外部访问、spec目录废弃、#194仍等待任意顺序合并。旧#123–125未合并，不将其关闭状态当作已交付。

线上更新完成后读回核对：标题、head、spec定位、验收表、数字、失败/未验证、依赖与关闭条件。#196未达到原9/11等条款时保持开放，并在重新请求审查时明示，不以新的通过数掩盖。

## 六、5b7b932 修复批次的验证记录

以下是该批次历史结果，不是后续测试输入清理的测试数量。后续记录见第七节。结果绑定源码的LF规范化SHA256、manifest和实现/规则hash，见 [validation.json](results/validation.json)。原始计时样本见 [performance.json](results/performance.json)，内容项结果见 [effect.json](results/effect.json)。这些是一次受控运行记录，不自动随代码变动刷新；变更后须重跑。提交身份由包含这些文件的提交提供，避免报告嵌入自身提交哈希的循环。

| 验证 | 实际结果 | 范围 |
| --- | --- | --- |
| 锁定Ruff0.14.10 | 31个Python文件，实际`--show-files`集合一致，退出0 | merge-base至原head＋本轮工作区全部新增/修改Python |
| 干净导出相关测试 | 579 passed，退出0 | `tests/unit/world`、`tests/integration/world`、`tests/integration/packaging` |
| 全量单测 | 1324 passed / 1 failed，退出1 | 唯一失败为既有`test_llm_service.py::TestLLMService::test_register_llm_module`真实请求401；未修改或跳过以刷绿 |
| wheel | 相关测试中通过 | 构建后隔离`-I -S`子进程真实导入规则并解析，核对模块来自wheel而非源码 |
| `compileall src` | 退出0 | 干净导出树 |
| 离线重组/效果/性能/提示词示例 | 均退出0 | 初始没有`.git`、作者`server/data`和密钥文件；工具输出使用外部临时目录 |

效果`--check`退出0只表示与独立预期的已审命中/缺口分布一致，不表示全部正确。精选12页78个内容检查项旧58命中、新67命中，**新仍有11缺口，`effect_complete=false`**；归一化歌词精确一致旧2/12、新9/12。保留Foxy、Sharing、社畜和部分简介事实的已知问题，未把旧有失败解释成本轮新回归，也未把它们删出语料。

性能固定8页，每页2次预热＋9轮，三组均满足新侧medians总和小于旧侧。原始报告中的整组比为约5.869 / 4.898 / 5.429，配对比中位数约7.208 / 6.974 / 7.382；冻结输入字节比中位数约30.475。仅为此环境的离线解析，不是网络/模型/生产吞吐速度，也不沿用旧26.7口径。

非作者复核发现并关闭三类本轮问题：保护空值被first-wins锁住、实验原始响应的JSON转义凭据脱敏绕过、选材台账29/32保留标志矛盾。修复及新增回归均再次核对。首次干净导出脚本遗漏应用新增LF属性造成hash失败，导出步骤已修正；这次失败未计作产品通过，后续导出全套验证通过。

仍未通过或未验证的验收：VCP-09原24首、VCP-11刹那芳华历史差异缺原同批输入；VCP-08尚有内容缺口；真实补提模型的本轮端到端质量未测试；VCP-19不访问生产库作全量重验；#196在这些证据与最终维护者验收闭合前保持开放。全量单测中的401是实际发生的外部请求失败，因此本轮不能笼统说“从未发出任何模型请求”，只能说“未取得新的真实补提成功证据”。

## 七、2026-10-02 测试输入与契约清理

本次根据站点模板定义核对合成测试，不改变产品解析代码、规则配置、真实冻结源码、内容oracle或历史参考算法。

- 使用不存在的`创作者名单`模拟制作信息的用例，改为真实的 [VOCALOID Songbox Introduction，revision 6619](https://vcpedia.cn/index.php?title=Template:VOCALOID_Songbox_Introduction&oldid=6619)。该模板支持`groupN/listN`角色行和具名角色字段，两种有效写法均保留。重复角色用多组角色行，不用重复参数名冒充多行。
- 普通 [VOCALOID Songbox，revision 539268](https://vcpedia.cn/index.php?title=Template:VOCALOID_Songbox&oldid=539268)不使用`简介/歌词`槽；有正文槽需求的解析和wheel样例改为 [VOCALOID Small Songbox，revision 451630](https://vcpedia.cn/index.php?title=Template:VOCALOID_Small_Songbox&oldid=451630)。普通框的制作角色移到staff，以真实的`演唱/UP主`验证首框值优先与补空。
- 包装遍历使用 [Hide，revision 2184](https://vcpedia.cn/index.php?title=Template:Hide&oldid=2184) 的`内容`或 [Toggle，revision 109](https://vcpedia.cn/index.php?title=Template:Toggle&oldid=109) 的`content`，不再以`Hide|content`证明有效正文抽取。
- 删除`test_nested_songboxes_do_not_end_first_box_interval_through_frames`及其6个参数化构造。该测试把无实际依据的“歌曲框参数内歌曲框必须不计数”固化成独立业务义务；不通过换个模板名继续保留这项特殊预期。
- 保留页级多框、staff前后范围、字段合并优先级、可见空值、nowiki/LC、Ruby、歌词、表格和故意非法JSON/provider配置等真实契约或通用健壮性测试。通用count材料测试只是任意模板参数清洗，不宣称远程模板必须存在；其中的歌曲框示例也换成有效字段。
- 不新增“参数内部 staff 必须排除”的测试或产品分支。VCP-05改为识别首框后通用遍历归集，不要求staff必须是页级兄弟节点；无效渲染构造不再额外产生排除或计数验收。

这里的测试仍是人工构造输入，不冒充从站点冻结的真实页面。有效模板定义提供输入接口依据，字段合并预期由已确认业务策略决定。历史缺口和其他复审事项不因本次测试清理自动关闭。

验证：lty环境Ruff0.14.10显式检查完整PR的31个Python文件，`--show-files`集合一致且退出0；六个直接修改的测试文件定向回归164 passed；`tests/unit/world`＋`tests/integration/world`＋`tests/integration/packaging`共573 passed，包含wheel真实导入解析。相对第六节579项减少6项，恰为移除的嵌套计数参数化用例；不是跳过失败测试，也没有修改产品去满足剩余输入。全量`tests/unit`、真实站点/模型和性能计时本次未重跑，第六节及其JSON仍是`5b7b932`批次历史证据，不自动升级为新结果。
