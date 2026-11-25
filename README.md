# 制造成果参展摘要与跨展项口径核对

业务资料使用虚构编号和合成叙述。文本保持来件拼写和措辞。各表是独立的来源记录。
TSV 文件采用 UTF-8，首行为列名。行首 id 是该表的稳定记录号，空格和标点属于原文，空单元格表示来件未填。
日期时间采用所在地本地时间。资料内注明为编号列表的字段用竖线分隔。

## 资料字段

- `materials/sources.tsv`。audience 是来件给定的最高披露范围，relates 是来件实际列出的来源引用。plan 表明观察来源还是在评估计划中。
- `materials/exhibits.tsv`。refs 是展项作者列出的文书，竖线分开。topic 是主办方选定的受众主题。
- `materials/releases.tsv`。limit 是以半宽为单位的可排字格数，phase 是版面的当前状态。source_event 是发布团队记录的来源变更。
- `materials/print_log.tsv`。surface 是当前安装的版面，exhibits 是版面上实际编排的展项，竖线分隔。
- `materials/priorities.tsv`。importance 是编辑确定的必讲或补充主题。allowed_formats 是素材台登记的渠道，竖线分隔。
- `materials/issuances.tsv`。出具与存放登记，board_code 为印在该份实物上的码标。
- `materials/permissions.tsv`。场馆收到的授权变更来函，at 为收到时间。

展板以固定字号排印。ASCII 字符各占一格，汉字和全宽标点各占两格。内页按整份文字共用字格。

## 运行资料检查

使用 CPython 3.11.2 和标准库。资料检查仅读取输入。

```sh
python3 pack_check.py
python3 -m unittest -v
# 若按环境要求以隔离模式读取资料：
python3 -I /workspace/pack_check.py
python3 -I /workspace/run_tests.py
```

## 编校项目入口

项目代码在 `exhibition/`，只依赖标准库。它会复用 `pack_check.read_tables` 做格式和引用校验，然后完成主张抽取、范围/单位/模态核对、授权与撤回判断、同边界替换、字格规划、补件清单、同步更正和按码标解析实物版本。

```sh
# 生成 out/editorial_report.json 与 out/editorial_report.md
python3 main.py --themes T1,T2,T3

# 只选必讲主题，也可重复传参
python3 main.py --theme T1

# 指定下一届资料包目录
python3 main.py --directory /path/to/materials --themes T1,T2

# 模拟某个二维码的扫码结果
python3 main.py --scan N17-zh-r1

# 编校决定把夜班子组只保留为内部核查（无授权时不能改成公开发布）
python3 main.py --merge-decision MRG-T8-LINE-NIGHT=retain_internal_only
```

Python API：

```python
from exhibition import EditorialService, publish_selected_themes

report = publish_selected_themes(["T1", "T2", "T3"], directory="materials")

service = EditorialService("materials")
plan = service.plan(["T1", "T3"])
qr = service.scan_response("N17-zh-r1")
service.decide_merge("MRG-T8-LINE-NIGHT", "retain_internal_only", editor="Beryl")
```

## 输出如何对应编校要求

- `claims` / `exhibit_claims`：抽取基线、现值、百分点或相对百分比、升降方向、指标、对象线别/班次/全厂范围、观察或预估、对照和“同期/该线/同一试验”等指代。
- `anaphora`：把指代回查到登记的同一周、T8 试验或通过展项上下文确定的“同名指标”；没有日期时明确不编造日期。
- `exhibit_reviews`：列出来稿超字格、撤回、授权不足、范围升级、单位混淆、模态不符、假独立印证和待核项。
- `zones.fact_zone`：仅放仍有凭据且至少有一个渠道授权的事实；`zones.pending_zone` 只作待核，不进入版面事实区。
- `merge_reviews`：展示共同/复算试验与局部子组若合并会失去的限制，并保留来源原话。缺少授权时，编校决定也不能把它改成公开发布。
- `plan.boards`：按 `releases.limit` 逐板核算。P1/P2 是各自中英展板，P3 是整份共用 260 格的双语扫码内页。排不下时先尝试保留对象、数字、单位、对照和模态的准确短写；仍排不下就移除主张并在 `omitted_themes` 与 `material_requests` 中交给负责人。
- `plan.shared_sentence_check` / `evaluate_shared_sentence()`：一句短写覆盖两项主题时，中文和英文都必须完整支持两项范围且分别过字格；半句话分工或重复排印不算达标。
- `corroboration_ledger`：按 `trial` 去重。V1/V2/V4/V6 都属 T8，多个短写或版面重复不会增加独立印证次数。
- `correction_release`：生成同一 `correction_id`、同一签发时间的中英同步更正；P1 已上墙与 P2 已印未贴的换稿动作不同，并标明不需要整板停发。
- `scan_responses`：按 `board_code` 绑定的实物出具时间、版本、修订状态、适用版本提示、旧板纠正提示、不同换稿动作和仍有凭据内容。公开扫码载荷会剔除仅审核来源的细表/原话，避免向扫码受众披露其未获授权阅读的资料。
- `editor_audit.theme_trace`：编辑可从主题反查每个版面实际排出的文字、事实、来源，以及哪些展项需要补什么边界的材料。

## 本届资料的当前结论

- T1「改善良率」可同时覆盖 P1 中文板和 P2 英文板：一号线 `70%→80%` 应写 **+10 个百分点 / +10 pp**，对照为同周、比上月同线；V1 初稿撤回后由同 T8、同边界、已授权的 V4 复算段替换。V1/V4 只算一次试验。
- E2 的 `plant-wide` 与 `two independent validations` 不成立；英文板已改为 Line 1、one trial。
- T2「返工计划」只能进 P3 扫码内页，且必须写明 V3 是“预计总体降 10%、尚未测量”。E5 的“首次换型后日夜合计”无同边界证据，列为待核并生成补件范围。
- T3「夜班表现」在 P1/P2 均不能覆盖：V2 仅审核、未获外发授权；V5 是 T10 二号线日班 `92%→91%`，不能替代 T8 一号线夜班 `60%→66%`。负责人需补 V2 外发授权或同边界公开原件。
- `N17-zh-r1` 是仍在墙上的旧版：立即用扫码页/板旁提示纠正，闭馆后换 r2。`N17-en-r1` 已印未贴：不得上墙，直接换印 r2 并封存/销毁 r1。
