# World 单元测试

本目录验证 World 时钟、Runtime 配置和单个任务的局部行为；公网、生产凭据和真实模型均不属于单元测试。连接数据库、Stage、Agent 或结算路由的场景位于 `tests/integration/world`，真实 VCPedia/B 站探测位于 `tests/e2e/external`。

统一的分层定义、执行命令和覆盖率门禁见 [`tests/README.md`](../../README.md)，不变量证据见 [`tests/INVARIANTS.md`](../../INVARIANTS.md)。

## VCPedia PR #195

- [进行中统一 spec](../../../../docs/开发进程文档/vcpedia-wikitext-migration.md)：产品行为与稳定验收ID。
- [全PR文档与工单核验](../../support/vcpedia_review/README.md)：历史文档合并/删除、旧声明限制、双向验收矩阵与本轮结果。
- [配对语料与独立内容预期](../../support/vcpedia_corpus/README.md)：源码/渲染片段身份、来源、权利说明、选材与效果/性能口径。

### 离线回归与门禁

以下命令从 `server/` 执行，Python使用项目依赖；Ruff固定为0.14.10，不通过`--isolated`跳过项目配置。

```powershell
python -m pytest tests/unit/world -q
python -m pytest tests/integration/world tests/integration/packaging -q
python scripts/check_pr_python.py --base 910af449680091e339e0e6fd517d08c1f5222923 --head HEAD --include-working-tree
```

检查入口打印base/head、版本、文件数及实际选中文件。提交前包含工作区及待提交新增Python文件；复核固定提交时去掉`--include-working-tree`。不要用`ruff check tests/unit/world/`的退出0推断所有测试都被检查：项目`include`对目录发现生效，显式文件与目录行为不同。

`test_vcpedia_lyrics_recovery.py`只验证两份已有源码的当前歌词与关键词，不运行旧HTML实现。`test_vcpedia_corpus_baseline.py`及配对工具的内容预期与行为快照用途分别说明；非空、字数、`needed`不是完整性判卷的替代品。原24首列表比较与刹那芳华64→723仍按历史证据单列，不由新的样本数量自动承接。

### 提示词实验

默认仅离线渲染提示词；输出目录应选新建目录，产物位于被忽略的`data/test_outputs`，不提交密钥或个人配置。

```powershell
python scripts/vcpedia_prompt_lab.py --material title:Foxy --out data/test_outputs/prompt-lab-local
```

`--dry-run`明确要求离线；`--live`才发起真实、可能计费的模型请求，需配置`extraction_llm_module`及其provider/凭据。live实验只支持配置中的OpenAI-compatible接口（如模板的DeepSeek接口），不宣称覆盖所有自定义provider类型。`--provider`只在显式live实验中覆盖补提provider，不默默回退总结模型；A/B用`--prompt`与`--prompt-b`。本工具不发送片段POST，采用生产材料与合并校验但不是完整在线采集验收，失败状态须与报告一起查看。

### 配对效果与性能

可执行命令、固定样本集合、基准协议与输出字段以[语料说明](../../support/vcpedia_corpus/README.md)为准。普通单测验证工具的统计、输入完整性与失败语义；真实计时是独立受控运行，不把本机某次毫秒数字作为所有CI机器的保证。冻结HTML若是API `parse.text`，输入字节比不能称网络传输量。
