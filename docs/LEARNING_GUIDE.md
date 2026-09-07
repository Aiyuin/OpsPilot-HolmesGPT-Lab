# HolmesGPT 复现与学习手册

> 目标：不是把开源项目运行起来就结束，而是能够解释 HolmesGPT 的 Agent 循环、工具系统、上下文治理、流式 API、安全边界和测试方法，最终独立写出一个 OpsPilot。

## 1. 本次环境结果

### 本机

- 源码：`../holmesgpt`
- 上游：<https://github.com/HolmesGPT/holmesgpt>
- 分支：`master`
- 初始学习基线提交：`5e983c1`
- Conda 环境：`holmesgpt`
- Python：3.12
- Poetry：1.8.5（遵循上游 `AGENTS.md` 的锁文件要求）
- 环境策略：只使用 Conda，不再叠加 `.venv`
- 安装方式：`pip install -e .`，修改源码后无需重复安装
- 检出策略：sparse-checkout，包含核心源码、Operator、文档、示例和脚本，省略大型评测资产

### 远程服务器

- 地址：通过环境变量 `OPSPILOT_SERVER` 注入，真实公网 IP 不提交到 Git
- 系统：Ubuntu 24.04 LTS，x86_64
- 资源：2 vCPU、1.6 GiB RAM、40 GiB 磁盘
- 新增 Swap：2 GiB，记录在 `/etc/fstab`
- 部署目录：`/opt/opspilot-holmes`
- 容器：`opspilot-holmes`
- 镜像：`opspilot-holmes:5e983c1`，由服务器根据锁定依赖和当前源码自行构建
- 基础运行时：Python 3.11 slim + `kubectl 1.37.0` + 常用只读诊断命令
- API：服务器 `127.0.0.1:5050`，不直接暴露公网
- 本机访问：SSH 隧道 `127.0.0.1:5050 -> 远程 127.0.0.1:5050`
- 模型：阿里云百炼 `qwen-plus`
- 快速摘要模型：阿里云百炼 `qwen-turbo`

为什么没有开放 `0.0.0.0:5050`：HolmesGPT 可以调用运维工具，API 即便有认证，也不应该在学习阶段直接暴露公网。SSH 隧道更简单、安全，也不需要额外配置 TLS 和反向代理。

本次没有直接拉取 HolmesGPT 官方镜像，是因为服务器访问 Google Artifact Registry 超时。替代方案仍是“远程 Docker”：部署脚本只把约 3 MB 核心源码和锁定依赖清单传给服务器，镜像在服务器上构建。本机 Docker 不参与构建或运行。容器依赖使用阿里云 PyPI、Debian 和 Kubernetes 镜像加速，并对 `kubectl` 安装包执行 SHA-256 校验。

## 2. 每次开始学习前

### 2.1 环境分工

```text
本机 Conda：阅读源码、断点调试、运行 CLI/测试
        |
        |  deploy-remote.sh 打包源码并通过 SSH 传输
        v
远程 Docker：构建镜像、运行 FastAPI/Agent、保存运行日志
        |
        |  OpenAI-compatible HTTPS
        v
阿里云百炼：qwen-plus / qwen-turbo
```

Conda 已经是完整的 Python 隔离环境，因此不要再创建 `.venv`。日常只需激活一次：

本机源码模式：

```bash
export PROJECT_ROOT=/path/to/ai-agent-OpsPilot
export OPSPILOT_SERVER=203.0.113.10  # 替换为你的服务器 IP
conda activate holmesgpt
cd "$PROJECT_ROOT/holmesgpt"
holmes --help
```

从零重建本机环境时执行：

```bash
conda create -n holmesgpt python=3.12 pip -y
conda activate holmesgpt
python -m pip install "poetry==1.8.5" "virtualenv<21"
cd "$PROJECT_ROOT/holmesgpt"
python -m pip install -e .
```

`virtualenv<21` 是为了保持 Poetry 1.8.5 可用；它不是让你再创建一层虚拟环境。Poetry 只负责读取上游 `poetry.lock` 或导出依赖，日常运行直接使用 Conda 中的 `python` 和 `holmes`。

检查本机环境：

```bash
cd "$PROJECT_ROOT/opspilot-lab"
./scripts/local-doctor.sh
```

检查远程服务：

```bash
./scripts/remote-status.sh
```

重新打包源码并在远程构建：

