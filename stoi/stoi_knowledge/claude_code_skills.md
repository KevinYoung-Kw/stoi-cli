# Claude Code Skills 知识库

> 来源：Claude Code 官方文档（code.claude.com/docs）、Anthropic 开发者文档（docs.anthropic.com）及社区最佳实践（2025）。

## 核心原则

Claude Code 的核心优化机制是**动态内存管理**（CLAUDE.md + 会话压缩）加**阶段性上下文清理**。与普通 LLM API 调用不同，Claude Code 内置了多轮对话的效率管理，但需要合理的 Skill 结构来充分利用缓存与 token 效率。

## 问题模式

### 模式1：CLAUDE.md 过大或更新频繁

**症状：**
- CLAUDE.md 文件 > 5000 tokens
- 文件中包含的信息大部分与当前任务无关
- 频繁 commit 微小改动导致缓存前部频繁变化

**根因：**
CLAUDE.md 是 Claude Code 的“长期记忆”文件，会在**每个新会话启动时**自动加载。虽然设计初衷是保存项目全局信息（架构决策、常用代码模式、约定），但开发者往往堆砌所有可能有用的信息，导致冗余。更重要的是，如果 CLAUDE.md 内容在会话之间频繁变化，配合 Anthropic Prompt Caching 的**精确前缀匹配**机制，会导致所有基于该前缀的缓存全部失效。

**修复：**
1. **内容精选**：CLAUDE.md 仅包含 3 类信息：
   - 当前项目的架构决策（为什么这样组织代码）
   - 常见代码模式和约定（如“所有 API 调用都用 try-catch”）
   - 持久性上下文（项目名、团队规范、常用命令）
2. **分层内存**：
   - 全局 CLAUDE.md（`~/.claude/CLAUDE.md`）：个人跨项目的通用风格与系统偏好
   - 项目 CLAUDE.md（项目根目录 `CLAUDE.md` 或 `.claude/CLAUDE.md`）：项目特定决策
   - **不存在 `autoMemoryDirectory` 之类的配置键**；会话级别的临时记录建议手动维护在独立 markdown 文件中
3. **定期整理**：每周检查 CLAUDE.md，删除已过时的决策（如“之前为了调试，临时允许 console.log”）
4. **版本控制**：提交有意义的 CLAUDE.md 变更到 git，避免无意义的微调导致缓存失效

**预期收益：**
- 每轮初始化成本下降 20–40%（CLAUDE.md 变小）
- 新会话的缓存命中率从 60% 提升至 85%+
- 团队协作效率提升（所有成员对项目约定有清晰认知）

