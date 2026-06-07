"""Split report rendering helper."""

from __future__ import annotations

import base64

from google.genai import types

from analysis_types import AnalysisContext
from config import (
    API_KEYS,
    ENABLE_REPORT_COVER,
    REPORT_COVER_ASPECT_RATIO,
    REPORT_COVER_FALLBACK_MODELS,
    REPORT_COVER_IMAGE_SIZE,
    REPORT_COVER_MODEL,
)
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    estimate_text_tokens,
    generate_images_async,
    is_missing_model_error,
    is_quota_or_rate_error,
    retry_delay_seconds,
)
from runtime_events import emit_log

def build_report_cover_prompt(context: AnalysisContext) -> str:
    """Build a professional Imagen prompt with Chinese company identity first."""
    data = context.get("data", {}) or {}
    identity = data.get("company_identity", {}) if isinstance(data.get("company_identity"), dict) else {}
    company_name = (
        identity.get("official_name")
        or data.get("company_name")
        or context.get("company_name")
        or context.get("ticker")
        or "目標公司"
    )
    industry = data.get("industry") or data.get("sector") or "global equities"
    ticker = data.get("ticker") or context.get("ticker") or ""
    return (
        "A professional Wall Street equity research report cover for "
        f"{company_name} {ticker}, high-tech visual background representing {industry}, "
        "institutional investment bank style, clean premium editorial layout, "
        "cinematic lighting, detailed market data texture, 8k, no logos, no watermark, "
        "no readable text inside the image."
    )


def _build_cover_generation_config():
    kwargs = {
        "number_of_images": 1,
        "aspect_ratio": REPORT_COVER_ASPECT_RATIO,
        "output_mime_type": "image/jpeg",
        "image_size": REPORT_COVER_IMAGE_SIZE,
    }
    try:
        return types.GenerateImagesConfig(**kwargs)
    except TypeError:
        kwargs.pop("image_size", None)
        kwargs.pop("enhance_prompt", None)
        return types.GenerateImagesConfig(**kwargs)


def _extract_image_source(response) -> str:
    generated_images = getattr(response, "generated_images", None) or []
    for generated in generated_images:
        image = getattr(generated, "image", None)
        if not image:
            continue
        gcs_uri = getattr(image, "gcs_uri", None)
        if gcs_uri:
            return str(gcs_uri)
        image_bytes = getattr(image, "image_bytes", None)
        if image_bytes:
            mime_type = getattr(image, "mime_type", None) or "image/jpeg"
            encoded = base64.b64encode(bytes(image_bytes)).decode("ascii")
            return f"data:{mime_type};base64,{encoded}"
    return ""


async def prepare_report_cover_async(context: AnalysisContext, rotator: KeyRotator | None = None) -> dict:
    """Generate a report cover when Imagen quota is available; otherwise skip."""
    existing = context.get("report_cover", {}) or {}
    if existing.get("image"):
        return existing

    if not ENABLE_REPORT_COVER or not API_KEYS:
        return {}

    prompt = build_report_cover_prompt(context)
    try:
        local_rotator = rotator if isinstance(rotator, KeyRotator) else KeyRotator(API_KEYS)
    except Exception:
        return {}

    model_sequence = list(dict.fromkeys([REPORT_COVER_MODEL, *REPORT_COVER_FALLBACK_MODELS]))
    for model_id in model_sequence:
        if not model_id:
            continue
        api_key = None
        try:
            api_key = await local_rotator.async_get_key(model_id, estimate_text_tokens(prompt))
            response = await generate_images_async(api_key, model_id, prompt, _build_cover_generation_config())
            image_source = _extract_image_source(response)
            if image_source:
                cover = {"image": image_source, "prompt": prompt, "model": model_id}
                context["report_cover"] = cover
                emit_log(f"  🖼️  報告封面已生成：{model_id}")
                return cover
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                emit_log(f"  ⚠️  Imagen 模型 {model_id} 不可用，改試下一個封面模型。")
                continue
            if is_quota_or_rate_error(str(exc)):
                if api_key:
                    local_rotator.penalize(api_key, model_id, retry_delay_seconds(exc, default=60))
                emit_log(f"  ⏭️  Imagen 封面額度不足，略過封面：{describe_quota_or_rate_error(exc)[:120]}")
                break
            emit_log(f"  ⚠️  Imagen 封面生成失敗，略過封面：{str(exc)[:120]}")
            break
    return {}
