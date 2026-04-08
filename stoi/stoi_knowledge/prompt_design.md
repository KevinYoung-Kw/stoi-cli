# Prompt Design 知识库

> 来源：Anthropic 提示工程文档 (docs.anthropic.com); OpenAI structured outputs 最佳实践; Atwood et al. (2024) in-context learning 研究。

## 核心原则

高效的提示设计遵循 **结构优先、冗余最小** 的原则。提示的每个部分应有明确的用途，格式应最小化视觉冗余。一个优化良好的提示可以在无损质量的情况下节省 15-30% 的 token。

## 问题模式

### 模式1：结构化输出指令不清晰

**症状：**
- 要求 JSON 输出但模型返回 Markdown 表格
- 输出格式时好时坏，需要频繁重新生成
- 校验失败率 > 10%（格式不符合预期）

**根因：**
不清晰或模糊的格式指令导致模型生成时不确定，往往会退到它训练中常见的格式（Markdown）。结果是需要后处理或重新调用 API，浪费 token。

**修复：**
1. **使用 JSON Schema 或 XML 模板**：不仅描述结构，还要提供完整示例
   ```markdown
   # 不好：
   Output as JSON with keys: name, age, city
   
   # 好：
   Output ONLY valid JSON matching this schema:
   {
     "name": "string",
     "age": "number (18-100)",
     "city": "string (ISO 3166-1 alpha-2 country code)"
   }
   
   # Example output:
   {"name": "John", "age": 28, "city": "US"}
   ```

2. **使用 XML 包装（更可靠）**：当 JSON 结构复杂时，XML 标签更清晰
   ```markdown
   Wrap your output in these XML tags:
   <response>
     <name>...</name>
     <age>...</age>
     <city>...</city>
   </response>
   ```

3. **显式完成指标**：告诉模型如何判断自己是否完成了格式要求
   ```markdown
   Your output is valid if:
   1. It is a single JSON object
   2. All keys are lowercase
   3. All values are strings or numbers
   4. No markdown formatting is used
   ```

**预期收益：**
- 格式校验成功率从 85% 提升至 99%
- 重新生成率从 10-15% 降低至 < 1%
- token 节省：避免重试，每次节省 1-2KB tokens

**参考：**
Anthropic 文档《Structured outputs》；OpenAI structured output 最佳实践

---

### 模式2：输出长度无限制

**症状：**
- 简单问题也得到 2000+ token 的长篇回答
- 生成的补充内容往往是"礼貌废话"或重复
- token 使用量（输出侧）占总成本的 40-50%，高于输入侧

**根因：**
模型通过 RLHF 训练倾向于详尽、有礼貌的回答。没有明确的长度约束时，模型会尽可能多地生成内容。虽然这对用户体验有好处，但对成本和延迟是灾难。

**修复：**
1. **显式长度约束**：在提示末尾明确指定
   ```markdown
   Keep your response to maximum 200 tokens.
   Be concise and direct.
   No introductions or conclusions.
   ```

2. **格式强制简洁**：
   ```markdown
   Response format:
   - Exactly 3 bullet points
   - Maximum 50 characters per point
   - No more
   ```

3. **负向约束**：明确说明不要做什么
   ```markdown
   Do NOT include:
   - "Thank you for asking"
   - "As an AI assistant"
   - Explanations of why you're answering
   - Multiple paragraphs
   ```

4. **停止序列**（对兼容 API）：在生成的前 N tokens 后截断
   ```python
   response = client.messages.create(
     ...,
     max_tokens=200,  # 绝对上限
     stop_sequences=["\n\n", "End of response"]  # 提前终止条件
   )
   ```

**预期收益：**
- 输出 token 数下降 40-60%
- 总成本下降 20-30%（输出侧变短）
- 延迟下降 30-40%（生成更快）
- 用户满意度无降或提升（更精准的信息）

**参考：**
Claude 文档《max_tokens 参数》；token 效率研究（OckBench, 2025）

---

### 模式3：冗余的示例

**症状：**
- Few-shot 提示中包含 5-10 个示例
- 示例之间高度相似，占提示总 token 的 30-40%
- 删除一半的示例后，模型质量没有降低

**根因：**
示例的边际效益递减。第 1 个示例教会模型一种风格，第 2 个加强，第 3 个开始冗余。之后的示例被模型"平均"处理而非精确学习。超过 3-4 个示例的性能提升往往 < 2%。

**修复：**
1. **精选最佳示例**：从成功案例中选择 2-3 个最代表性的示例
2. **示例多样性**：3 个示例应覆盖不同的难度或场景变化
   ```markdown
   # Example 1: Simple case
   Input: "hello"
   Output: {"greeting": true}
   
   # Example 2: Edge case with punctuation
   Input: "hello!"
   Output: {"greeting": true, "punctuation": "!"}
   
   # Example 3: Non-greeting
   Input: "goodbye"
   Output: {"greeting": false}
   ```

3. **删除平庸示例**：如果一个示例的学习信号 < 其他示例，删除

**预期收益：**
- Few-shot 部分的 token 下降 50-70%
- 总提示大小下降 15-25%
- 质量指标：无变化或轻微提升（更清晰的示范）

**参考：**
in-context learning 研究（Atwood et al., 2024）

---

### 模式4：格式装饰符过度

**症状：**
- System prompt 充满 Markdown 标题（### 、####）、粗体（**）、列表符号
- JSON 示例包含大量缩进和空行
- 提示总 token 中，格式符号占 20%+

