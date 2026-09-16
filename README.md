# OpsPilot HolmesGPT 复现实验室

这个目录保存 HolmesGPT 的部署覆盖、辅助脚本和中文学习文档；上游源码位于相邻的 `../holmesgpt/`。

## 当前布局

```text
ai-agent-OpsPilot/
├── holmesgpt/                 # HolmesGPT 上游源码（sparse checkout）
└── opspilot-lab/
    ├── deployment/            # 远程 Docker Compose 配置
    ├── docs/LEARNING_GUIDE.md # 中文学习与复现手册
    └── scripts/               # 本地、远程运维脚本
```

## 快速入口

```bash
# 当前终端统一指定远程服务器，真实 IP 不提交到 Git
export OPSPILOT_SERVER=203.0.113.10  # 替换为你的服务器 IP

# 本机源码环境
conda activate holmesgpt
cd ../holmesgpt
holmes --help

# 从本机源码打包，在远程服务器构建并启动 Docker 镜像
cd ../opspilot-lab
./scripts/deploy-remote.sh

# 建立到远程 API 的安全隧道
./scripts/tunnel.sh

# 另开终端检查远程服务
./scripts/remote-status.sh

# 安全写入百炼 API Key（交互输入，不回显）
./scripts/configure-bailian-key.sh

# 或从被 Git 忽略的本地文件读取，只提取 DASHSCOPE_API_KEY
./scripts/configure-bailian-key.sh --env-file deployment/.env

# 模型端到端冒烟测试
./scripts/remote-smoke-test.sh

# SSE 流式链路测试
./scripts/remote-sse-test.sh
```

完整说明见 [学习手册](docs/LEARNING_GUIDE.md)。

## Docker 放在哪里

- **正常开发/学习：** 本机只需要 Conda 与 HolmesGPT 源码，不需要启动 Docker。
- **服务部署：** Docker Compose 运行在远程服务器，本机通过 SSH 隧道访问 API。
- **论文故障注入（可选）：** `experiments/chapter3` 可临时使用本机 Docker Desktop + Kind；它只用于隔离 Kubernetes 实验，不参与远程服务部署。不做论文实验时可以完全关闭 Docker Desktop。
