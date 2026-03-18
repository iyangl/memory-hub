# 测试策略与质量约束

- 使用 pytest 进行单元测试
- 每个 lib/ 模块对应一个测试文件
- 所有 memory 相关改动都必须补回归测试
- memory 相关改动必须运行 `pytest -q`