```bash
./scripts/deploy-remote.sh
```

建立隧道：

```bash
./scripts/tunnel.sh
```

保持隧道终端运行，然后访问：

```bash
curl http://127.0.0.1:5050/healthz
curl http://127.0.0.1:5050/readyz
```

Swagger UI 可打开：<http://127.0.0.1:5050/docs>

## 3. 配置阿里百炼

### 3.1 为什么能直接接入

HolmesGPT 使用 LiteLLM，并支持 OpenAI-compatible endpoint。阿里百炼提供 OpenAI 兼容接口，华北 2（北京）的共享地址为：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

HolmesGPT 中使用的模型名必须带 LiteLLM provider 前缀：

```yaml
model: openai/qwen-plus
fast_model: openai/qwen-turbo
```

百炼的 `qwen-plus`、`qwen-max`、`qwen-turbo` 支持 function calling；这是 HolmesGPT 工具调用的必要条件。

官方资料：

- <https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope>
- <https://help.aliyun.com/zh/model-studio/base-url>
- <https://github.com/HolmesGPT/holmesgpt/blob/master/docs/ai-providers/openai-compatible.md>

### 3.2 写入密钥

不要把 API Key 发到聊天记录、写进 `config.yaml` 或提交到 Git。运行：

```bash
cd "$PROJECT_ROOT/opspilot-lab"
./scripts/configure-bailian-key.sh
```

脚本会静默读取密钥，更新服务器 `/opt/opspilot-holmes/.env`，权限设为 `600`，随后重新创建容器。

如果你的 Key 属于新加坡、美国或专属业务空间，必须同步修改 `BAILIAN_BASE_URL`，Key 和 Endpoint 不可跨地域使用。

### 3.3 验证模型

```bash
./scripts/remote-smoke-test.sh
```

通过标准：`readyz` 成功，并返回“HolmesGPT 百炼模型连接成功”。如果出现 401，优先检查 API Key 与 Endpoint 地域是否匹配；如果模型能回答但不调用工具，确认所选模型支持 function calling。

## 4. 先理解整体请求链路

一次 `/api/chat` 请求的主链路：

```text
HTTP POST /api/chat
    -> server.py: chat()
    -> Config 创建 LLM 与 ToolExecutor
    -> prompt.py 组装系统提示词和用户上下文
    -> ToolCallingLLM.call_stream()/call()
    -> LLM 决定是否产生 tool_calls
    -> ToolExecutor 执行工具并返回结构化结果
    -> 结果经过限制、落盘、摘要或上下文压缩
    -> 继续调用 LLM，直到给出最终答案或达到 max_steps
    -> server.py 返回 JSON 或 SSE
```

建议打开以下文件并按顺序打断点：

1. `server.py`
2. `holmes/config.py`
3. `holmes/core/prompt.py`
4. `holmes/core/tool_calling_llm.py`
5. `holmes/core/tools_utils/tool_executor.py`
6. `holmes/core/tools_utils/tool_context_window_limiter.py`
7. `holmes/core/truncation/input_context_window_limiter.py`
8. `holmes/core/truncation/compaction.py`
9. `holmes/utils/stream.py`

## 5. 模块精读

### 5.1 CLI 入口

文件：`holmes/main.py`、`holmes_cli.py`

需要回答：

- Typer 子命令如何注册？
- `ask`、`investigate`、`toolset` 的边界是什么？
- CLI 参数、环境变量、配置文件的优先级是什么？
- `max_steps` 最终如何进入 `ToolCallingLLM`？

练习：给 `holmes ask` 增加一个只影响本地输出的 `--request-label` 参数，并为它写单元测试。不要先改 Agent 核心逻辑。

### 5.2 配置与模型注册

文件：`holmes/config.py`、`holmes/core/llm.py`

核心对象：

- `Config`：模型、工具集、告警源、运行限制。
- `LLMModelRegistry`：解析模型配置并生成 `ModelEntry`。
- `DefaultLLM`：封装 LiteLLM 调用、流式响应、token 计算与模型能力。

重点理解：

- `model` 是配置选择名还是 LiteLLM 实际模型名？
- `openai/qwen-plus` 中 `openai/` 的作用是什么？
- `api_base` 如何覆盖默认 OpenAI Endpoint？
- 为什么 Key 不应该写进 YAML？
- 未知模型的上下文长度和价格如何处理？

