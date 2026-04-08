# 🚀 STOI 迭代开发路线图

基于 [ultra-orchestration](https://github.com/keithhegit/ultra-orchestration) 架构理念的迭代开发计划

---

## 📊 当前状态 (v0.2.0)

### ✅ 已完成
- [x] 核心 CLI 功能 (analyze, init, tts, config)
- [x] Rich UI 双模式 (简洁 + 仪表盘)
- [x] 多模型提供商支持 (OpenAI/DashScope/Anthropic 等)
- [x] TTS 语音播报
- [x] SQLite 数据持久化
- [x] 配置管理系统
- [x] 基础测试套件 (5/6 通过)

### ⚠️ 已知问题
- 仪表盘模式在子进程中环境变量传递有问题 (不影响核心功能)

---

## 🎯 迭代规划

### Phase 1: 核心架构升级 (v0.3.0) - 本周

#### 1.1 数据模型重构 - Observation 树形结构
**目标**: 支持嵌套追踪，精确分析 LLM 调用链

**任务**:
- [ ] 创建 `observations` 表 (支持 parent_observation_id 嵌套)
- [ ] 创建 `traces` 表 (顶层执行追踪)
- [ ] 创建 `model_pricing` 表 (模型定价)
- [ ] 实现数据迁移脚本 (向后兼容)
- [ ] 更新数据库初始化逻辑

**验收标准**:
```python
# 可以创建嵌套观测
obs1 = observation.create(name="RAG流程", type="SPAN")
obs2 = observation.create(name="向量检索", type="RETRIEVER", parent=obs1.id)
obs3 = observation.create(name="LLM生成", type="GENERATION", parent=obs1.id)
```

#### 1.2 自动成本计算
**目标**: 实时 USD 成本追踪

**任务**:
- [ ] 内置主流模型定价表
- [ ] 实现 `calculate_cost()` 函数
- [ ] Observation 保存时自动计算
- [ ] UI 显示成本信息

**验收标准**:
- 每次 LLM 调用自动记录成本
- 支持按项目/用户/模型汇总成本

#### 1.3 异步批处理
**目标**: 内存队列 + 后台线程，降低性能开销

**任务**:
- [ ] 实现 `EventQueue` 内存队列
- [ ] 创建后台线程处理队列
- [ ] 批量写入数据库
- [ ] 配置参数：flush_at, flush_interval

**验收标准**:
- 追踪开销 < 10ms (当前 ~100ms)
- 支持高频调用 (100+ TPS)

---

### Phase 2: 客户端增强 (v0.4.0) - 下周

#### 2.1 @observe 装饰器
**目标**: 零侵入自动追踪

**任务**:
- [ ] 实现 `@observe()` 装饰器
- [ ] 支持同步/异步函数
- [ ] 自动捕获输入/输出/异常
- [ ] 自动计时和 Token 统计

**验收标准**:
```python
@observe(name="llm_call")
def call_openai(prompt):
    return client.chat.completions.create(...)
# 自动创建 Observation，无需手动调用
```

#### 2.2 流式输出支持
**目标**: 支持实时捕获 stdout/stderr

**任务**:
- [ ] 包装 sys.stdout/stderr
- [ ] 增量捕获流式输出
- [ ] 支持交互式 CLI 工具

#### 2.3 离线缓存
**目标**: 网络故障时不丢数据

**任务**:
- [ ] SQLite 本地队列存储
- [ ] 自动重传机制
- [ ] 断路器模式 (失败 N 次后暂停)

---

### Phase 3: 分析增强 (v0.5.0) - 第 3 周

#### 3.1 多源评分系统
**目标**: API + ANNOTATION + MODEL 评估

**任务**:
- [ ] 创建 `scores` 表
- [ ] 支持 NUMERIC/BOOLEAN/CATEGORICAL 评分
- [ ] 人工标注接口
- [ ] LLM-as-a-Judge 自动评估

#### 3.2 成本异常检测
**目标**: 自动发现 Token 使用异常

**任务**:
- [ ] 统计异常检测算法 (3-sigma)
- [ ] 成本阈值告警
- [ ] 异常时语音播报
- [ ] 异常分析报告

#### 3.3 数据导出
**目标**: 支持多种格式导出

**任务**:
- [ ] JSON/CSV 导出
- [ ] OTLP 协议支持
- [ ] Langfuse 格式兼容

---

### Phase 4: 生态集成 (v0.6.0) - 第 4 周

#### 4.1 LangChain 集成
**目标**: 原生 Callback 支持

**任务**:
- [ ] 实现 LangChain Callback Handler
- [ ] 自动追踪 Chain 执行
- [ ] 追踪 Agent 工具调用

#### 4.2 MCP Server 封装
**目标**: 让 Claude Code 原生调用

**任务**:
- [ ] 封装为 MCP Server
- [ ] 暴露 `stoi_analyze` 工具
- [ ] 暴露 `stoi_get_stats` 工具

#### 4.3 Web Dashboard (可选)
**目标**: 基础可视化界面

**任务**:
- [ ] 轻量级 Web 服务器 (Flask/FastAPI)
- [ ] 基础图表展示
- [ ] 实时数据更新 (WebSocket)

---

## 🏗️ 架构设计

### 模块结构 (基于 ultra-orchestration)

```
stoi/
├── core/                    # 核心模块
│   ├── __init__.py
│   ├── models.py           # 数据模型 (Trace/Observation/Score)
│   ├── database.py         # 数据库操作
│   ├── pricing.py          # 定价表管理
│   └── config.py           # 配置管理
├── client/                  # 客户端 SDK
│   ├── __init__.py
│   ├── decorator.py        # @observe 装饰器
│   ├── queue.py            # 异步队列
│   └── context.py          # 上下文管理
├── analysis/                # 分析引擎
│   ├── __init__.py
│   ├── evaluator.py        # LLM 评估
│   ├── cost.py             # 成本计算
│   └── anomaly.py          # 异常检测
├── ui/                      # 用户界面
│   ├── __init__.py
│   ├── rich_ui.py          # Rich 终端界面
│   ├── web.py              # Web Dashboard (可选)
│   └── tts.py              # 语音播报
├── integrations/            # 生态集成
│   ├── __init__.py
│   ├── langchain.py        # LangChain Callback
│   └── mcp.py              # MCP Server
├── cli.py                   # CLI 入口
└── tests/                   # 测试套件
    ├── test_core.py
    ├── test_client.py
    └── test_integration.py
```

### 数据流

```
应用代码
    ↓
@observe 装饰器 / Hook
    ↓
EventQueue (内存队列)
    ↓
后台线程 (批量处理)
    ↓
SQLite / ClickHouse (存储)
    ↓
分析引擎 (成本/异常/评估)
    ↓
UI 展示 (Rich / Web)
```

---

## 🧪 测试策略

### 单元测试
- 每个模块独立测试
- Mock 外部依赖 (API 调用)

### 集成测试
- 端到端工作流测试
- 数据库迁移测试

### 性能测试
- 追踪开销测试
- 高并发测试

---

## 📦 发布计划

| 版本 | 时间 | 核心功能 |
|------|------|----------|
| v0.3.0 | 本周 | Observation 模型 + 成本计算 + 异步批处理 |
| v0.4.0 | 下周 | @observe 装饰器 + 流式输出 + 离线缓存 |
| v0.5.0 | 第 3 周 | 多源评分 + 异常检测 + 数据导出 |
| v0.6.0 | 第 4 周 | LangChain + MCP Server + Web Dashboard |

---

## 🎓 开发原则 (来自 ultra-orchestration)

1. **渐进式演进**: 每个版本向后兼容，平滑升级
2. **模块化设计**: 各模块独立可替换
3. **测试驱动**: 先写测试，再写实现
4. **性能优先**: 追踪开销必须 < 10ms
5. **开发体验**: 一行代码集成，零配置启动

---

## 🚀 立即开始

### 本周冲刺 (Phase 1.1)

**今日任务**:
1. 设计 Observation 数据模型
2. 创建数据库迁移脚本
3. 实现基础 Observation CRUD

**命令**:
```bash
# 创建新分支
git checkout -b feature/observation-model

# 开始开发
python3 -m stoi.core.models
```

---

**准备开始 Phase 1.1 吗？** 我可以立即：
- A. 创建 Observation 数据模型代码
- B. 设计数据库迁移脚本
- C. 重构现有代码到新的模块结构
