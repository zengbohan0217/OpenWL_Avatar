# Game CG Generation Pipeline

## Current Pipeline

`GameCGOperator` generates a short game cinematic with this real chain:

1. `get_storyboard()` loads or generates a storyboard, then normalizes it to the v2 IR.
2. `compile_storyboard_prompts()` turns structured fields into Qwen image prompts and an LTX motion prompt.
3. `validate_storyboard_timing()` checks monotonic `time_sec`, frame spacing, duration tail, refs, and strengths.
4. `gen_storyboard_images()` uses Qwen-Image-Edit to generate one keyframe per shot.
5. Qwen is unloaded to free VRAM.
6. `gen_cg_video()` uses LTX-2.3 keyframe interpolation.
7. If multiple `segment_id` values are present, each segment is generated as a clip under `output/.../clips/` and concatenated with ffmpeg.

`transition` is currently metadata consumed by the prompt compiler. Independent hard-cut I2V generation is not implemented.

## Storyboard v2 Minimal Schema

Top-level fields:

- `video_prompt`
- `character_prompt`
- `style_prompt`
- `duration_sec`
- `shots`

Shot fields:

- `shot_id`
- `beat_role`
- `segment_id`
- `transition`
- `time_sec`
- `ref`
- `strength`
- `camera`
- `subject`
- `vfx`
- `image_prompt`
- `motion_prompt`

Legacy storyboards are still accepted. Missing `ref` defaults to `original` for the first shot and `previous` for later shots. Missing `segment_id` defaults to `0`; missing `transition` defaults to `transition`.

## Outputs

For an end-to-end run, the operator writes:

```text
output/
  storyboard/
    shot_00.png
    ...
  clips/
    segment_00_id_00.mp4
    segment_01_id_01.mp4
  contact_sheet.png
  storyboard_resolved.json
  run_manifest.json
  luffy_cg.mp4
```

`run_manifest.json` records the input storyboard path, normalized storyboard, compiled prompts, refs, output files, seed, fps, size, model paths, offload, quantization, git summary, and runtime.

## Real Inference

```bash
CUDA_VISIBLE_DEVICES=4 PYTHONPATH=. \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
python test/test_game_cg_gen.py \
  --storyboard assets/storyboard.json \
  --ref assets/luffy.jpg \
  --output-dir output/game_cg \
  --seed 42 --fps 24 --height 512 --width 768
```

Dry-run and validation modes do not load Qwen or LTX and are only for checking storyboard structure:

```bash
PYTHONPATH=. python test/test_game_cg_gen.py --validate-only
PYTHONPATH=. python test/test_game_cg_gen.py --dry-run --output-dir output/validate
```

## Model Configuration

Defaults in `test/test_game_cg_gen.py` can be overridden through CLI flags:

- `--gen-image-model`
- `--ltx-root`
- `--gemma-root`
- `--offload`
- `--quantization`

The LTX wrapper expects `ltx_root` to be a local directory containing:

- `ltx-2.3-22b-dev.safetensors`
- `ltx-2.3-22b-distilled-lora-384-1.1.safetensors`
- `ltx-2.3-spatial-upscaler-x2-1.1.safetensors`
