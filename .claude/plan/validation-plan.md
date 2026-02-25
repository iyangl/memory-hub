# Memory Hub 验证计划

> 从零开始，逐步验证每个命令和关键链路。
> 所有命令在项目根目录执行，使用 `python3 -m lib.cli` 代替 `memory-hub`。

---

## 第一步：init — 创建骨架

```bash
python3 -m lib.cli init
```

验证点：
- [ ] 返回 `"ok": true`
- [ ] `.memory/` 目录已创建
- [ ] 5 个基础文件存在且为空：`pm/decisions.md`、`architect/tech-stack.md`、`architect/decisions.md`、`dev/conventions.md`、`qa/strategy.md`
- [ ] `catalog/topics.md` 存在且包含 `## 代码模块` 和 `## 知识文件` 两个 section
- [ ] `catalog/modules/` 目录存在
- [ ] `repair_result` 中 `ai_actions` 列出 5 个 `missing_registration`（基础文件未注册，符合预期——由 AI 在 Skill 流程中通过 write 注册）

```bash
# 确认目录结构
ls -R .memory/
```

---

## 第二步：init 幂等性 — 重复执行报错

```bash
python3 -m lib.cli init
```

验证点：
- [ ] 返回 `"ok": false, "code": "ALREADY_INITIALIZED"`
- [ ] `.memory/` 内容未被修改

---

## 第三步：write — 写入知识文件

### 3a. overwrite 模式写入 tech-stack

```bash
python3 -c "import sys; sys.stdout.write('## 技术栈\n\n- Python 3.10+\n- 纯标准库，无外部依赖\n- CLI 入口：python3 -m lib.cli\n')" | python3 -m lib.cli write architect tech-stack.md --topic tech-stack --summary "技术栈、关键依赖、使用方式与限制" --mode overwrite
```

验证点：
- [ ] 返回 `"ok": true`，`bytes_written` > 0
- [ ] `.memory/architect/tech-stack.md` 内容正确
- [ ] `.memory/catalog/topics.md` 的「知识文件」section 下出现 `### tech-stack` 和 `- architect/tech-stack.md — 技术栈、关键依赖、使用方式与限制`

### 3b. overwrite 模式写入 conventions

```bash
python3 -c "import sys; sys.stdout.write('## 目录结构\n\n- bin/ — CLI 入口\n- lib/ — 核心 Python 模块\n- tests/ — 测试\n- skills/ — Skill 提示词\n')" | python3 -m lib.cli write dev conventions.md --topic conventions --summary "目录命名规则、模块组织方式、代码约定" --mode overwrite
```

验证点：
- [ ] `.memory/dev/conventions.md` 内容正确
- [ ] `topics.md` 新增 `### conventions` 条目

### 3c. append 模式追加内容

```bash
python3 -c "import sys; sys.stdout.write('\n## 命名约定\n\n- 文件名：snake_case\n- 类名：PascalCase\n')" | python3 -m lib.cli write dev conventions.md --topic conventions --summary "目录命名规则、模块组织方式、代码约定" --mode append
```

验证点：
- [ ] `.memory/dev/conventions.md` 同时包含「目录结构」和「命名约定」两个 section
- [ ] `topics.md` 中 conventions 条目未重复（更新而非新增）

### 3d. 创建新文件

```bash
python3 -c "import sys; sys.stdout.write('## 缓存策略\n\n当前不使用缓存。\n')" | python3 -m lib.cli write architect caching.md --topic caching --summary "缓存策略与决策"
```

验证点：
- [ ] `.memory/architect/caching.md` 被创建
- [ ] `topics.md` 新增 `### caching` 条目

---

## 第四步：read — 读取知识文件

### 4a. 正常读取

```bash
python3 -m lib.cli read architect tech-stack.md
```

验证点：
- [ ] 返回 `"ok": true`，`data.content` 包含写入的内容

### 4b. 带有效锚点读取

```bash
python3 -m lib.cli read architect tech-stack.md --anchor 技术栈
```

验证点：
- [ ] `data.anchor_valid` 为 `true`

### 4c. 带无效锚点读取

```bash
python3 -m lib.cli read architect tech-stack.md --anchor 不存在的标题
```

验证点：
- [ ] `data.anchor_valid` 为 `false`
- [ ] `data.repair_triggered` 为 `true`
- [ ] 返回中包含 repair 结果

