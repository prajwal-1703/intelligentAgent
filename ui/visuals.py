from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import psutil

class VisualizationOverlay(QWidget):
    def __init__(self, metric_type="cpu"):
        super().__init__()
        self.metric_type = metric_type
        self.initUI()
        self.offset = None
        
        # Make frameless, stays on top, tool window
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.show()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        
        # Transparent background styling
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 200);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 50);
            }
            QLabel {
                color: #FFFFFF;
                background-color: transparent;
                border: none;
            }
            QPushButton {
                background-color: transparent;
                color: rgba(255, 100, 100, 200);
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #FF0000;
            }
        """)
        self.container_layout = QVBoxLayout(self.container)
        
        self.title = QLabel(f"Visualization: {self.metric_type.upper()}")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        
        self.value_label = QLabel("Loading...")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFont(QFont("Segoe UI", 24))
        
        self.close_btn = QPushButton("X")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)
        
        self.container_layout.addWidget(self.close_btn, alignment=Qt.AlignRight)
        self.container_layout.addWidget(self.title)
        self.container_layout.addWidget(self.value_label)
        self.container_layout.addStretch()
        
        self.layout.addWidget(self.container)
        self.resize(200, 150)
        
        # Set up a timer to update the metric
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_metric)
        self.timer.start(1000)
        self.update_metric()

    def update_metric(self):
        if self.metric_type == "cpu":
            val = psutil.cpu_percent()
            self.value_label.setText(f"{val}%")
        elif self.metric_type == "ram":
            val = psutil.virtual_memory().percent
            self.value_label.setText(f"{val}%")
        else:
            self.value_label.setText("N/A")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.pos() - self.offset)

    def mouseReleaseEvent(self, event):
        self.offset = None

class VisibilityController:
    def __init__(self):
        self.active_overlays = []
        
    def show_visualization(self, metric_type):
        overlay = VisualizationOverlay(metric_type)
        self.active_overlays.append(overlay)
