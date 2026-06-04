import logging
import os
import tempfile

from django.conf import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        model_name = settings.WHISPER_MODEL
        logger.info(f"Loading Whisper model: {model_name}")
        _model = WhisperModel(model_name, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _model


HALLUCINATION_PHRASES = {
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "subtitles by",
    "i don't know",
    "no, i don't",
    "you",
}

MIN_AUDIO_DURATION = 2.0  # seconds


def transcribe_file(file_path: str) -> str:
    try:
        model = _get_model()
        segments, info = model.transcribe(
            file_path,
            beam_size=5,
            vad_filter=True,           # suppress hallucinations on silence
            vad_parameters={"min_silence_duration_ms": 500},
            language=None,             # auto-detect
            condition_on_previous_text=False,  # prevents repetition loops
        )
        logger.info(f"Processing audio with duration {info.duration:.3f}s, language: {info.language} (p={info.language_probability:.2f})")

        if info.duration < MIN_AUDIO_DURATION:
            logger.warning(f"Audio too short ({info.duration:.1f}s), skipping transcription")
            return ""

        parts = []
        for segment in segments:
            text = segment.text.strip()
            # Skip low-confidence or hallucinated segments
            if not text:
                continue
            if any(phrase in text.lower() for phrase in HALLUCINATION_PHRASES):
                logger.warning(f"Skipping likely hallucinated segment: {text!r}")
                continue
            if segment.no_speech_prob > 0.8:
                continue
            parts.append(text)

        transcript = " ".join(parts)
        logger.info(f"Transcription complete: {len(transcript)} chars")
        return transcript
    except Exception as e:
        logger.error(f"Transcription failed for {file_path}: {e}")
        raise


def transcribe_attachment(attachment) -> str:
    with tempfile.NamedTemporaryFile(
        suffix=os.path.splitext(attachment.original_filename)[1],
        delete=False,
    ) as tmp:
        for chunk in attachment.file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        return transcribe_file(tmp_path)
    finally:
        os.unlink(tmp_path)
