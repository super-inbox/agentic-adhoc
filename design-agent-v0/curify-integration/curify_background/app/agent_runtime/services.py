from __future__ import annotations

import asyncio
import io
import ipaddress
import json
import logging
import math
import socket
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image
from google import genai
from google.genai import types

from app.agent_runtime.schemas import (
    AgentArtifact,
    AgentArtifactKind,
    TryOnReview,
    VerificationVerdict,
    VoteAnalysis,
    VoteDraft,
    VoteSegment,
)
from app.config import settings
from app.utils import gcs_storage

logger = logging.getLogger(__name__)

VARIANT_IDS = ("A", "B", "C", "D")
GEMINI_TIMEOUT_MS = 60_000
MAX_IMAGE_PIXELS = 40_000_000

_genai_client: Optional[genai.Client] = None


def _get_genai_client() -> genai.Client:
    """Keep the runtime independent from ``app.services`` import side effects."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is required for Design Agent model calls.")
    try:
        _genai_client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
        )
    except Exception:
        logger.warning(
            "google-genai rejected the configured request timeout; using its default client",
            exc_info=True,
        )
        _genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _genai_client


def _extract_first_image_from_response(response: Any) -> Image.Image:
    parts = getattr(response, "parts", None)
    if parts is None:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            parts = getattr(getattr(candidates[0], "content", None), "parts", None)
    for part in parts or []:
        data = getattr(getattr(part, "inline_data", None), "data", None)
        if data:
            return Image.open(io.BytesIO(data)).convert("RGB")
    raise RuntimeError("Gemini returned no generated image.")


class ImageLoaderProtocol(Protocol):
    async def load(self, source: str) -> bytes: ...


class ArtifactStoreProtocol(Protocol):
    async def put(
        self,
        run_id: str,
        filename: str,
        data: bytes,
        media_type: str,
        kind: AgentArtifactKind,
        label: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentArtifact: ...

    async def sign(self, object_path: str, expiry_minutes: int = 60) -> str: ...


class DesignModelGatewayProtocol(Protocol):
    model_name: str
    generation_model_name: str

    async def analyze_vote(
        self,
        prompt: str,
        candidate_images: List[bytes],
        repair_instruction: Optional[str] = None,
    ) -> VoteDraft: ...

    async def review_vote(
        self,
        prompt: str,
        candidate_images: List[bytes],
        analysis: VoteAnalysis,
    ) -> VerificationVerdict: ...

    async def generate_tryon(
        self,
        selfie: bytes,
        product: Optional[bytes],
        prompt: str,
        direction: str,
        repair_instruction: Optional[str] = None,
    ) -> bytes: ...

    async def review_tryon(
        self,
        selfie: bytes,
        product: Optional[bytes],
        prompt: str,
        posters: List[bytes],
    ) -> TryOnReview: ...


class SafeImageLoader:
    """Load a private GCS object path or a public HTTPS image with SSRF guards."""

    def __init__(self, max_bytes: int = 12 * 1024 * 1024):
        self.max_bytes = max_bytes

    @staticmethod
    def _validate_public_https(url: str) -> None:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Only private GCS object paths or public HTTPS image URLs are allowed.")
        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)
            }
        except socket.gaierror as exc:
            raise ValueError("Image host could not be resolved.") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ValueError("Private, loopback, and link-local image hosts are not allowed.")

    def _load_sync(self, source: str) -> bytes:
        if "://" not in source:
            raw = gcs_storage.download_bytes_from_gcs(source)
        else:
            current = source
            raw = b""
            with httpx.Client(timeout=20.0, follow_redirects=False) as client:
                for _ in range(4):
                    self._validate_public_https(current)
                    with client.stream(
                        "GET",
                        current,
                        headers={"User-Agent": "CurifyDesignAgent/1.0"},
                    ) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get("location")
                            if not location:
                                raise ValueError("Image redirect has no destination.")
                            current = urljoin(current, location)
                            continue
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").lower()
                        if content_type and not content_type.startswith("image/"):
                            raise ValueError("URL did not return an image.")
                        content_length = response.headers.get("content-length")
                        if content_length and int(content_length) > self.max_bytes:
                            raise ValueError("Image URL exceeds the maximum allowed size.")
                        chunks = bytearray()
                        for chunk in response.iter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > self.max_bytes:
                                raise ValueError("Image URL exceeds the maximum allowed size.")
                        raw = bytes(chunks)
                        break
                else:
                    raise ValueError("Too many image redirects.")
        if not raw or len(raw) > self.max_bytes:
            raise ValueError(f"Image must be between 1 byte and {self.max_bytes} bytes.")
        try:
            im = Image.open(io.BytesIO(raw))
            if im.width * im.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions are too large.")
            im.verify()
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=92, optimize=True)
            return out.getvalue()
        except Exception as exc:
            raise ValueError("Uploaded source is not a readable image.") from exc

    async def load(self, source: str) -> bytes:
        return await asyncio.to_thread(self._load_sync, source)


class GCSArtifactStore:
    async def put(
        self,
        run_id: str,
        filename: str,
        data: bytes,
        media_type: str,
        kind: AgentArtifactKind,
        label: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentArtifact:
        safe_name = "".join(ch for ch in filename if ch.isalnum() or ch in "-_.")
        if not safe_name:
            raise ValueError("Invalid artifact filename.")
        object_path = f"design_agent/{run_id}/{safe_name}"
        await asyncio.to_thread(
            gcs_storage.upload_bytes_to_gcs,
            data,
            object_path,
            media_type,
            "private, no-store",
        )
        return AgentArtifact(
            artifact_id=uuid.uuid4().hex[:12],
            kind=kind,
            label=label,
            object_path=object_path,
            media_type=media_type,
            metadata=metadata or {},
        )

    async def sign(self, object_path: str, expiry_minutes: int = 60) -> str:
        return await asyncio.to_thread(
            gcs_storage.generate_signed_url,
            object_path,
            expiry_minutes,
        )


def _extract_text(response: Any) -> str:
    texts: List[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text:
                texts.append(str(text))
    return "\n".join(texts).strip()


def _parse_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model did not return a JSON object.")
    return json.loads(cleaned[start : end + 1])


def _jpeg_part(data: bytes) -> types.Part:
    return types.Part(inline_data=types.Blob(data=data, mime_type="image/jpeg"))


class GeminiDesignGateway:
    def __init__(self):
        configured = getattr(settings, "DESIGN_AGENT_ANALYSIS_MODEL", "")
        self.model_name = configured or settings.GEMINI_IMAGE_MODEL
        self.generation_model_name = settings.GEMINI_IMAGE_MODEL

    def _text_call_sync(self, parts: List[Any]) -> Dict[str, Any]:
        response = _get_genai_client().models.generate_content(
            model=self.model_name,
            contents=parts,
            config=types.GenerateContentConfig(response_modalities=["TEXT"]),
        )
        return _parse_json_object(_extract_text(response))

    async def analyze_vote(
        self,
        prompt: str,
        candidate_images: List[bytes],
        repair_instruction: Optional[str] = None,
    ) -> VoteDraft:
        instructions = f"""
