# Recall-First Implementation Checklist

> 当前执行以 `recall-first-redesign-plan.md` + `recall-first-contract.md` 为准
> `v3-phase1-dev-plan.md` 仅作历史实现参考，不作当前执行蓝图

---

## 0. 冻结边界

- [ ] 确认 `recall-first-redesign-plan.md` 已更新为最新版本
- [ ] 确认 `recall-first-contract.md` 已冻结
- [ ] 明确 docs 是唯一正本
- [ ] 明确 working set 是会话派生物
- [ ] 明确 `search before guess`
- [ ] 明确 `read before write`
- [ ] 明确 `/save` 支持 `noop / create / append / merge / update`

---

## 1. 实现 `recall-plan`

- [ ] 新增 `lib/recall_planner.py`
- [ ] `lib/cli.py` 注册 `recall-plan`
- [ ] 输入读取：BRIEF / topics / module cards
- [ ] 输出字段：`task_kind / recall_level / ambiguity / search_first / why_these / evidence_gaps`
- [ ] 对象不明确时先 search
- [ ] 不允许盲猜模块
- [ ] 新增 `tests/test_recall_planner.py`

---

## 2. 实现 `working-set`

- [ ] 新增 `lib/session_working_set.py`
- [ ] `lib/cli.py` 注册 `working-set`
- [ ] 仅在 `deep` 时执行
- [ ] 输出保留 sources
- [ ] 输出保留 evidence gaps
- [ ] working set 不可直接落长期 docs
- [ ] 新增 `tests/test_session_working_set.py`

---

## 3. 重构 `scan_modules`

- [ ] 保留 `name / dir_tree / total_files / files`
- [ ] 新增 `read_when / entry_points / read_order / implicit_constraints / known_risks / verification_focus / related_memory`
- [ ] 新增导航字段测试

---

## 4. 重构 `catalog_update`

- [ ] module card 改成阅读导航卡
- [ ] topics 代码模块区改成导航入口索引
- [ ] 兼容旧 schema 输入
- [ ] 更新 `tests/test_catalog.py`

---

## 5. 重构 `brief`

- [ ] BRIEF 变成 base brief / boot summary
- [ ] 优先抽取决策 / 约束 / 风险 / 验证策略
- [ ] 不再均匀拼接 docs 首段
- [ ] 更新 `tests/test_brief.py`

---

## 6. 更新 `memory_init` 与 paths

- [ ] 增加 `.memory/session/`
- [ ] init 后生成 BRIEF
- [ ] 更新 layout version
- [ ] 更新 `tests/test_memory_init.py`
- [ ] 更新 `tests/test_paths.py`

---

## 7. 重写 command 模板

- [ ] `/memory-hub:recall` 先执行 `recall-plan`
- [ ] 若 `search_first = true`，先 search 再决定来源
- [ ] `deep` 时构建 working set
- [ ] `/memory-hub:save` 使用 `noop / create / append / merge / update`
- [ ] `/memory-hub:init` 强调导航、约束、风险、验证重点

---

## 8. 端到端测试

- [ ] 新增 `tests/test_memory_flow.py`
- [ ] 覆盖 `init -> scan-modules -> catalog-update -> brief -> recall-plan -> working-set`
- [ ] 覆盖局部任务 / 模糊任务 / 高风险任务 / `noop`

---

## 9. 验收标准

- [ ] `recall-plan` 输出稳定 JSON
- [ ] `working-set` 每条 item 都有来源
- [ ] `/save` guard 语义清晰
- [ ] `.memory/catalog/modules/*.md` 变成阅读导航卡
- [ ] `BRIEF.md` 变成 boot summary
