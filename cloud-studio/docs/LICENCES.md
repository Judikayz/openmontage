# Model and tool licence inventory (review before use)

| Component | Official source | Code/weights note | Compute / limitation |
|---|---|---|---|
| Wan 2.2 | https://github.com/Wan-Video/Wan2.2 | Check repository and each checkpoint licence independently; do not assume weights share code terms. | Large GPU memory footprint; T4 15GB may require quantisation/offload and is not guaranteed. |
| LongCat-Video | https://github.com/meituan-longcat/LongCat-Video | Verify current code and weight terms before use. | High VRAM demand; T4 compatibility unverified. |
| IP-Adapter | https://github.com/tencent-ailab/IP-Adapter | Check model-specific weights and base-model licence. | GPU conditioning; depends on chosen diffusion stack. |
| MuseTalk | https://github.com/TMElyralab/MuseTalk | Check code, checkpoint and face model terms separately. | GPU recommended; exact T4 profile unverified. |
| LatentSync | https://github.com/bytedance/LatentSync | Review source and checkpoint terms; do not assume commercial rights. | GPU required for practical use; T4 unverified. |
| Real-ESRGAN | https://github.com/xinntao/Real-ESRGAN | Source commonly BSD-3-Clause; pretrained weights and dependencies need separate review. | GPU recommended; CPU possible but slower. |
| RIFE | https://github.com/hzwer/ECCV2022-RIFE | Review repository and model-weight terms. | GPU recommended; CPU slower. |
| FFmpeg | https://ffmpeg.org/ | LGPL/GPL build configuration dependent. | CPU media processing. |

This inventory is a due-diligence starting point, not legal advice or a representation that every listed model is already bundled or activated. Optional models are selected through runtime configuration; no weights are included.