You are the visual-understanding stage of a design decision agent.
The user asks: {prompt}

Four candidate designs are attached and explicitly labeled A-D. Inspect only
visible evidence: hierarchy, typography, whitespace, color, brand placement,
product/category cues, and commercial context. Define a single evaluation axis
that answers the request. Create 3-6 plausible category-specific consumer
segments whose shares sum approximately to 1. For every segment, assign a
preference distribution across A-D and explain it from visible design cues.

This is a simulation, not real market research. Do not invent respondents,
sample sizes, surveys, quotations, sales, or demographic facts. If the images
do not contain four coherent candidate designs, set valid_variants=false and
explain why in issues.

Return only JSON with this shape:
{{
  "valid_variants": true,
  "issues": [],
  "product": "...",
  "category": "...",
  "axis": "...",
  "variants": [
    {{"id":"A","design_language":"...","strengths":["..."],"weaknesses":["..."]}}
  ],
  "segments": [
    {{"name":"...","share":0.25,"votes":{{"A":25,"B":25,"C":25,"D":25}},"rationale":"..."}}
  ],
  "recommendation": "...",
  "confidence": 0.0
}}
"""
        if repair_instruction:
            instructions += f"\nA verifier rejected the prior result. Repair it using: {repair_instruction}\n"
        parts: List[Any] = [instructions]
        for label, image in zip(VARIANT_IDS, candidate_images):
            parts.extend([f"VARIANT {label}", _jpeg_part(image)])
        payload = await asyncio.to_thread(self._text_call_sync, parts)
        return VoteDraft.model_validate(payload)

    async def review_vote(
        self,
        prompt: str,
        candidate_images: List[bytes],
        analysis: VoteAnalysis,
    ) -> VerificationVerdict:
        instructions = f"""
