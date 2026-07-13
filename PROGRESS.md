### 07-13 11:55
为 GitHub Actions runner `node-39-137` 添加了 `node-39-137` 自定义标签，修复其无法匹配 `internal-command.yml` 的 `runs-on` 条件的问题。端到端探针已被该 runner 接收，但工作流在完成步骤后仍未回写终态，待在 runner 主机上排查 actions-runner 服务。

### 07-13 16:07
将 `scripts/Qwen3_flashcomm.sh` 改为启动基于 `AsyncLLM.generate()` 的离线单请求生成脚本，保留 FlashComm、四卡 TP 和专家并行配置。

### 07-13 16:42
`remote-run.sh` 改为通过 workflow dispatch REST API 直接获取 `workflow_run_id`，删除创建阶段的 `gh run list` 轮询，并将运行状态刷新间隔设为 15 秒。

### 07-13 16:56
将 FlashComm 离线生成所需的环境变量移入 Python 脚本，并固定使用空闲设备 `1,2,3,5`。

### 07-13 17:12
为 Actions checkout 的源码运行补充容器已安装包生成的 `_build_info.py` 搜索路径，避免源码树缺少构建元数据导致初始化失败。

### 07-13 18:06
通过 GitHub Actions 在 server1 的 `xrs_090` 中创建持久 venv，并尝试以 editable 模式安装 vLLM 与 vLLM Ascend。构建 run `29240586688` 的命令步骤已执行，但 artifact 上传未回写终态；已 force-cancel，验证 run `29241316216` 等待 runner 释放。

### 07-13 18:24
确认 pip editable 安装因绿区缺少 `setuptools_rust` 且无法访问 PyPI 而未完成，改用 venv `.pth` 优先加载 Actions checkout。run `29242516053` 已验证主进程和新子进程均加载 checkout 源码。NPU 1、2、3 被其他容器任务占用，本次实验将临时覆盖为当前空闲的 4、5、6、7，脚本默认值仍为 1、2、3、5。

### 07-13 18:28
离线 run `29242788168` 已进入 Ascend 插件初始化，因 vLLM checkout 缺少打包生成的 `_version.py` 而将版本识别为 `dev`。按插件错误提示为脚本补充当前子模块对应的 `VLLM_VERSION=0.23.0` 默认值。

### 07-13 18:32
离线 run `29242916573` 已从 checkout 加载模型并完成 4 个 worker 的权重加载，在 profile run 因源码树缺少 `vllm_ascend_C` 原生扩展而失败。脚本保持 checkout Python 代码优先，仅追加容器已安装包目录以复用原生 `.so`。

### 07-13 18:38
离线 run `29243183112` 已成功加载原生扩展，但启动时目标设备仅剩约 3GB 空闲显存。检查确认 NPU 0–3 被其他 DP worker 占用，NPU 4–7 被 `zjs_test` 容器的 TP8 worker 占用；这些进程均不属于 `xrs_090`，未做清理。server1 当前没有可用于 TP4 实验的设备，生成实验等待资源释放。
