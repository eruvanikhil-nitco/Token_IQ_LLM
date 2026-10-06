"""Mistral OCR handler for Unified Guardrails."""

from typing import Final

from token_iq.gateway.llms.mistral.ocr.guardrail_translation.handler import OCRHandler
from token_iq.gateway.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.ocr: OCRHandler,
    CallTypes.aocr: OCRHandler,
}

__all__ = ["OCRHandler", "guardrail_translation_mappings"]
