# 需求结论与产品决策

### 结论 1 — 2026-03-11
背景：Phase 1F 完成后，Codex 路径的真实会话验收已基本符合预期；Claude 路径暂时搁置，不再阻塞当前版本收口。
结论：
- 若暂不要求 Claude 的增强交互一并完成，则 durable-memory v1 MVP 可视为完成。
- Codex 路径作为当前默认使用路径。
- 后续工作从“继续重构”切换为“真实使用 + 体验优化 + Claude 补验”。

### 结论 2 — 2026-03-11
背景：近期收尾事项中的 review 队列清理、真实任务观察和 backlog 归类已完成，剩余问题已不再属于 MVP 阻塞项。
结论：
- review 队列清理完成后，当前 durable memory 状态可进入真实使用。
- 真实任务观察通过后，boot-first、review show handoff 和文本三分叉可按当前规则继续使用。
- 延期项统一进入 post-MVP backlog，不再混入 v1 结论。

### 结论 3 — 2026-03-11
背景：v1 MVP 已收口，下一阶段需要开始规划 post-MVP 路线，但必须避免把远期平台化能力混入 v2 主线，重新放大范围。
结论：
- v2 主线只包含四项能力：自动会话提炼、语义检索 / 混合检索、review surface 提升、`.memory` 与 `.memoryhub` 的迁移 / 导出策略。
- Claude 路径补验、Claude 结构化确认交互、review 摘要 / diff 展示优化继续归入 v1.x 体验优化，不纳入 v2 主线。
- 多租户、远程服务、图结构、alias、多跳关系等平台化方向明确降级为更后续版本议题，不参与 v2 范围定义。

### Post-MVP Backlog 分层

v1.x 体验优化：
- Claude 路径补验
- Claude 结构化确认交互验证
- review 摘要 / diff 展示优化

v2 主线：
- 自动会话提炼
- 语义检索 / 混合检索
- review surface 提升
- `.memory` 与 `.memoryhub` 迁移 / 导出策略

更后续版本：
- 图结构、alias、多跳关系
- 多租户、远程部署
