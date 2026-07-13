# vLLM Ascend Request Data Flow

本文记录在 `vllm-ascend` 项目中，执行 `vllm serve ...` 后，一个请求进入系统会经过哪些主要阶段、哪些关键文件，以及 `vllm` 与 `vllm-ascend` 的职责边界。

为了便于理解，下面默认以最常见的 OpenAI 兼容接口 `/v1/chat/completions` 为例。

## 1. 总体分工

可以先记一个粗粒度结论：

- `vllm` 负责通用 serving 框架。
- `vllm-ascend` 负责 Ascend/NPU 平台接入和执行细节。

更具体地说：

- `vllm` 负责 CLI、FastAPI/OpenAI API、chat/completion 协议、prompt 渲染、tokenization、`AsyncLLM`、`EngineCore`、scheduler、executor、多进程/Ray 编排、输出拼装。
- `vllm-ascend` 负责 platform plugin、Ascend 配置修正、NPU worker/model runner、Ascend custom ops、ACL graph、HCCL/KV connector/weight transfer，以及对上游 `vllm` 的必要 patch。

## 2. 启动链路

执行：

```bash
vllm serve <model> ...
```

后，主要会经过下面这条启动路径。

### 2.1 CLI 入口属于上游 vLLM

- `vllm` 的 console script 定义在 `vllm/pyproject.toml`
- 入口函数在 `vllm/entrypoints/cli/main.py`
- `serve` 子命令逻辑在 `vllm/entrypoints/cli/serve.py`

这里会完成参数解析，并最终进入 API server 启动逻辑。

### 2.2 API server 启动

`serve.py` 会进入：

- `vllm/entrypoints/openai/api_server.py`

这里负责：

- 创建监听 socket
- 初始化 FastAPI app
- 创建 `EngineClient`
- 启动 HTTP 服务

### 2.3 vllm-ascend 通过 plugin 接入

`vllm-ascend` 并不自己实现 `vllm serve` 命令，而是通过 entry point 注册为 `vllm` 的插件。

注册位置：

- `setup.py`
- `vllm_ascend/__init__.py`

其中主要有两类插件：

- `vllm.platform_plugins`
- `vllm.general_plugins`

platform plugin 会告诉 `vllm` 当前平台应当使用哪个 `Platform` 实现；
general plugin 会在 engine/worker 进程里执行一些全局注册逻辑，例如 patch、model loader、KV connector、profiling 注册等。

### 2.4 平台识别切到 AscendPlatform

上游 `vllm` 在：

- `vllm/platforms/__init__.py`

里解析当前 platform plugin。

`vllm-ascend` 的 `register()` 会返回：

- `vllm_ascend.platform.NPUPlatform`

即：

- `vllm_ascend/platform.py`

这个 `NPUPlatform` 会做很多 Ascend 平台相关工作，例如：

- 修正默认配置
- 验证并修改 `VllmConfig`
- 选择 Ascend worker 类

当 `parallel_config.worker_cls == "auto"` 时，`NPUPlatform` 会把 worker 设置成：

- `vllm_ascend.worker.worker.NPUWorker`

特殊场景下也可能切到 310P 或 Xlite worker。

## 3. 一个请求进来的主链路

下面按时间顺序看一个 `/v1/chat/completions` 请求如何流动。

## 3.1 请求进入 FastAPI 路由

HTTP 请求首先进入上游 `vllm` 的 OpenAI-compatible router：

- `vllm/entrypoints/openai/chat_completion/api_router.py`

核心入口函数是：

- `create_chat_completion`

它会从 `app.state` 中拿到 `OpenAIServingChat`，并调用其 `create_chat_completion(...)`。

## 3.2 OpenAI 协议层处理

真正的 chat completion 逻辑在：

- `vllm/entrypoints/openai/chat_completion/serving.py`

这里主要做：

- 请求字段校验
- model 选择
- request id 生成
- sampling params 构造
- trace headers、LoRA、tool parser、reasoning parser 等处理

在这个阶段，请求还处在“OpenAI 协议对象”层面，还没有变成 engine 可以直接调度的内部请求对象。

## 3.3 Chat request 渲染成 EngineInput

`OpenAIServingChat` 不会自己做 prompt 渲染，而是委托给：

- `vllm/entrypoints/serve/render/serving.py`

对应对象：

- `OpenAIServingRender`

核心调用链大致是：

