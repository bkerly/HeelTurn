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
                background-color: #f8f9fa;
                border-right: 1px solid #dee2e6;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        
        # Main content area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_area.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
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
        title.setStyleSheet("color: #007bff; margin: 20px;")
        self.content_layout.addWidget(title)
        
        loading_label = QLabel("Scanning for stories...")
        loading_label.setFont(QFont("Arial", 14))
        loading_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(loading_label)
        
    def scan_available_stories(self):
        """Scan for available stories with improved path handling"""
        print("Scanning for stories...")
        self.available_stories = []  # Clear first
        
        # Try multiple possible data directory locations
        possible_dirs = [
            Path.cwd() / "data",  # Current working directory/data
            Path(__file__).parent / "data",  # Script directory/data
            Path.home() / "heel_turn_data",  # Home directory
            Path("/Users/brianerly/Documents/HeelTurn/data"),  # Your specific path
        ]
        
        # Also check relative to the script location
        script_dir = Path(__file__).parent
        possible_dirs.extend([
            script_dir / "data",
            script_dir.parent / "data",
            script_dir / "heel_turn_data"
        ])
        
        found_stories = []
        checked_dirs = []
        
        for data_dir in possible_dirs:
            checked_dirs.append(str(data_dir))
            print(f"Checking directory: {data_dir}")
            if data_dir.exists() and data_dir.is_dir():
                for folder in data_dir.iterdir():
                    if folder.is_dir():
                        # Check for the required files with more flexible naming
                        story_variations = [
                            f"{folder.name} - story sheet.csv",
                            f"{folder.name}_story_sheet.csv", 
                            f"{folder.name}_story.csv",
                            "story_sheet.csv",
                            "story.csv"
                        ]
                        
                        skill_variations = [
                            f"{folder.name} - skill sheet.csv",
                            f"{folder.name}_skill_sheet.csv",
                            f"{folder.name}_skill.csv",
                            "skill_sheet.csv", 
                            "skill.csv"
                        ]
                        
                        story_file_found = None
                        skill_file_found = None
                        
                        # Look for story file
                        for variation in story_variations:
                            story_file = folder / variation
                            if story_file.exists():
                                story_file_found = story_file
                                break
                        
                        # Look for skill file
                        for variation in skill_variations:
                            skill_file = folder / variation
                            if skill_file.exists():
                                skill_file_found = skill_file
                                break
                        
                        if story_file_found and skill_file_found:
                            print(f"Found valid story: {folder.name}")
                            print(f"  Story file: {story_file_found}")
                            print(f"  Skill file: {skill_file_found}")
                            found_stories.append(folder.name)
                        else:
                            print(f"Skipping {folder.name} - missing required files")
        
        # Remove duplicates and sort
        self.available_stories = sorted(list(set(found_stories)))
        
        print(f"Total stories found: {len(self.available_stories)}")
        print(f"Stories: {self.available_stories}")
        
        # Update UI after scanning
        self.show_story_selection()
        
    def show_story_selection(self):
        """Show the story selection screen"""
        self.clear_content()
        self.clear_sidebar()
        
        # Reset game state
        self.game_started = False
        self.story_selected = False
        self.story_data = None
        self.character_data = None
        self.selected_character = None
        self.current_row = 1
        self.story_history = []
        
        # Clear any game-specific UI elements
        self.action_entry = None
        self.story_text = None
        self.game_buttons_layout = None
        
        title = QLabel("Choose Your Story")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("margin: 10px 0; color: #333;")
        self.content_layout.addWidget(title)
        
        # Debug info
        debug_text = QLabel(f"Found {len(self.available_stories)} stories")
        debug_text.setStyleSheet("color: #28a745; font-size: 12px; margin-bottom: 10px;")
        self.content_layout.addWidget(debug_text)
        
        if self.available_stories:
            self.story_combo = QComboBox()
            self.story_combo.addItems(self.available_stories)
            self.story_combo.setStyleSheet("""
                QComboBox {
                    padding: 8px;
                    font-size: 14px;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                }
            """)
            self.content_layout.addWidget(self.story_combo)
            
            select_btn = QPushButton("Select Story")
            select_btn.clicked.connect(self.select_story)
            select_btn.setStyleSheet("margin-top: 10px;")
            self.content_layout.addWidget(select_btn)
        else:
            # Show detailed error info
            error_label = QLabel("No stories found. Please check:")
            error_label.setStyleSheet("color: #dc3545; font-size: 14px; margin: 10px 0;")
            self.content_layout.addWidget(error_label)
            
            self.story_combo = QComboBox()
            self.story_combo.addItem("No stories available")
            self.story_combo.setEnabled(False)
            self.story_combo.setStyleSheet("""
                QComboBox {
                    padding: 8px;
                    font-size: 14px;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                }
            """)
            self.content_layout.addWidget(self.story_combo)
            
            select_btn = QPushButton("Select Story")
            select_btn.setEnabled(False)
            select_btn.setStyleSheet("margin-top: 10px;")
            self.content_layout.addWidget(select_btn)
            
    def show_character_selection(self):
        """Show character selection screen"""
        self.clear_content()
        self.clear_sidebar()
        
        title = QLabel("Choose Your Character")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("margin: 10px 0; color: #333;")
        self.content_layout.addWidget(title)
        
        self.character_combo = QComboBox()
        character_names = [row['Character'] for _, row in self.character_data.iterrows()]
        self.character_combo.addItems(character_names)
        self.character_combo.currentTextChanged.connect(self.update_character_preview)
        self.character_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                font-size: 14px;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }
        """)
        self.content_layout.addWidget(self.character_combo)
        
        # Character preview with image support
        self.preview_widget = QWidget()
        preview_layout = QVBoxLayout(self.preview_widget)
        preview_layout.setSpacing(10)
        
        self.character_image_label = QLabel()
        self.character_image_label.setAlignment(Qt.AlignCenter)
        self.character_image_label.setFixedSize(150, 150)
        self.character_image_label.setStyleSheet("border: 2px solid #007bff; background-color: #f8f9fa; border-radius: 8px;")
        preview_layout.addWidget(self.character_image_label)
        
        self.preview_text_label = QLabel()
        self.preview_text_label.setWordWrap(True)
        self.preview_text_label.setStyleSheet("font-size: 12px; padding: 10px; background-color: #e9ecef; border-radius: 4px;")
        preview_layout.addWidget(self.preview_text_label)
        
        self.content_layout.addWidget(self.preview_widget)
        
        start_btn = QPushButton("Start Adventure!")
        start_btn.clicked.connect(self.start_game)
        start_btn.setStyleSheet("margin-top: 15px; padding: 10px; font-size: 14px;")
        self.content_layout.addWidget(start_btn)
        
        back_btn = QPushButton("← Back to Story Selection")
        back_btn.clicked.connect(self.back_to_story)
        back_btn.setStyleSheet("margin-top: 5px; padding: 8px; font-size: 12px; background-color: #6c757d; color: white;")
        self.content_layout.addWidget(back_btn)
        
        self.update_character_preview()
        
    def show_game_screen(self):
        """Show the main game screen with improved readability"""
        self.clear_content()
        self.clear_sidebar()
        
        # Character info in sidebar
        char_title = QLabel("Character Info")
        char_title.setFont(QFont("Arial", 14, QFont.Bold))
        char_title.setStyleSheet("margin-bottom: 10px; color: #007bff;")
        self.sidebar_layout.addWidget(char_title)
        
        # Character image in sidebar
        self.sidebar_image_label = QLabel()
        self.sidebar_image_label.setAlignment(Qt.AlignCenter)
        self.sidebar_image_label.setFixedSize(120, 120)
        self.sidebar_image_label.setStyleSheet("border: 2px solid #007bff; background-color: #f8f9fa; border-radius: 8px;")
        self.sidebar_layout.addWidget(self.sidebar_image_label)
        
        if self.selected_character:
            char_name = QLabel(f"Name: {self.selected_character['Character']}")
            char_name.setFont(QFont("Arial", 11, QFont.Bold))
            char_name.setStyleSheet("margin-top: 10px; color: #333;")
            self.sidebar_layout.addWidget(char_name)
            
            char_desc = QLabel(f"Description: {self.selected_character['Description']}")
            char_desc.setWordWrap(True)
            char_desc.setStyleSheet("font-size: 10px; margin: 5px 0; color: #666;")
            self.sidebar_layout.addWidget(char_desc)
            
        story_label = QLabel(f"Story: {self.selected_story}")
        story_label.setStyleSheet("margin-top: 15px; font-weight: bold; color: #007bff;")
        self.sidebar_layout.addWidget(story_label)
        
        self.progress_label = QLabel(f"Progress: {self.current_row}/{len(self.story_data)}")
        self.progress_label.setStyleSheet("margin: 5px 0; font-weight: bold; color: #28a745;")
        self.sidebar_layout.addWidget(self.progress_label)
        
        self.sidebar_layout.addStretch()
        
        new_game_btn = QPushButton("New Game")
        new_game_btn.clicked.connect(self.quit_game)
        new_game_btn.setStyleSheet("padding: 8px; font-size: 12px; background-color: #ffc107; color: #333;")
        self.sidebar_layout.addWidget(new_game_btn)
        
        # Load character image for sidebar
        self.load_character_image_for_sidebar()
        
        # Main game content - create new widgets each time
        self.story_text = QTextBrowser()
        self.story_text.setFont(self.fixed_font)
        self.story_text.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
                padding: 15px;
                border-radius: 4px;
                font-family: "Courier New", Monaco, monospace;
                font-size: 12px;
            }
        """)
        self.content_layout.addWidget(self.story_text)
        
        # Input area - create new widget each time
        input_label = QLabel("What do you do?")
        input_label.setFont(QFont("Arial", 12, QFont.Bold))
        input_label.setStyleSheet("margin-top: 15px; color: #333;")
        self.content_layout.addWidget(input_label)
        
        self.action_entry = QLineEdit()
        self.action_entry.setFont(self.fixed_font)
        self.action_entry.returnPressed.connect(self.submit_action)
        self.action_entry.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                font-size: 14px;
                border: 2px solid #007bff;
                border-radius: 4px;
                background-color: #ffffff;
                font-family: "Courier New", Monaco, monospace;
            }
            QLineEdit:focus {
                border-color: #0056b3;
                background-color: #ffffff;
            }
        """)
        self.content_layout.addWidget(self.action_entry)
        
        # Buttons - create new layout each time
        self.game_buttons_layout = QHBoxLayout()
        
        submit_btn = QPushButton("Submit Action")
        submit_btn.clicked.connect(self.submit_action)
        submit_btn.setStyleSheet("padding: 10px 15px; background-color: #28a745; color: white; font-weight: bold;")
        self.game_buttons_layout.addWidget(submit_btn)
        
        skip_btn = QPushButton("Skip Challenge")
        skip_btn.clicked.connect(self.skip_challenge)
        skip_btn.setStyleSheet("padding: 10px 15px; background-color: #17a2b8; color: white; font-weight: bold;")
        self.game_buttons_layout.addWidget(skip_btn)
        
        quit_btn = QPushButton("Quit Game")
        quit_btn.clicked.connect(self.quit_game)
        quit_btn.setStyleSheet("padding: 10px 15px; background-color: #dc3545; color: white; font-weight: bold;")
        self.game_buttons_layout.addWidget(quit_btn)
        
        self.content_layout.addLayout(self.game_buttons_layout)
        
        self.update_story_display()
        
    def load_character_image(self, character_name, target_label):
        """Load character sprite image if available"""
        if not self.selected_story:
            return
            
        # Look for character sprite in story folder
        possible_dirs = [
            Path(f"/Users/brianerly/Documents/HeelTurn/data/{self.selected_story}"),
            Path.cwd() / "data" / self.selected_story,
            Path(__file__).parent / "data" / self.selected_story,
            Path.home() / "heel_turn_data" / self.selected_story,
        ]
        
        script_dir = Path(__file__).parent
        possible_dirs.extend([
            script_dir / "data" / self.selected_story,
            script_dir.parent / "data" / self.selected_story,
            script_dir / "heel_turn_data" / self.selected_story
        ])
        
        # Try different image file extensions
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
        
        for data_dir in possible_dirs:
            if data_dir.exists():
                for ext in image_extensions:
                    image_path = data_dir / f"{character_name}{ext}"
                    if image_path.exists():
                        try:
                            pixmap = QPixmap(str(image_path))
                            if not pixmap.isNull():
                                # Scale the image to fit the label while maintaining aspect ratio
                                scaled_pixmap = pixmap.scaled(
                                    target_label.width(), 
                                    target_label.height(),
                                    Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation
                                )
                                target_label.setPixmap(scaled_pixmap)
                                print(f"Loaded character image: {image_path}")
                                return
                        except Exception as e:
                            print(f"Error loading image {image_path}: {e}")
        
        # If no image found, show placeholder
        target_label.setText("No Image")
        target_label.setStyleSheet("color: #6c757d; font-style: italic; border: 1px dashed #6c757d;")
        
    def load_character_image_for_sidebar(self):
        """Load character image for the sidebar"""
        if self.selected_character:
            self.load_character_image(self.selected_character['Character'], self.sidebar_image_label)
        
    def update_character_preview(self):
        if not hasattr(self, 'preview_text_label') or not hasattr(self, 'character_image_label'):
            return
            
        char_name = self.character_combo.currentText()
        if char_name and self.character_data is not None:
            character_row = self.character_data[
                self.character_data['Character'] == char_name
            ]
            
            if not character_row.empty:
                character = character_row.iloc[0]
                self.preview_text_label.setText(
                    f"<b>{character['Character']}</b><br/>"
                    f"{character['Description']}"
                )
                # Load character image for preview
                if self.selected_story:
                    self.load_character_image(char_name, self.character_image_label)
        
    def clear_content(self):
        """Clear all content widgets"""
        for i in reversed(range(self.content_layout.count())):
            item = self.content_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Clear layout recursively
                self.clear_layout(item.layout())
                item.layout().deleteLater()
                
    def clear_layout(self, layout):
        """Recursively clear a layout and its widgets"""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())
                    
    def clear_sidebar(self):
        """Clear sidebar widgets"""
        for i in reversed(range(self.sidebar_layout.count())):
            item = self.sidebar_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())
                item.layout().deleteLater()
                
    def find_story_files(self, story_name):
        """Find story files with flexible naming"""
        possible_dirs = [
            Path.cwd() / "data" / story_name,
            Path(__file__).parent / "data" / story_name,
            Path.home() / "heel_turn_data" / story_name,
            Path("/Users/brianerly/Documents/HeelTurn/data") / story_name,
        ]
        
        script_dir = Path(__file__).parent
        possible_dirs.extend([
            script_dir / "data" / story_name,
            script_dir.parent / "data" / story_name,
            script_dir / "heel_turn_data" / story_name
        ])
        
        story_variations = [
            f"{story_name} - story sheet.csv",
            f"{story_name}_story_sheet.csv",
            f"{story_name}_story.csv",
            "story_sheet.csv",
            "story.csv"
        ]
        
        skill_variations = [
            f"{story_name} - skill sheet.csv",
            f"{story_name}_skill_sheet.csv", 
            f"{story_name}_skill.csv",
            "skill_sheet.csv",
            "skill.csv"
        ]
        
        for data_dir in possible_dirs:
            if data_dir.exists():
                # Look for story file
                story_file_found = None
                for variation in story_variations:
                    story_file = data_dir / variation
                    if story_file.exists():
                        story_file_found = story_file
                        break
                
                # Look for skill file
                skill_file_found = None
                for variation in skill_variations:
                    skill_file = data_dir / variation
                    if skill_file.exists():
                        skill_file_found = skill_file
                        break
                
                if story_file_found and skill_file_found:
                    return story_file_found, skill_file_found
        
        return None, None
        
    def select_story(self):
        story_name = self.story_combo.currentText()
        if story_name == "No stories available":
            QMessageBox.warning(self, "Warning", "No stories available")
            return
            
        try:
            story_path, skill_path = self.find_story_files(story_name)
            
            if not story_path or not skill_path:
                QMessageBox.critical(self, "Error", 
                    f"Could not find required files for story '{story_name}'\n"
                    f"Looking for story sheet and skill sheet files.")
                return
            
            print(f"Loading story from: {story_path}")
            print(f"Loading skills from: {skill_path}")
            
            self.story_data = pd.read_csv(story_path)
            self.character_data = pd.read_csv(skill_path)
            self.selected_story = story_name
            self.story_selected = True
            
            self.show_character_selection()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load story: {str(e)}")
            
    def start_game(self):
        char_name = self.character_combo.currentText()
        if not char_name:
            QMessageBox.warning(self, "Warning", "Please select a character")
            return
            
        character_row = self.character_data[
            self.character_data['Character'] == char_name
        ]
        
        if character_row.empty:
            QMessageBox.critical(self, "Error", "Selected character not found")
            return
            
        self.selected_character = character_row.iloc[0].to_dict()
        
        self.game_started = True
        self.current_row = 1
        self.story_history = []
        
        self.show_game_screen()
        
    def back_to_story(self):
        """Go back to story selection"""
        self.story_selected = False
        self.story_data = None
        self.character_data = None
        self.selected_character = None
        self.current_row = 1
        self.story_history = []
        
        # Clear game-specific UI elements
        self.action_entry = None
        self.story_text = None
        self.game_buttons_layout = None
        
        self.show_story_selection()
        
    def quit_game(self):
        """Quit the current game and return to story selection"""
        self.back_to_story()
        
    def reset_game(self):
        """Reset the game (same as quit)"""
        self.quit_game()
        
    def update_story_display(self):
        if not self.story_text:
            return
            
        # Clear the text browser
        self.story_text.clear()
        
        # Create text cursor for formatting
        cursor = self.story_text.textCursor()
        
        # Computer text format (dark blue)
        computer_format = QTextCharFormat()
        computer_format.setForeground(QColor("#000080"))  # Dark blue
        computer_format.setFont(self.fixed_font)
        
        # Player text format (dark red - bold)
        player_format = QTextCharFormat()
        player_format.setForeground(QColor("#8B0000"))  # Dark red
        player_format.setFont(self.fixed_font)
        player_format.setFontWeight(QFont.Bold)
        
        # Header format (dark green - bold)
        header_format = QTextCharFormat()
        header_format.setForeground(QColor("#006400"))  # Dark green
        header_format.setFont(self.fixed_font)
        header_format.setFontWeight(QFont.Bold)
        
        # Success format (dark green)
        success_format = QTextCharFormat()
        success_format.setForeground(QColor("#006400"))  # Dark green
        success_format.setFont(self.fixed_font)
        success_format.setFontWeight(QFont.Bold)
        
        # Failure format (dark red)
        failure_format = QTextCharFormat()
        failure_format.setForeground(QColor("#8B0000"))  # Dark red
        failure_format.setFont(self.fixed_font)
        failure_format.setFontWeight(QFont.Bold)
        
        # Show history with visual distinction
        for i, history in enumerate(self.story_history):
            # Challenge header
            cursor.insertText(f"[CHALLENGE {i+1}] ", header_format)
            cursor.insertText(history['prompt'] + "\n", computer_format)
            
            # Player action
            cursor.insertText(">>> YOU: ", player_format)
            cursor.insertText(history['action'] + "\n", player_format)
            
            # Outcome
            outcome_text = history['response']
            if "Success!" in outcome_text or "✓" in outcome_text:
                cursor.insertText("<<< RESULT: ", success_format)
                cursor.insertText(outcome_text + "\n\n", success_format)
            elif "Failed." in outcome_text or "✗" in outcome_text:
                cursor.insertText("<<< RESULT: ", failure_format)
                cursor.insertText(outcome_text + "\n\n", failure_format)
            else:
                cursor.insertText("<<< RESULT: " + outcome_text + "\n\n", computer_format)
        
        # Show current challenge
        if self.current_row <= len(self.story_data):
            cursor.insertText("[CURRENT CHALLENGE] ", header_format)
            current_prompt = self.story_data.iloc[self.current_row - 1]['Prompt']
            cursor.insertText(current_prompt + "\n\n", computer_format)
        else:
            cursor.insertText("========================================\n", header_format)
            cursor.insertText("🎉 ADVENTURE COMPLETE! 🎉\n", success_format)
            cursor.insertText("========================================\n\n", header_format)
            cursor.insertText("Well, that's all the story there is for now! Thanks for playing!\n", computer_format)
            
        self.story_text.setTextCursor(cursor)
        
        # Scroll to bottom
        self.story_text.moveCursor(QTextCursor.End)
        
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(f"Progress: {self.current_row}/{len(self.story_data)}")
        
    def submit_action(self):
        # Safety check - only process if game is active
        if not self.game_started or not self.story_data or not self.action_entry:
            return
            
        action = self.action_entry.text().strip()
        if not action:
            QMessageBox.warning(self, "Warning", "Please enter an action")
            return
            
        if self.current_row > len(self.story_data):
            return
            
        # Disable input during processing
        self.action_entry.setEnabled(False)
        
        # Use worker thread to avoid blocking GUI
        self.worker = WorkerThread(self.process_action, action)
        self.worker.finished.connect(self.on_action_processed)
        self.worker.start()
        
    def process_action(self, action):
        # Safety check
        if not self.story_data or not self.selected_character:
            return {'error': 'Game state invalid'}
            
        current_story = self.story_data.iloc[self.current_row - 1]
        
        # Build context
        character_prompt = f"The user has chosen the character: {self.selected_character['Character']}\nwhich has the characteristics of {self.selected_character['Description']}"
        
        history_text = ""
        if self.story_history:
            for i, h in enumerate(self.story_history):
                history_text += f"\n--- Previous Challenge {i+1} ---\nChallenge: {h['prompt']}\nPlayer Action: {h['action']}\nOutcome: {h['response']}\n"
                
        context = f"{character_prompt}{history_text}\n--- Current Challenge ---\nChallenge: {current_story['Prompt']}"
        
        goal = current_story['Goal']
        relevant_skill = current_story['Relevant_skill']
        relevant_skill_level = int(self.selected_character[relevant_skill])
        
        # Evaluate input
        input_value = self.input_evaluation_function(goal, context, action)
        random_value = random.randint(1, 10)
        success = (input_value + relevant_skill_level + random_value) >= current_story['Difficulty']
        
        # Generate response
        response = self.response_generate_function(goal, context, action, success)
        
        result_msg = f"{'✓ Success!' if success else '✗ Failed.'} Your idea: {input_value}/10, Skill ({relevant_skill}): {relevant_skill_level}, Luck: {random_value}/10\n\n{response}"
        
        return {
            'action': action,
            'prompt': current_story['Prompt'],
            'result_msg': result_msg,
            'success': success
        }
        
    def on_action_processed(self, result):
        # Safety check
        if not self.story_data or not self.action_entry:
            return
            
        if 'error' in result:
            QMessageBox.critical(self, "Error", f"Processing error: {result['error']}")
            self.action_entry.setEnabled(True)
            return
            
        # Add to history
        self.story_history.append({
            'prompt': result['prompt'],
            'action': result['action'],
            'response': result['result_msg'],
            'success': result['success']
        })
        
        # Move to next challenge if successful
        if result['success']:
            self.current_row += 1
            self.action_entry.clear()
            
        # Re-enable input and update display
        self.action_entry.setEnabled(True)
        self.update_story_display()
        
        # Show result popup
        title = "Success!" if result['success'] else "Not Quite..."
        QMessageBox.information(self, title, result['result_msg'])
        
    def skip_challenge(self):
        # Safety check
        if not self.game_started or not self.story_data:
            return
            
        if self.current_row > len(self.story_data):
            return
            
        current_prompt = self.story_data.iloc[self.current_row - 1]['Prompt']
        self.story_history.append({
            'prompt': current_prompt,
            'action': "(skipped)",
            'response': "(Skipped)",
            'success': True
        })
        
        self.current_row += 1
        if self.action_entry:
            self.action_entry.clear()
        self.update_story_display()
        
    # Ollama API functions
    def call_ollama(self, prompt, format_schema=None):
        url = f"{self.ollama_server}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False
        }
        
        if format_schema:
            payload["format"] = format_schema
            
        headers = {}
        if self.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.ollama_api_key}"
            
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            print(f"Ollama API error: {e}")
            return '{"input_evaluation_numeric": 5}' if "input_evaluation" in prompt else '{"success_failure_string": "Default response due to API error"}'
    
    def input_evaluation_function(self, goal, context, user_input):
        base_prompt = 'Background: Please assume the role of a fun and silly text based adventure prompt. Keep the tone consistent with the context_input so far. Keep it appropriate for a 6 year old user. You will need to respond to context.'
        
        evaluation_prompt = 'Based on the context, user input, and goal, evaluate how likely it is that the user input would achieve the goal on a scale of 1 to 10. One is something that is very unlikely to work. Return only a numeric response between 1 and 10.'
        
        full_prompt = f"{base_prompt}\n---\nInstructions = \n{evaluation_prompt}\n---\ngoal_input =\n{goal}\n---\ncontext_input =\n{context}\n---\nuser_input =\n{user_input}"
        
        format_schema = {
            "type": "object",
            "properties": {"input_evaluation_numeric": {"type": "integer"}},
            "required": ["input_evaluation_numeric"]
        }
        
        response = self.call_ollama(full_prompt, format_schema)
        try:
            return int(json.loads(response)["input_evaluation_numeric"])
        except:
            return 5  # Default value
            
    def response_generate_function(self, goal, context, user_input, success):
        base_prompt = 'Background: Please assume the role of a fun and silly text based adventure prompt. Keep the tone consistent with the context_input so far. Keep it appropriate for a 6 year old user. You will need to respond to context.'
        
        if success:
            prompt_text = 'IMPORTANT: The character SUCCEEDED and achieved the goal! The math shows they succeeded. Based on the context, character, and user input, explain in 2-3 sentences how the character was SUCCESSFUL in achieving the goal. Be creative and silly. Focus ONLY on the current goal and action, not previous challenges. The outcome must be positive and show success. Return only a string.'
        else:
            prompt_text = 'IMPORTANT: The character FAILED to achieve the goal! The math shows they failed. Based on the context, character, and user input, explain in 2-3 sentences how the character was UNSUCCESSFUL and why their action did not work. Be creative and silly. Focus ONLY on the current goal and action, not previous challenges. The outcome must show failure and what went wrong. Return only a string.'
            
        full_prompt = f"{base_prompt}\n---\nInstructions = \n{prompt_text}\n---\ngoal_input =\n{goal}\n---\ncontext_input =\n{context}\n---\nuser_input =\n{user_input}"
        
        format_schema = {
            "type": "object",
            "properties": {"success_failure_string": {"type": "string"}},
            "required": ["success_failure_string"]
        }
        
        response = self.call_ollama(full_prompt, format_schema)
        try:
            return json.loads(response)["success_failure_string"]
        except:
            return "The adventure continues in an unexpected way!"

def main():
    app = QApplication(sys.argv)
    window = HeelTurnAdventure()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
