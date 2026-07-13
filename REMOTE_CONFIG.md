# 蓝区 Agent 远程驱动绿区服务器

## 目前配置
在docker 容器中进行开发。
xrs_090容器运行在worker-97-44上 （server1）
xrs_090容器运行在worker-97-4上 （server2）
xrs_090容器运行在node-39-137上 （server3 80.5.17.110）
在97开头机器上，权重位置在/mnt/share/weights文件夹中。
先用Qwen3-30B-A3B跑通

`node-39-137` 的 GitHub Actions runner 标签必须包含：`self-hosted`、`Linux`、`ARM64` 和 `node-39-137`。`scripts/remote-run.sh` 会将第四个参数作为必需标签传给 workflow。

## 背景

蓝区可以方便地使用 Agent 辅助开发，但内网绿区的 950 机器通常无法直接使用 Agent。  
实际工作中，流程往往会变成：

1. 在蓝区让 Agent 修改代码、生成测试命令。
2. 手动把命令复制到绿区 950 机器执行。
3. 再把执行结果、日志、profile 等复制回蓝区。
4. 如果命令失败，再回到蓝区继续分析并重新生成命令。

这个来回复制的过程比较繁琐。

为了解决这个问题，可以把绿区 950 机器注册为 GitHub 仓库的 self-hosted runner。这样蓝区 Agent 就可以通过 GitHub Actions 间接向绿区 950 发送命令，并把执行结果通过 artifact 回传到蓝区。

## 方案效果

采用这个方案后：

- 蓝区仍然是主要开发环境。
- 绿区 950 负责真实构建、安装、benchmark 和 profile。
- 蓝区 Agent 可以直接触发绿区命令，不需要人工反复复制命令和日志。
- 执行结果可以通过 GitHub artifact 自动回传。

## 使用方法

在蓝区环境的仓库中直接执行：

```bash
scripts/remote-run.sh '<command>' '<artifact paths>' '96K' '<worker name>'
```

参数说明：

- `<command>`: 要在绿区 950 runner 上执行的 shell 命令。
- `<artifact paths>`: 需要从绿区回传到蓝区的文件或目录。
- `96K`: artifact 最大上传预算。由于绿区不适合上传过大文件，这里建议控制在约 `96K`。
- `<worker name>`: 绿区 runner 的label，必须与 runner 配置时的名称一致。

执行完成后，脚本会在蓝区下载并解压 artifact，输出目录类似：

```text
output/<run-key>/
```

## 使用示例

下面是一个构建并安装自定义算子的示例：

```bash
scripts/remote-run.sh 'source /usr/local/Ascend/cann-9.0.T550/set_env.sh && conda activate /home/xlm/conda_envs/fa && rm -rf build build_out third_party && bash build.sh --pkg --soc=ascend950 --vendor_name=custom --ops=block_sparse_attention && /home/xlm/tmp/bsa_pkg/cann-ops-transformer-custom_linux-aarch64.run --install-path=/home/xlm/ascend_custom && test -f /home/xlm/ascend_custom/vendors/custom_transformer/bin/set_env.bash' 'run-output/' '96K'
```

## 配置方法

### 1. 配置个人github repo
https://github.com/MmMmaru/vllm-ascend.git

### 2. 配置绿区 950 Runner

在 GitHub 仓库页面添加 self-hosted runner：

```text
Settings -> Actions -> Runners -> New self-hosted runner
```

选择 `ARM64` 平台，然后在绿区 950 机器上执行 GitHub 页面提供的命令。一般会类似下面这样：

```bash
# Create a folder
mkdir actions-runner && cd actions-runner# Download the latest runner package
curl -o actions-runner-linux-arm64-2.335.1.tar.gz -L https://github.com/actions/runner/releases/download/v2.335.1/actions-runner-linux-arm64-2.335.1.tar.gz# Optional: Validate the hash
echo "6d1e85bfd1a506a8b17c1f1b9b57dba458ffed90898799aaa9f599520b0d9207  actions-runner-linux-arm64-2.335.1.tar.gz" | shasum -a 256 -c# Extract the installer
tar xzf ./actions-runner-linux-arm64-2.335.1.tar.gz
# Create the runner and start the configuration experience
./config.sh --url https://github.com/MmMmaru/vllm-ascend --token ARSQUCYPOBJENDRQUYBRV4DKJ4TP6# Last step, run it!
./run.sh
```

执行 `./run.sh` 后，runner 就会启动并开始监听任务。
目前runner名称：worker-97-4


### 3. 配置蓝区仓库

蓝区自己的开发分支需要包含以下三个文件，可以参考 `xlm_fa` 分支：

```text
ops-transformer/.github/workflows/internal-command.yml
ops-transformer/scripts/prepare-internal-artifact.py
ops-transformer/scripts/remote-run.sh
```

它们的职责分别是：

- `.github/workflows/internal-command.yml`: 接收命令并在 self-hosted runner 上执行。
- `scripts/prepare-internal-artifact.py`: 打包执行日志和指定路径，并控制 artifact 大小，避免上传失败。
- `scripts/remote-run.sh`: 蓝区调用入口，负责触发 workflow、等待完成、下载 artifact、展示日志。

### 4. 配置蓝区 GitHub CLI

蓝区需要安装并登录 GitHub CLI：

```bash
gh auth login
```

建议确认 `gh` 可以正常访问目标仓库：

```bash
gh repo view <user-or-org>/ops-transformer
```

注意：通过 `apt` 安装的 `gh` 版本可能过老，无法正常触发或查询 workflow。建议按 GitHub CLI 官方文档安装最新版，或至少先确认：

```bash
gh --version
```

## 注意事项

- runner 每次执行 GitHub Actions 时通常会进行干净的 checkout，不要假设 `build/`、`build_out/` 等工作目录内容会长期保留。
- 需要长期保存的 `.run` 包、benchmark 结果、profile 数据等，应主动复制到持久目录。
- artifact 上传大小受限，建议提前规划需要回传的文件，避免上传过大目录。

## 最终调用方式

完成以上配置后，就可以在蓝区直接执行：

```bash
scripts/remote-run.sh '<command>' '<artifact paths>' '96K'
```
