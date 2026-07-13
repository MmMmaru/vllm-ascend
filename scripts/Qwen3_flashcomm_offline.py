"""使用 FlashComm 对 Qwen3-30B-A3B 进行一次离线异步生成。"""

# docker exec -w "$source_root" xrs_090 \
#   /usr/local/python3.11.10/bin/python3 \
#   scripts/Qwen3_flashcomm_offline.py

import asyncio
import os
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path


def configure_environment() -> None:
    """在导入 vLLM 前配置 FlashComm 离线生成的运行环境。"""
    os.environ.update(
        {
            "VLLM_ASCEND_ENABLE_FLASHCOMM1": "1",
            "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
            "ASCEND_RT_VISIBLE_DEVICES": "1,2,3,5",
            "VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS": "86400",
        }
    )


configure_environment()
sys.path[0] = os.getcwd()


def configure_source_build_info() -> None:
    """为源码包补充已安装包生成的构建元数据模块。"""
    import vllm_ascend

    try:
        installed_package_path = Path(
            distribution("vllm-ascend").locate_file("vllm_ascend")
        )
    except PackageNotFoundError as error:
        raise RuntimeError("未找到已安装的 vllm-ascend 构建元数据") from error

    build_info_path = installed_package_path / "_build_info.py"
    if not build_info_path.is_file():
        raise RuntimeError(f"缺少 vllm-ascend 构建元数据: {build_info_path}")
    if str(installed_package_path) not in vllm_ascend.__path__:
        vllm_ascend.__path__.append(str(installed_package_path))


configure_source_build_info()

from vllm import SamplingParams
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.v1.engine.async_llm import AsyncLLM

MODEL_PATH = "/mnt/share/weights/Qwen3-30B-A3B"
PROMPT = "用一句话回答：FlashComm 离线生成已启动。"
REQUEST_ID = "qwen3-flashcomm-offline"
MAX_TOKENS = 32


async def generate_once(
    engine: AsyncLLM,
    prompt: str,
    request_id: str,
) -> str:
    """使用异步引擎生成一条请求，并返回完整的首个候选文本。"""
    sampling_params = SamplingParams(
        temperature=0.0,
        max_tokens=MAX_TOKENS,
    )
    async for output in engine.generate(
        request_id=request_id,
        prompt=prompt,
        sampling_params=sampling_params,
    ):
        if output.finished:
            if not output.outputs:
                raise RuntimeError("生成完成但未返回候选结果")
            return output.outputs[0].text
    raise RuntimeError("生成请求未返回完成结果")


async def main() -> None:
    """初始化四卡 FlashComm 异步引擎并打印一次离线生成结果。"""
    engine_args = AsyncEngineArgs(
        model=MODEL_PATH,
        tensor_parallel_size=4,
        enable_expert_parallel=True,
        gpu_memory_utilization=0.9,
        trust_remote_code=True,
        enable_prefix_caching=False,
        async_scheduling=False,
        enforce_eager=True,
    )
    engine = AsyncLLM.from_engine_args(engine_args)
    try:
        generated_text = await generate_once(engine, PROMPT, REQUEST_ID)
        print(f"Prompt: {PROMPT}")
        print(f"Generated: {generated_text}")
    finally:
        engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
