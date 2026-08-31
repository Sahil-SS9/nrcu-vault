"""MiniMax H3 workflow builder and local ComfyUI renderer."""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from pipeline.digest import sha256_file
from pipeline.studio import ShotSpec

H3_MODEL = "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"
H3_TEXT_ENCODER = "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
H3_VIDEO_VAE = "vae/minimax_h3_video_vae_fp16.safetensors"
H3_AUDIO_VAE = "vae/minimax_h3_audio_vae_fp32.safetensors"
H3_TURBO_LORA = "minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors"
H3_PREVIEW_LORA = "minimax_h3_fl2va_fasth3_preview_v0.2_lora_pruned_rank128_fp16.safetensors"
NEGATIVE = (
    "identity drift, costume change, duplicate person, extra limbs, malformed hands, "
    "frozen pose, slideshow, subtitles, captions, readable text, blur"
)


def build_workflow(
    shot: ShotSpec,
    index: int,
    *,
    image_name: str | None = None,
) -> dict:
    if shot.backend != "h3":
        raise ValueError(f"H3 workflow cannot render backend {shot.backend}")
    route = {
        "base": (20, None),
        "turbo": (6, H3_TURBO_LORA),
        "preview": (4, H3_PREVIEW_LORA),
    }.get(shot.quality)
    if route is None:
        raise ValueError(f"H3 quality route {shot.quality!r} is not implemented")
    steps, lora = route
    model_link: list[object] = ["1", 0]
    workflow: dict[str, dict] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": H3_MODEL, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": H3_TEXT_ENCODER, "type": "minimax"},
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": H3_VIDEO_VAE}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": H3_AUDIO_VAE}},
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": image_name or shot.keyframe.name},
        },
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["2", 0]}},
        "7": {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "prompt": shot.prompt,
                "width": 832,
                "height": 480,
                "length": 124,
                "first_frame": ["5", 0],
            },
        },
    }
    if lora:
        workflow["15"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0},
        }
        model_link = ["15", 0]
    workflow.update(
        {
            "8": {
                "class_type": "MiniMaxH3SigmaShift",
                "inputs": {"model": model_link, "shift_video": 12.0, "shift_audio": 3.0},
            },
            "9": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["8", 0],
                    "seed": 20260830 + index,
                    "steps": steps,
                    "cfg": 1.0,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "positive": ["7", 0],
                    "negative": ["6", 0],
                    "latent_image": ["7", 1],
                    "denoise": 1.0,
                },
            },
            "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
            "11": {
                "class_type": "VAEDecodeAudio",
                "inputs": {"samples": ["9", 0], "vae": ["4", 0]},
            },
            "12": {
                "class_type": "CreateVideo",
                "inputs": {"images": ["10", 0], "audio": ["11", 0], "fps": 24.0},
            },
            "13": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["12", 0],
                    "filename_prefix": f"private-studio/{shot.id}",
                    "format": "mp4",
                    "codec": "h264",
                },
            },
        }
    )
    return workflow


def _fetch_json(endpoint: str, path: str) -> dict:
    with urlopen(endpoint + path, timeout=30) as response:
        return json.load(response)


def render_shot(
    shot: ShotSpec,
    index: int,
    *,
    endpoint: str,
    comfy_input: Path,
    destination: Path,
    poll_seconds: float = 5.0,
    timeout_seconds: float = 3600.0,
) -> Path:
    parsed = urlparse(endpoint)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("H3 rendering is restricted to localhost")
    if destination.exists():
        raise FileExistsError(destination)
    if not shot.keyframe.is_file():
        raise FileNotFoundError(shot.keyframe)
    comfy_input = comfy_input.resolve(strict=True)
    source_digest = sha256_file(shot.keyframe)
    staged_name = f"private-{shot.id}-{source_digest[:12]}{shot.keyframe.suffix.lower()}"
    staged = comfy_input / staged_name
    if staged.exists():
        if sha256_file(staged) != source_digest:
            raise RuntimeError(f"staged keyframe digest mismatch: {staged}")
    else:
        shutil.copy2(shot.keyframe, staged)

    workflow = build_workflow(shot, index, image_name=staged_name)
    body = json.dumps({"prompt": workflow, "client_id": str(uuid.uuid4())}).encode()
    request = Request(
        endpoint.rstrip("/") + "/prompt",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            submission = json.load(response)
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI rejected the workflow: {details[:4000]}") from error
    if submission.get("node_errors"):
        raise RuntimeError(json.dumps(submission["node_errors"], indent=2))

    prompt_id = submission["prompt_id"]
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        time.sleep(poll_seconds)
        history = _fetch_json(endpoint.rstrip("/"), "/history/" + prompt_id)
        if prompt_id not in history:
            continue
        item = history[prompt_id]
        if item.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(item.get("status", {}), indent=2))
        output = item.get("outputs", {}).get("13", {})
        media = output.get("videos") or output.get("images") or []
        if not media:
            raise RuntimeError(f"shot {shot.id} completed without saved video")
        result = media[0]
        query = urlencode(
            {
                "filename": result["filename"],
                "subfolder": result.get("subfolder", ""),
                "type": result.get("type", "output"),
            }
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with (
                urlopen(endpoint.rstrip("/") + "/view?" + query, timeout=120) as response,
                temporary.open("xb") as handle,
            ):
                shutil.copyfileobj(response, handle)
            os.link(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
    raise TimeoutError(f"shot {shot.id} did not complete within {timeout_seconds}s")
