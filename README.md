# AstrBot WOT Plugin

AstrBot 插件，用于查询《坦克世界》玩家效率

## 目录说明

- `main.py`: AstrBot 插件注册与命令入口。
- `src/application`: 应用层，负责编排命令处理、查询流程和报表流程。
- `src/domain`: 领域模型与领域枚举。
- `src/infrastructure`: 基础设施层，包含网络客户端、解析器、仓储与网关实现。
- `src/settings`: 配置常量与消息模板。
- `src/jobs`: 定时任务入口（例如坦克数据同步调度）。
- `resources/static`: 模板、字体和静态数据。
- `runtime/report`: 运行时生成的 HTML/PNG 报表。

## 开发说明

- 运行产物位于 `runtime/`，不要提交到仓库。
- Python 缓存和测试缓存已通过 `.gitignore` 排除。