**根因：**
开发者为了提高提示的人类可读性，使用了大量 Markdown。虽然对人类有帮助，但对 LLM 纯粹是冗余。每个 `#` 、`**` 、缩进都是 token。

**修复：**
1. **去掉 Markdown**：使用纯文本加简单分隔符
   ```markdown
   # 之前
   ### Role
   You are a **helpful** assistant.
   - Point 1: Do this
   - Point 2: Do that
   
   # 之后
   ROLE:
   You are a helpful assistant.
   Point 1: Do this
   Point 2: Do that
   ```

2. **使用分隔符而非标题**：
   ```markdown
   ===== SYSTEM INSTRUCTIONS =====
   You are a helpful assistant.
   
   ===== TASK =====
   Analyze the following code.
   ```

3. **JSON minify**：提示中的 JSON 示例用紧凑格式
   ```python
   # 之前：json.dumps(example, indent=2)
   # 之后：json.dumps(example, separators=(',', ':'))
   ```

4. **YAML 作为替代**：某些情况下，YAML 比 JSON 节省 10-15% token
   ```yaml
   # YAML
   name: john
   age: 28
   
   # vs JSON
   {"name": "john", "age": 28}
   ```

**预期收益：**
- Prompt 总 token 下降 10-20%
- 格式部分的 token 下降 40-50%
- 模型理解能力无变化

**参考：**
Anthropic 官方案例中的 prompt 优化

---

### 模式5：角色和任务混合不清

**症状：**
- 角色定义太长（如详细的人设），占 30% token
- 任务描述与角色重复
- 模型因为信息混乱而生成不符预期的内容

**根因：**
将"你是什么角色"与"具体任务是什么"混在一起，导致模型优先权不清。实际上，**任务优先权高于角色**：一个法律专家被要求写代码时，应该按代码要求生成，而非法律文本。

**修复：**
1. **分离角色和任务**：角色简洁，任务详细
   ```markdown
   # 不好
   You are a senior software engineer with 10 years of experience in Python,
   known for best practices, and who cares deeply about code quality.
   Write optimized code.
   
   # 好
   Role: Software engineer
   Task: Write Python code that:
   - Passes all tests
   - Has <10ms latency
   - Uses < 50MB memory
   ```

2. **角色简洁化**：用 1-2 句描述，不需要人设细节
3. **任务明确化**：列出具体的完成标准，而非模糊目标

**预期收益：**
- Prompt token 下降 15-25%（角色部分变短）
- 输出质量提升 10-15%（任务更清晰）
- 成本下降 10%

**参考：**
Anthropic 提示工程文档《Role specification》

---

## 诊断问题

**当 STOI 检测到以下模式时，应标记为 Prompt Design 问题：**

1. **Pattern：输出 token 占总 token 的 > 40%，且输出包含明显冗余内容**
   → 建议：添加长度约束和负向指令

2. **Pattern：格式校验失败 > 5%，频繁需要重新生成**
   → 建议：添加更清晰的格式示例和完成检查表

3. **Pattern：System prompt > 3000 tokens，其中 > 20% 是 Markdown 符号**
   → 建议：格式优化，从 Markdown 转为纯文本

4. **Pattern：Few-shot 示例 > 5 个**
   → 建议：删除相似/低质示例，保留 2-3 个最佳

5. **Pattern：角色定义 > 500 tokens**
   → 建议：简化角色，将细节移到任务描述

---

## 改进建议模板

**场景：代码审查 prompt，输出冗长且经常格式错误**

### 当前 Prompt：
```markdown
You are an expert senior software engineer with deep knowledge of Python,
design patterns, and best practices. Your role is to thoroughly review code
and identify potential issues.

Please analyze the following code:
[CODE]

Provide your findings in JSON format with these keys:
- issues: list of issues
- severity: high/medium/low
- recommendations: suggestions for improvement

Output a JSON object.
```

### 问题：
- 角色描述冗长（100+ tokens，对结果无实质影响）
- 输出格式指令模糊（"JSON object"不够明确）
- 输出长度无限制，模型会生成冗长的建议

### 改进后的 Prompt：
```markdown
Role: Code reviewer

Task: Review the following code and output ONLY a JSON object:

{
  "issues": [
    {"line": 10, "problem": "unused variable", "severity": "low"}
  ],
  "summary": "string (max 100 chars)",
  "fix_priority": "high" | "medium" | "low"
}

Constraints:
- Max 3 issues
- Each issue description: max 50 chars
- Total output: max 400 tokens
- Do NOT include: explanations, markdown, pleasantries

Code to review:
[CODE]
```

### 改进点：
1. ✓ 角色简化：从 2 句变为 1 句
2. ✓ 格式示例：完整 JSON 示范（而非描述）
3. ✓ 长度约束：明确输出限制和格式限制
4. ✓ 负向约束：明确列出不要做什么

### 预期结果：
```
Before:
- Prompt tokens: 1200
- Output tokens: 1500-2000 (冗长、需重试)
- Success rate: 80% (经常格式错误)
- Cost per call: ~$0.20

After:
- Prompt tokens: 800 (减少 33%)
- Output tokens: 300-400 (减少 80%)
- Success rate: 99% (格式明确)
- Cost per call: ~$0.05 (减少 75%)
```

### 验证指标：
- ✓ 输出格式 100% 正确（可直接 JSON parse）
- ✓ 输出 token 数 < 500
- ✓ 质量评分（发现真实问题的能力）无降低
