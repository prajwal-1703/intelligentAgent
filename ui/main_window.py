"""
Main application window.

New in this version
───────────────────
• Animated waveform indicator (WaveformWidget) while listening/speaking
• Continuous background STT with toggle (🎙 / ⏹)
• Wake-word mode toggle ("hey agent …")
• Camera preview overlay with live feed (📷 button)
• Camera-frame analysis sent to AI vision pipeline
• Screen capture intent unchanged
• TTS speaking-state wired to waveform animation
• Status bar showing current mode
"""

import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit,
    QGraphicsDropShadowEffect, QLabel,
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QColor, QFont

from ai.bedrock_client import BedrockClient
from voice.stt import SpeechToText
from voice.tts import TextToSpeech
from actions.executor import ActionExecutor
from memory.storage import MemoryStorage
from vision.capture import ScreenCapture
from ui.waveform import WaveformWidget
from ui.camera_preview import CameraPreviewOverlay


class MainWindow(QWidget):
    # Qt signals (emitted from background threads → safe UI updates)
    message_received         = pyqtSignal(str, str)   # sender, text
    system_action_done       = pyqtSignal(str)
    indicator_status_changed = pyqtSignal(bool)        # True = listening
    speaking_changed         = pyqtSignal(bool)        # True = TTS active
    status_text_changed      = pyqtSignal(str)         # bottom status bar

    def __init__(self, vis_controller):
        super().__init__()

        # ── Core modules ───────────────────────────────────────────────────
        self.ai       = BedrockClient()
        self.memory   = MemoryStorage()
        self.vision   = ScreenCapture()
        self.executor = ActionExecutor(self.memory, vis_controller)

        # TTS with speaking callback
        self.tts = TextToSpeech(on_speaking_change=lambda s: self.speaking_changed.emit(s))

        # STT
        self.stt = SpeechToText()

        # State
        self._continuous_running  = False
        self._wake_word_mode      = False
        self._camera_overlay: CameraPreviewOverlay | None = None
        self.offset = None

        # ── Build UI ───────────────────────────────────────────────────────
        self._build_ui()

        # ── Connect signals ────────────────────────────────────────────────
        self.message_received.connect(self.append_message)
        self.system_action_done.connect(self.system_message)
        self.indicator_status_changed.connect(self._on_listening_changed)
        self.speaking_changed.connect(self._on_speaking_changed)
        self.status_text_changed.connect(self._status_label.setText)

        # ── Greet ──────────────────────────────────────────────────────────
        self.append_message("Agent", "Hello! I'm online and ready.")
        self.append_message(
            "Agent",
            "<i>Tip: Click 🎙 to toggle continuous mic listening. "
            "Enable '🤖 Jarvis' wake-word mode and say <b>'Jarvis, ...'</b> or <b>'Friday, ...'</b> before each command. "
            "Click 📷 to open the live camera.</i>"
        )
        self.tts.speak("Systems online. Ready.")

    # ════════════════════════════════════════════════════════════════════════
    # UI construction
    # ════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(380, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Glassmorphism container ─────────────────────────────────────────
        self._container = QWidget()
        self._container.setObjectName("MainContainer")
        self._container.setStyleSheet("""
            QWidget#MainContainer {
                background-color: rgba(22, 24, 38, 215);
                border-radius: 22px;
                border: 1px solid rgba(255, 255, 255, 28);
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(12)
        shadow.setColor(QColor(0, 0, 0, 120))
        self._container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(self._container)
        c_layout.setContentsMargins(14, 12, 14, 14)
        c_layout.setSpacing(8)

        # ── Header row ──────────────────────────────────────────────────────
        header = QHBoxLayout()

        self._indicator = QLabel()
        self._indicator.setFixedSize(10, 10)
        self._indicator.setStyleSheet(
            "background-color: rgba(100,255,100,160); border-radius: 5px;"
        )

        self._mode_label = QLabel("Idle")
        self._mode_label.setStyleSheet(
            "color: rgba(180,200,255,160); font-family: 'Segoe UI'; font-size: 11px;"
            " background: transparent;"
        )

        self._waveform = WaveformWidget()

        self._wake_btn = QPushButton("🤖 Jarvis")
        self._wake_btn.setFixedHeight(24)
        self._wake_btn.setCheckable(True)
        self._wake_btn.setToolTip(
            "Wake Word Mode\n"
            "When ON: Say 'Jarvis, ...' or 'Friday, ...' before each command\n"
            "When OFF: Everything you say is treated as a command"
        )
        self._wake_btn.setStyleSheet(self._toggle_style(False))
        self._wake_btn.toggled.connect(self._on_wake_word_toggled)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton { background: rgba(255,100,100,150); color: white;
                          border-radius: 14px; font-weight: bold; }
            QPushButton:hover { background: rgba(255,100,100,255); }
        """)
        close_btn.clicked.connect(self.close)

        header.addWidget(self._indicator)
        header.addWidget(self._mode_label)
        header.addStretch()
        header.addWidget(self._waveform)
        header.addWidget(self._wake_btn)
        header.addWidget(close_btn)

        # ── Chat display ────────────────────────────────────────────────────
        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #E0E0F0;
                border: none;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
        """)
        self._chat.verticalScrollBar().setStyleSheet("width: 0px;")

        # ── Input row ───────────────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        # Mic toggle button
        self._mic_btn = QPushButton("🎙")
        self._mic_btn.setFixedSize(42, 42)
        self._mic_btn.setCheckable(True)
        self._mic_btn.setStyleSheet(self._mic_style(False))
        self._mic_btn.clicked.connect(self._on_mic_toggled)

        # Camera button
        self._cam_btn = QPushButton("📷")
        self._cam_btn.setFixedSize(42, 42)
        self._cam_btn.setToolTip("Open camera preview")
        self._cam_btn.setStyleSheet("""
            QPushButton { background: rgba(60,180,120,150); color: white;
                          border-radius: 21px; font-size: 17px; }
            QPushButton:hover { background: rgba(60,180,120,220); }
            QPushButton:pressed { background: rgba(30,140,90,255); }
        """)
        self._cam_btn.clicked.connect(self._on_camera_clicked)

        # Text input
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Type a command…")
        self._text_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,18);
                color: white;
                border-radius: 21px;
                padding: 10px 14px;
                border: 1px solid rgba(255,255,255,45);
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid rgba(100,150,255,200); }
        """)
        self._text_input.returnPressed.connect(self._on_text_entered)

        input_row.addWidget(self._mic_btn)
        input_row.addWidget(self._cam_btn)
        input_row.addWidget(self._text_input)

        # ── Status bar ──────────────────────────────────────────────────────
        self._status_label = QLabel("Ready")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "color: rgba(150,160,200,160); font-size: 11px;"
            " font-family: 'Segoe UI'; background: transparent;"
        )

        # ── Assemble ────────────────────────────────────────────────────────
        c_layout.addLayout(header)
        c_layout.addWidget(self._chat, stretch=1)
        c_layout.addLayout(input_row)
        c_layout.addWidget(self._status_label)

        root.addWidget(self._container)

    # ════════════════════════════════════════════════════════════════════════
    # Style helpers
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _mic_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { background: rgba(255,80,80,220); color: white;"
                " border-radius: 21px; font-size: 17px; }"
                "QPushButton:hover { background: rgba(255,80,80,255); }"
            )
        return (
            "QPushButton { background: rgba(100,150,255,150); color: white;"
            " border-radius: 21px; font-size: 17px; }"
            "QPushButton:hover { background: rgba(100,150,255,220); }"
            "QPushButton:pressed { background: rgba(60,100,200,255); }"
        )

    @staticmethod
    def _toggle_style(on: bool) -> str:
        if on:
            return (
                "QPushButton { background: rgba(80,200,120,180); color: white;"
                " border-radius: 10px; font-size: 10px; padding: 0 6px; }"
            )
        return (
            "QPushButton { background: rgba(80,80,100,150); color: rgba(200,200,220,180);"
            " border-radius: 10px; font-size: 10px; padding: 0 6px; }"
        )

    # ════════════════════════════════════════════════════════════════════════
    # Mic / STT
    # ════════════════════════════════════════════════════════════════════════

    def _on_mic_toggled(self, checked: bool):
        if checked:
            self._start_continuous_stt()
        else:
            self._stop_continuous_stt()

    def _start_continuous_stt(self):
        self._continuous_running = True
        self._mic_btn.setStyleSheet(self._mic_style(True))
        self._update_mode("Listening…")
        self.stt.start_continuous(
            on_speech=self._on_speech_received,
            on_listening=lambda s: self.indicator_status_changed.emit(s),
            wake_word_mode=self._wake_word_mode,
        )

    def _stop_continuous_stt(self):
        self._continuous_running = False
        self.stt.stop_continuous()
        self._mic_btn.setChecked(False)
        self._mic_btn.setStyleSheet(self._mic_style(False))
        self._update_mode("Idle")
        self.indicator_status_changed.emit(False)

    def _on_speech_received(self, text: str):
        """Called from STT background thread."""
        self.message_received.emit("You", text)
        self._process_command_async(text)

    # ── One-shot mic (legacy fallback, not used in continuous mode) ──────────
    def _one_shot_listen(self):
        self.indicator_status_changed.emit(True)
        threading.Thread(target=self._listen_thread, daemon=True).start()

    def _listen_thread(self):
        text = self.stt.listen()
        self.indicator_status_changed.emit(False)
        if text:
            self.message_received.emit("You", text)
            self._process_command_async(text)

    # ── Wake-word toggle ─────────────────────────────────────────────────────
    def _on_wake_word_toggled(self, on: bool):
        self._wake_word_mode = on
        label = "🤖 Jarvis  ● ON" if on else "🤖 Jarvis"
        self._wake_btn.setText(label)
        self._wake_btn.setStyleSheet(self._toggle_style(on))
        hint = ("Wake-word ON — say 'Jarvis, ...' or 'Friday, ...' before each command"
                if on else "Wake-word OFF — mic sends everything to AI")
        self.status_text_changed.emit(hint)
        if self._continuous_running:
            self._stop_continuous_stt()
            self._start_continuous_stt()

    # ════════════════════════════════════════════════════════════════════════
    # Camera
    # ════════════════════════════════════════════════════════════════════════

    def _on_camera_clicked(self):
        if self._camera_overlay and self._camera_overlay.isVisible():
            self._camera_overlay._on_close()
            return

        self._camera_overlay = CameraPreviewOverlay(self.vision)
        # Position to the right of the main window
        geo = self.geometry()
        self._camera_overlay.move(geo.right() + 10, geo.top())
        self._camera_overlay.capture_requested.connect(self._on_camera_capture)
        self._camera_overlay.closed.connect(self._on_camera_closed)
        self._camera_overlay.show()

    def _on_camera_capture(self):
        """Capture a webcam frame and analyze it with the AI."""
        self.system_action_done.emit("Capturing camera frame…")
        threading.Thread(target=self._camera_analyze_thread, daemon=True).start()

    def _camera_analyze_thread(self):
        img_b64 = self.vision.capture_camera_frame_as_base64()
        if not img_b64:
            self.message_received.emit("Agent", "Could not capture a camera frame.")
            return
        prompt = "Describe and analyze what you see in this camera image in detail."
        resp = self.ai.get_intent(prompt, image_base64=img_b64)
        reply = resp.get("message", "Camera image analyzed.")
        self.message_received.emit("Agent", reply)
        self.tts.speak(reply)
        self.status_text_changed.emit("Camera analysis complete")

    def _on_camera_closed(self):
        self._camera_overlay = None

    # ════════════════════════════════════════════════════════════════════════
    # Text input
    # ════════════════════════════════════════════════════════════════════════

    def _on_text_entered(self):
        text = self._text_input.text().strip()
        if text:
            self._text_input.clear()
            self.message_received.emit("You", text)
            self._process_command_async(text)

    # ════════════════════════════════════════════════════════════════════════
    # AI processing
    # ════════════════════════════════════════════════════════════════════════

    def _process_command_async(self, text: str):
        threading.Thread(
            target=self._process_command, args=(text,), daemon=True
        ).start()

    def _process_command(self, text: str):
        self.status_text_changed.emit("Thinking…")
        response_json = self.ai.get_intent(text)
        intent = response_json.get("intent")

        if intent == "multi_action":
            for act in response_json.get("actions", []):
                self._run_single_action(act, text)
        else:
            self._run_single_action(response_json, text)

        self.status_text_changed.emit("Ready")

    def _run_single_action(self, action_json: dict, user_text: str):
        intent = action_json.get("intent")

        if intent == "analyze_screen":
            self.system_action_done.emit("Capturing screen…")
            img_b64 = self.vision.capture_as_base64()
            resp = self.ai.get_intent(user_text, image_base64=img_b64)
            reply = resp.get("message", "Screen analyzed.")
            self.message_received.emit("Agent", reply)
            self.tts.speak(reply)
            return

        if intent == "analyze_camera":
            self._on_camera_capture()
            return

        reply = self.executor.execute(action_json)
        self.message_received.emit("Agent", reply)
        if reply:
            self.tts.speak(reply)

    # ════════════════════════════════════════════════════════════════════════
    # Signal slots (UI thread)
    # ════════════════════════════════════════════════════════════════════════

    @pyqtSlot(bool)
    def _on_listening_changed(self, active: bool):
        self._waveform.set_active(active)
        if active:
            self._indicator.setStyleSheet(
                "background-color: rgba(255,100,100,255); border-radius: 5px;"
            )
        else:
            self._indicator.setStyleSheet(
                "background-color: rgba(100,255,100,160); border-radius: 5px;"
            )

    @pyqtSlot(bool)
    def _on_speaking_changed(self, speaking: bool):
        if speaking:
            self._waveform.set_active(True)
            self._update_mode("Speaking…")
        else:
            if not self._continuous_running:
                self._waveform.set_active(False)
            self._update_mode("Listening…" if self._continuous_running else "Idle")

    @pyqtSlot(str, str)
    def append_message(self, sender: str, text: str):
        colour = "#4A9EFF" if sender == "You" else "#4ADF80"
        self._chat.append(f"<b style='color:{colour};'>{sender}:</b> {text}")
        self._chat.verticalScrollBar().setValue(
            self._chat.verticalScrollBar().maximum()
        )

    @pyqtSlot(str)
    def system_message(self, text: str):
        self._chat.append(f"<i style='color:#888AAA;'>{text}</i>")

    def _update_mode(self, text: str):
        """Thread-safe mode label update via signal."""
        self.status_text_changed.emit(text)

    # ════════════════════════════════════════════════════════════════════════
    # Drag
    # ════════════════════════════════════════════════════════════════════════

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.pos() - self.offset)

    def mouseReleaseEvent(self, event):
        self.offset = None

    # ════════════════════════════════════════════════════════════════════════
    # Cleanup
    # ════════════════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        self._stop_continuous_stt()
        if self._camera_overlay:
            self._camera_overlay._on_close()
        self.tts.shutdown()
        self.vision.release_camera()
        super().closeEvent(event)
