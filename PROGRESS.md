### 07-13 11:55
为 GitHub Actions runner `node-39-137` 添加了 `node-39-137` 自定义标签，修复其无法匹配 `internal-command.yml` 的 `runs-on` 条件的问题。端到端探针已被该 runner 接收，但工作流在完成步骤后仍未回写终态，待在 runner 主机上排查 actions-runner 服务。

### 07-13 16:07
将 `scripts/Qwen3_flashcomm.sh` 改为启动基于 `AsyncLLM.generate()` 的离线单请求生成脚本，保留 FlashComm、四卡 TP 和专家并行配置。

### 07-13 16:42
`remote-run.sh` 改为通过 workflow dispatch REST API 直接获取 `workflow_run_id`，删除创建阶段的 `gh run list` 轮询，并将运行状态刷新间隔设为 15 秒。

### 07-13 16:56
将 FlashComm 离线生成所需的环境变量移入 Python 脚本，并固定使用空闲设备 `1,2,3,5`。
