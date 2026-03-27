# Init 深度改版：进展封存

> 日期：2026-03-23
> 状态：Phase 1-3 已完成，已发现优化点待后续处理

---

## 已完成的修改

### Phase 1: scan-modules 输出改进（`lib/scan_modules.py`）

**1a. `_pick_notable_files` 按子目录分配**

- 原逻辑：全局拍平取 top-15，深层子目录无代表
- 新逻辑：三阶段选择
  - Phase 1：每个直接子目录至少选 1 个代表（NOTABLE_PATTERNS 优先），超预算截断
  - Phase 2：剩余预算填充 NOTABLE_PATTERNS
  - Phase 3：按 sorted 顺序填充其余文件
- 签名变更：`_pick_notable_files(files, module_prefix="")` 新增 module_prefix 参数

**1b. 新增 `_build_dir_tree(files, module_prefix, max_depth=2)`**

- 从文件列表构建紧凑目录树字符串
- 附带每个子目录的文件计数
- 示例输出：`common/ (13 files)\nnetwork/ (65 files)`

**1c. 输出 JSON schema 扩展**

- 每个 module dict 新增 `total_files`（int）和 `dir_tree`（string）

### Phase 2: catalog/modules/*.md 格式升级（`lib/catalog_update.py`）

**`_generate_module_md` 重写**

新增 5 个可选 section（缺失时 graceful degrade）：
1. `## 职责` — 来自 `purpose` 字段
2. `## 关键抽象` — 来自 `key_abstractions` 列表
3. `## 内部依赖` — 来自 `internal_deps` 列表
4. `## 目录结构` — 来自 `dir_tree` 字段（code block）
5. `## 代表文件` — 文件路径用反引号包裹

### Phase 3: init.md 模板重写

**Step 3 新增 3d：architecture.md 生成**
- 4 个必填 section：整体架构、模块依赖关系、关键设计模式、通信机制
- 强制约束：每个 claim 引用源码路径，必须 Read 实际文件

**Step 4 拆为两轮分析**
- Round 1（结构分析）：每个模块 Read 清单+入口文件，填 summary/purpose/internal_deps
- Round 2（深度分析）：最多 8 个非平凡模块，Read 核心源码，填 key_abstractions + 修正 description

**同步更新**：omni_sunpure 的 init.md 模板（CLI 命令为 `memory-hub` 而非 `python3 -m lib.cli`）

### 测试

- 全量 108 个测试通过
- 新增 11 个测试：
  - `test_scan_modules.py`：子目录分配（5）、dir_tree（4）、total_files/dir_tree 字段（2）、深层模块覆盖（2）
  - `test_catalog.py`：全字段格式输出（1）、可选字段缺失降级（1）

---

## 已发现的问题

### P1: assets 静态资源污染文件选择（高优先）

**现象**：module_lora（323 files）的 15 个代表文件中，大量被 `assets/` 下的静态 JS 占据（jquery.js、echarts.min.js、app.7e6dacda.js），真正的业务代码（lib/networks/65、lib/store/68、lib/ui/110）几乎未覆盖。

**根因**：
1. `assets/Sunpure_BigScreen/js/index.js` 命中 NOTABLE_PATTERNS
2. Phase 3 按 sorted 顺序填充，`assets/` 排在 `lib/` 前面吃掉了剩余预算
3. `SOURCE_EXTS` 包含 `.js`，无法区分源码和 vendor/dist 产物

**修复方向**：
- 方案 A：Phase 3 填充时优先选非 assets/dist/vendor 目录的文件
- 方案 B：新增 `DEPRIORITY_DIRS`（assets、dist、static、vendor、generated），这些目录的文件在 Phase 3 排最后
- 方案 C：识别 minified/bundled 文件（含 `.min.`、hash 后缀如 `.7e6dacda.`）自动排除

**推荐**：方案 B + C 组合，简单有效。

### P2: pubspec.yaml 未进入 NOTABLE_PATTERNS

Flutter 项目的核心清单文件 `pubspec.yaml` 不在 `NOTABLE_PATTERNS` 中，导致模块的 pubspec.yaml 不会被优先选为代表文件。

**修复**：在 `NOTABLE_PATTERNS` 中添加 `"pubspec.yaml"`。

### P3: dir_tree 文件计数在某些层级显示 0

`network/ (0 files)` 出现在 dir_tree 中，实际意义是该目录本身没有直接文件，但子目录有。逻辑正确但视觉上可能困惑。

**修复方向**：
- 方案 A：不显示 0 files 的行，让子目录自然缩进
- 方案 B：改为显示递归总数 `network/ (37 files total)`
- 方案 C：保持现状（最精确）

---

## 下一步计划

### 短期（本轮后续）

1. **修复 P1**：在 `_pick_notable_files` 的 Phase 3 中实现降权逻辑
2. **修复 P2**：NOTABLE_PATTERNS 添加 `pubspec.yaml`
3. **端到端验证**：删除 omni_sunpure 的 `.memory/` 重新执行 `/memory-hub:init`，检查：
   - 模块文档丰富度（应有职责、关键抽象、内部依赖等 section）
   - architecture.md 是否基于实际代码生成
   - BRIEF.md 行数（<200）

### 中期（可选优化）

4. **dir_tree 计数优化**：解决 P3（0 files 显示问题）
5. **scan-modules 增加 `pubspec.yaml` / `build.gradle` 解析**：从清单文件提取 dependencies，自动填充 `internal_deps`
6. **Round 2 智能选择**：当前按模块顺序取前 8 个，改为按 `total_files` 降序或按复杂度指标选择

### 长期方向

7. **增量 init**：当前增量更新模式（Step 6）指令较弱，可以对比上次 scan-modules 的 diff，只分析变化的模块
8. **architecture.md 自动更新**：模块索引变化时触发 architecture.md 的局部更新

---

## 涉及文件清单

| 文件 | 修改类型 |
|------|----------|
| `lib/scan_modules.py` | 已修改 |
| `lib/catalog_update.py` | 已修改 |
| `.claude/commands/memory-hub/init.md` | 已修改 |
| `tests/test_scan_modules.py` | 已修改 |
| `tests/test_catalog.py` | 已修改 |
| `omni_sunpure/.claude/commands/memory-hub/init.md` | 已同步 |

---

## 恢复工作指引

恢复时的操作顺序：

1. 读取本文档了解进展
2. 从 P1 开始修复（assets 降权）
3. 修复 P2（pubspec.yaml）
4. 跑 `pytest tests/` 确认绿色
5. 对 omni_sunpure 执行端到端验证
