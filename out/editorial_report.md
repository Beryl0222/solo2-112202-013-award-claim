# 参展摘要编校报告

选中主题：T1, T2, T3

## 一、中英版面与字格
### P1 · 现场中文（zh） 54/55 格 ✅

- `P1-T1`，54 格，主题 T1

```text
良率：一号线70%至80%，升十个百分点；复算V4，比上月同线
```
- ⚠️ 未覆盖 T3（夜班表现）：来源仅限编辑核查，未获外发授权；补件请求：MR-E4-NIGHT-AUTH

### P2 · 现场英文（en） 104/105 格 ✅

- `P2-T1`，104 格，主题 T1

```text
Yield: Line1 70-80%, +10 percentage points (V4 recalc; vs prior-month same line; V1 withdrawn; 1 trial).
```
- ⚠️ 未覆盖 T3（夜班表现）：来源仅限编辑核查，未获外发授权；补件请求：MR-E4-NIGHT-AUTH

### P3 · 扫码内页（bilingual） 255/260 格 ✅

- `P3-INNER`，255 格，主题 T1,T2

```text
中：一号线70%-80%，+10个百分点（复算V4；比上月同线）。返工预计总体-10%（V3，尚未测量）。
EN: Line1 70-80%,+10pp(V4 recalc;week vs prior-month same line). Rework: forecast overall -10%(V3,unmeasured).
V1初稿撤回；V1/V4同T8。
V1 withdrawn; V1/V4 same T8 trial.
```

## 二、一句短写覆盖两项主题校验
- 结论：当前不可行
- 语言支持：{'zh': False, 'en': False}
- 规则：同一句短写只有在中文和英文都支持两项主题各自的范围时才成立；把两个半句话分别排印或重复排印不能算作一句双语达标
- 原因：T3 夜班事实 V2 未获外发授权，V5 边界不同；因此中文和英文均不能形成同时覆盖 T1+T3 的合规短写

## 三、合并会失去的限制与原话
### MRG-T8-LINE-NIGHT（试验 T8）
- 不建议合并；以下限制必须分别保留：
  - V2 是仅审核的夜班细表，未获外发准许。
  - 60%→66% 的绝对差是6个百分点，相对增幅才是10%/一成。
  - 同一周全部车间并未纳入试验，不能把一号线写成全车间结论。
  - V6 两班汇总约80%只是供稿员暂填，没有正式报告且未授权外发。
- 同试验独立印证数：1
- 当前有效决定：drop_external
- 原话：
  - `V1`：试件车间一号线，良率由 70% 到 80%，一周对照，比上月同线。
  - `V2`：同一周全部车间没纳入试验；一号线夜班良率由 60% 到 66%。
  - `V6`：投产汇总的两班良率没有出正式报告，供稿员暂填约 80%。
  - `V4`：同一条一号线同一周，统计复盘消除重件后仍为 70% 至 80%。

## 四、展项核对发现
### E1 · 改善良率（zh）
来稿：一号线良率提升十个百分点，全车间验证成功。同一试验夜班也提升一成。
- [warning] `DRAFT_OVER_LIMIT` 来稿占 66 格，超过P1登记上限 55 格，不能原样上板
- [correction] `WITHDRAWN_WITH_REPLACEMENT` V1 已撤回；可用同边界、同授权的 V4 作同义/复算替换，不能把两者说成独立印证
- [block] `AUTHORIZATION_MISSING` V2 仅限编辑核查、未获外发授权，且无同边界授权替换件
- [block] `PENDING_VERIFICATION` “workshop”层级的验证结论没有同范围来文证据；该核心范围只能降级为待核，不能进入事实区
- [warning] `RELATIVE_RATE_QUALIFIER_REQUIRED` “一成/10%”是相对基线的幅度；若要与“六个百分点”并列，必须写明“相对提高10%”，不能与6pp混写

### E2 · 改善良率（en）
来稿：Two independent validations confirm a 10% plant-wide yield increase.
- [correction] `WITHDRAWN_WITH_REPLACEMENT` V1 已撤回；可用同边界、同授权的 V4 作同义/复算替换，不能把两者说成独立印证
- [block] `SCOPE_ESCALATION` 对象范围过宽：主张为plant，证据仅为line
- [correction] `UNIT_MISMATCH` 相对幅度不符：主张10%，证据相对变化14.29%
- [block] `PENDING_VERIFICATION` 该主张的核心范围或单位不能由所引来文支持；在补证前只能列为待核
- [correction] `FALSE_INDEPENDENCE` T8 中各文书有初稿/复算或引用关系，只能算一次试验，不能写成两次独立印证
- [block] `PENDING_VERIFICATION` “plant”层级的验证结论没有同范围来文证据；该核心范围只能降级为待核，不能进入事实区

