"""
Speech-to-Text module with:
  - One-shot recognition (listen once, return text)
  - Continuous background listening with a callback
  - Wake-word detection ("hey agent")
  - Robust PyAudio resource management
"""

import sys
import threading
import time

# ── distutils shim for Python 3.12+ ─────────────────────────────────────────
try:
    import distutils  # noqa: F401
except ImportError:
    pass

if "distutils" not in sys.modules or not hasattr(sys.modules.get("distutils"), "version"):
    try:
        from packaging.version import Version as LooseVersion
        import types as _types
        _d = _types.ModuleType("distutils")
        _dv = _types.ModuleType("distutils.version")
        _dv.LooseVersion = LooseVersion
        sys.modules["distutils"] = _d
        sys.modules["distutils.version"] = _dv
    except ImportError:
        pass

import speech_recognition as sr


class SpeechToText:
    """
    Speech recognition wrapper.

    Usage patterns
    --------------
    1. One-shot:
        text = stt.listen()

    2. Continuous background listening:
        stt.start_continuous(on_speech_callback, on_listening_callback)
        ...
        stt.stop_continuous()

    Wake words (when wake_word_mode=True):
        Say "Hey agent ..." or "Hey nova ..." before your command.
    """

    WAKE_WORDS = {"hey jarvis", "jarvis", "hey friday", "friday", "okay jarvis"}

    def __init__(self, device_index: int | None = None):
        """
        Parameters
        ----------
        device_index : int or None
            PyAudio microphone device index.  None = system default.
        """
        self.device_index = device_index

        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.8
        self.recognizer.non_speaking_duration = 0.4

        self._stop_bg = threading.Event()
        self._bg_thread: threading.Thread | None = None
        self._on_speech = None
        self._on_listening = None
        self._wake_word_mode: bool = False

    # ── helpers ──────────────────────────────────────────────────────────────

    def _micro_source(self):
        """Return a configured Microphone context manager."""
        if self.device_index is not None:
            return sr.Microphone(device_index=self.device_index)
        return sr.Microphone()

    def _recognize(self, audio: sr.AudioData) -> str:
        try:
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"[STT] Google service error: {e}")
            return ""

    def _notify_listening(self, state: bool):
        """Safely call the on_listening callback."""
        if self._on_listening:
            try:
                self._on_listening(state)
            except Exception as e:
                print(f"[STT] on_listening callback error: {e}")

    # ── one-shot listening ────────────────────────────────────────────────────

    def listen(self, timeout: float = 6, phrase_time_limit: float = 12) -> str:
        """Block until speech is detected or timeout. Returns recognized text."""
        try:
            with self._micro_source() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
            return self._recognize(audio)
        except sr.WaitTimeoutError:
            return ""
        except OSError as e:
            print(f"[STT] Microphone error: {e}")
            return ""
        except Exception as e:
            print(f"[STT] Unexpected error: {e}")
            return ""

    # ── continuous background listening ───────────────────────────────────────

    def start_continuous(
        self,
        on_speech,
        on_listening=None,
        wake_word_mode: bool = False,
    ):
        """
        Start background thread that continuously listens.
        """
        # If there's an existing thread, tell it to stop and wait briefly
        if self._bg_thread and self._bg_thread.is_alive():
            self.stop_continuous()
            self._bg_thread.join(timeout=1.0)

        self._on_speech = on_speech
        self._on_listening = on_listening
        self._wake_word_mode = wake_word_mode
        self._stop_bg.clear()

        self._bg_thread = threading.Thread(
            target=self._continuous_loop, daemon=True, name="STT-BG"
        )
        self._bg_thread.start()

    def stop_continuous(self):
        """Signal the background listener to stop."""
        self._stop_bg.set()

    def is_running(self) -> bool:
        return self._bg_thread is not None and self._bg_thread.is_alive()

    # ── core loop ─────────────────────────────────────────────────────────────

    def _continuous_loop(self):
        """
        Runs in a daemon thread.

        Key design decisions
        --------------------
        • Open the microphone, listen for ONE phrase, then close it.
          This avoids PyAudio holding the device between phrases and
          prevents deadlocks when the mic context is re-entered.
        • WaitTimeoutError just loops back — no special state needed.
        • The on_listening callback is called *outside* the `with` block
          where possible, because emitting Qt signals while PyAudio is
          busy can cause issues on some Windows drivers.
        """
        _activated = not self._wake_word_mode

        while not self._stop_bg.is_set():
            audio = None

            try:
                # ── Open mic and capture exactly one phrase ────────────────
                with self._micro_source() as source:
                    # Quick ambient calibration on first pass
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.25)

                    # Signal UI: we're now actively listening
                    self._notify_listening(True)

                    try:
                        audio = self.recognizer.listen(
                            source,
                            timeout=3,           # wait up to 3s for speech to start
                            phrase_time_limit=12, # max 12s per phrase
                        )
                    except sr.WaitTimeoutError:
                        pass   # no speech in window, loop again

                # ── Mic is closed here; safe to do network call ────────────
                self._notify_listening(False)

                if audio is None or self._stop_bg.is_set():
                    continue

                text = self._recognize(audio)
                if not text:
                    continue

                # ── Wake-word gate ─────────────────────────────────────────
                if self._wake_word_mode:
                    lower = text.lower().strip()
                    matched = any(lower.startswith(w) for w in self.WAKE_WORDS)
                    if matched:
                        _activated = True
                        for ww in self.WAKE_WORDS:
                            if lower.startswith(ww):
                                text = text[len(ww):].strip()
                                break
                        if not text:
                            # Pure wake word only — wait for next utterance
                            self._notify_listening(True)
                            try:
                                with self._micro_source() as source:
                                    audio2 = self.recognizer.listen(
                                        source, timeout=5, phrase_time_limit=12
                                    )
                                self._notify_listening(False)
                                text = self._recognize(audio2)
                            except Exception:
                                self._notify_listening(False)
                                continue
                        if not text:
                            continue
                    elif not _activated:
                        continue

                # ── Deliver speech ─────────────────────────────────────────
                if self._on_speech and text:
                    try:
                        self._on_speech(text)
                    except Exception as e:
                        print(f"[STT] on_speech callback error: {e}")

                # Reset wake-word gate after delivery
                if self._wake_word_mode:
                    _activated = False

            except OSError as e:
                self._notify_listening(False)
                print(f"[STT] Microphone unavailable: {e}")
                time.sleep(2)
            except Exception as e:
                self._notify_listening(False)
                print(f"[STT] Loop error: {type(e).__name__}: {e}")
                time.sleep(0.5)

        # ── Cleanup on stop ────────────────────────────────────────────────
        self._notify_listening(False)
        print("[STT] Background listener stopped.")

    @staticmethod
    def list_microphones() -> list[tuple[int, str]]:
        """Return list of (index, name) for all PyAudio input devices."""
        return list(enumerate(sr.Microphone.list_microphone_names()))