- `OpenAIServingChat._create_chat_completion`
- `OpenAIServingChat.render_chat_request`
- `OpenAIServingRender.render_chat`
- `renderer.render_chat_async(...)`

这个阶段会完成：

- chat template 应用
- messages 转换为 conversation
- tokenization
- multimodal 输入预处理
- 最终生成 `EngineInput`

这一步非常关键，因为从这里开始，请求从“OpenAI API 请求”变成了“引擎内部输入”。

## 3.4 进入 AsyncLLM

当 `EngineInput` 准备好后，`OpenAIServingChat` 会调用：

- `engine_client.generate(...)`

在单机/多进程默认路径下，这个 `engine_client` 实际就是：

- `vllm/v1/engine/async_llm.py`
- `AsyncLLM`

`AsyncLLM.generate(...)` 是 API server 与 engine core 之间最关键的桥梁。

它主要做四件事：

- 接收 `EngineInput`
- 生成内部请求对象
- 把请求发给后台 engine core
- 在前台异步接收输出并流式返回

## 3.5 InputProcessor 把输入转成 EngineCoreRequest

`AsyncLLM.generate(...)` 内部会调用：

- `InputProcessor.process_inputs(...)`

位置：

- `vllm/v1/engine/input_processor.py`

这里会把 `EngineInput` 进一步转成：

- `EngineCoreRequest`

它做的事情包括：

- 校验 sampling/pooling 参数
- 校验 LoRA 请求
- 校验 data parallel rank
- 校验当前平台对输入的约束
- 拆分 encoder/decoder 输入
- 组装 multimodal 特征
- 填充内部 request 结构

这一步之后，请求就已经进入 scheduler/engine 能直接消费的格式了。

## 3.6 请求发送到 EngineCore 进程

`AsyncLLM` 会一边在前台注册 `OutputProcessor`，一边把 `EngineCoreRequest` 发给 engine core：

- `AsyncLLM._add_request(...)`
- `engine_core.add_request_async(...)`

对应底层 client 在：

- `vllm/v1/engine/core_client.py`

这个 client 会把请求通过 IPC/ZMQ 发送给后台 engine core 进程。

## 3.7 EngineCore 调度请求

后台调度核心在：

- `vllm/v1/engine/core.py`
- `EngineCore`

`EngineCore` 是整个 vLLM V1 engine 的核心循环，负责：

- 维护 scheduler
- 维护 KV cache 视图
- 调度 waiting/running requests
- 调用 executor 执行模型
- 根据输出更新 scheduler 状态

单步执行最关键的逻辑是：

- `scheduler.schedule(...)`
- `model_executor.execute_model(...)`
- `scheduler.update_from_output(...)`

也就是说，一个迭代的本质是：

1. scheduler 挑出本轮该执行哪些 token/request
2. executor 把这批工作发给 worker
3. engine 根据执行结果更新 request 状态和输出

## 3.8 Executor 把任务发给 Worker

默认多卡/多进程路径一般会走：

- `vllm/v1/executor/multiproc_executor.py`
- `MultiprocExecutor`

这里的：

- `execute_model(...)`

会通过广播/RPC 把 `SchedulerOutput` 发给对应 worker，并从指定 worker 收回 `ModelRunnerOutput`。

## 3.9 Ascend Worker 接管设备执行

当 platform 已经切到 Ascend 后，真正实例化的 worker 是：

- `vllm_ascend/worker/worker.py`
- `NPUWorker`

`NPUWorker` 初始化时会做几件 Ascend 特有的事情：

- 调用 `adapt_patch()` 打 Ascend worker 级 patch
- 注册 Ascend dummy fusion op
- 注册 Ascend custom ops
- 初始化 Ascend 配置
- 初始化 NPU 设备
- 创建 Ascend model runner

对应关键位置：

- `vllm_ascend/utils.py`
- `vllm_ascend/worker/worker.py`

## 3.10 NPUModelRunner 真正做前向和采样

`NPUWorker.init_device()` 之后，会创建真正的执行核心：

- `vllm_ascend/worker/model_runner_v1.py`
- `vllm_ascend/worker/v2/model_runner.py`

类名都是：

- `NPUModelRunner`

这层是 Ascend 执行逻辑最核心的位置，负责：

- 准备 Ascend 输入 buffer
- 管理 KV cache
- 调用 Ascend attention/backend
- 执行前向
- 执行采样
- 管理 ACL graph
- 处理 speculative decoding、PP、TP、通信等

