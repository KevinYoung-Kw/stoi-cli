# Claude Code Skills 知识库

## 核心原则

Claude Code 的核心优化机制是**动态内存管理**（CLAUDE.md + 自动记忆）加**阶段性上下文清理**。与普通 LLM API 调用不同，Claude Code 内置了多轮对话的效率管理，但需要合理的 Skill 结构来充分利用。

## 问题模式

### 模式1：CLAUDE.md 过大或更新频繁

**症状：**
- CLAUDE.md 文件 > 5000 tokens
- 每轮对话都自动附带整个 CLAUDE.md（导致冗余计费）
- 文件中包含的信息大部分与当前任务无关

**根因：**
CLAUDE.md 是 Claude Code 的"长期记忆"文件，会在每个会话启动时自动加载。虽然设计初衷是保存项目全局信息（架构决策、常用代码模式、约定），但开发者往往堆砌所有可能有用的信息，导致冗余。更新频繁时，KV cache 中的旧版本 CLAUDE.md 也会失效。

**修复：**
1. **内容精选**：CLAUDE.md 仅包含3类信息：
   - 当前项目的架构决策（为什么这样组织代码）
   - 常见代码模式和约定（如"所有 API 调用都用 try-catch"）
   - 持久性上下文（项目名、团队规范）
2. **分层内存**：
   - 全局 CLAUDE.md（`~/.claude/CLAUDE.md`）：个人跨项目的通用风格
   - 项目 CLAUDE.md（`CLAUDE.md` 或 `.claude/CLAUDE.md`）：项目特定决策
   - 任务内存（`.claude/session-memory.md`）：当前会话的临时笔记
3. **定期整理**：每周检查 CLAUDE.md，删除已过时的决策（如"之前为了调试，临时允许 console.log"）
4. **版本控制**：提交有意义的 CLAUDE.md 变更到 git，避免频繁微调导致缓存失效

**预期收益：**
- 每轮初始化成本下降 20-40%（CLAUDE.md 变小）
- 多轮对话中缓存命中率从 60% 提升至 85%+
- 团队协作效率提升（所有成员对项目约定有清晰认知）

**参考：**
Claude Code 文档《Memory》— CLAUDE.md 最佳实践

---

### 模式2：Skill 定义中含有动态参数

**症状：**
- 编写 Skill 时，在 frontmatter 中硬编码了当前工作目录路径、用户名或时间戳
- 每次调用 Skill 时，前缀都在变化，导致缓存失效
- 团队成员在不同机器上跑同一 Skill，缓存无法共享

**根因：**
Skill 是项目级别的提示模板，可被多人重用。如果 Skill 定义包含环境特定的动态信息，就破坏了其通用性，更重要的是破坏了缓存的一致性。例如：
```yaml
# 不好的做法
---
name: audit
description: Code audit
context: "Project root: /Users/alice/my-project, Date: 2026-04-08"  # ← 每次变化
```

**修复：**
1. **静态 Skill 定义**：Frontmatter 中仅保留不变的元数据
   ```yaml
   ---
   name: audit
   description: Code audit for identifying bugs and improvements
   temperature: 0.3
   ---
   ```
2. **动态参数外置**：需要的动态信息（当前项目、用户上下文）通过参数传递，而非嵌入 Skill
   ```bash
   claude /audit --project-dir . --focus security
   ```
3. **使用环境变量引用**：如果需要上下文，用 `${CLAUDE_PROJECT_DIR}` 等标准变量，而非硬编码
   ```markdown
   ## Project Context
   Working directory: ${CLAUDE_PROJECT_DIR}
   ```

**预期收益：**
- Skill 调用的缓存命中率从 30% 提升至 85%+
- 团队共享 Skill 时，所有成员看到一致的性能
- 成本下降 40-60%（多人场景）

**参考：**
Claude Code 文档《Skills》— Best practices for skill design

---

### 模式3：Memory 注入位置错误导致缓存击穿

**症状：**
- Claude Code 的自动记忆功能启用，但每轮对话的缓存都失效
- 长对话中后半部分性能明显下降
- 同样的问题，在新会话中重复提问时缓存不共享

**根因：**
Claude Code 支持两种内存机制：
1. **自动记忆** (`autoMemory`)：每轮对话后自动更新记忆文件
2. **显式记忆注入**：在 `/memory` 命令中手动编辑

自动记忆的问题在于：如果记忆文件被注入到系统提示中，每次更新都会导致系统提示变化，从而击穿缓存。

**修复：**
1. **记忆与系统提示分离**：
   - 系统提示（不变）：项目架构、代码风格约定
   - 自动记忆（变化）：存储在单独文件，仅在需要时加载
2. **显式记忆点**：而非持续自动更新，在明确的"检查点"（如完成一个功能模块）时触发记忆保存
3. **记忆压缩**：定期总结长记忆文件（如"第 1-10 轮的重要决策"）为摘要
4. **配置 `autoMemoryDirectory`**：使用自定义位置（不在项目根），避免与 `.claude/` 混淆
   ```json
   {
     "autoMemoryDirectory": "~/.claude/memory/project-name"
   }
   ```

**预期收益：**
- 多轮对话的缓存稳定性提升 50%+
- 长会话（> 10 轮）的性能不衰减
- 团队成员间的会话记忆可复用（共享的摘要）

**参考：**
Claude Code 文档《Memory》— Auto memory configuration

---

### 模式4：Skill 间的上下文重复

**症状：**
- 定义了多个相关 Skill（`/review`, `/test`, `/fix`），但每个都包含完整的项目背景
- 调用多个 Skill 执行一个工作流时，相同的上下文被重复处理
- 三个 Skill 的系统提示加起来 > 8000 tokens，造成严重冗余

