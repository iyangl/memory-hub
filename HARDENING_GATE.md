# Hardening Gate Checklist (Memory Hub)

## 1) 当前阶段定义
- 阶段: `Feature Complete + Hardening`
- 目标: 停止新增能力，收敛高风险边界，建立可重复验证机制。

## 2) 变更策略
- 只允许两类改动:
  - 修复 `High` 风险问题
  - 为不变量补充契约测试
- 禁止:
  - 新功能
  - 大规模重构
  - 非必要接口变更

## 3) 五条硬不变量 (必须全部满足)
1. `project_id` 隔离: 跨项目读写必须拒绝。  
2. workspace 绑定一致: `pull/push/catalog/worker` 全入口都校验同一绑定。  
3. migration 可恢复: 迁移要么原子完成，要么可自愈恢复。  
4. 协议一致: MCP `tools/list` schema 与运行时校验一致。  
5. 作业幂等: `catalog_jobs` 不重复 claim，不重复处理，同步链可追溯。  

## 4) Gate 验收标准
- Gate A: 全量测试通过  
  - `python3 -m unittest discover -s tests -v`
- Gate B: 不变量契约测试通过  
  - 每条不变量至少 1 个正向 + 1 个反向用例
- Gate C: 连续 2 轮 Code Review 无 `High`
- Gate D: 仅允许新增/修改与 Hardening 相关文件

## 5) 风险处理规则 (防止无限修改)
- `High`: 必修，阻塞合并。
- `Medium`: 进入 `risk_backlog.md`，仅在触发路径高频时升为当前迭代。
- `Low`: 记录即可，不阻塞。
- 同一问题最多允许 2 次修复尝试，第二次失败必须先补“失败复盘 + 新测试”再改代码。

## 6) 每次修复最小交付
- 必须同时提交:
  - 代码修复
  - 复现测试（先失败后通过）
  - 风险条目状态更新（Open -> Fixed）

## 7) PR Checklist (可直接粘贴)
- [ ] 本 PR 未引入新功能，仅修复 hardening 问题
- [ ] 对应风险级别已标注 (`High/Medium/Low`)
- [ ] 已补契约测试（含反向用例）
- [ ] 全量测试通过
- [ ] MCP schema 与运行时校验一致
- [ ] 不变量影响评估已填写（5 条逐项）
- [ ] 若问题复发，已附失败复盘与根因

## 8) 退出 Hardening 条件
- 连续 2 个迭代窗口无 `High` 新增问题
- 5 条不变量契约测试稳定通过
- 跨会话命中率验收达标（总 >= 90%，单项目 >= 85%）
