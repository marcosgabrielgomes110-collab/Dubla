"""Dubla video dubbing pipeline.

Packages:
    Dubla_Config        configuration loaded from configs.json
    Dubla_Input         video inputs (YouTube download and local files)
    Dubla_Transcribe    speech-to-text (Vosk and faster-whisper)
    Dubla_Translate     translation (deep-translator, Argos, OpenAI-compatible LLM)
    Dubla_Voicegen      voice generation (Piper, Pocket, Qwen3-TTS, ElevenLabs, eSpeak)
    Dubla_MovieManager  full pipeline, mux and publication (main entry point)

Utilities:
    etc                 colored logging persisted to Data/logs
"""