练习：增加 `~/.holmes/model_list.yaml`，给百炼模型定义易读别名，并比较直接模型名和别名两种加载路径。

### 5.3 Agent 工具调用循环

文件：`holmes/core/tool_calling_llm.py`

这是最重要的文件。阅读时画出以下状态：

```text
prepare messages
    -> call LLM
    -> no tool call? -> final answer
    -> tool approval required? -> pause/deny/approve
    -> execute tools
    -> append tool results
    -> context check
    -> next iteration
```

重点查找：

- `while True` 的退出条件。
- `max_steps` 在哪里检查。
- 每次工具调用如何追加到 message history。
- 并行工具调用如何组织。
- orphaned tool call 为什么必须补齐或拒绝。
- 工具执行失败后，是抛异常还是把错误作为证据交回模型。

面试表达：Agent 的可靠性不来自 Prompt，而来自围绕循环构建的状态约束、工具协议、预算和终止条件。

### 5.4 Toolset 与 ToolExecutor

文件：

- `holmes/core/tools.py`
- `holmes/core/toolset_manager.py`
- `holmes/core/tools_utils/tool_executor.py`
- `holmes/plugins/toolsets/`

Toolset 是数据源或能力的集合。工具可以由 Python、受限 Bash、HTTP API 或 MCP Server 提供。

精读三个代表：

1. `holmes/plugins/toolsets/kubernetes.yaml`：声明式工具配置。
2. `holmes/plugins/toolsets/prometheus/prometheus.py`：Python API Toolset。
3. `holmes/plugins/toolsets/mcp/toolset_mcp.py`：MCP 工具发现、连接与调用。

每个工具都应该做到：

- 参数 Schema 明确。
- 查询尽可能在服务端过滤。
- 空数据要说明查了什么范围。
- 错误返回原始状态码、查询条件和时间范围。
- 默认只读；变更操作需要额外审批。

练习：实现一个本地 `systemd` 只读 Toolset，只允许执行 `systemctl status`、`journalctl --since` 和磁盘/内存查询，不允许 restart、stop 或写文件。

### 5.5 MCP

文件：`holmes/plugins/toolsets/mcp/toolset_mcp.py`

MCP 在这里解决的是“Agent 如何用统一协议发现和调用外部工具”，不是替代 Agent 编排。

需要掌握：

- stdio、SSE、Streamable HTTP 的传输区别。
- `tools/list` 与 `tools/call` 的生命周期。
- MCP JSON Schema 如何转换为 LLM function schema。
- 服务断开、刷新失败和 OAuth 失效如何处理。
- 为什么 MCP Server 不应该天然被信任。

练习：写一个只包含 `get_host_health` 的 FastMCP Server，返回 load average、内存、磁盘和最近 20 行服务日志；然后将它配置为 HolmesGPT 的 remote MCP toolset。

### 5.6 上下文治理

文件：

- `holmes/core/tools_utils/tool_context_window_limiter.py`
- `holmes/core/truncation/input_context_window_limiter.py`
- `holmes/core/truncation/compaction.py`
- `holmes/core/transformers/`

大型日志和指标查询最容易把 Agent 撑爆。HolmesGPT 的处理思想包括：

- 首先在数据源端过滤。
- 工具结果设置内存与 token 预算。
- 过大结果写入临时文件，只把预览交给模型。
- 对历史消息压缩，而不是简单删除最近证据。
- 可使用 fast model 摘要大型工具输出。
- 为最终回答预留输出 token。

实验：生成 1 MB、10 MB、50 MB 三种日志结果，记录进入模型的字符数、token 数、临时文件大小和进程峰值内存。

### 5.7 流式 API

文件：`server.py`、`holmes/utils/stream.py`

`/api/chat` 的 `stream: true` 返回 SSE。它不仅流式输出最终文字，还可以传递状态、工具调用和使用量事件。

实验请求：

```bash
curl -N -X POST http://127.0.0.1:5050/api/chat \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <HOLMES_API_KEY>' \
  -d '{"ask":"分析一个 CrashLoopBackOff 的常见原因并列出证据收集步骤","stream":true}'
```

需要解释：

- 为什么生成器执行期间异常不能完全依赖 FastAPI 全局异常处理？
- 客户端断开时如何清理临时工具结果？
- SSE 和 WebSocket 在这个场景中的取舍是什么？

### 5.8 安全设计