### E3 · 返工计划（zh）
来稿：新设备使整体返工率下降 10%。
- [correction] `MODALITY_MISMATCH` 来稿用已发生语气报道，但来源仍在预估且未到测量期；公开稿必须写明“预计/预估、尚未测量”

### E4 · 夜班表现（en）
来稿：In the same night trial, first-line yield rose by six percentage points.
- [block] `AUTHORIZATION_MISSING` V2 仅限编辑核查、未获外发授权，且无同边界授权替换件

### E5 · 返工计划（zh）
来稿：首次换型后日夜合计返工率预计减少一成。
- [block] `AUTHORIZATION_MISSING` V6 仅限编辑核查、未获外发授权，且无同边界授权替换件
- [warning] `UNSUPPORTED_CORE_SCOPE` 缺少日夜合计口径；无证据的扩写范围降级待核，只能保留来源实际覆盖的短写
- [warning] `UNSUPPORTED_CORE_SCOPE` 缺少首次换型后的阶段边界；无证据的扩写范围降级待核，只能保留来源实际覆盖的短写

## 五、需向展项负责人补交资料的范围
### MR-E4-NIGHT-AUTH · E4 · 夜班表现
- 同时关联：E1
- 需要范围：T8 试验中一号线夜班子组、同一周、良率基线60%与现值66%的外发授权；并确认按+6个百分点还是相对+10%表述。
- 可接受证据：V2 保管方出具的公开发布授权，或另一件已授权原件，且边界必须同为 T8、一号线、夜班、同一周及相同工单/采集范围。
- 不能替代：`V5` — T10、二号线、日班采集，92%→91%，试验/线别/班次/方向均不同
- 不能替代：`V6` — 仅审核、无正式报告、约80%为暂填，且是两班汇总而非夜班子组

### MR-E1-WORKSHOP · E1 · 改善良率
- 需要范围：可公开引用的全车间/全厂 T8 汇总良率报告，含基线、现值、周期、产线/班次覆盖和是否消除重件。
- 可接受证据：经统计/质量负责人签发的公开汇总件，覆盖边界至少等于稿中“全车间验证成功”。
- 不能替代：`V1/V4` — 仅覆盖试件车间一号线同一周，不能外推全车间
- 不能替代：`V2` — 称同一周全部车间未纳入试验，且仅审核
- 不能替代：`V6` — 两班良率约80%为暂填，无正式报告且仅审核

### MR-E2-PLANT-INDEPENDENCE · E2 · 改善良率
- 需要范围：若保留 plant-wide 与 two independent validations，需要全厂口径审计件，以及与 V1/V4 无初稿—复算或引用关系的第二次独立试验。
- 可接受证据：覆盖全厂的基线/复核算术报告，加一个不同 trial 编号、不同数据集或独立机构出具的验证。
- 不能替代：`V1/V4` — 同为 T8；V4 明确 relates V1，是消除重件后的复算，不是独立验证

### MR-E5-REWORK-AFTER-CHANGEOVER · E5 · 返工计划
- 需要范围：首次换型后、日夜合计的返工率实测/预测口径，含基线、目标或实测值、统计区间和授权渠道。
- 可接受证据：V3 保管方补充的换型后日夜合计测量期数据，或另一件覆盖该边界的扫码公开/现场公开原件。
- 不能替代：`V3` — 只支持新装备总体返工率预计降10%，明确未到测量期，未给换型后日夜合计边界
- 不能替代：`V6` — 指标是两班良率且为暂填，不是返工率，也未授权外发

## 六、同步更正签发与实物动作
- 更正签发号：CORR-20261021-SYNC
- 同步签发时间：2026-10-21T11:35
### zh · P1
- 字格：54/55，排得下：True
```text
良率：一号线70%至80%，升十个百分点；复算V4，比上月同线
```
- 实物动作：已上墙且闭馆前不能回收：立即在二维码/板旁更正提示中标明旧版有误，闭馆后换挂 N17-zh-r2；不整板停发可凭据的一号线口径。
### en · P2
- 字格：104/105，排得下：True
```text
Yield: Line1 70-80%, +10 percentage points (V4 recalc; vs prior-month same line; V1 withdrawn; 1 trial).
```
- 实物动作：已印未贴：DA2/N17-en-r1 不得上墙，换印 N17-en-r2 后再安装；r1 封存或销毁，避免公众扫到未注明状态的旧码。同板改用已更正的一号线口径，不必取消整个展点。
### scan_inner · P3
- 字格：255/260，排得下：True
```text
中：一号线70%-80%，+10个百分点（复算V4；比上月同线）。返工预计总体-10%（V3，尚未测量）。
EN: Line1 70-80%,+10pp(V4 recalc;week vs prior-month same line). Rework: forecast overall -10%(V3,unmeasured).
V1初稿撤回；V1/V4同T8。
V1 withdrawn; V1/V4 same T8 trial.
```
- 实物动作：开放扫码内页：更新 N17-web-r1 指向的页面并保留修订记录；纸质取阅内页用完即换，旧夹页加盖更正或撤下。

