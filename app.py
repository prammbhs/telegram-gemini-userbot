import customtkinter as ctk
import asyncio
import threading
from userbot import GeminiUserbot
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# Configure appearance
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class UserbotApp:
    def __init__(self):
        # Set modern appearance 
        ctk.set_appearance_mode("System")  # Can be "System", "Dark" or "Light"
        ctk.set_default_color_theme("blue")  # More modern color theme
        
        self.app = ctk.CTk()
        self.app.title("Telegram Gemini Userbot")
        self.app.geometry("800x700")  # Wider window for better layout
        self.app.resizable(True, True)
        self.app.minsize(650, 600)  # Set minimum size
        
        # Load icons if available
        self.icons = self.load_icons()
        
        self.userbot = None
        self.userbot_thread = None
        
        # Create a scrollable frame for all content with better padding
        self.main_container = ctk.CTkScrollableFrame(self.app, corner_radius=10)
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.setup_ui()
        
    def load_icons(self):
        """Load icons for the UI"""
        icons_dir = os.path.join(os.path.dirname(__file__), "icons")
        icons = {}
        
        # Define default icons even if files don't exist
        icon_files = {
            "start": "play.png", 
            "stop": "stop.png",
            "settings": "settings.png",
            "analytics": "chart.png",
            "file": "file.png",
            "link": "link.png",
            "stats": "stats.png",
            "learn": "brain.png"
        }
        
        # Try to load icons if directory exists
        if os.path.exists(icons_dir):
            for name, filename in icon_files.items():
                icon_path = os.path.join(icons_dir, filename)
                if os.path.exists(icon_path):
                    try:
                        image = Image.open(icon_path)
                        image = image.resize((20, 20), Image.LANCZOS)
                        icons[name] = ImageTk.PhotoImage(image)
                    except Exception as e:
                        print(f"Error loading icon {filename}: {e}")
        
        return icons
    
    def setup_ui(self):
        # Create modern header with gradient effect
        self.header_frame = ctk.CTkFrame(self.main_container, corner_radius=10, 
                                        fg_color=("lightblue", "#1f538d"))
        self.header_frame.pack(fill="x", pady=(0, 15))
        
        # Header with title and version
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="Telegram Gemini AI Userbot", 
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=("black", "white")
        )
        self.title_label.pack(pady=15)
        
        self.version_label = ctk.CTkLabel(
            self.header_frame,
            text="v1.0",
            font=ctk.CTkFont(size=12),
            text_color=("black", "white")
        )
        self.version_label.pack(pady=(0, 10))
        
        # Create tabview for better organization
        self.tabs = ctk.CTkTabview(self.main_container, corner_radius=10)
        self.tabs.pack(fill="x", pady=10)
        
        # Create tabs for different sections
        self.main_tab = self.tabs.add("Main Settings")
        self.resources_tab = self.tabs.add("Resources")
        self.advanced_tab = self.tabs.add("Advanced")
        
        # Set initial tab
        self.tabs.set("Main Settings")
        
        # Group ID input with better styling
        self.group_frame = ctk.CTkFrame(self.main_tab, corner_radius=8)
        self.group_frame.pack(fill="x", pady=10, padx=15)
        
        self.group_label = ctk.CTkLabel(
            self.group_frame, 
            text="Target Group Username/ID:",
            font=ctk.CTkFont(weight="bold", size=14)
        )
        self.group_label.pack(anchor="w", padx=12, pady=(12, 5))
        
        self.group_entry = ctk.CTkEntry(self.group_frame, width=400, height=35, corner_radius=8)
        self.group_entry.pack(padx=12, pady=(0, 12), fill="x")
        self.group_entry.insert(0, "@group_username")
        
        # Super Context input with better styling
        self.context_frame = ctk.CTkFrame(self.main_tab, corner_radius=8)
        self.context_frame.pack(fill="x", pady=10, padx=15)
        
        self.context_label = ctk.CTkLabel(
            self.context_frame, 
            text="Super Context (Topic):",
            font=ctk.CTkFont(weight="bold", size=14)
        )
        self.context_label.pack(anchor="w", padx=12, pady=(12, 5))
        
        self.context_text = ctk.CTkTextbox(
            self.context_frame, 
            height=100, 
            corner_radius=8,
            border_width=1,
            border_color=("gray75", "gray30")
        )
        self.context_text.pack(padx=12, pady=(0, 12), fill="x")
        self.context_text.insert("1.0", "Discuss the latest trends in AI technology")
        
        # Duration input with better styling
        self.duration_frame = ctk.CTkFrame(self.main_tab, corner_radius=8)
        self.duration_frame.pack(fill="x", pady=10, padx=15)
        
        self.duration_label = ctk.CTkLabel(
            self.duration_frame, 
            text="Duration (minutes):",
            font=ctk.CTkFont(weight="bold", size=14)
        )
        self.duration_label.pack(anchor="w", padx=12, pady=(12, 5))
        
        # Add slider value display on the same row as the slider
        self.slider_container = ctk.CTkFrame(self.duration_frame, fg_color="transparent")
        self.slider_container.pack(fill="x", padx=12, pady=(0, 12))
        
        self.duration_slider = ctk.CTkSlider(
            self.slider_container, 
            from_=5, 
            to=60,
            number_of_steps=11,
            command=self.update_duration_label,
            width=350
        )
        self.duration_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.duration_slider.set(30)
        
        self.duration_value_label = ctk.CTkLabel(
            self.slider_container, 
            text="30 minutes",
            width=80,
            font=ctk.CTkFont(size=13)
        )
        self.duration_value_label.pack(side="right")
        
        # Resources tab content
        self.setup_resources_tab()
        
        # Advanced tab content
        self.setup_advanced_tab()
        
        # Status display with better visualization
        self.status_frame = ctk.CTkFrame(self.main_container, corner_radius=8)
        self.status_frame.pack(fill="x", pady=15)
        
        self.status_indicator = ctk.CTkLabel(
            self.status_frame,
            text="●",
            font=ctk.CTkFont(size=20),
            text_color="red"  # Red for not running
        )
        self.status_indicator.pack(side="left", padx=(15, 5), pady=12)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame, 
            text="Not Running",
            font=ctk.CTkFont(weight="bold", size=14)
        )
        self.status_label.pack(side="left", pady=12)
        
        # Log display with better styling
        self.log_frame = ctk.CTkFrame(self.main_container, corner_radius=8)
        self.log_frame.pack(fill="both", expand=True, pady=10)
        
        self.log_header = ctk.CTkFrame(self.log_frame, corner_radius=0, height=30,
                                      fg_color=("gray85", "gray25"))
        self.log_header.pack(fill="x")
        
        self.log_label = ctk.CTkLabel(
            self.log_header, 
            text="Activity Log",
            font=ctk.CTkFont(weight="bold")
        )
        self.log_label.pack(anchor="w", padx=10, pady=5)
        
        self.log_text = ctk.CTkTextbox(
            self.log_frame, 
            state="disabled", 
            height=150,
            corner_radius=0
        )
        self.log_text.pack(padx=0, pady=0, fill="both", expand=True)
        
        # Control buttons with better styling and icons
        self.button_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.button_frame.pack(fill="x", pady=15)

        # Start button with icon if available
        self.start_button = ctk.CTkButton(
            self.button_frame, 
            text="Start Bot", 
            command=self.start_bot,
            fg_color="#28a745",  # Green
            hover_color="#218838",  # Darker green
            width=200,
            height=40,
            corner_radius=8,
            image=self.icons.get("start"),
            compound="left"
        )
        self.start_button.pack(side="left", padx=10, pady=10)
        
        # Stop button with icon if available
        self.stop_button = ctk.CTkButton(
            self.button_frame, 
            text="Stop Bot", 
            command=self.stop_bot,
            fg_color="#dc3545",  # Red
            hover_color="#c82333",  # Darker red
            state="disabled",
            width=200,
            height=40,
            corner_radius=8,
            image=self.icons.get("stop"),
            compound="left"
        )
        self.stop_button.pack(side="right", padx=10, pady=10)
        
        # Theme toggle in footer
        self.footer_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.footer_frame.pack(fill="x", pady=(0, 5))
        
        self.appearance_label = ctk.CTkLabel(
            self.footer_frame,
            text="Theme:",
            font=ctk.CTkFont(size=12)
        )
        self.appearance_label.pack(side="left", padx=(10, 5))
        
        self.appearance_mode = ctk.CTkOptionMenu(
            self.footer_frame,
            values=["System", "Light", "Dark"],
            command=self.change_appearance_mode,
            width=100,
            height=25,
            corner_radius=5
        )
        self.appearance_mode.pack(side="left")
        
    def setup_resources_tab(self):
        """Set up the resources tab content"""
        # Resources Management section
        self.resources_label = ctk.CTkLabel(
            self.resources_tab, 
            text="Resources Management", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.resources_label.pack(anchor="w", padx=15, pady=(15, 10))
        
        self.resources_description = ctk.CTkLabel(
            self.resources_tab,
            text="Add files or URLs to enhance the bot's knowledge",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70")
        )
        self.resources_description.pack(anchor="w", padx=15, pady=(0, 15))
        
        self.resources_buttons_frame = ctk.CTkFrame(self.resources_tab, fg_color="transparent")
        self.resources_buttons_frame.pack(fill="x", padx=15, pady=5)
        
        self.add_file_button = ctk.CTkButton(
            self.resources_buttons_frame,
            text="Add File",
            command=self.add_file_resource,
            width=120,
            height=32,
            corner_radius=8,
            image=self.icons.get("file"),
            compound="left"
        )
        self.add_file_button.pack(side="left", padx=5, pady=5)
        
        self.add_url_button = ctk.CTkButton(
            self.resources_buttons_frame,
            text="Add URL",
            command=self.add_url_resource,
            width=120,
            height=32,
            corner_radius=8,
            image=self.icons.get("link"),
            compound="left"
        )
        self.add_url_button.pack(side="left", padx=5, pady=5)
        
        self.view_resources_button = ctk.CTkButton(
            self.resources_buttons_frame,
            text="View Resources",
            command=self.show_resources,
            width=120,
            height=32,
            corner_radius=8
        )
        self.view_resources_button.pack(side="right", padx=5, pady=5)
        
        self.resources_status = ctk.CTkLabel(
            self.resources_tab,
            text="No resources added yet",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70")
        )
        self.resources_status.pack(padx=15, pady=10)
        
    def setup_advanced_tab(self):
        """Set up the advanced tab content"""
        # Analytics section
        self.analytics_label = ctk.CTkLabel(
            self.advanced_tab, 
            text="Session Analytics", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.analytics_label.pack(anchor="w", padx=15, pady=(15, 10))
        
        self.analytics_description = ctk.CTkLabel(
            self.advanced_tab,
            text="View detailed analytics about the current session",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70")
        )
        self.analytics_description.pack(anchor="w", padx=15, pady=(0, 15))

        self.analytics_button = ctk.CTkButton(
            self.advanced_tab,
            text="View Analytics",
            command=self.show_analytics,
            width=160,
            height=32,
            corner_radius=8,
            image=self.icons.get("analytics"),
            compound="left"
        )
        self.analytics_button.pack(anchor="w", padx=15, pady=5)
        
        # Learning section
        self.learning_label = ctk.CTkLabel(
            self.advanced_tab, 
            text="Response Learning", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.learning_label.pack(anchor="w", padx=15, pady=(25, 10))
        
        self.learning_description = ctk.CTkLabel(
            self.advanced_tab,
            text="Configure how the bot learns from interactions",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70")
        )
        self.learning_description.pack(anchor="w", padx=15, pady=(0, 15))

        # Create a frame for the learning controls
        self.learning_controls_frame = ctk.CTkFrame(self.advanced_tab, fg_color="transparent")
        self.learning_controls_frame.pack(fill="x", padx=15, pady=5)

        # Learning toggle
        self.learning_var = tk.BooleanVar(value=True)
        self.learning_checkbox = ctk.CTkCheckBox(
            self.learning_controls_frame,
            text="Enable Learning",
            variable=self.learning_var,
            command=self.toggle_learning,
            width=30,
            corner_radius=4
        )
        self.learning_checkbox.pack(side="left", padx=5, pady=5)

        # Learn from logs button
        self.learn_logs_button = ctk.CTkButton(
            self.learning_controls_frame,
            text="Learn From Past Logs",
            command=self.learn_from_logs,
            width=160,
            height=32,
            corner_radius=8,
            image=self.icons.get("learn"),
            compound="left"
        )
        self.learn_logs_button.pack(side="left", padx=15, pady=5)
        
        # View learning stats button
        self.learning_stats_button = ctk.CTkButton(
            self.learning_controls_frame,
            text="View Learning Stats",
            command=self.show_learning_stats,
            width=160,
            height=32,
            corner_radius=8,
            image=self.icons.get("stats"),
            compound="left"
        )
        self.learning_stats_button.pack(side="right", padx=5, pady=5)

        self.learning_status = ctk.CTkLabel(
            self.advanced_tab,
            text="Learning enabled - bot will improve over time",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70")
        )
        self.learning_status.pack(padx=15, pady=10)
    
    def update_duration_label(self, value):
        """Update the duration label when slider moves"""
        minutes = int(value)
        self.duration_value_label.configure(text=f"{minutes} minutes")
    
    def change_appearance_mode(self, new_appearance_mode):
        """Change the app's appearance mode"""
        ctk.set_appearance_mode(new_appearance_mode)
    
    def log_message(self, message):
        """Add a message to the log display with timestamp"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{formatted_message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def start_bot(self):
        """Start the userbot"""
        group = self.group_entry.get().strip()
        context = self.context_text.get("1.0", "end").strip()
        duration = int(self.duration_slider.get())
        
        if not group or not context:
            self.log_message("Error: Please fill in all fields")
            return
        
        self.log_message(f"Starting bot in group: {group}")
        self.log_message(f"Super Context: {context}")
        self.log_message(f"Duration: {duration} minutes")
        
        # Update UI
        self.status_indicator.configure(text_color="#28a745")  # Green
        self.status_label.configure(text="Running")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        
        # Create and start userbot in separate thread
        self.userbot = GeminiUserbot(context, group, duration)
        
        # Apply current learning setting
        is_learning_enabled = self.learning_var.get()
        self.userbot.set_learning_enabled(is_learning_enabled)
        self.log_message(f"Response learning {'enabled' if is_learning_enabled else 'disabled'}")
        
        # Update resource count if there are any pre-loaded resources
        self.update_resource_count()
        
        def run_bot():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.userbot.start())
            except Exception as e:
                self.app.after(0, lambda: self.handle_bot_error(e))
            finally:
                # Close the loop properly
                pending = asyncio.all_tasks(loop)
                if pending:
                    for task in pending:
                        task.cancel()
                    # Allow cancelled tasks to complete
                    try:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        pass
                loop.close()
                # Update UI when bot stops
                self.app.after(0, self.bot_stopped)
        
        self.userbot_thread = threading.Thread(target=run_bot)
        self.userbot_thread.daemon = True
        self.userbot_thread.start()
    
    def handle_bot_error(self, error):
        """Handle bot errors and display appropriate messages"""
        import telethon.errors as telethon_errors
        
        if isinstance(error, telethon_errors.rpcerrorlist.ChatWriteForbiddenError):
            self.log_message("ERROR: Bot does not have permission to write in this chat.")
            self.log_message("Please ensure you have write permissions in the group or channel.")
            messagebox.showerror("Permission Error", 
                                "You don't have permission to write in this chat.\n\n"
                                "Possible causes:\n"
                                "- You are not a member of the group\n"
                                "- You are restricted from sending messages\n"
                                "- The group has restricted message sending\n\n"
                                "Please check your permissions and try again.")
        elif isinstance(error, telethon_errors.rpcerrorlist.FloodWaitError):
            wait_time = getattr(error, 'seconds', 60)
            self.log_message(f"ERROR: Telegram rate limit exceeded. Wait for {wait_time} seconds.")
            messagebox.showerror("Rate Limit", f"Telegram rate limit exceeded. Please wait for {wait_time} seconds before trying again.")
        else:
            error_message = str(error)
            self.log_message(f"ERROR: {error_message}")
            messagebox.showerror("Bot Error", f"An error occurred: {error_message}")
            
        # Reset the UI state
        self.status_indicator.configure(text_color="red")
        self.status_label.configure(text="Error")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
    
    def stop_bot(self):
        """Stop the userbot"""
        if self.userbot:
            self.log_message("Stopping bot...")
            
            # Stop the userbot in a separate thread
            def stop_bot_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.userbot.stop())
                except Exception as e:
                    self.app.after(0, lambda: self.log_message(f"Error during shutdown: {e}"))
                finally:
                    # Proper cleanup
                    pending = asyncio.all_tasks(loop)
                    if pending:
                        for task in pending:
                            task.cancel()
                        try:
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        except Exception:
                            pass
                    loop.close()
                    
                    # Update UI when bot stops
                    self.app.after(0, self.bot_stopped)
            
            stop_thread = threading.Thread(target=stop_bot_thread)
            stop_thread.daemon = True
            stop_thread.start()
    
    def bot_stopped(self):
        """Called when the bot stops"""
        self.log_message("Bot stopped")
        self.status_indicator.configure(text_color="red")
        self.status_label.configure(text="Not Running")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
    
    def add_file_resource(self):
        """Add a file resource"""
        filetypes = [
            ("Document Files", "*.pdf;*.txt;*.docx"),
            ("PDF Files", "*.pdf"),
            ("Text Files", "*.txt"),
            ("Word Documents", "*.docx"),
            ("All Files", "*.*")
        ]
        
        file_path = filedialog.askopenfilename(
            title="Select a resource file",
            filetypes=filetypes
        )
        
        if not file_path:
            return
        
        # Get description
        description = self.prompt_for_description(os.path.basename(file_path))
        
        if self.userbot:
            self.process_resource_addition(file_path, description)
        else:
            self.log_message("Create a bot instance first by filling in details and clicking 'Start Bot'")

    def add_url_resource(self):
        """Add a URL resource"""
        url_window = tk.Toplevel(self.app)
        url_window.title("Add URL Resource")
        url_window.geometry("400x150")
        url_window.resizable(False, False)
        
        url_label = tk.Label(url_window, text="Enter URL:")
        url_label.pack(pady=(10, 0))
        
        url_entry = tk.Entry(url_window, width=50)
        url_entry.pack(pady=5, padx=10)
        
        def submit_url():
            url = url_entry.get().strip()
            if not url:
                messagebox.showerror("Error", "URL cannot be empty")
                return
                
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            description = self.prompt_for_description(url)
            
            if self.userbot:
                self.process_resource_addition(url, description)
            else:
                self.log_message("Create a bot instance first by filling in details and clicking 'Start Bot'")
                
            url_window.destroy()
        
        submit_button = tk.Button(url_window, text="Add URL", command=submit_url)
        submit_button.pack(pady=10)

    def prompt_for_description(self, default_name):
        """Prompt user for resource description"""
        desc_window = tk.Toplevel(self.app)
        desc_window.title("Resource Description")
        desc_window.geometry("400x150")
        desc_window.resizable(False, False)
        
        desc_label = tk.Label(desc_window, text="Enter a description for this resource:")
        desc_label.pack(pady=(10, 0))
        
        desc_entry = tk.Entry(desc_window, width=50)
        desc_entry.insert(0, default_name)
        desc_entry.pack(pady=5, padx=10)
        
        description = [default_name]  # Use a list to store the value from the callback
        
        def submit_desc():
            description[0] = desc_entry.get().strip()
            if not description[0]:
                description[0] = default_name
            desc_window.destroy()
        
        submit_button = tk.Button(desc_window, text="Save Description", command=submit_desc)
        submit_button.pack(pady=10)
        
        # Wait for the window to be destroyed
        self.app.wait_window(desc_window)
        
        return description[0]

    def process_resource_addition(self, resource_path, description):
        """Process adding a resource asynchronously"""
        self.log_message(f"Adding resource: {resource_path}")
        
        def add_resource_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            success, result = loop.run_until_complete(
                self.userbot.add_resource(resource_path, description)
            )
            
            loop.close()
            
            # Update UI from main thread
            if success:
                self.app.after(0, lambda: self.log_message(f"Resource added successfully: {description}"))
                self.app.after(0, lambda: self.update_resource_count())
            else:
                self.app.after(0, lambda: self.log_message(f"Failed to add resource: {result}"))
        
        # Run in a separate thread
        thread = threading.Thread(target=add_resource_thread)
        thread.daemon = True
        thread.start()

    def update_resource_count(self):
        """Update the resource count display"""
        if self.userbot:
            resources = self.userbot.get_resources()
            count = len(resources)
            self.resources_status.configure(text=f"{count} resource(s) added")

    def show_resources(self):
        """Show a list of all added resources"""
        if not self.userbot:
            self.log_message("Create a bot instance first by filling in details and clicking 'Start Bot'")
            return
            
        resources = self.userbot.get_resources()
        
        if not resources:
            messagebox.showinfo("Resources", "No resources have been added yet")
            return
        
        resource_window = tk.Toplevel(self.app)
        resource_window.title("Added Resources")
        resource_window.geometry("600x400")
        
        # Create a frame with scrollbar
        main_frame = tk.Frame(resource_window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add resources to the scrollable frame
        tk.Label(
            scrollable_frame, 
            text="Resources", 
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        
        headers = ["Description", "Type", "Source"]
        for i, header in enumerate(headers):
            tk.Label(
                scrollable_frame,
                text=header,
                font=("Arial", 10, "bold")
            ).grid(row=1, column=i, sticky="w", padx=5, pady=5)
        
        for i, resource in enumerate(resources):
            tk.Label(
                scrollable_frame,
                text=resource['description'],
                wraplength=150
            ).grid(row=i+2, column=0, sticky="w", padx=5, pady=5)
            
            tk.Label(
                scrollable_frame,
                text=resource['type']
            ).grid(row=i+2, column=1, sticky="w", padx=5, pady=5)
            
            tk.Label(
                scrollable_frame,
                text=resource['source'],
                wraplength=250
            ).grid(row=i+2, column=2, sticky="w", padx=5, pady=5)

    def show_analytics(self):
        """Show analytics for the current session"""
        if not self.userbot:
            self.log_message("No active bot session. Start a bot first.")
            return
            
        analytics = self.userbot.get_session_analytics()
        
        if analytics["total_responses"] == 0:
            messagebox.showinfo("Session Analytics", "No responses recorded in the current session.")
            return
        
        # Create analytics window
        analytics_window = tk.Toplevel(self.app)
        analytics_window.title("Session Analytics")
        analytics_window.geometry("700x500")
        
        # Create a frame with scrollbar
        main_frame = tk.Frame(analytics_window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Session overview
        tk.Label(
            scrollable_frame, 
            text="Session Overview", 
            font=("Arial", 16, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        # Session duration
        tk.Label(
            scrollable_frame,
            text="Session Duration:",
            font=("Arial", 10, "bold")
        ).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        tk.Label(
            scrollable_frame,
            text=f"{analytics['session_duration_minutes']} minutes"
        ).grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Total responses
        tk.Label(
            scrollable_frame,
            text="Total Responses:",
            font=("Arial", 10, "bold")
        ).grid(row=2, column=0, sticky="w", padx=5, pady=5)
        
        tk.Label(
            scrollable_frame,
            text=str(analytics['total_responses'])
        ).grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        # Average words
        tk.Label(
            scrollable_frame,
            text="Avg Words Per Response:",
            font=("Arial", 10, "bold")
        ).grid(row=3, column=0, sticky="w", padx=5, pady=5)
        
        tk.Label(
            scrollable_frame,
            text=str(analytics['average_words_per_response'])
        ).grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        # Emoji usage
        tk.Label(
            scrollable_frame,
            text="Emoji Usage:",
            font=("Arial", 10, "bold")
        ).grid(row=4, column=0, sticky="w", padx=5, pady=5)
        
        tk.Label(
            scrollable_frame,
            text=f"{analytics['emoji_usage_percentage']}%"
        ).grid(row=4, column=1, sticky="w", padx=5, pady=5)
        
        # Users engaged
        tk.Label(
            scrollable_frame,
            text="Users Engaged:",
            font=("Arial", 10, "bold")
        ).grid(row=5, column=0, sticky="w", padx=5, pady=5)
        
        tk.Label(
            scrollable_frame,
            text=str(analytics['unique_users_engaged'])
        ).grid(row=5, column=1, sticky="w", padx=5, pady=5)
        
        # Response types heading
        tk.Label(
            scrollable_frame, 
            text="Response Types", 
            font=("Arial", 14, "bold")
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        # Response types
        row = 7
        for response_type, count in analytics['response_types'].items():
            # Make the response type more readable
            readable_type = response_type.replace('_', ' ').title()
            
            tk.Label(
                scrollable_frame,
                text=readable_type + ":",
                font=("Arial", 10)
            ).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            
            tk.Label(
                scrollable_frame,
                text=str(count)
            ).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            
            row += 1
        
        # Topics heading
        tk.Label(
            scrollable_frame, 
            text="Top Topics", 
            font=("Arial", 14, "bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        row += 1
        
        # Top topics
        for topic, count in analytics['top_topics']:
            tk.Label(
                scrollable_frame,
                text=topic,
                wraplength=300
            ).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            
            tk.Label(
                scrollable_frame,
                text=str(count)
            ).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            
            row += 1
        
        # Button to export full log
        def export_log():
            file_path = self.userbot.ai.save_session_log()
            messagebox.showinfo("Log Exported", f"Session log exported to:\n{file_path}")
            
        export_button = tk.Button(
            scrollable_frame,
            text="Export Full Session Log",
            command=export_log
        )
        export_button.grid(row=row+1, column=0, columnspan=2, pady=20)

    def toggle_learning(self):
        """Toggle learning on/off"""
        is_enabled = self.learning_var.get()
        
        if self.userbot:
            self.userbot.set_learning_enabled(is_enabled)
            
        status_text = "Learning enabled - bot will improve over time" if is_enabled else "Learning disabled"
        self.learning_status.configure(text=status_text)
        self.log_message(f"Response learning {'enabled' if is_enabled else 'disabled'}")

    def learn_from_logs(self):
        """Process all logs to learn patterns"""
        if not self.userbot:
            self.log_message("Create a bot instance first by filling in details and clicking 'Start Bot'")
            return
            
        self.log_message("Processing previous logs to learn response patterns...")
        
        def learn_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            patterns_learned = self.userbot.learn_from_past_logs()
            
            # Update UI from main thread
            self.app.after(0, lambda: self.log_message(f"Learning complete! Learned {patterns_learned} patterns from previous logs"))
            
        # Run in a separate thread
        thread = threading.Thread(target=learn_thread)
        thread.daemon = True
        thread.start()

    def show_learning_stats(self):
        """Show statistics about what has been learned"""
        if not self.userbot:
            self.log_message("Create a bot instance first by filling in details and clicking 'Start Bot'")
            return
            
        stats = self.userbot.get_learning_stats()
        
        if stats["topics_learned"] == 0:
            messagebox.showinfo("Learning Stats", "No learning data available yet. Start a bot session or click 'Learn From Past Logs'.")
            return
        
        # Create stats window
        stats_window = tk.Toplevel(self.app)
        stats_window.title("Learning Statistics")
        stats_window.geometry("500x400")
        
        # Create a frame for the content
        main_frame = tk.Frame(stats_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Add stats heading
        tk.Label(
            main_frame, 
            text="Bot Learning Statistics", 
            font=("Arial", 16, "bold")
        ).pack(pady=(0, 20))
        
        # Stats labels
        stats_items = [
            ("Topics Learned", stats["topics_learned"]),
            ("Questions & Answers", stats["questions_learned"]),
            ("Users Tracked", stats["users_tracked"]),
            ("Response Types with Emoji Patterns", stats["response_types_with_emojis"]),
            ("Total Responses Remembered", stats["total_responses_remembered"])
        ]
        
        for label, value in stats_items:
            frame = tk.Frame(main_frame)
            frame.pack(fill="x", pady=5)
            
            tk.Label(
                frame,
                text=label + ":",
                font=("Arial", 11, "bold"),
                width=30,
                anchor="w"
            ).pack(side="left")
            
            tk.Label(
                frame,
                text=str(value),
                font=("Arial", 11)
            ).pack(side="left", padx=10)
        
        # Add an explanation of what this means
        explanation = """
        The bot learns from each conversation to improve future responses.
        
        It remembers successful topic responses, question-answer pairs,
        emoji usage patterns, and interaction preferences for each user.
        
        This data is used to make conversations feel more natural and
        consistent over time as the bot adapts to your style.
        """
        
        explanation_frame = tk.Frame(main_frame)
        explanation_frame.pack(fill="x", pady=15)
        
        tk.Label(
            explanation_frame,
            text=explanation,
            font=("Arial", 10),
            justify="left",
            wraplength=460
        ).pack()
        
        # Add buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill="x", pady=15)
        
        def reset_learning():
            if messagebox.askyesno("Reset Learning", "Are you sure you want to reset all learned patterns? This cannot be undone."):
                # Create a new learning manager to reset everything
                if self.userbot:
                    self.userbot.ai.learning_manager = LearningManager()
                    self.userbot.ai.learning_manager.save_learned_patterns()
                    self.log_message("Learning data has been reset")
                    stats_window.destroy()
        
        reset_button = tk.Button(
            button_frame,
            text="Reset Learning Data",
            command=reset_learning
        )
        reset_button.pack(side="left", padx=10)
        
        close_button = tk.Button(
            button_frame,
            text="Close",
            command=stats_window.destroy
        )
        close_button.pack(side="right", padx=10)

    def run(self):
        """Run the application"""
        # Add initial log message
        self.log_message("Application started. Fill in details and click 'Start Bot'")
        self.app.mainloop()

if __name__ == "__main__":
    app = UserbotApp()
    app.run()