精读：

- `holmes/core/safeguards.py`
- `holmes/plugins/toolsets/bash/validation.py`
- `docs/data-sources/tool-execution-safety.md`
- `docs/reference/kubernetes-permissions.md`

安全边界：

- API 用 `HOLMES_API_KEY` 认证。
- 远程端口只监听 loopback。
- Toolset 默认只读。
- Bash 命令需要允许列表和参数级校验。
- Kubernetes 使用最小权限 RBAC。
- 不把 Docker Socket 挂载给 Holmes 容器，因为这近似等价于宿主机 root。
- LLM 输出不是可信指令，工具层必须再次校验。

## 6. API 实验清单

### 6.1 健康检查

```bash
curl http://127.0.0.1:5050/healthz
curl http://127.0.0.1:5050/readyz
```

### 6.2 非流式对话

```bash
curl -X POST http://127.0.0.1:5050/api/chat \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <HOLMES_API_KEY>' \
  -d '{"ask":"解释 Kubernetes OOMKilled 的证据链","stream":false}'
```

### 6.3 流式对话

```bash
curl -N -X POST http://127.0.0.1:5050/api/chat \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <HOLMES_API_KEY>' \
  -d '{"ask":"给出排查 HTTP 5xx 激增的步骤","stream":true}'
```

### 6.4 结构化输出

```bash
curl -X POST http://127.0.0.1:5050/api/chat \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <HOLMES_API_KEY>' \
  -d '{
    "ask":"评估一个持续重启的 Pod",
    "response_format":{
      "type":"json_schema",
      "json_schema":{
        "name":"Diagnosis",
        "strict":true,
        "schema":{
          "type":"object",
          "properties":{
            "root_cause":{"type":"string"},
            "confidence":{"type":"number"},
            "evidence":{"type":"array","items":{"type":"string"}}
          },
          "required":["root_cause","confidence","evidence"],
          "additionalProperties":false
        }
      }
    }
  }'
```

如果百炼模型对严格 JSON Schema 支持不完整，先把它作为兼容性问题记录下来，不要用字符串截取伪装成严格结构化输出。

## 7. 调试方法

### 查看容器日志

```bash
ssh "root@${OPSPILOT_SERVER}" \
  'cd /opt/opspilot-holmes && docker compose logs --tail=200 -f holmes'
```

### 检查最终生效配置

下面命令不会显示 API Key：

```bash
ssh "root@${OPSPILOT_SERVER}" \
  'cd /opt/opspilot-holmes && docker compose config --no-interpolate | sed "/API_KEY/d"'
```

### 本地调试 CLI

```bash
conda activate holmesgpt
cd "$PROJECT_ROOT/holmesgpt"
export OPENAI_API_KEY="$DASHSCOPE_API_KEY"
export OPENAI_API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"
holmes ask "只回答 OK" --model openai/qwen-plus
```

不要把 Key 写进 shell history。更推荐临时 `read -s` 或通过系统密钥管理器注入。

### 常见故障

1. `401 invalid_api_key`：Key 与地域 Endpoint 不匹配，或 Key 未开通模型权限。
2. `404 model not found`：模型名或业务空间配置错误。
3. 模型一直输出文字、不调用工具：模型不支持 function calling，或 tool schema 不兼容。
4. 容器退出码 137：内存不足；检查 `docker stats` 和 `swapon --show`。
5. `max steps reached`：问题过大、工具错误导致自我纠错循环，或终止条件不足。
6. 大量 token：查询未在服务端过滤，或工具结果 limiter 没有生效。
7. 本机 Poetry 改写 lock：确认使用 1.8.5，不要用 Poetry 2.x 重新生成锁文件。

## 8. 六周学习计划

### 第 1 周：跑通与画图

- 完成本手册所有 API 实验。
- 给一次请求记录完整日志和 SSE 事件。
- 自己画一张调用链图。
- 输出：《HolmesGPT 一次请求从 FastAPI 到 LLM 的调用路径》。

验收：能脱离文档讲清 `server.py -> Config -> ToolCallingLLM -> ToolExecutor`。

### 第 2 周：工具系统

- 精读 Kubernetes、Prometheus 和 MCP Toolset。
- 写一个只读 systemd Toolset。
- 故意让工具超时、返回空数据、返回 500。
- 比较“抛异常”和“结构化错误交回模型”的行为。

