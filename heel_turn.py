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
                           QLineEdit, QMessageBox, QProgressBar, QSplitter)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

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
        
        # Main content area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        
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
        title.setFont(QFont("Arial", 20, QFont.Bold))
        self.content_layout.addWidget(title)
        
        loading_label = QLabel("Scanning for stories...")
        loading_label.setFont(QFont("Arial", 12))
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
        self.clear_content()
        
        title = QLabel("Choose Your Story")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        self.content_layout.addWidget(title)
        
        # Debug info
        debug_text = QLabel(f"Found {len(self.available_stories)} stories")
        debug_text.setStyleSheet("color: green; font-size: 10px;")
        self.content_layout.addWidget(debug_text)
        
        if self.available_stories:
            self.story_combo = QComboBox()
            self.story_combo.addItems(self.available_stories)
            self.content_layout.addWidget(self.story_combo)
            
            select_btn = QPushButton("Select Story")
            select_btn.clicked.connect(self.select_story)
            self.content_layout.addWidget(select_btn)
        else:
            # Show detailed error info
            error_label = QLabel("No stories found. Please check:")
            error_label.setStyleSheet("color: red; font-size: 12px;")
            self.content_layout.addWidget(error_label)
            
            self.story_combo = QComboBox()
            self.story_combo.addItem("No stories available")
            self.story_combo.setEnabled(False)
            self.content_layout.addWidget(self.story_combo)
            
            select_btn = QPushButton("Select Story")
            select_btn.setEnabled(False)
            self.content_layout.addWidget(select_btn)
            
    def show_character_selection(self):
        self.clear_content()
        self.clear_sidebar()
        
        title = QLabel("Choose Your Character")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        self.content_layout.addWidget(title)
        
        self.character_combo = QComboBox()
        character_names = [row['Character'] for _, row in self.character_data.iterrows()]
        self.character_combo.addItems(character_names)
        self.character_combo.currentTextChanged.connect(self.update_character_preview)
        self.content_layout.addWidget(self.character_combo)
        
        # Character preview with image support
        self.preview_widget = QWidget()
        preview_layout = QVBoxLayout(self.preview_widget)
        
        self.character_image_label = QLabel()
        self.character_image_label.setAlignment(Qt.AlignCenter)
        self.character_image_label.setFixedSize(150, 150)
        self.character_image_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        preview_layout.addWidget(self.character_image_label)
        
        self.preview_text_label = QLabel()
        self.preview_text_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_text_label)
        
        self.content_layout.addWidget(self.preview_widget)
        
        start_btn = QPushButton("Start Adventure!")
        start_btn.clicked.connect(self.start_game)
        self.content_layout.addWidget(start_btn)
        
        back_btn = QPushButton("← Back to Story Selection")
        back_btn.clicked.connect(self.back_to_story)
        self.content_layout.addWidget(back_btn)
        
        self.update_character_preview()
        
    def show_game_screen(self):
        self.clear_content()
        self.clear_sidebar()
        
        # Character info in sidebar
        char_title = QLabel("Character Info")
        char_title.setFont(QFont("Arial", 12, QFont.Bold))
        self.sidebar_layout.addWidget(char_title)
        
        # Character image in sidebar
        self.sidebar_image_label = QLabel()
        self.sidebar_image_label.setAlignment(Qt.AlignCenter)
        self.sidebar_image_label.setFixedSize(120, 120)
        self.sidebar_image_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.sidebar_layout.addWidget(self.sidebar_image_label)
        
        if self.selected_character:
            char_name = QLabel(f"Name: {self.selected_character['Character']}")
            char_name.setFont(QFont("Arial", 10, QFont.Bold))
            self.sidebar_layout.addWidget(char_name)
            
            char_desc = QLabel(f"Description: {self.selected_character['Description']}")
            char_desc.setWordWrap(True)
            self.sidebar_layout.addWidget(char_desc)
            
        story_label = QLabel(f"Story: {self.selected_story}")
        self.sidebar_layout.addWidget(story_label)
        
        self.progress_label = QLabel(f"Progress: {self.current_row}/{len(self.story_data)}")
        self.sidebar_layout.addWidget(self.progress_label)
        
        self.sidebar_layout.addStretch()
        
        new_game_btn = QPushButton("New Game")
        new_game_btn.clicked.connect(self.reset_game)
        self.sidebar_layout.addWidget(new_game_btn)
        
        # Load character image for sidebar
        self.load_character_image_for_sidebar()
        
        # Main game content
        self.story_text = QTextEdit()
        self.story_text.setReadOnly(True)
        self.content_layout.addWidget(self.story_text)
        
        # Input area
        input_label = QLabel("What do you do?")
        self.content_layout.addWidget(input_label)
        
        self.action_entry = QLineEdit()
        self.action_entry.returnPressed.connect(self.submit_action)
        self.content_layout.addWidget(self.action_entry)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        submit_btn = QPushButton("Submit Action")
        submit_btn.clicked.connect(self.submit_action)
        btn_layout.addWidget(submit_btn)
        
        skip_btn = QPushButton("Skip Challenge")
        skip_btn.clicked.connect(self.skip_challenge)
        btn_layout.addWidget(skip_btn)
        
        quit_btn = QPushButton("Quit Game")
        quit_btn.clicked.connect(self.quit_game)
        btn_layout.addWidget(quit_btn)
        
        self.content_layout.addLayout(btn_layout)
        
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
        target_label.setStyleSheet("color: gray; font-style: italic;")
        
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
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
                
    def clear_sidebar(self):
        for i in reversed(range(self.sidebar_layout.count())):
            widget = self.sidebar_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
                
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
        self.story_selected = False
        self.story_data = None
        self.character_data = None
        self.selected_character = None
        self.show_story_selection()
        
    def update_story_display(self):
        text = ""
        
        # Show history
        for i, history in enumerate(self.story_history):
            text += f"<b>Challenge {i+1}:</b> {history['prompt']}<br/>"
            text += f"<i>Your Action:</i> {history['action']}<br/>"
            text += f"Outcome: {history['response']}<br/><br/>"
            
        # Show current challenge
        if self.current_row <= len(self.story_data):
            text += "<b>Current Challenge:</b><br/>"
            current_prompt = self.story_data.iloc[self.current_row - 1]['Prompt']
            text += f"{current_prompt}<br/><br/>"
        else:
            text += "<h3>🎉 Adventure Complete!</h3>"
            text += "Well, that's all the story there is for now! Thanks for playing!"
            
        self.story_text.setHtml(text)
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(f"Progress: {self.current_row}/{len(self.story_data)}")
        
    def submit_action(self):
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
        self.action_entry.clear()
        self.update_story_display()
        
    def quit_game(self):
        self.game_started = False
        self.story_selected = False
        self.current_row = 1
        self.story_history = []
        self.show_story_selection()
        
    def reset_game(self):
        self.quit_game()
        
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
