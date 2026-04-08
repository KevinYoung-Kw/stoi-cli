# KV Cache 优化知识库

## 核心原则

KV Cache 是 LLM 推理中最高效的成本优化点。一次 cache 失效可能导致 25-50% 的成本增加。关键洞察：缓存失效往往不是因为上下文变长，而是因为系统提示或工具定义的细微变化。

## 问题模式

### 模式1：时间戳/UUID 注入导致缓存失效

**症状：**
- 每次 API 调用的 `cache_read_input_tokens` 都是 0
- `cache_creation_input_tokens` 持续非零（表示缓存不断重写）
- 多轮对话中每一轮都在重新处理相同的系统提示

**根因：**
动态内容（当前时间、会话 ID、请求 UUID）被注入到系统提示或工具定义中。即使是微小的变化（如时间戳从 `14:32:15` 变为 `14:32:16`），也会导致缓存键完全不同，前缀哈希无法匹配。Anthropic 文档明确指出：缓存只在 100% 完全匹配时命中。

**修复：**
1. **识别注入点**：检查代码中所有插入到 `system` 或 `tools` 字段的动态数据
2. **移至用户消息**：将时间戳、会话 ID、用户特定数据移到 `messages[].content` 中的最后一个用户块
3. **验证命中**：运行两次相同的请求，检查第二次是否显示 `cache_read_input_tokens > 0`

**预期收益：**
- 多轮对话中，缓存命中率从 0% 提升至 85-95%
- 成本降低 70-85%（缓存读取仅为基础价格的 10%）
- 延迟改善 50-70%（避免重新计算前缀）

**参考：**
Anthropic 官方文档《Prompt Caching》— "Placing cache_control on content that changes every request"；实际案例见 Notion AI 集成（成本下降 90%，延迟下降 79%）

---

### 模式2：工具定义动态切换

**症状：**
- 在不同请求间切换 `tools` 数组内容
- 每次缓存都需要 `cache_creation_input_tokens` 值很大
- 相同的系统提示和用户消息，仅因工具集不同就产生不同的成本

**根因：**
工具定义是系统提示的一部分。Anthropic 的缓存层级是 `tools` → `system` → `messages`，任何工具定义的改变都会导致其下游所有缓存失效。例如，从 10 个工具切换到 12 个工具，整个前缀缓存都失效。

**修复：**
1. **合并工具集**：将所有可能需要的工具放在一个静态 `tools` 数组中，一次性加载
2. **使用工具选择**：用 `tool_choice` 参数（而非修改 `tools` 数组）来控制哪些工具可用
3. **或使用多个显式断点**：如果必须更换工具集，在切换时设置多个缓存断点，第一个断点缓存通用前缀，第二个缓存工具集，这样后续同工具集的请求能命中第二个断点

**预期收益：**
- 编码助手场景：工具集固定后，缓存命中率从 30% 提升至 90%+
- 成本下降 50-65%

**参考：**
Anthropic 文档"What invalidates the cache"表格 — 工具定义修改导致完全缓存失效；LangSmith 实验数据显示代理系统中工具切换是最常见的性能陷阱

---

### 模式3：多轮对话中的上下文膨胀

**症状：**
- 第 1 轮对话：系统提示 2000 tokens + 用户消息 500 tokens，缓存写入 2500 tokens
- 第 2 轮对话：系统提示 2000 tokens + 用户消息 500 tokens + 历史 450 tokens，缓存需要重新计算整个 2950 token 前缀（因为消息块变化了）
- 趋势：每轮成本持续上升，而信息重复度也持续上升

**根因：**
自动缓存（automatic caching）的缓存断点是移动的（moving breakpoint）：每次新请求时，系统自动将缓存断点设在最后一个可缓存块。在多轮对话中，每新增一轮历史，最后一块内容都在变化，导致缓存键频繁变更。虽然 Anthropic 的回溯窗口（lookback window）能检测旧的缓存位置（20 块内），但如果对话超长，回溯会失败。

**修复：**
1. **定期压缩历史**：每 5-8 轮后，将前面的轮次总结成一个结构化摘要，替代全量历史
2. **使用滑动窗口**：始终只保留最近 3-4 轮完整对话 + 之前的摘要
3. **显式多断点策略**：设置第一个缓存断点在系统提示末尾（1-3 轮都能命中），第二个断点在历史摘要末尾（长对话中防止回溯失败）

**预期收益：**
- 12 轮对话中，累积成本从 22000 tokens（全量追加）降低到 15000 tokens（压缩策略）
- 节省 30-40% 成本；延迟持续稳定（不会随轮次增加而线性增长）

**参考：**
LangSmith 多轮数据分析；microsoft/LLMLingua 的 `dynamic_context_compression_ratio` 参数案例

---

### 模式4：Image/Document 缓存未充分利用

**症状：**
- 每次上传相同的 PDF 或图像，都要重新编码和处理
- 文档处理成本随请求数持续累积，不见缓存优化效果

**根因：**
虽然 Anthropic 支持缓存 Images 和 Documents，但需要满足两个条件：
1. 最小缓存大小阈值（Claude Sonnet 4.6 需要 2048+ tokens）
2. 缓存断点必须设在 content 块上（包含完整文档）