## 七、扫码版本响应
### N17-zh-r1 · DA1 · wall_edition_r1_visible_pending_closure_replacement
- 出具时间：2026-10-21T09:00；更正时间：2026-10-21T11:35
- 适用版本：本结果按码标绑定的 N17-zh-r1 / DA1 中文上墙旧版出具；您眼前看到的仍是旧板，以下更正适用于该旧版。
- 纠正提示：【旧板更正】V1 初稿已撤回；“全车间验证成功”无证据，“夜班提升一成”所依据的细表未获外发授权。可保留事实仅为：一号线70%至80%，升10个百分点（V4复算，比上月同线）。
- 换稿动作：已上墙且闭馆前不能回收：立即在二维码/板旁更正提示中标明旧版有误，闭馆后换挂 N17-zh-r2；不整板停发可凭据的一号线口径。
- 仍有凭据内容：
```text
良率：一号线70%至80%，升十个百分点；复算V4，比上月同线
```
### N17-en-r1 · DA2 · printed_r1_withheld_replace_before_install
- 出具时间：2026-10-21T10:00；更正时间：2026-10-21T11:35
- 适用版本：This result is bound to N17-en-r1 / DA2, the printed-but-not-installed English edition. Do not treat r1 as the current public board.
- 纠正提示：[Correction] “Two independent validations” and “plant-wide” are not supported. V1 is withdrawn; V4 is a same-trial recalculation. Credentialed fact: Line1 70%-80%, +10pp.
- 换稿动作：已印未贴：DA2/N17-en-r1 不得上墙，换印 N17-en-r2 后再安装；r1 封存或销毁，避免公众扫到未注明状态的旧码。同板改用已更正的一号线口径，不必取消整个展点。
- 仍有凭据内容：
```text
Yield: Line1 70-80%, +10 percentage points (V4 recalc; vs prior-month same line; V1 withdrawn; 1 trial).
```
### N17-web-r1 · DA3 · scan_edition_revised_with_history
- 出具时间：2026-10-21T10:00；更正时间：2026-10-21T11:35
- 适用版本：本结果按 N17-web-r1 / DA3 扫码内页出具；页面已按同步更正口径修订，并保留出具与修订记录。/ This is the N17-web-r1 / DA3 scan inner page with the synchronized revision history.
- 纠正提示：扫码页当前仅展示有授权、有凭据的事实；无证据扩写列为待核。
- 换稿动作：开放扫码内页：更新 N17-web-r1 指向的页面并保留修订记录；纸质取阅内页用完即换，旧夹页加盖更正或撤下。
- 仍有凭据内容：
```text
中：一号线70%-80%，+10个百分点（复算V4；比上月同线）。返工预计总体-10%（V3，尚未测量）。
EN: Line1 70-80%,+10pp(V4 recalc;week vs prior-month same line). Rework: forecast overall -10%(V3,unmeasured).
V1初稿撤回；V1/V4同T8。
V1 withdrawn; V1/V4 same T8 trial.
```

## 八、编辑主题回查
### T1 · 改善良率（必讲）— 已覆盖
- 关联展项：E1, E2
- 现场中文：covered
  - 事实 `F-V4-C1`：yield 70.0→80.0 delta=10.0percentage_point modality=observed comparator=prior_month_same_line+same_week trial=T8 source=V4
- 现场英文：covered
  - 事实 `F-V4-C1`：yield 70.0→80.0 delta=10.0percentage_point modality=observed comparator=prior_month_same_line+same_week trial=T8 source=V4
- 扫码内页：covered
  - 事实 `F-V4-C1`：yield 70.0→80.0 delta=10.0percentage_point modality=observed comparator=prior_month_same_line+same_week trial=T8 source=V4
### T2 · 返工计划（补充）— 已覆盖
- 关联展项：E3, E5
- 扫码内页：covered
  - 事实 `F-V3-C1`：rework_rate None→None delta=10.0percent modality=expected comparator=None trial=T9 source=V3
### T3 · 夜班表现（补充）— 未覆盖
- 关联展项：E4
- 现场中文：uncovered
- 现场英文：uncovered
- 需补材料：MR-E4-NIGHT-AUTH