### 4d. 读取不存在的文件

```bash
python3 -m lib.cli read architect nope.md
```

验证点：
- [ ] 返回 `"code": "FILE_NOT_FOUND"`

---

## 第五步：list — 列出桶内文件

```bash
python3 -m lib.cli list architect
```

验证点：
- [ ] `data.files` 包含 `decisions.md`、`tech-stack.md`、`caching.md`

---

## 第六步：search — 全文检索

```bash
python3 -m lib.cli search "Python"
```

验证点：
- [ ] `data.total` >= 1
- [ ] 匹配结果中包含 `architect/tech-stack.md`

```bash
python3 -m lib.cli search "zzzznotfound"
```

验证点：
- [ ] `data.total` == 0

---

## 第七步：catalog-update — 更新代码模块索引

```bash
python3 -c "import sys,json; sys.stdout.write(json.dumps({'modules':[{'name':'core','summary':'核心模块：CLI、envelope、路径','files':[{'path':'lib/cli.py','description':'CLI 分发器'},{'path':'lib/envelope.py','description':'统一 JSON envelope'},{'path':'lib/paths.py','description':'路径常量与验证'}]},{'name':'memory','summary':'知识读写命令','files':[{'path':'lib/memory_read.py','description':'memory.read'},{'path':'lib/memory_write.py','description':'memory.write'},{'path':'lib/memory_list.py','description':'memory.list'},{'path':'lib/memory_search.py','description':'memory.search'},{'path':'lib/memory_init.py','description':'memory.init'}]},{'name':'catalog','summary':'索引管理命令','files':[{'path':'lib/catalog_read.py','description':'catalog.read'},{'path':'lib/catalog_update.py','description':'catalog.update'},{'path':'lib/catalog_repair.py','description':'catalog.repair'}]}]},ensure_ascii=False))" | python3 -m lib.cli catalog-update
```

验证点：
- [ ] 返回 `"ok": true`
- [ ] `catalog/modules/core.md`、`catalog/modules/memory.md`、`catalog/modules/catalog.md` 三个文件被创建
- [ ] `topics.md` 的「代码模块」section 列出三个模块
- [ ] `repair_result` 已自动执行

```bash
# 验证 catalog-read 能读到模块索引
python3 -m lib.cli catalog-read core
```

验证点：
- [ ] 返回 `data.content` 包含 `lib/cli.py`

---

## 第八步：catalog-read — 读取索引

```bash
python3 -m lib.cli catalog-read topics
```

验证点：
- [ ] 返回完整的 topics.md 内容
- [ ] 包含「代码模块」section（core、memory、catalog）
- [ ] 包含「知识文件」section（tech-stack、conventions、caching）

---

## 第九步：catalog-repair — 一致性检查

### 9a. 正常状态

```bash
python3 -m lib.cli catalog-repair
```

验证点：
- [ ] `fixed` 为空或仅包含预期项
- [ ] 检查 `ai_actions` 中是否有未注册的基础文件（pm/decisions.md、architect/decisions.md、qa/strategy.md 如果还没通过 write 注册的话）

### 9b. 制造死链接后修复

手动在 topics.md 中添加一行指向不存在文件的引用，然后执行 repair：

```bash
python3 -m lib.cli catalog-repair
```

验证点：
- [ ] `fixed` 中包含 `dead_link_removed`
- [ ] topics.md 中死链接行已被删除

---

## 第十步：端到端链路 — 完整生命周期

回顾整个流程：

1. `init` 创建骨架 ✓
2. `write` 填充知识 + 自动更新 topics.md ✓
3. `read` 精准读取 ✓
4. `search` 全文检索 ✓
5. `catalog-update` 更新代码模块索引 ✓
6. `catalog-read` 读取索引 ✓
7. `catalog-repair` 一致性自愈 ✓

最终验证：
- [ ] `catalog-read topics` 的输出是完整的、一致的入口索引
- [ ] 所有知识文件可通过 `read` 正确读取
- [ ] `catalog-repair` 返回 `fixed: [], ai_actions: [...仅剩未填充的空基础文件], manual_actions: []`

---

## 清理

验证完成后删除测试产生的 `.memory/` 目录：

```bash
rm -rf .memory/
```
