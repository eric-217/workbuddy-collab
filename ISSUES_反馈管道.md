# 反馈管道 — 任务与待办

> **用途**：跟踪反馈管道建设的所有任务、问题和待办
> **创建**：2026-08-01
> **最后更新**：2026-08-01

---

## 🚧 建设阶段 (Phase 1: 基础设施)

### ERIC 端

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| E1 | PyTorch 升级到 2.6.0 | 🔄 下载中 | 本地下载 wheel → scp ERIC |
| E2 | 安装兼容 unsloth 的依赖 | ⏳ | transformers 4.51.3 + trl 0.20.0 + torchao |
| E3 | MS-v1.1 训练 (26 条新数据) | ⏳ | 依赖 E1+E2 |
| E4 | 启动 llama-server 推理服务 | ⏳ | MS-v1.1 checkpoint |
| E5 | 下载 bge-small-zh-v1.5 | ⏳ | CPU embedding，102MB |
| E6 | 安装 ChromaDB + FastAPI + uvicorn | ⏳ | `pip install chromadb fastapi uvicorn` |
| E7 | 编写 ERIC API 编排脚本 | ⏳ | 7B+RAG 管道逻辑 |
| E8 | 启动 RAG API 服务 (端口 8001) | ⏳ | uvicorn 后台运行 |

### 本机端

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| L1 | GitHub 协作中枢文件 | ✅ | MEMORY_SYNC + ISSUES + LOG |
| L2 | 反馈管道机制规范.md | ⏳ | 写入大模型训练目录 |
| L3 | 更新 ~/.workbuddy/MEMORY.md | ⏳ | 管道恢复规则 |
| L4 | Git commit + push | ⏳ | — |

---

## 🔮 后续阶段

### Phase 2: RAG 知识库初始化
- [ ] 提取固收分析框架文档为 RAG 知识片段
- [ ] 提取 format_b 框架注入数据
- [ ] 建立知识库更新机制

### Phase 3: 管道联调
- [ ] 本机 WorkBuddy → ERIC API 端到端测试
- [ ] Yourself 润色环节接入
- [ ] 训练数据自动收集验证

### Phase 4: 优化迭代
- [ ] 调优 embedding 相似度阈值
- [ ] 加入置信度评分
- [ ] 自动标记 vs 人工审查比例调优