**根因：**
开发者为了保证每个 Skill 的独立性，会在各自的描述中重复项目背景。这在初期无害，但当 Skill 数量增加或在自动化工作流中连续调用多个 Skill 时，冗余成本指数增长。

**修复：**
1. **共享基础上下文**：创建一个 "project-context" Skill，仅包含项目背景描述
   ```markdown
   ---
   name: project-context
   hidden: true  # 不直接调用，仅供其他 Skill 引用
   ---
   
   # Project Context
   - Language: TypeScript
   - Framework: Next.js
   - Key modules: auth, database, API
   ```
2. **Skill 之间的引用**：其他 Skill 通过 `@project-context` 引用
   ```yaml
   ---
   name: review
   description: Code review
   depends_on: project-context
   ---
   ```
3. **阶段性上下文**：而非全量重复，仅在 Skill 之间传递必要的增量上下文
4. **使用工作流而非单 Skill**：如果多个 Skill 需要执行，创建一个 "workflow" Skill 来协调，避免重复加载背景

**预期收益：**
- 多 Skill 工作流的总 token 使用下降 35-50%
- 成本下降 30-45%
- 工作流执行速度提升 20-30%（缓存效率提升）

**参考：**
Claude Code 文档《Subagents》— 组织多个 Agent 的最佳方式

---

### 模式5：缺乏显式缓存断点导致长会话性能衰减

**症状：**
- 长编码会话（> 15 轮）中，后期响应变慢（延迟翻倍）
- 同样的代码问题，越往后解决越花时间
- 用户能明显感受到"Claude 变傻了"的现象

**根因：**
Claude Code 在 LLM 背后使用 Anthropic 的 API，支持 prompt caching。但如果没有显式的缓存策略，长会话会让缓存回溯窗口（20 块）失效，导致频繁的缓存重计算。

**修复：**
1. **定期会话检查点**：每 8-10 轮后，运行 `/checkpoint` 命令或手动中断会话保存进度
   ```bash
   # 会话中执行
   /save-session session-name  # 保存到可恢复状态
   /new-session  # 启动新会话，旧会话的上下文通过摘要继承
   ```
2. **显式内存写入**：而非依赖自动记忆，在重要决策点手动更新 `.claude/session-memory.md`
3. **上下文整理命令**：创建一个 Skill 来周期性地总结会话历史
   ```markdown
   ---
   name: session-summary
   description: Summarize recent session work
   ---
   
   Please create a concise summary of the work done so far:
   - Major decisions made
   - Key files modified
   - Current blockers
   ```
4. **利用显式缓存断点**：（高级）如果需要长会话，可以编写脚本定期调用 API，在特定点设置 `cache_control`

**预期收益：**
- 长会话的延迟稳定化：不随轮数增加而增长
- 响应质量无衰减
- 用户感知的"流畅性"提升 50%+

**参考：**
Anthropic 缓存文档《Automatic caching in multi-turn conversations》；Claude Code settings《cleanupPeriodDays》

---

## 诊断问题

**当 STOI 检测到以下信号时，应标记为 Claude Code Skills 问题：**

1. **Signal：CLAUDE.md 变更频率 > 每天 2 次**
   → 检查：是否包含临时信息，应分离到会话内存

2. **Signal：同一工作流中多个 Skill 调用，但缓存命中率 < 40%**
   → 检查：Skill 间是否存在重复上下文，应提取共享基础

3. **Signal：长会话（> 10 轮）中后期延迟明显增加**
   → 检查：是否需要显式检查点或会话分割

4. **Signal：团队成员对同一 Skill 的执行成本不一致**
   → 检查：Skill 定义中是否包含环境特定的动态参数

---

## 改进建议模板

**场景：编码任务中连续调用 `/review`, `/test`, `/fix` 三个 Skill，总成本很高**

### 当前问题：
```
/review code.ts
├─ System context: 3000 tokens（项目背景 × 1）
└─ Review logic: 1000 tokens

/test code.ts
├─ System context: 3000 tokens（项目背景 × 1，重复）
└─ Test logic: 800 tokens

/fix code.ts
├─ System context: 3000 tokens（项目背景 × 1，重复）
└─ Fix logic: 900 tokens

Total: 12700 tokens，其中 9000 tokens 是重复的项目背景
```

### 改进方案：
1. **创建项目上下文 Skill**：
   ```markdown
   ---
   name: project-context
   hidden: true
   ---
   # Code Style: TypeScript, Functional patterns
   # Testing: Vitest, 100% coverage target
   # Review criteria: Performance, maintainability, test coverage
   ```
2. **重构 `/review` Skill**：
   ```markdown
   ---
   name: review
   depends_on: project-context
   ---
   Review this file for:
   - Performance issues
   - Code style consistency
   - Test coverage gaps
   ```
3. **类似地更新 `/test` 和 `/fix`**

### 预期结果：
```
First call to /review:
├─ project-context: 1200 tokens (cached)
└─ review logic: 1000 tokens
Total: 2200 tokens (缓存写入)

Second call to /test:
├─ project-context: 1200 tokens (cached read, $0.12 instead of $0.36)
└─ test logic: 800 tokens
Total: 2000 tokens

Third call to /fix:
├─ project-context: 1200 tokens (cached read)
└─ fix logic: 900 tokens
Total: 2100 tokens

Cumulative: 2200 + 2000 + 2100 = 6300 tokens (原来 12700)
Cost reduction: 50%
```

### 验证指标：
- ✓ 第 2、3 个 Skill 调用的 `cache_read_input_tokens > 1000`
- ✓ 工作流总成本下降 > 45%
- ✓ 每个 Skill 的响应质量无降低
