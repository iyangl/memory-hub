# Memory Hub End-of-Task Probe Trigger Samples

日期：2026-03-11  
状态：草案

## 1. 目的

这份样本集用于验证 `end-of-task probe` 的三件事：

- 什么时候应该运行 probe
- 什么时候应该跳过 probe
- probe 运行后，期望结果应是 `NOOP`、`docs-only`、`durable-only` 还是 `dual-write`

它不是通用记忆系统触发样本，而是专门面向“任务结束前的强制自检”。

## 2. 使用方式

对每个样本，依次检查：

1. 最终答复前是否应运行 probe
2. 若运行，预期结果是什么
3. 若结果涉及 durable，是否满足 boot-first、`why_not_in_code`、`recall_when`

## 3. Should Run Probe

### R01

- Scenario: 本次任务中，用户明确表达了稳定偏好“默认中文、答复尽量简洁”，并要求后续会话沿用。
- Why: 跨会话稳定偏好，且不适合放进正式项目 docs
- Expected probe: run
- Expected outcome: `durable-only`

### R02

- Scenario: 本次任务完成了新项目 bootstrap/intake 方案，并明确将其作为 `memory-admin` 的后续候选工作流。
- Why: 形成了正式项目知识，应进入项目文档体系
- Expected probe: run
- Expected outcome: `docs-only`

### R03

- Scenario: 本次会话明确达成结论，`end-of-task probe` 是 `project-memory` 的内部收尾步骤，不新增新的公开 skill / MCP 主入口。
- Why: 这是稳定的产品决策，既应进入 docs，也值得后续跨会话快速召回
- Expected probe: run
- Expected outcome: `dual-write`

### R04

- Scenario: 本次任务只是一次无行为变化的代码重构，最终代码、测试和现有 docs 已足以恢复全部结论。
- Why: 任务是有效任务，但没有新增值得沉淀的知识
- Expected probe: run
- Expected outcome: `NOOP`

### R05

- Scenario: 本次任务发现并确认“memory 相关逻辑变更必须补自动化测试和自测记录”，且该约束此前未文档化。
- Why: 稳定项目约束，不仅应写入 docs，也会影响后续协作
- Expected probe: run
- Expected outcome: `dual-write`

### R06

- Scenario: 本次任务补齐了仓库 tech stack 和运行/测试方式扫描结果，但这些内容此前未进入 docs lane。
- Why: 正式项目知识，适合 docs lane
- Expected probe: run
- Expected outcome: `docs-only`

### R07

- Scenario: 本次任务里用户纠正了一个长期使用的非代码约定，例如“不要替我自动 rollback durable memory”。
- Why: 稳定协作约束，代码里不能恢复
- Expected probe: run
- Expected outcome: `durable-only` 或 `dual-write`
- Preferred decision: 若该约束属于仓库公开规则，则 `dual-write`；若只是用户协作偏好，则 `durable-only`

### R08

- Scenario: 本次任务结束时，probe 发现候选与现有记忆等价，或命中更合适的 update target。
- Why: probe 仍应运行，但不应制造重复候选
- Expected probe: run
- Expected outcome: `NOOP` 或 route 到 update target，而不是 create 新对象

## 4. Should Skip Probe

### S01

- Scenario: 纯 casual chat，没有项目上下文，也没有任务交付物。
- Why: 不属于 task-oriented 会话
- Expected probe: skip

### S02

- Scenario: 用户只要求把一段英文翻译成中文。
- Why: 纯语言任务，不需要项目记忆沉淀
- Expected probe: skip

### S03

- Scenario: 用户要求重写一段现成文案，但没有形成新的项目规则、结论或偏好。
- Why: 写作协助，不是知识沉淀
- Expected probe: skip

### S04

- Scenario: 用户问一个与当前仓库无关的一次性事实问题。
- Why: 与项目记忆无关
- Expected probe: skip

### S05

- Scenario: 用户明确说“这段不要记录，也不要记住”。
- Why: 用户显式禁止记忆沉淀
- Expected probe: skip

### S06

- Scenario: 会话中途终止，任务没有完成，也没有形成稳定结论。
- Why: 不满足“任务准备结束”的触发条件
- Expected probe: skip

## 5. Borderline Cases

### B01

- Scenario: 用户说“把这次调试结论记一下，后面可能还会用到”。
- Why: 可能是 docs、durable，也可能只是当前会话注释
- Preferred decision: 只有当结论已经稳定且超出代码可恢复范围时才运行并产出；否则 `NOOP`

### B02

- Scenario: 本次任务新增了一个命令，但 `README` 和测试里已经完整覆盖。
- Why: 可能没有额外沉淀价值
- Preferred decision: 运行 probe，但大概率 `NOOP`

### B03

- Scenario: 本次任务只是 brainstorming，提出了几个方案，但没有形成最终决策。
- Why: 有讨论价值，但未达到稳定知识门槛
- Preferred decision: 若无最终决策，probe 可运行但应返回 `NOOP`

### B04

- Scenario: 用户说“帮我保存这个结论，后面还要用”，但没有明确是项目 docs 还是跨会话个人偏好。
- Why: 保存意图明确，但落点不明确
- Preferred decision: probe 运行；优先 `docs-only`，只有明确满足 durable 门槛时才走 durable

### B05

- Scenario: 本次任务命中了一个已有 pending review，最终并未批准，只是讨论了是否值得保留。
- Why: 容易重复制造候选
- Preferred decision: probe 若运行，应优先命中现有 pending review，并避免创建新的等价候选

## 6. Review Checklist

- 是否只在 task-oriented 会话结束前运行 probe
- 是否在应跳过的样本上保持静默
- 是否优先给出 `NOOP`，而不是低价值候选
- 是否把正式项目知识优先路由到 `docs-only`
- 是否只在满足高门槛时才进入 `durable-only`
- 是否在需要 durable 的样本上仍遵守 boot-first 与 review handoff