Act as an independent visual verifier. Compare the attached A-D designs against
this proposed simulated-vote analysis and the user's request: {prompt}

Analysis JSON:
{analysis.model_dump_json()}

Judge whether claims are grounded in visible design evidence, segments fit the
product category, the winner is defensible, and the recommendation is useful.
Do not demand real survey evidence: this is explicitly an AI simulation.
Return only JSON:
{{"passed":true,"scores":{{"grounding":0.0,"segment_plausibility":0.0,"ranking_sanity":0.0,"actionability":0.0}},"hard_failures":[],"repairable_failures":[],"repair_instruction":null,"retry_scope":[]}}
Scores use 0-5. Set passed=false if any score is below 3.0. Use hard_failures
only when there are not four usable designs; other issues are repairable.
"""
        parts: List[Any] = [instructions]
        for label, image in zip(VARIANT_IDS, candidate_images):
            parts.extend([f"VARIANT {label}", _jpeg_part(image)])
        payload = await asyncio.to_thread(self._text_call_sync, parts)
        return VerificationVerdict.model_validate(payload)

    def _generate_tryon_sync(
        self,
        selfie: bytes,
        product: Optional[bytes],
        prompt: str,
        direction: str,
        repair_instruction: Optional[str],
    ) -> bytes:
        product_rule = (
            "IMAGE 2 is the exact merchandise reference. Preserve its silhouette, color, material, pattern, logos, and construction."
            if product
            else "No merchandise reference is supplied; create a plausible outfit concept from the text and do not claim SKU accuracy."
        )
        instruction = f"""
Create one polished 4:5 ecommerce campaign image.
IMAGE 1 is the person: preserve the exact recognizable face, skin tone, body
proportions, and identity. Change clothing and scene only. {product_rule}
User brief: {prompt}
Creative direction: {direction}
Use believable anatomy, hands, garment occlusion, and commercial lighting.
Leave clean negative space at the top and bottom for deterministic typography.
Do not render text, captions, watermarks, price tags, or logos not present in
the product reference.
"""
        if repair_instruction:
            instruction += f"\nRepair the rejected prior attempt: {repair_instruction}\n"
        parts: List[Any] = [_jpeg_part(selfie)]
        if product:
            parts.append(_jpeg_part(product))
        parts.append(instruction)
        response = _get_genai_client().models.generate_content(
            model=settings.GEMINI_IMAGE_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
        image = _extract_first_image_from_response(response).convert("RGB")
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue()

    async def generate_tryon(
        self,
        selfie: bytes,
        product: Optional[bytes],
        prompt: str,
        direction: str,
        repair_instruction: Optional[str] = None,
    ) -> bytes:
        return await asyncio.to_thread(
            self._generate_tryon_sync,
            selfie,
            product,
            prompt,
            direction,
            repair_instruction,
        )

    async def review_tryon(
        self,
        selfie: bytes,
        product: Optional[bytes],
        prompt: str,
        posters: List[bytes],
    ) -> TryOnReview:
        instructions = f"""
