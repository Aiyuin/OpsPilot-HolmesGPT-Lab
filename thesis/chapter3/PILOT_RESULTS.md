# 第三章先导实验记录

## P0：Direct-Qwen 无工具基线

- 运行编号：`pilot-direct-20260916-153147`
- 日期：2026-09-16
- 模型：阿里百炼 `qwen-plus`
- 温度：0.2
- 场景：6 类，每类 1 次
- 工具：无
- 评分：预注册关键词组硬评分；语义与人工复核尚未进行
- 逐次数据：`experiments/chapter3/results/processed/pilot-direct-20260916-153147.csv`

### 结果

Direct-Qwen 命中 2/6，先导正确率为 33.3%，Wilson 95% CI 为 `[9.7%, 70.0%]`。六次请求均正常返回，没有 API 错误。模型命中了 readiness probe 与 OOM 两类，但未识别环境变量缺失、指定镜像不可拉取、指定 StorageClass 不存在和 NetworkPolicy 标签不匹配。

这两个命中不能证明模型获得了真实环境证据：无工具基线没有访问集群，输出只是基于资源名称和常见 Kubernetes 故障模式的推断。后续人工复核必须把“正确猜测”和“证据支持的诊断”分开记录。

| 场景 | 正确 | 时延/s | token |
|---|---:|---:|---:|
| `09_crashpod` | 0 | 8.07 | 339 |
| `10_image_pull_backoff` | 0 | 6.54 | 360 |
| `15_failed_readiness_probe` | 1 | 5.43 | 300 |
| `17_oom_kill` | 1 | 8.09 | 431 |
| `80_pvc_storage_class_mismatch` | 0 | 6.58 | 361 |
| `176_network_policy_blocking_traffic_no_skills` | 0 | 9.71 | 492 |

### 结论边界

本先导只证明调用、采集、评分、汇总和绘图链路可用。每场景只有一次，样本量不足，置信区间很宽，不能写入论文正式结论。正式 Direct-Qwen 基线随后已完成每场景 10 次；20% 人工复核仍待完成。

## P1：HolmesGPT 工具 Agent

- 成功运行编号：`tool_agent_pilot-20260916-155515`
- 场景：`09_crashpod`
- 结果：通过，Judge 正确性得分 1
- HolmesGPT 诊断时延：40.52 秒
- pytest 总调用阶段：60.27 秒（不含独立记录的 setup/cleanup）
- LLM 调用：7 次
- 工具调用：14 次
- 总 token：86,984（prompt 85,492；completion 1,492；cached 45,056）

该次实验先后查询资源计数、Deployment/Pod 状态、日志、`kubectl describe` 和 Deployment YAML，最终从容器命令及配置中确认 `DEPLOY_ENV` 未定义，而不是仅凭问题文本猜测。故障注入和清理均成功。

运行中出现两类可复现异常：模型先请求了未注册的 `kubectl_describe` 工具；第一次日志请求把 `now` 作为结束时间，触发 `dateutil` 解析异常。Agent 随后改用 bash 与不带异常时间参数的日志调用完成诊断。这些异常将作为工具故障传播与降级机制的真实工程动机，而不能隐去。

首次运行编号 `tool_agent_pilot-20260916-155339` 在推理开始前因本机缺少 Helm CLI 失败。安装 Helm 4.3.0 后，同一场景重跑通过。该失败属于环境前置检查失败，保留在 processed CSV 中，但因 `phase=pilot` 不纳入正式正确率。

另一个成功样本为 `80_pvc_storage_class_mismatch`：诊断正确，HolmesGPT 时延 35.66 秒，6 次 LLM 调用、17 次工具调用、72,503 token。`17_oom_kill` 在 ARM64 等价故障夹具上超过 180 秒，记录为未收敛；网络场景在用户终止本地批量实验时记录为 incomplete。镜像和探针场景尚未完成工具 Agent 先导。全部通过前，不得声称工具 Agent 已覆盖六类故障。

阶段性结论是：远程 Docker 服务复现不依赖本机 Docker；本机 Kind 只用于可选论文实验。当前已有两个带真实集群证据的工具 Agent 成功案例，以及一个有价值的超时失败案例，足以支持后续学习和简历演示，但不足以形成三方法的完整统计对比。

## F0：Direct-Qwen 正式基线阶段结果

- 运行编号：`rq1-direct-20260916-153841`
- 样本：6 场景 × 10 次 = 60 次
- API 失败：0 次
- 数据阶段：`phase=formal`

| 场景 | 正确数/总数 | 正确率 | Wilson 95% CI | P50/s | P95/s |
|---|---:|---:|---:|---:|---:|
| `09_crashpod` | 0/10 | 0% | [0.0%, 27.8%] | 6.35 | 6.68 |
| `10_image_pull_backoff` | 0/10 | 0% | [0.0%, 27.8%] | 6.64 | 7.01 |
| `15_failed_readiness_probe` | 10/10 | 100% | [72.2%, 100%] | 5.30 | 5.66 |
| `17_oom_kill` | 9/10 | 90% | [59.6%, 98.2%] | 6.44 | 8.22 |
| `80_pvc_storage_class_mismatch` | 0/10 | 0% | [0.0%, 27.8%] | 7.37 | 8.19 |
| `176_network_policy_blocking_traffic_no_skills` | 0/10 | 0% | [0.0%, 27.8%] | 9.21 | 13.68 |

当前总体硬评分为 19/60（31.7%），六类宏平均同为 31.7%。这一结果尚未完成 20% 人工复核；readiness 和 OOM 的命中可能属于无环境证据的正确猜测，因此这里只报告阶段数据，不据此接受或拒绝 H1。
