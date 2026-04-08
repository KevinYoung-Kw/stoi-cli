const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel,
        AlignmentType, BorderStyle, WidthType, ShadingType, LevelFormat, Header, Footer,
        PageNumber, PageBreak } = require('docx');
const fs = require('fs');

// 定义样式
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "2E74B5" },
        paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2E74B5" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "5B9BD5" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "STOI Technical Design Document", italics: true, color: "666666", size: 20 })]
      })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Page ", size: 20 }),
          new TextRun({ children: [PageNumber.CURRENT], size: 20 }),
          new TextRun({ text: " of ", size: 20 }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 20 })
        ]
      })] })
    },
    children: [
      // 标题页
      new Paragraph({ spacing: { before: 2400 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "STOI", bold: true, size: 72, color: "2E74B5", font: "Arial" })]
      }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Shit Token On Investment", size: 32, color: "666666" })]
      }),
      new Paragraph({ spacing: { before: 400 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "技术设计文档", bold: true, size: 40, color: "2E74B5" })]
      }),
      new Paragraph({ spacing: { before: 600 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Technical Design Document", size: 28, color: "666666" })]
      }),
      new Paragraph({ spacing: { before: 1200 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "版本: v1.0", size: 24 })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "日期: 2026-04-08", size: 24 })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "文档状态: 技术评审", size: 24 })]
      }),

      // 分页
      new Paragraph({ children: [new PageBreak()] }),

      // 目录
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("目录")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ children: [new TextRun("1. 执行摘要 ............................................................. 3")] }),
      new Paragraph({ children: [new TextRun("2. 产品概述 ............................................................. 4")] }),
      new Paragraph({ children: [new TextRun("3. 技术架构 ............................................................. 5")] }),
      new Paragraph({ children: [new TextRun("4. 核心模块设计 ......................................................... 7")] }),
      new Paragraph({ children: [new TextRun("5. 数据模型 ............................................................. 12")] }),
      new Paragraph({ children: [new TextRun("6. CLI 命令设计 ......................................................... 15")] }),
      new Paragraph({ children: [new TextRun("7. 开发路线图 ........................................................... 18")] }),
      new Paragraph({ children: [new TextRun("8. 技术风险与缓解 ....................................................... 19")] }),
      new Paragraph({ children: [new TextRun("9. 参考来源 ............................................................. 20")] }),

      new Paragraph({ children: [new PageBreak()] }),

      // 1. 执行摘要
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("1. 执行摘要")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({
        children: [new TextRun({ text: "STOI (Shit Token On Investment)", bold: true }), new TextRun(" 是一款专为 AI 编程工具设计的 CLI 效率监控工具。它通过量化 Token 消耗的转化率，帮助开发者和企业识别\"有效代码输出 (Value)\"与\"无效/冗余消耗 (Shit)\"的比例，最终给出直观的「含屎量」评级。")]
      }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("1.1 核心价值主张")] }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "成本控制: ", bold: true }), new TextRun("识别并减少因 Prompt 设计缺陷导致的 Token 浪费")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "效率提升: ", bold: true }), new TextRun("量化 AI 辅助编程的真实 ROI")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "生态优化: ", bold: true }), new TextRun("通过生成 Issue 报告倒逼框架改进")]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("1.2 技术选型总览")] }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 6560],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA }, shading: { fill: "2E74B5", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "层级", bold: true, color: "FFFFFF" })] })] }),
              new TableCell({ borders, width: { size: 6560, type: WidthType.DXA }, shading: { fill: "2E74B5", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "技术选型", bold: true, color: "FFFFFF" })] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("CLI 框架")] })] }),
              new TableCell({ borders, width: { size: 6560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Typer + Rich (Python)")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("数据存储")] })] }),
              new TableCell({ borders, width: { size: 6560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("SQLite + Pydantic")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("LLM 评估")] })] }),
              new TableCell({ borders, width: { size: 6560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("GPT-4.1 + Claude-4 + Gemini-2 (多模型集成)")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("拦截机制")] })] }),
              new TableCell({ borders, width: { size: 6560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Claude Code Hooks + MCP 中间件")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Diff 算法")] })] }),
              new TableCell({ borders, width: { size: 6560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("语义 + 行级 + Token 级多层 Diff")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // 2. 产品概述
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("2. 产品概述")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("2.1 背景与痛点")] }),
      new Paragraph({
        children: [new TextRun("随着 Claude Code 等 AI 编程工具的普及，开发者发现系统提示词中的硬编码时间戳导致 KV-Cache 大面积不命中，引发 Token 的无谓暴涨（Token 刺客现象）。然而，业界目前只有 Token 消耗计费，却缺乏衡量 Token 产出比（TOI）的指标。")]
      }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("2.2 核心痛点")] }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun({ text: "缺乏衡量标准: ", bold: true }), new TextRun("开发者不知道消耗的 Token 是转化成了高价值代码，还是变成了毫无意义的废话")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun({ text: "企业效能黑盒: ", bold: true }), new TextRun("难以界定员工 AI 辅助编程的真实效率")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun({ text: "成本失控: ", bold: true }), new TextRun("每次无效的上下文对话都在\"烧钱\"")]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("2.3 产品定位")] }),
      new Paragraph({
        children: [new TextRun("STOI 是开发者侧首个基于 CLI 形态的「词元投资回报率」分析与监控工具。它通过监控底层 Token 消耗，结合 LLM-as-a-judge 机制，为开发者和企业量化 Token 效率，最终给出直观的「含屎量」评级和改进建议。")]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // 3. 技术架构
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("3. 技术架构")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.1 架构全景")] }),
      new Paragraph({
        children: [new TextRun("STOI 采用分层架构设计，包含 CLI 层、核心服务层、数据采集层、评估层和存储层。各层之间通过明确定义的接口进行交互，确保系统的可扩展性和可维护性。")]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.2 核心组件")] }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 3600, 3360],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "组件", bold: true })] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "职责", bold: true })] })] }),
              new TableCell({ borders, width: { size: 3360, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "技术选型", bold: true })] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Session Manager")] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("会话生命周期管理")] })] }),
              new TableCell({ borders, width: { size: 3360, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Python asyncio")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Token Analyzer")] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Token 效率分析")] })] }),
              new TableCell({ borders, width: { size: 3360, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("多模型集成评估")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Cache Inspector")] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("KV-Cache 分析")] })] }),
              new TableCell({ borders, width: { size: 3360, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Diff 算法 + 模式匹配")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Report Generator")] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("报告生成与导出")] })] }),
              new TableCell({ borders, width: { size: 3360, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Jinja2 + Markdown")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.3 数据流")] }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("数据采集: Hook 拦截 → MCP 中间件 → JSONL 解析")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("实时处理: 数据清洗 → 模式检测 → Cache 事件标记")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("深度分析: LLM 评估 → 冗余检测 → 价值提取")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("存储索引: SQLite 写入 → 聚合统计 → 报表生成")]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // 4. 核心模块设计
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("4. 核心模块设计")] }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.1 LLM-as-Judge 评估体系")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ children: [new TextRun({ text: "评估维度与权重", bold: true })] }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 1200, 3600, 2160],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "维度", bold: true })] })] }),
              new TableCell({ borders, width: { size: 1200, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "权重", bold: true })] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "评估内容", bold: true })] })] }),
              new TableCell({ borders, width: { size: 2160, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "评分方法", bold: true })] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("问题解决度")] })] }),
              new TableCell({ borders, width: { size: 1200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("35%")] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("功能完整性、边界处理、实际可用性")] })] }),
              new TableCell({ borders, width: { size: 2160, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("1-5 分 Likert 量表")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("代码质量")] })] }),
              new TableCell({ borders, width: { size: 1200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("25%")] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("正确性、可读性、最佳实践、健壮性")] })] }),
              new TableCell({ borders, width: { size: 2160, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("多因子加权")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("信息密度")] })] }),
              new TableCell({ borders, width: { size: 1200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("20%")] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("信噪比、重复率、相关度")] })] }),
              new TableCell({ borders, width: { size: 2160, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Token 级分析")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("上下文效率")] })] }),
              new TableCell({ borders, width: { size: 1200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("20%")] })] }),
              new TableCell({ borders, width: { size: 3600, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("利用率、精准度、选择性")] })] }),
              new TableCell({ borders, width: { size: 2160, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("上下文追踪")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ children: [new TextRun({ text: "STOI 指数计算公式", bold: true })] }),
      new Paragraph({
        children: [new TextRun("STOI_Index = Σ(Dimension_Score_i × Weight_i) × Efficiency_Factor × Reliability_Factor")]
      }),
      new Paragraph({
        children: [new TextRun("含屎量 (Waste Ratio) = 1 - (Effective_Tokens / Total_Tokens)")]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.2 Token 拦截与 Cache 分析")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ children: [new TextRun({ text: "多层拦截架构", bold: true })] }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "Layer 1: ", bold: true }), new TextRun("Claude Code Hooks (PreToolUse/PostToolUse) - 事件捕获")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "Layer 2: ", bold: true }), new TextRun("MCP Middleware - 请求/响应拦截")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "Layer 3: ", bold: true }), new TextRun("Statusbar Monitor - Token 计数轮询")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "Layer 4: ", bold: true }), new TextRun("JSONL Log Parser - 异步分析")]
      }),

      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ children: [new TextRun({ text: "Cache Miss 检测模式", bold: true })] }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 4000, 2560],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "模式类型", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4000, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "正则表达式", bold: true })] })] }),
              new TableCell({ borders, width: { size: 2560, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "影响级别", bold: true })] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("ISO_TIMESTAMP")] })] }),
              new TableCell({ borders, width: { size: 4000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}")])] })] }),
              new TableCell({ borders, width: { size: 2560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("CRITICAL")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("UUID_V4")] })] }),
              new TableCell({ borders, width: { size: 4000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-...")] })] })] }),
              new TableCell({ borders, width: { size: 2560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("CRITICAL")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("ABS_PATH")] })] }),
              new TableCell({ borders, width: { size: 4000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("/home|Users|root/...")] })] })] }),
              new TableCell({ borders, width: { size: 2560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("HIGH")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // 5. 数据模型
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("5. 数据模型")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({
        children: [new TextRun("STOI 采用关系型数据模型，核心实体包括 Session、Message、TokenUsage、Evaluation 和 CacheEvent。以下是主要模型的字段定义：")]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("5.1 Session（会话）")] }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 2000, 4560],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "字段", bold: true })] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "类型", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "说明", bold: true })] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("id")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("UUID")] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("主键")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("name")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("String")] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("会话名称")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("project")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("String")] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("项目标识")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("start_time")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("DateTime")] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("开始时间")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("5.2 TokenUsage（Token 使用）")] }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 2000, 4560],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "字段", bold: true })] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "类型", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "说明", bold: true })] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("message_id")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("UUID")] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("关联消息")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("input_tokens")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Integer")] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("输入 Token 数")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("cache_read_tokens")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Integer")] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Cache 读取 Token")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2800, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("cache_creation_tokens")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Integer")] })] }),
              new TableCell({ borders, width: { size: 4560, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Cache 创建 Token")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // 6. CLI 命令设计
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("6. CLI 命令设计")] }),
      new Paragraph({ spacing: { before: 200 } }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("6.1 核心命令清单")] }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 4200, 2760],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA }, shading: { fill: "2E74B5", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "命令", bold: true, color: "FFFFFF" })] })] }),
              new TableCell({ borders, width: { size: 4200, type: WidthType.DXA }, shading: { fill: "2E74B5", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "功能", bold: true, color: "FFFFFF" })] })] }),
              new TableCell({ borders, width: { size: 2760, type: WidthType.DXA }, shading: { fill: "2E74B5", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "关键参数", bold: true, color: "FFFFFF" })] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun({ text: "stoi track", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("开始/停止追踪")] })] }),
              new TableCell({ borders, width: { size: 2760, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("start/stop, --name")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun({ text: "stoi analyze", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("效率分析")] })] }),
              new TableCell({ borders, width: { size: 2760, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("--session, --format")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun({ text: "stoi blame", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Cache 归因")] })] }),
              new TableCell({ borders, width: { size: 2760, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("--pattern, --suggest")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun({ text: "stoi report", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("生成报告")] })] }),
              new TableCell({ borders, width: { size: 2760, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("--period, --output")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun({ text: "stoi config", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4200, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("配置管理")] })] }),
              new TableCell({ borders, width: { size: 2760, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("show/edit/set")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("6.2 使用示例")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ children: [new TextRun({ text: "开始追踪会话", bold: true })] }),
      new Paragraph({
        shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
        children: [new TextRun({ text: "$ stoi track start --name \"API Refactor\" --tags backend,python", font: "Courier New" })]
      }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ children: [new TextRun({ text: "分析并导出报告", bold: true })] }),
      new Paragraph({
        shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
        children: [new TextRun({ text: "$ stoi analyze --format json --output analysis.json", font: "Courier New" })]
      }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ children: [new TextRun({ text: "生成 Git Blame 式报告", bold: true })] }),
      new Paragraph({
        shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
        children: [new TextRun({ text: "$ stoi blame --suggest --threshold 60", font: "Courier New" })]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // 7. 开发路线图
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("7. 开发路线图")] }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("7.1 Phase 1: MVP (Week 1-4)")] }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("CLI 框架搭建（Typer + Rich）")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("数据模型实现（Pydantic + SQLite）")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("stoi track / analyze 基础命令")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Hook 拦截器实现")]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("7.2 Phase 2: 分析引擎 (Week 5-8)")] }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("LLM-as-judge 评估模块")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Cache Miss 检测算法")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("stoi blame 命令")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("报告生成器")]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("7.3 Phase 3: 集成与优化 (Week 9-12)")] }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("MCP 服务器暴露")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Claude Code 深度集成")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("性能优化与缓存")]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // 8. 技术风险与缓解
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("8. 技术风险与缓解")] }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 2000, 4960],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "风险", bold: true })] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "影响", bold: true })] })] }),
              new TableCell({ borders, width: { size: 4960, type: WidthType.DXA }, shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: "缓解策略", bold: true })] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Claude Code API 限制")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("高")] })] }),
              new TableCell({ borders, width: { size: 4960, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("多层拦截架构、Hook 系统、Statusbar 轮询")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("LLM 评判偏见")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("中")] })] }),
              new TableCell({ borders, width: { size: 4960, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("多模型集成、偏见检测、自适应评判")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ borders, width: { size: 2400, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("Token 计数不准确")] })] }),
              new TableCell({ borders, width: { size: 2000, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("中")] })] }),
              new TableCell({ borders, width: { size: 4960, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("使用 Statusbar API、JSONL 校验")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // 9. 参考来源
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("9. 参考来源")] }),
      new Paragraph({ spacing: { before: 200 } }),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("9.1 学术论文")] }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Bai et al. (2022). Constitutional AI: Harmlessness from AI Feedback. arXiv:2212.08073")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Zheng et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS 2023")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Chen et al. (2021). Evaluating Large Language Models Trained on Code. arXiv:2107.03374")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("MultiChallenge (2025). A Realistic Multi-Turn Conversation Evaluation Benchmark. arXiv:2501.17399")]
      }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("9.2 技术文档")] }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Claude Code Hooks Documentation")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("MCP Protocol Specification")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Typer & Rich Official Documentation")]
      }),

      new Paragraph({ spacing: { before: 600 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "--- 文档结束 ---", color: "666666" })]
      })
    ]
  }]
});

// 生成文档
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/Users/kevinyoung/Desktop/red-hackathon/STOI-Technical-Design-v1.0.docx", buffer);
  console.log("✅ Document generated: STOI-Technical-Design-v1.0.docx");
});
