"""Transcript file I/O and translation services."""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import List

from deep_translator import GoogleTranslator

from config import TRANSCRIPTS_DIR
from schemas import TranscriptInfo
from store import append_final_utterance, get_or_create_meeting


def load_transcript_from_file(bot_id: str) -> bool:
    """Load transcript from file into meeting state if not already loaded.
    
    Returns True if transcript was loaded (or already exists), False if file not found.
    """
    st = get_or_create_meeting(bot_id)
    
    # Already has transcript data
    if st.transcript_history:
        return True
    
    # Try to load from file
    transcript_file = os.path.join(TRANSCRIPTS_DIR, f"transcript_{bot_id}.jsonl")
    if not os.path.exists(transcript_file):
        return False
    
    try:
        with open(transcript_file, "r", encoding="utf-8") as f:
            first_ts = None
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                ts = obj.get("ts", 0.0)
                speaker = obj.get("speaker", "unknown")
                text = obj.get("text", "")
                if text:
                    append_final_utterance(bot_id, speaker=speaker, text=text, ts=ts)
                    if first_ts is None:
                        first_ts = ts
            
            # Set recording_started_at from first utterance
            if first_ts is not None:
                st.recording_started_at = first_ts
            
            # Mark as done since this is historical
            st.status = "done"
        return True
    except Exception as e:
        print(f"[load_transcript] Error loading {transcript_file}: {repr(e)}")
        return False


def save_transcript_line(bot_id: str, speaker: str, text: str, participant: dict, event: str) -> None:
    """Save a transcript line to the per-meeting file."""
    import time
    
    line = {
        "ts": time.time(),
        "bot_id": bot_id,
        "speaker": speaker,
        "participant": participant,
        "text": text,
        "raw_event": event,
    }
    transcript_file = os.path.join(TRANSCRIPTS_DIR, f"transcript_{bot_id}.jsonl")
    with open(transcript_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def list_transcript_files() -> List[TranscriptInfo]:
    """List available transcripts from the transcripts directory.
    
    Excludes translated versions (files with language suffix like _es.jsonl).
    Returns transcripts sorted by creation time (newest first).
    """
    transcripts = []
    
    # Pattern to match original transcripts only (not translated ones)
    # Format: transcript_{uuid}.jsonl (excludes transcript_{uuid}_{lang}.jsonl)
    pattern = re.compile(r"^transcript_([a-f0-9\-]+)\.jsonl$")
    
    if not os.path.exists(TRANSCRIPTS_DIR):
        return []
    
    for filename in os.listdir(TRANSCRIPTS_DIR):
        match = pattern.match(filename)
        if not match:
            continue
        
        bot_id = match.group(1)
        filepath = os.path.join(TRANSCRIPTS_DIR, filename)
        
        try:
            # Get file modification time as creation date
            mtime = os.path.getmtime(filepath)
            created_at = datetime.fromtimestamp(mtime).strftime("%B %d, %Y at %I:%M %p")
            
            # Count lines (utterances)
            with open(filepath, "r", encoding="utf-8") as f:
                utterance_count = sum(1 for line in f if line.strip())
            
            transcripts.append(TranscriptInfo(
                bot_id=bot_id,
                filename=filename,
                created_at=created_at,
                utterance_count=utterance_count,
            ))
        except Exception as e:
            print(f"[list_transcripts] Error processing {filename}: {repr(e)}")
            continue
    
    # Sort by modification time (newest first)
    transcripts.sort(key=lambda t: os.path.getmtime(
        os.path.join(TRANSCRIPTS_DIR, t.filename)
    ), reverse=True)
    
    return transcripts


async def translate_jsonl_file(
    input_file: str,
    target_lang: str,
    batch_size: int = 5,
) -> list[dict]:
    """Translate a JSONL transcript file using deep-translator."""

    objects = []
    texts = []
    text_positions = []

    # 1. Read JSONL safely
    with open(input_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue

            obj = json.loads(line)
            objects.append(obj)

            text = obj.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
                text_positions.append(len(objects) - 1)

    print(f"[translate] Found {len(texts)} texts to translate to {target_lang}")

    if not texts:
        return objects

    # 2. Map language codes to deep-translator format
    lang_map = {
        "zh-cn": "chinese (simplified)",
        "zh-tw": "chinese (traditional)",
    }
    normalized_lang = lang_map.get(target_lang.lower(), target_lang)

    # 3. Create translator instance for target language
    translator = GoogleTranslator(source='en', target=normalized_lang)

    # 4. Translate in batches (deep-translator is sync, so use run_in_executor)
    translated_texts = []
    loop = asyncio.get_event_loop()

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        print(f"[translate] Translating batch {i//batch_size + 1}: {len(batch)} items")

        try:
            # Run sync translate_batch in thread pool to not block event loop
            batch_results = await loop.run_in_executor(
                None,
                translator.translate_batch,
                batch
            )
            translated_texts.extend(batch_results)
            print(f"[translate] Batch success: {batch_results[:2]}...")
        except Exception as e:
            print(f"[translate] Batch failed: {repr(e)}, trying one by one")
            # fallback to single translation
            for text in batch:
                try:
                    result = await loop.run_in_executor(
                        None,
                        translator.translate,
                        text
                    )
                    translated_texts.append(result)
                    print(f"[translate] Single success: '{text[:30]}' -> '{result[:30]}'")
                except Exception as e2:
                    print(f"[translate] Single failed: {repr(e2)}, keeping original")
                    translated_texts.append(text)

    print(f"[translate] Completed: {len(translated_texts)} translations")

    # 5. Map translations back
    for pos, translated in zip(text_positions, translated_texts):
        objects[pos]["text"] = translated

    return objects


async def translate_file_with_cache(filename: str, target_lang: str) -> dict:
    """Translate a transcript file, with caching.
    
    Cached translations are stored as: transcript_{botId}_{lang}.jsonl
    Returns dict with translated_data and cached flag.
    """
    from fastapi import HTTPException
    
    # Build file paths
    original_file = os.path.join(TRANSCRIPTS_DIR, filename)
    
    # Extract bot_id from filename (e.g., "transcript_abc123.jsonl" -> "abc123")
    base_name = filename.replace("transcript_", "").replace(".jsonl", "")
    cache_file = os.path.join(TRANSCRIPTS_DIR, f"transcript_{base_name}_{target_lang}.jsonl")

    if not os.path.exists(original_file):
        raise HTTPException(status_code=404, detail="Transcript file not found")

    # Check if cached translation exists
    if os.path.exists(cache_file):
        print(f"[translate] Using cached translation: {cache_file}")
        try:
            cached_data = []
            with open(cache_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        cached_data.append(json.loads(line))
            return {"translated_data": cached_data, "cached": True}
        except Exception as e:
            print(f"[translate] Cache read failed, regenerating: {e}")

    try:
        # Run translation (now async)
        translated_data = await translate_jsonl_file(
            input_file=original_file,
            target_lang=target_lang,
        )

        # Save to cache file
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                for item in translated_data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"[translate] Cached translation to: {cache_file}")
        except Exception as e:
            print(f"[translate] Failed to cache translation: {e}")

        return {"translated_data": translated_data, "cached": False}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}",
        )
