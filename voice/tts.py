"""
Text-to-Speech module with:
  - Queue-based non-blocking speech (never blocks the calling thread)
  - Interrupt / flush current speech
  - Speaking state callbacks (for UI animations)
"""

import pyttsx3
import threading
import queue
from typing import Callable, Optional


class TextToSpeech:
    """
    Non-blocking TTS engine backed by a worker thread and a speech queue.

    Usage:
        tts = TextToSpeech()
        tts.speak("Hello world")          # queues immediately
        tts.speak("Another line")         # queues behind the first
        tts.stop()                        # interrupt current speech & clear queue
    """

    def __init__(
        self,
        rate: int = 165,
        on_speaking_change: Optional[Callable[[bool], None]] = None,
    ):
        """
        Parameters
        ----------
        rate : int
            Words per minute (default 165).
        on_speaking_change : callable(bool), optional
            Called with True when speech starts, False when it finishes.
        """
        self._on_speaking_change = on_speaking_change
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._is_speaking = threading.Event()
        self._stop_event = threading.Event()

        self._worker = threading.Thread(
            target=self._run, daemon=True, name="TTS-Worker"
        )
        self._worker.start()

        # The pyttsx3 engine is created inside the worker thread so that
        # its internal COM objects (on Windows) live on the right thread.
        self._rate = rate
        self._engine_ready = threading.Event()

    # ── public API ────────────────────────────────────────────────────────────

    def speak(self, text: str):
        """Queue text to be spoken.  Returns immediately."""
        if text and text.strip():
            self._queue.put(text.strip())

    def stop(self):
        """Interrupt the current utterance and discard any queued text."""
        # Drain the queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        # Signal engine stop via sentinel-style flag
        self._stop_event.set()

    def wait_until_done(self, timeout: float = 30):
        """Block until the TTS queue is empty."""
        self._queue.join()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking.is_set()

    def set_rate(self, rate: int):
        """Update the speaking rate (takes effect on next utterance)."""
        self._rate = rate

    # ── internal worker ───────────────────────────────────────────────────────

    def _run(self):
        """Worker thread: owns the pyttsx3 engine for its entire lifetime."""
        engine = pyttsx3.init()
        engine.setProperty("rate", self._rate)

        # Pick a pleasant voice
        voices = engine.getProperty("voices")
        preferred_keywords = ["Zira", "Female", "Hazel", "Susan"]
        for kw in preferred_keywords:
            for v in voices:
                if kw.lower() in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            else:
                continue
            break

        self._engine_ready.set()

        while True:
            try:
                text = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if text is None:          # shutdown sentinel
                break

            self._stop_event.clear()
            self._is_speaking.set()
            if self._on_speaking_change:
                try:
                    self._on_speaking_change(True)
                except Exception:
                    pass

            # Update rate in case it changed
            engine.setProperty("rate", self._rate)

            engine.say(text)

            # Pump the engine event loop in small slices so we can honour stop()
            engine.startLoop(False)
            try:
                while engine.isBusy() and not self._stop_event.is_set():
                    engine.iterate()
            finally:
                engine.endLoop()

            if self._stop_event.is_set():
                engine.stop()

            self._is_speaking.clear()
            if self._on_speaking_change:
                try:
                    self._on_speaking_change(False)
                except Exception:
                    pass

            self._queue.task_done()

    def shutdown(self):
        """Gracefully shut down the worker thread."""
        self.stop()
        self._queue.put(None)   # shutdown sentinel
        self._worker.join(timeout=3)
