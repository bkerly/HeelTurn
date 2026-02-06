import sys
import pandas as pd
import requests
import json
import random
import os
from pathlib import Path
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                           QWidget, QPushButton, QLabel, QComboBox, QTextEdit, 
                           QLineEdit, QMessageBox, QProgressBar, QSplitter, 
                           QTextBrowser)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QTextCharFormat, QTextCursor, QColor

class WorkerThread(QThread):
    finished = pyqtSignal(object)
    
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        
    def run(self):
        try:
            result = self.function(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({'error': str(e)})

class HeelTurnAdventure(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heel Turn: A Text-Based Adventure Game")
        self.setGeometry(100, 100, 1200, 800)
        
        # Configuration
        self.ollama_server = "http://localhost:11434"
        self.ollama_model = "mistral"
        self.ollama_api_key = None
        
        # Game state
        self.game_started = False
        self.story_selected = False
        self.available_stories = []
        self.selected_story = None
        self.story_data = None
        self.character_data = None
        self.selected_character = None
        self.current_row = 1
        self.story_history = []
        
        # UI elements that need to be tracked for cleanup
        self.action_entry = None
        self.story_text = None
        self.game_buttons_layout = None
        
        # Styling
        self.fixed_font = QFont("Courier New", 12)  # Fixed-width font
        self.monospace_font = QFont("Monaco", 11)  # Alternative monospace
        
        self.setup_ui()
        self.scan_available_stories()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # Sidebar
        self.sidebar = QWidget()
        self.sidebar.setMaximumWidth(300)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                border-right: 1px solid #34495e;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
            }
            QLabel {
                color: #ecf0f1;
            }
        """)
        
        # Main content area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_area.setStyleSheet("""
            QWidget {
                background-color: #34495e;
            }
        """)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.content_area)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)
        
        # Don't show story selection immediately - wait for scan to complete
        self.show_loading_screen()
        
    def show_loading_screen(self):
        """Show loading screen while scanning for stories"""
        self.clear_content()
        
        title = QLabel("Heel Turn")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #3498db; margin: 20px;")
        self.content_layout.addWidget(title)
        
        loading_label = QLabel("Scanning for stories...")
        loading_label.setFont(QFont("Arial", 14))
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("color: #ecf0f1;")
        self.content_layout.addWidget(loading_label)
        
    def scan_available_stories(self):
        """Scan for available stories with improved path handling"""
        print("Scanning for stories...")
        self.available_stories = []  # Clear first
        
        # Try multiple possible data directory locations
        possible_dirs = [
            Path.cwd() / "data",  # Current working directory/data
            Path(__file__).parent / "data",  # Script directory/data
            Path.home() / "heel_turn_data](streamdown:incomplete-link)