在 worker 侧的主调用链大致是：

- `NPUWorker.execute_model(...)`
- `self.model_runner.execute_model(...)`

如果需要采样，则还会走：

- `NPUWorker.sample_tokens(...)`
- `self.model_runner.sample_tokens(...)`

## 3.11 Ascend custom ops 和 patch 在哪里生效

Ascend 和 GPU 的主要差异，不是体现在 API 层，而是体现在 worker/model runner/backend 层。

主要生效点包括：

- `vllm_ascend/utils.py`
  - `adapt_patch(...)`
  - `register_ascend_customop(...)`
- `vllm_ascend/platform.py`
  - config 修正与 worker 选择
- `vllm_ascend/worker/`
  - Ascend worker 和 model runner
- `vllm_ascend/ops/`
  - Ascend 算子实现
- `vllm_ascend/patch/`
  - 对上游 `vllm` 某些组件的 patch

例如 `register_ascend_customop(...)` 会把一批上游抽象算子替换成 Ascend 版本，包括：

- rotary embedding
- linear
- RMSNorm
- MLA
- MM encoder attention
- fused MoE
- 其他 Ascend 专用算子

## 3.12 输出如何回到客户端

NPU worker 产出结果后，结果会沿着反方向返回：

1. worker 返回 `ModelRunnerOutput`
2. executor 收到结果并回传给 engine core
3. `EngineCore` 调用 `scheduler.update_from_output(...)`
4. `EngineCoreOutputs` 通过 `core_client` 发回 API server 进程
5. `AsyncLLM` 后台 `output_handler` 从 `engine_core.get_output_async()` 拉取输出
6. `OutputProcessor` 把内部输出整理成 `RequestOutput`
7. `OpenAIServingChat` 再把它包装成 SSE 流或最终 JSON

对应前台输出处理关键位置：

- `vllm/v1/engine/async_llm.py`
- `vllm/v1/engine/output_processor.py`
- `vllm/entrypoints/openai/chat_completion/serving.py`

## 4. 一条简化调用链

如果只看最关键的主干，可以把一次请求理解成下面这条链：

```text
vllm serve
  -> vllm/entrypoints/cli/serve.py
  -> vllm/entrypoints/openai/api_server.py
  -> FastAPI /v1/chat/completions
  -> OpenAIServingChat.create_chat_completion()
  -> OpenAIServingRender.render_chat()
  -> renderer.render_chat_async()
  -> AsyncLLM.generate()
  -> InputProcessor.process_inputs()
  -> EngineCore.add_request()
  -> Scheduler.schedule()
  -> Executor.execute_model()
  -> NPUWorker.execute_model()
  -> NPUModelRunner.execute_model()
  -> Ascend ops / ACL graph / KV cache / sampling
  -> EngineCore.update_from_output()
  -> AsyncLLM output_handler
  -> SSE / JSON response
```

## 5. 阅读代码时的推荐顺序

如果想顺着代码快速读懂整个链路，建议按下面顺序看：

1. `vllm/entrypoints/cli/serve.py`
2. `vllm/entrypoints/openai/api_server.py`
3. `vllm/entrypoints/openai/chat_completion/api_router.py`
4. `vllm/entrypoints/openai/chat_completion/serving.py`
5. `vllm/entrypoints/serve/render/serving.py`
6. `vllm/v1/engine/async_llm.py`
7. `vllm/v1/engine/input_processor.py`
8. `vllm/v1/engine/core.py`
9. `vllm/v1/executor/multiproc_executor.py`
10. `vllm_ascend/platform.py`
11. `vllm_ascend/worker/worker.py`
12. `vllm_ascend/worker/model_runner_v1.py`
13. `vllm_ascend/worker/v2/model_runner.py`
14. `vllm_ascend/utils.py`
15. `vllm_ascend/ops/`

## 6. 记忆方式

可以把整个系统想成四层：

- API 层：接 HTTP，请求格式是 OpenAI 协议
- Render/Input 层：把 chat/completion 请求转成 `EngineInput`
- Engine/Scheduler 层：调度 request、组织 batch、管理 KV cache
- Worker/Backend 层：真正跑 Ascend 前向、采样和图执行

其中：

- 前三层主要由 `vllm` 提供
- 最后一层以及与平台强相关的部分主要由 `vllm-ascend` 提供
