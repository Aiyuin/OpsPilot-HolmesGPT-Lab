# 第三章实验运行手册

本目录用于生成论文可以追溯的实验数据，不把一次成功截图当作实验结论。HolmesGPT 上游固定到提交 `5e983c1`，模型使用阿里百炼 `qwen-plus`，故障场景来自上游官方评测夹具。

## 1. 实验环境

- 本机 Conda 环境：`holmesgpt`，Python 3.12。
- 本机 Docker Desktop：分配 10 vCPU、8 GiB 内存。
- 隔离集群：Kind，context 为 `kind-opspilot-thesis`。
- Agent 模型：`openai/qwen-plus`。
- 评分模型：`qwen-plus`，通过相同 OpenAI-compatible endpoint 调用。
- 单个 pytest case 硬超时：180 秒；可用 `HOLMES_TEST_TIMEOUT_SECONDS` 调整。
- 原始数据：`results/raw/<run-id>/`，默认不提交 Git。
- 可提交数据：`results/processed/<run-id>.csv`、统计汇总和图表。

## 2. 创建实验集群

首次启动 Docker Desktop 时，macOS 会要求管理员授权配置网络组件。完成授权后运行：

```bash
cd /Users/aiyuin/AiProjects/ai-agent-OpsPilot/opspilot-lab
./experiments/chapter3/setup_kind.sh
```

该集群只用于故障注入，不连接生产 Kubernetes。

统计分析单独使用 Conda 环境，避免污染 HolmesGPT 运行依赖：

```bash
./experiments/chapter3/setup_analysis_env.sh
```

官方评测 runner 还需要单 case 超时插件：

```bash
conda run -n holmesgpt python -m pip install \
  -r experiments/chapter3/requirements-eval.txt
```

## 3. 先导实验

先运行无工具基线（不要求 Docker/Kubernetes）：

```bash
conda run -n holmesgpt python experiments/chapter3/run_direct_baseline.py \
  --repetitions 1 --label pilot-direct --phase pilot
```

再运行工具 Agent：

```bash
./experiments/chapter3/run_official_eval.sh 09_crashpod 1 pilot
```

验收条件：测试成功创建 `payment-processing-worker`，HolmesGPT 至少调用 Kubernetes 状态/日志工具，并把缺失 `DEPLOY_ENV` 识别为根因。无论通过或失败都保留 JSON、控制台日志和逐次 CSV。

## 4. 正式实验

正式数据不得用单次调用。每个场景、每个实验变体运行 10 次；先串行运行避免并发场景互相污染和触发模型限流。

```bash
conda run -n holmesgpt python experiments/chapter3/run_direct_baseline.py \
  --repetitions 10 --label rq1-direct --phase formal

filter="09_crashpod or 10_image_pull_backoff or 15_failed_readiness_probe or 17_oom_kill or 80_pvc_storage_class_mismatch or 176_network_policy_blocking_traffic_no_skills"
./experiments/chapter3/run_official_eval.sh "${filter}" 10 tool_agent formal
```

场景覆盖：配置缺失、镜像拉取、探针失败、OOM、PVC/StorageClass、NetworkPolicy。

`17_oom_kill` 上游夹具固定选择 `amd64` 节点。在 Apple Silicon 的 `arm64` Kind 集群中，运行脚本会临时应用 `patches/arm64-oom-fixture.patch`：改用多架构 Python 镜像制造相同的 100 MiB 内存限制 OOM，退出时自动还原上游文件。元数据会记录节点架构和是否应用补丁；这属于实验平台兼容层，不改变预设根因。

## 5. 数据纪律

1. 不删除失败样本；区分模型错误、场景部署失败和 API 限流。
2. 每次运行记录源码 commit、模型、集群 context、重复次数和 token 上限。
3. 正式对比使用相同场景顺序和重复次数。
4. 报告正确率时给出 Wilson 95% 置信区间。
5. 报告时延时给出中位数、P95 和 bootstrap 95% 置信区间。
6. 对配对正确率使用 McNemar 检验；对时延使用 Wilcoxon 配对检验。
7. 论文中的每个数字必须能追溯到 processed CSV 和对应 raw run-id。

完整研究问题、变量和验收门槛见 `../../thesis/chapter3/EXPERIMENT_PROTOCOL.md`。

## 6. 汇总与完成门禁

```bash
./experiments/chapter3/run_analysis.sh
```

`validate_completion.py` 只有在六类场景、三个方法变体均达到每组合 10 次且汇总产物齐全时才返回成功。先导实验不会被误报为第三章完成。
