### 07-13 11:55
为 GitHub Actions runner `node-39-137` 添加了 `node-39-137` 自定义标签，修复其无法匹配 `internal-command.yml` 的 `runs-on` 条件的问题。端到端探针已被该 runner 接收，但工作流在完成步骤后仍未回写终态，待在 runner 主机上排查 actions-runner 服务。

### 07-13 16:07
将 `scripts/Qwen3_flashcomm.sh` 改为启动基于 `AsyncLLM.generate()` 的离线单请求生成脚本，保留 FlashComm、四卡 TP 和专家并行配置。
