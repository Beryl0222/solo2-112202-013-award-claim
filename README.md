# 制造成果参展摘要与跨展项口径核对

业务资料使用虚构编号和合成叙述。文本保持来件拼写和措辞。各表是独立的来源记录。
TSV 文件采用 UTF-8，首行为列名。行首 id 是该表的稳定记录号，空格和标点属于原文，空单元格表示来件未填。
日期时间采用所在地本地时间。资料内注明为编号列表的字段用竖线分隔。

## 资料字段

- `materials/sources.tsv`。audience 是来件给定的最高披露范围，relates 是来件实际列出的来源引用。plan 表明观察来源还是在评估计划中。
- `materials/exhibits.tsv`。refs 是展项作者列出的文书，竖线分开。topic 是主办方选定的受众主题。
- `materials/releases.tsv`。limit 是按 Unicode 字符计的可排字格，phase 是此发表物所处状态。source_event 可录入发布团队的来源事件。
- `materials/print_log.tsv`。surface 是当前安装的版面，exhibits 是版面上实际编排的展项，竖线分隔。
- `materials/priorities.tsv`。importance 是编辑确定的必讲或补充主题。allowed_formats 是素材台登记的渠道，竖线分隔。
- `materials/issuances.tsv`。出具与存放登记，board_code 为印在该份实物上的码标。
- `materials/permissions.tsv`。场馆收到的授权变更来函，at 为收到时间。

展板的 limit 记录字号固定后的半宽格数。空格、ASCII 字母、数字和标点均占一格，汉字和全宽标点占两格。内页按整份文字共用字格。

## 运行资料检查

使用 CPython 3.11.2 和标准库。资料检查仅读取输入。

```sh
python3 pack_check.py
python3 -m unittest -v
```
