# Sequence Parallelism

## Overview

Sequence Parallelism (SP) shards the token dimension across tensor-parallel
ranks around the communication boundaries of transformer layers. vLLM owns
the SP compilation pass and the `parallel_config` state that describes the
active model parallelism. vLLM-Ascend keeps the Ascend attention and MoE
implementations aligned with that state; it does not expose a separate
communication switch.

## How to use

Enable the upstream compilation pass together with tensor parallelism:

```bash
vllm serve Qwen/Qwen3-VL-2B-Instruct \
    --tensor-parallel-size 2 \
    --compilation-config '{"pass_config": {"enable_sp": true}}'
```

For workloads with a small token count, `sp_min_token_num` can be set in the
upstream `pass_config` to avoid applying SP below the measured threshold:

```bash
vllm serve Qwen/Qwen3-VL-2B-Instruct \
    --tensor-parallel-size 2 \
    --compilation-config '{"pass_config": {"enable_sp": true, "sp_min_token_num": 512}}'
```

SP requires `tensor_parallel_size > 1`. For MoE models using expert
parallelism, vLLM-Ascend derives the active SP state from
`vllm_config.parallel_config.use_sequence_parallel_moe`. Custom attention
splitting follows this same upstream state.

## Multimodal and attention behavior

The multimodal encoder remains outside the decoder SP path. For Qwen3-VL,
deepstack embeddings are chunked to the local tensor-parallel sequence shard
before they are added to the reduced-scattered hidden states.

MLA, DSA, sparse attention, rotary embedding, and GDN attention use the
current vLLM parallel configuration when deciding whether query/key/value or
hidden-state tensors need to be gathered. This preserves the existing custom
attention split behavior while removing the former private communication
branch.

## Configuration compatibility

The former FlashComm settings are removed. Supplying either

```text
FlashComm is deprecated
```

Use the upstream SP compilation configuration shown above instead.