You are the visual QA stage for ecommerce try-on posters. IMAGE 1 is the source
selfie. {"IMAGE 2 is the exact product reference." if product else "There is no exact product reference; product_fidelity must be null."}
The remaining images are generated posters numbered from 0. User brief: {prompt}

For each poster score 0-5: identity, product_fidelity (null without product),
anatomy, instruction_following, and layout. List concrete visible failures.
Be strict about face identity, extra/malformed limbs, garment geometry, and
unreadable/AI-rendered text. Return only JSON:
{{"posters":[{{"index":0,"identity":0.0,"product_fidelity":null,"anatomy":0.0,"instruction_following":0.0,"layout":0.0,"failures":[]}}]}}
"""
        parts: List[Any] = [instructions, "SOURCE SELFIE", _jpeg_part(selfie)]
        if product:
            parts.extend(["PRODUCT REFERENCE", _jpeg_part(product)])
        for index, poster in enumerate(posters):
            parts.extend([f"POSTER {index}", _jpeg_part(poster)])
        payload = await asyncio.to_thread(self._text_call_sync, parts)
        return TryOnReview.model_validate(payload)


def normalize_percentages(values: Dict[str, float]) -> Dict[str, int]:
    nonnegative = {key: max(0.0, float(values.get(key, 0.0))) for key in VARIANT_IDS}
    total = sum(nonnegative.values())
    if total <= 0:
        nonnegative = {key: 1.0 for key in VARIANT_IDS}
        total = 4.0
    scaled = {key: nonnegative[key] * 100.0 / total for key in VARIANT_IDS}
    floors = {key: int(math.floor(value)) for key, value in scaled.items()}
    remaining = 100 - sum(floors.values())
    order = sorted(VARIANT_IDS, key=lambda key: scaled[key] - floors[key], reverse=True)
    for key in order[:remaining]:
        floors[key] += 1
    return floors


def aggregate_vote_draft(draft: VoteDraft) -> VoteAnalysis:
    variant_by_id = {
        variant.id.upper(): variant.model_copy(update={"id": variant.id.upper()})
        for variant in draft.variants
    }
    if set(variant_by_id) != set(VARIANT_IDS):
        raise ValueError("Vote analysis must describe exactly variants A-D.")
    if not draft.segments:
        raise ValueError("Vote analysis must contain at least one audience segment.")
    shares = [max(0.0, segment.share) for segment in draft.segments]
    share_total = sum(shares)
    if share_total <= 0:
        shares = [1.0 / len(draft.segments)] * len(draft.segments)
    else:
        shares = [share / share_total for share in shares]
    segments: List[VoteSegment] = []
    overall_float = {key: 0.0 for key in VARIANT_IDS}
    for share, segment in zip(shares, draft.segments):
        votes = normalize_percentages(segment.votes)
        for key in VARIANT_IDS:
            overall_float[key] += share * votes[key]
        segments.append(
            VoteSegment(
                name=segment.name,
                share=round(share, 4),
                votes=votes,
                rationale=segment.rationale,
            )
        )
    overall = normalize_percentages(overall_float)
    winner = max(VARIANT_IDS, key=lambda key: overall[key])
    return VoteAnalysis(
        product=draft.product,
        category=draft.category,
        axis=draft.axis,
        variants=[variant_by_id[key] for key in VARIANT_IDS],
        segments=segments,
        overall=overall,
        winner=winner,
        recommendation=draft.recommendation,
        confidence=max(0.0, min(1.0, draft.confidence)),
    )


@dataclass
class DesignAgentServices:
    gateway: DesignModelGatewayProtocol
    image_loader: ImageLoaderProtocol
    artifact_store: ArtifactStoreProtocol


def default_services() -> DesignAgentServices:
    return DesignAgentServices(
        gateway=GeminiDesignGateway(),
        image_loader=SafeImageLoader(),
        artifact_store=GCSArtifactStore(),
    )