很多实现忽略了第二个条件，或者在缓存文档后又添加了新 context，导致缓存失效。

**修复：**
1. **独立缓存文档**：设置一个专属的 `cache_control` 在文档末尾
2. **后续请求重用该文档**：在新请求中，保持相同的文档块（相同的 content 对象），仅改变后续的用户查询
3. **验证对齐**：确保 `<document>` 块的字节序列完全相同（编码、格式）

**预期收益：**
- RAG 或文档 Q&A 场景：缓存命中后，相同文档的处理成本下降 85-90%
- 例：100 页 PDF 文档 × 10 个查询，从 50000 tokens 降到 15000 tokens

**参考：**
Anthropic 文档"What can be cached" — Images & Documents section；Braintrust 案例研究中文档缓存优化

---

### 模式5：缓存写入成本高于预期

**症状：**
- 明明设置了 `cache_control`，但成本没有明显下降
- `cache_creation_input_tokens` 持续很高（与基础 `input_tokens` 接近）

**根因：**
缓存写入的成本是基础价格的 1.25 倍（5 分钟 TTL）或 2 倍（1 小时 TTL）。如果缓存命中率低（< 30%），写入成本的额外 25% 可能抵消缓存读取节省的 90%。这在一次性或低频调用中最明显。

**修复：**
1. **计算 ROI 阈值**：评估缓存内容被重用的频率。如果相同前缀预计被用 3 次以上，缓存才划算
   - ROI = (写入成本增益 × 命中数) - 写入成本额外费用 > 0
   - 对于 1000 token 的缓存：写入+25% = 1250，读取×3 = 300，节省总计 950 tokens（$ 值取决于模型）
2. **对低频内容禁用缓存**：仅对系统提示、大型背景文档缓存；不要缓存一次性内容
3. **选择 TTL**：短期对话用 5 分钟 TTL（标准），长期会话或档案用 1 小时 TTL

**预期收益：**
- 聊天机器人场景（高频用户）：60% 成本节省
- API 聚合场景（混合频率）：10-30% 成本节省；一次性任务：无需缓存

**参考：**
Anthropic 缓存成本计算器；LangSmith 的缓存 ROI 分析工具

---

## 诊断问题

**当 STOI 检测到以下信号时，应提示用户审查 KV Cache 配置：**

1. **Signal：多轮对话中 `cache_read_input_tokens` 始终为 0**
   → 检查：系统提示或工具定义中是否有动态时间戳、UUID、用户 ID
   
2. **Signal：成本随轮数线性增长（无平台期）**
   → 检查：是否使用滑动窗口 + 显式多断点，还是让上下文无限膨胀

3. **Signal：同样的系统提示，不同工具集导致成本差异 > 20%**
   → 检查：工具集是否动态切换，应改为固定集合 + `tool_choice`

4. **Signal：文档 Q&A 系统每个查询都产生高昂的 `cache_creation_input_tokens`**
   → 检查：文档是否被独立缓存，新查询是否真正重用了旧缓存

---

## 改进建议模板

**场景：编码助手在多轮对话中成本持续上升**

### 当前问题：
```
Turn 1: cache_write=2500, cache_read=0, new_tokens=500 → total cost = 250 + 0 + 50 = $300
Turn 2: cache_write=3200, cache_read=0, new_tokens=650 → total cost = 320 + 0 + 65 = $385
Turn 3: cache_write=3900, cache_read=0, new_tokens=800 → total cost = 390 + 0 + 80 = $470
（缓存未命中，每轮都在重新写入整个前缀）
```

### 根因诊断：
系统提示中包含 `Current session: ${uuid}`，每次生成新 uuid 导致前缀哈希变化。

### 改进方案：
1. **修改系统提示**：将 `Current session: <dynamic>` 移出系统提示，改为在用户消息中传递
2. **代码更改**：
   ```python
   # 之前（错误）
   messages = [{
     "role": "user",
     "content": f"Session {session_uuid}: {user_query}"
   }]
   system = f"You are an assistant. Current session: {session_uuid}. Tools: ..."
   
   # 之后（正确）
   system = "You are an assistant. Tools: ..."  # 静态
   messages = [{
     "role": "user", 
     "content": f"Session ID: {session_uuid}\n\nUser query: {user_query}"
   }]
   ```

3. **缓存配置**：
   ```python
   response = client.messages.create(
     model="claude-sonnet-4-6",
     max_tokens=2000,
     system=system,
     messages=messages,
     cache_control={"type": "ephemeral"}  # 自动缓存
   )
   ```

### 预期结果：
```
Turn 1: cache_write=2500, cache_read=0, new_tokens=500 → $300 (首次，缓存建立)
Turn 2: cache_write=0, cache_read=2500, new_tokens=650 → $250 + $65 = $315 (缓存命中)
Turn 3: cache_write=0, cache_read=2500, new_tokens=800 → $250 + $80 = $330 (缓存命中)
总成本下降：从 $1255 → $945（节省 24%）；更重要的是成本稳定，后续轮数无增长
```

### 验证成功指标：
- ✓ 第 2 轮及以后 `cache_read_input_tokens > 0`
- ✓ 每轮成本差异 < 5%（仅新输入变化导致）
- ✓ 对话可扩展性：即使 20 轮，总成本仍控制在预期范围内