验收：Toolset 有参数校验、超时、错误信息和测试。

### 第 3 周：循环与收敛

- 给工具循环增加 trace ID、step number 和 elapsed time。
- 复现重复工具调用。
- 实现重复参数指纹检测实验。
- 比较 `max_steps=5/10/30` 的完成率和成本。

验收：提交一份包含失败案例的收敛实验报告。

### 第 4 周：上下文治理

- 构造超大日志。
- 跟踪 limiter、临时文件和 compaction。
- 比较启用/禁用 fast model 的 token 和耗时。
- 检查敏感日志是否会被送往云端模型。

验收：形成可量化的 token、延迟、内存对比表。

### 第 5 周：故障场景

- 搭建 Kind 或独立测试 K3s，不连接生产集群。
- 注入 ImagePullBackOff、CrashLoopBackOff、OOMKilled、Service 端口错误。
- 记录根因是否正确、调用了哪些工具、花费多少步。
- 为每个场景保留 manifest、预期根因和证据。

验收：至少 4 个可重复故障用例。

### 第 6 周：独立重构 OpsPilot

- 不复制核心循环，使用 LangGraph 自己实现 Planner/Executor/Validator/Reporter。
- 复用自己写的 MCP Server 和故障用例。
- 增加 step、deadline、token、repeat、evidence 五层约束。
- 将 HolmesGPT 作为 baseline，对比准确率、耗时和工具调用数。

验收：能明确指出哪些是上游思想、哪些是自己的设计。

## 9. 从复现到简历项目

第一阶段简历只能写：

> 基于 HolmesGPT 完成开源 SRE Agent 的本地与云端复现，接入阿里百炼 OpenAI 兼容接口，分析其工具调用循环、MCP Toolset、上下文治理与 SSE 流式服务实现。

完成独立重构和实验后才可以写：

> 独立实现智能运维诊断 Agent，以 LangGraph 编排有界 Plan-Execute-Validate-Replan 工作流，通过 MCP 接入日志与监控工具，并以 HolmesGPT 为 baseline 在多类 Kubernetes 故障上评测根因定位准确率、平均诊断步数与 token 成本。

不要直接声称自己“开发了 HolmesGPT”，也不要把上游已有能力包装成自己的创新。面试含金量来自：你能展示提交历史、测试、故障复现脚本、实验数据和设计取舍。

## 10. 学习笔记模板

每读一个模块，使用以下模板：

```markdown
# 模块名称

## 解决的问题

## 输入与输出

## 主要类和函数

## 正常路径

## 失败路径

## 安全边界

## 我运行的实验

## 我发现的问题

## 如果重新设计，我会怎么做
```

## 11. 运维命令速查

```bash
# 状态
ssh "root@${OPSPILOT_SERVER}" 'cd /opt/opspilot-holmes && docker compose ps'

# 日志
ssh "root@${OPSPILOT_SERVER}" 'cd /opt/opspilot-holmes && docker compose logs --tail=200 holmes'

# 重启
ssh "root@${OPSPILOT_SERVER}" 'cd /opt/opspilot-holmes && docker compose restart holmes'

# 更新源码并在远程重建镜像（在本机 opspilot-lab 目录执行）
./scripts/deploy-remote.sh

# 资源
ssh "root@${OPSPILOT_SERVER}" 'docker stats --no-stream opspilot-holmes; free -h; swapon --show'

# 关闭（保留配置和数据卷）
ssh "root@${OPSPILOT_SERVER}" 'cd /opt/opspilot-holmes && docker compose down'
```

更新前记录当前镜像摘要和上游提交，避免学习过程中“代码没变但行为变了”。

## 12. 下一阶段建议

当前服务器适合 HolmesGPT API 与轻量测试，不适合运行 vLLM：1.6 GiB RAM、无 GPU，即使增加 Swap 也只能避免 OOM，不能提供合理推理性能。后续 vLLM 应放在有 NVIDIA GPU、至少 16～24 GiB 显存的机器；当前服务器继续承担 FastAPI、Agent 编排和 MCP Gateway。

推荐下一步按这个顺序：

1. 配置百炼 Key并完成模型冒烟测试。
2. 完成第一周源码调用链笔记。
3. 新建只读 systemd MCP/Toolset。
4. 部署独立 Kind/K3s 测试环境，不接生产集群。
5. 开始 LangGraph 版 OpsPilot 重构。