**参考：**
- [Claude Code Docs — Best Practices](https://code.claude.com/docs/en/best-practices)
- [Anthropic Docs — Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)

---

### 模式2：Skill frontmatter 中使用了不存在的字段

**症状：**
- 搜索社区示例时看到 `hidden: true` 或 `depends_on: project-context`
- 照抄后 Skill 无法被识别或行为与预期不一致
- 试图用 `depends_on` 建立 Skill 依赖链，但 Claude Code 并不支持该字段

**根因：**
部分第三方博客或旧版草案中出现了非官方的 frontmatter 字段。Claude Code 官方 `SKILL.md` 规范（2025）**并不支持 `hidden` 或 `depends_on`**。用这些字段无法达到隐藏 Skill 或声明依赖的目的。

**修复（官方字段）：**
1. **`disable-model-invocation: true`** — 禁止模型自动调用该 Skill（相当于对模型“隐藏”）
   ```yaml
   ---
   name: project-context
   description: 内部项目上下文（不直接调用）
   disable-model-invocation: true
   ---
   ```
2. **`user-invocable: false`** — 用户无法通过 `/skill-name` 直接调用（但模型仍可在合适时调用）
3. **Skill 间引用**：在正文里用 `@skill-name` 语法引用其他 Skill 的内容，而不是 `depends_on`
   ```markdown
   @project-context

   请基于以上上下文审查这段代码。
   ```
4. **避免动态参数硬编码**：Frontmatter 中不放当前工作目录路径、用户名或时间戳，保持静态

**预期收益：**
- Skill 定义符合官方规范，在所有 Claude Code 版本上行为一致
- 静态 frontmatter 保证跨设备、跨用户的缓存一致性
- 团队共享 Skill 时，所有成员看到一致的性能

**参考：**
- [Claude Code Docs — Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Claude Code Docs — Create custom subagents](https://code.claude.com/docs/en/sub-agents)

---

### 模式3：将动态内容注入 System Prompt 导致缓存击穿

**症状：**
- 多轮对话中 `cache_read_input_tokens` 始终为 0
- `cache_creation_input_tokens` 持续非零（缓存不断重写）
- 同样的系统提示，每次请求都重新计算前缀

**根因：**
Anthropic Prompt Caching 基于**精确前缀匹配（exact prefix matching）**。任何动态内容（当前时间、会话 ID、随机 UUID、运行时路径、心跳包）注入 system prompt，都会导致缓存键完全不同。即使只改变一个字符，也会触发完整的前缀失效。Anthropic 官方文档明确指出：Cache 只在 100% 匹配时命中。

**修复：**
1. **识别注入点**：检查代码/配置中将时间戳、UUID、用户特定数据插入 `system` 或 `tools` 的位置
2. **移至 user message**：将动态数据移到 `messages[].content` 中的最后一个用户块，保证 system prompt 静态
3. **验证命中**：运行两次相同的请求，检查第二次是否显示 `cache_read_input_tokens > 0`
4. **利用显式缓存断点**：在 system prompt 的最后一个静态块上加 `cache_control: {type: "ephemeral"}`（API 用户）

**预期收益：**
- 多轮对话中，缓存命中率从 0% 提升至 85–95%
- 成本降低 70–85%（缓存读取价格约为输入的 10%）
- 延迟改善 50–70%（避免重新计算前缀 KV）

**参考：**
- [Anthropic Docs — Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [Anthropic Docs — What invalidates the cache](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching#what-invalidates-the-cache)

---

### 模式4：Skill 间的上下文重复

**症状：**
- 定义了多个相关 Skill（如 `/review`、`/test`、`/fix`），但每个正文都包含完整的项目背景
- 调用多个 Skill 执行一个工作流时，相同的上下文被重复处理
- 三个 Skill 的系统提示加起来 > 8000 tokens，造成严重冗余

**根因：**
开发者为了保证每个 Skill 的独立性，会在各自的描述中重复项目背景。这在初期无害，但当 Skill 数量增加或在自动化工作流中连续调用多个 Skill 时，冗余成本指数增长。

**修复：**
1. **创建共享上下文 Skill**：将通用项目背景拆分为独立的 `project-context` Skill，并设置 `disable-model-invocation: true`
   ```markdown
   ---
   name: project-context
   description: 内部项目上下文（不直接调用）
   disable-model-invocation: true
   ---

   # Project Context
   - Language: TypeScript
   - Framework: Next.js
   - Key modules: auth, database, API
   ```
2. **Skill 之间通过 `@` 引用**：其他 Skill 在需要时引用该上下文
   ```markdown
   @project-context

   请审查以下代码的性能和可维护性...
   ```
3. **阶段性上下文传递**：仅在 Skill 之间传递必要的增量上下文
4. **使用工作流或 sub-agents**：如果多个 Skill 需要协同，创建一个协调 Skill 来统一加载背景，避免每个子 Skill 重复读取

**预期收益：**
- 多 Skill 工作流的总 token 使用下降 35–50%
- 成本下降 30–45%
- 工作流执行速度提升 20–30%（缓存效率提升）

**参考：**
- [Claude Code Docs — Sub-agents](https://code.claude.com/docs/en/sub-agents)

---

### 模式5：长会话性能衰减与错误的“检查点”命令

**症状：**
- 长编码会话（> 15 轮）中，后期响应变慢（延迟翻倍）
- 误信网络上流传的 `/checkpoint` 或 `/save-session` 命令，但 Claude Code 实际并不支持
- 用户能感受到“Claude 变傻了”的现象

**根因：**
Claude Code 在 LLM 背后使用 Anthropic 的 API，支持 prompt caching，但**缓存不是无限的**。长会话会让模型需要处理越来越多的历史消息，导致有效上下文利用率下降（Lost in the Middle）。网络上一些非官方教程推荐了不存在的命令，反而让用户忽视了真正有效的手段。

**修复：**
1. **使用 `/compact`**：Claude Code 官方支持 `/compact` 命令，它会将当前会话历史压缩成一段结构化摘要，显著减少后续请求的消息长度
2. **显式内存写入**：在重要决策点手动更新 `CLAUDE.md` 或 `.claude/session-notes.md`，然后开启新会话
3. **拆分任务 session**：将独立子任务拆成多个新会话。不要让一个会话无限增长。 Start a new session for distinct tasks.
4. **定期上下文整理**：不要依赖不存在的 `/checkpoint` 或 `/save-session`；正确做法是 `/compact` 或手动结束当前会话

**预期收益：**
- 长会话的延迟稳定化：不随轮数增加而增长
- 响应质量无衰减
- 用户感知的“流畅性”提升 50%+

**参考：**
- [Claude Code Docs — Best Practices](https://code.claude.com/docs/en/best-practices)
- Anthropic 缓存文档《Automatic caching in multi-turn conversations》

---

## 诊断问题

**当 STOI 检测到以下信号时，应标记为 Claude Code Skills 问题：**

1. **Signal：CLAUDE.md 变更频率 > 每天 2 次**
   → 检查：是否包含临时信息？应分离到单独的会话笔记中

2. **Signal：同一工作流中多个 Skill 调用，但缓存命中率 < 40%**
   → 检查：Skill 间是否存在重复上下文？应提取共享 `project-context` Skill

3. **Signal：长会话（> 10 轮）中后期延迟明显增加**
   → 检查：是否已使用 `/compact` 压缩历史，或是否需要拆分 session

4. **Signal：团队成员对同一 Skill 的执行成本不一致**
   → 检查：Skill 的正文/frontmatter 中是否包含环境特定的动态参数（如 `/Users/alice`）

---

## 改进建议模板

**场景：编码任务中连续调用 `/review`、`/test`、`/fix` 三个 Skill，总成本很高**

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
1. **创建项目上下文 Skill**（`disable-model-invocation: true`）：
   ```markdown
   ---
   name: project-context
   description: 内部项目上下文
   disable-model-invocation: true
   ---
   # Code Style: TypeScript, Functional patterns
   # Testing: Vitest, 100% coverage target
   # Review criteria: Performance, maintainability, test coverage
   ```
2. **重构 `/review` Skill**，通过 `@project-context` 引用：
   ```markdown
   ---
   name: review
   description: Code review for performance and maintainability
   ---
   @project-context

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
