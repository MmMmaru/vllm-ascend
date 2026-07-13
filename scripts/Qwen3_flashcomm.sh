# server1

export VLLM_ASCEND_ENABLE_FLASHCOMM1=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export ASCEND_RT_VISIBLE_DEVICES=1,2,3,5
export PYTHONPATH=/vllm-ascend/vllm-ascend:/vllm-ascend/vllm
export VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=86400

/usr/local/python3.12.13/bin/python3 \
  -m vllm.entrypoints.cli.main \
  serve /mnt/share/weights/Qwen3-30B-A3B \
  --served-model-name qwen \
  --host 0.0.0.0 \
  --port 8010 \
  --tensor-parallel-size 4 \
  --enable-expert-parallel \
  --gpu-memory-utilization 0.9 \
  --trust-remote-code \
  --no-enable-prefix-caching \
  --no-async-scheduling \
  --enforce-eager