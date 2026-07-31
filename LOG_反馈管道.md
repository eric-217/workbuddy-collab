# 反馈管道 — 决策日志

> **用途**：记录反馈管道相关的推理链条、关键决策和上下文
> **创建**：2026-08-01

---

## 2026-08-01: 架构设计与认知对齐

### 船长的初始设想
- 7B 推理初始反馈 → RAG 交叉验证 → Yourself 润色 → 对话窗口 → 检验 → 不匹配→训练数据

### 关键认知偏差修正

**偏差 1：RAG 是 WorkBuddy 系统？**
- 纠正：RAG = ChromaDB + Embedding + 检索逻辑，纯 Python，不需要 WorkBuddy
- 结论：ERIC 上一个 FastAPI 服务即可编排全部 7B+RAG 交互

**偏差 2：RAG + 7B 需要 WorkBuddy 中转？**
- 纠正：两者在 ERIC 同一进程内互调，WorkBuddy 只负责发送问题和接收结果
- 结论：架构比预想的简单得多

**偏差 3：笔记本装不了 RAG → 管道不可行？**
- 纠正：RAG 从头到尾在 ERIC 上，笔记本只收发 HTTP
- 结论：笔记本资源约束不影响管道可行性

**偏差 4：QLoRA 训练 = 知识灌输？**
- 纠正：QLoRA = 行为模式塑形（风格/框架/优先级），不是教新事实
- 船长确认：这恰好是他想做的事——"用新的视角和分析框架对已有知识进行组合"
- 结论：QLoRA + RAG 形成完美互补（QLoRA 管"怎么想"，RAG 管"参考什么"）

### 架构决策

1. **ERIC 端**：FastAPI + 7B (llama.cpp) + ChromaDB + bge-small-zh (CPU)
2. **本机端**：WorkBuddy 通过 Tailscale HTTP 调用 ERIC API
3. **润色层**：Yourself skill 在本机 WorkBuddy 上执行
4. **训练数据**：用户纠偏 → training-data-collector 自动收集
5. **降级起步**：第一版不做全自动不匹配检测，RAG 作为增强注入（非验证）

### ERIC 依赖地狱记录

```
初始状态：
├── torch 2.5.1+cu121 (太旧，缺 torch.int1)
├── transformers 4.48.0 (太旧，unsolth 需 ≥4.51.3)
├── trl 0.9.6 (太旧，unsolth 需 ≥0.18.2)
└── unsloth 2026.7.6

尝试路径：
1. transformers 5.14.1 → unsloth 拒绝（≥5.5.0 不兼容）
2. transformers 5.5.0 → 导入链拉 torchao → torch.int1 缺失
3. trl 0.24.0 → 要求 transformers ≥4.56.1 → 与 unsloth ≤5.5.0 冲突
4. trl 0.20.0 → 拉 transformers 5.14.1 → 回到起点

根因：PyTorch 2.5.1 缺少 torch.int1 → torchao 崩 → transformers 导入链崩
解法：升级 PyTorch → 2.6.0（网络慢，本地下载 wheel 再 SCP）
```
