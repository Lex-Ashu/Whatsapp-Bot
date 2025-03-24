"""
WhatsApp OpenAI Chat Bot with GUI
---------------------------------
A WhatsApp bot that integrates with OpenAI's chat models, with a GUI for configuration and monitoring.

Requirements:
- openai
- python-dotenv
- twilio
- flask
- customtkinter
"""

import openai
import os
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext
import customtkinter as ctk
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import threading
import traceback
import time
import queue

# Load environment variables
load_dotenv()

DEFAULT_CONFIG = {
    "model": "gpt-3.5-turbo",
    "temperature": 0.7,
    "max_tokens": 1000,
    "api_key": "",  
    "server_port": 5000,
    "appearance_mode": "dark"  # "dark" or "light"
}

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "whatsapp_bot_config.json")

def load_config():
    """Load configuration from file or create default if not exists"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")

    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

app = Flask(__name__)
message_queue = queue.Queue()  # Queue for passing messages to GUI

class WhatsAppOpenAIBot:
    def __init__(self):
        self.config = load_config()
        self.conversations = {}  # Dictionary to store conversation history for each user
        self.load_api_key()
        self.running = False
        self.server_thread = None
        self.user_details = {} 
        self.load_user_details()
        
    def load_api_key(self):
        """Load API key from environment or config"""
        api_key = os.getenv("OPENAI_API_KEY")
        
        # If not in environment, try from saved config
        if not api_key and "api_key" in self.config:
            api_key = self.config.get("api_key")
        
        # Set the API key if found
        if api_key:
            openai.api_key = api_key
            return True
        return False
    
    def load_user_details(self):
        """Load saved user details"""
        user_file = os.path.join(os.path.dirname(__file__), "user_details.json")
        if os.path.exists(user_file):
            try:
                with open(user_file, 'r') as f:
                    self.user_details = json.load(f)
            except Exception as e:
                print(f"Error loading user details: {e}")
    
    def save_user_details(self):
        """Save user details"""
        user_file = os.path.join(os.path.dirname(__file__), "user_details.json")
        try:
            with open(user_file, 'w') as f:
                json.dump(self.user_details, f, indent=2)
        except Exception as e:
            print(f"Error saving user details: {e}")
    
    def get_user_name(self, user_id):
        """Get user name from phone number"""
        if user_id in self.user_details:
            return self.user_details[user_id]
        
        phone = user_id.replace('whatsapp:', '')
        
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if twilio_sid and twilio_token:
            try:
                client = Client(twilio_sid, twilio_token)
                name = phone
                self.user_details[user_id] = name
                self.save_user_details()
                return name
            except Exception:
                pass
                
        return phone
    
    def get_conversation_history(self, user_id):
        """Get conversation history for a specific user"""
        if user_id not in self.conversations:
            self.conversations[user_id] = [
                {"role": "system", "content": "You are a helpful assistant responding via WhatsApp."}
            ]
        return self.conversations[user_id]
    
    def clear_conversation(self, user_id):
        """Clear conversation history for a specific user"""
        if user_id in self.conversations:
            self.conversations[user_id] = [
                {"role": "system", "content": "You are a helpful assistant responding via WhatsApp."}
            ]
            return "Conversation history cleared. What would you like to talk about?"
        return "No conversation history found."
    
    def process_message(self, user_id, user_message):
        """Process incoming message and get response from OpenAI"""
        try:
            # Get user name for logging
            user_name = self.get_user_name(user_id)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message_queue.put(f"[{timestamp}] Received from {user_name}: {user_message}")
            
            # Check for special commands
            if user_message.lower() == "!clear":
                response = self.clear_conversation(user_id)
                message_queue.put(f"[{timestamp}] Sent to {user_name}: {response}")
                return response
            
            if user_message.lower() == "!help":
                response = (
                    "WhatsApp OpenAI Bot Help:\n"
                    "- !clear: Clear conversation history\n"
                    "- !help: Show this help message\n"
                    "- !info: Show current bot configuration\n"
                    "Just type a message to chat with the AI assistant!"
                )
                message_queue.put(f"[{timestamp}] Sent to {user_name}: {response}")
                return response
            
            if user_message.lower() == "!info":
                response = (
                    f"Bot Configuration:\n"
                    f"- Model: {self.config.get('model')}\n"
                    f"- Temperature: {self.config.get('temperature')}\n"
                    f"- Max tokens: {self.config.get('max_tokens')}"
                )
                message_queue.put(f"[{timestamp}] Sent to {user_name}: {response}")
                return response
            # Conversation histroy
            conversation = self.get_conversation_history(user_id)
            
            # Add user message to conversation history
            conversation.append({"role": "user", "content": user_message})
            
            # Check if API key is set
            if not openai.api_key:
                response = "⚠️ API key not set. Please contact the administrator."
                message_queue.put(f"[{timestamp}] Sent to {user_name}: {response}")
                return response
            
            # Log processing
            message_queue.put(f"[{timestamp}] Processing request for {user_name}...")
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model=self.config.get("model", "gpt-3.5-turbo"),
                messages=conversation,
                temperature=self.config.get("temperature", 0.7),
                max_tokens=self.config.get("max_tokens", 1000)
            )
            
            # Extract and store response
            assistant_message = response["choices"][0]["message"]["content"]
            conversation.append({"role": "assistant", "content": assistant_message})
            
            # Limit conversation history to prevent token limit issues
            if len(conversation) > 20:  # Last 20 messages including system message
                conversation = [conversation[0]] + conversation[-19:]
                self.conversations[user_id] = conversation
            
            # Log response
            message_queue.put(f"[{timestamp}] Sent to {user_name}: {assistant_message}")
            
            return assistant_message
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(f"{error_message}\n{traceback.format_exc()}")
            message_queue.put(f"[{timestamp}] ERROR: {error_message}")
            return f"Sorry, I encountered an error: {error_message}"
    
    def start_server(self):
        """Start the Flask server in a separate thread"""
        if self.running:
            return False
        
        try:
            self.running = True
            port = self.config.get("server_port", 5000)
            
            def run_server():
                app.run(debug=False, use_reloader=False, host='0.0.0.0', port=port)
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            message_queue.put(f"[INFO] Server started on port {port}")
            return True
        except Exception as e:
            self.running = False
            message_queue.put(f"[ERROR] Failed to start server: {str(e)}")
            return False
    
    def stop_server(self):
        """Stop the Flask server"""
        if not self.running:
            return
        
        import requests
        try:
            port = self.config.get("server_port", 5000)
            requests.get(f"http://localhost:{port}/shutdown")
        except:
            pass
        
        self.running = False
        message_queue.put("[INFO] Server stopped")

@app.route('/shutdown')
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

# Create bot instance
bot = WhatsAppOpenAIBot()

@app.route("/bot", methods=["POST"])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages"""
    # Incoming message details
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')  # This includes 'whatsapp:+1234567890'
    
    response_text = bot.process_message(sender, incoming_msg)
    
    # Create response
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(response_text)
    
    return str(resp)

class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WhatsApp OpenAI Bot")
        self.root.geometry("900x600")
        
        # Appearance mode
        ctk.set_appearance_mode(bot.config.get("appearance_mode", "dark"))
        ctk.set_default_color_theme("blue")
        
        # Main frame
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        self.create_header()
        
        self.create_tabs()
        
        # Status bar
        self.status_var = ctk.StringVar(value="Ready")
        self.status_bar = ctk.CTkLabel(
            self.root, 
            textvariable=self.status_var,
            anchor="w",
            height=25
        )
        self.status_bar.pack(fill="x", padx=10)
        
        # Start log updater
        self.update_logs()
    
    def create_header(self):
        """Create header with title and controls"""
        header_frame = ctk.CTkFrame(self.main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame, 
            text="WhatsApp OpenAI Bot", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(side="left", padx=10, pady=10)
        
        # Server controls
        self.server_btn = ctk.CTkButton(
            header_frame,
            text="Start Server",
            command=self.toggle_server,
            width=120
        )
        self.server_btn.pack(side="right", padx=10, pady=10)
        
        # Appearance switch
        appearance_var = ctk.StringVar(value=bot.config.get("appearance_mode", "dark"))
        appearance_switch = ctk.CTkSwitch(
            header_frame,
            text="Dark Mode",
            onvalue="dark",
            offvalue="light",
            variable=appearance_var,
            command=lambda: self.toggle_appearance(appearance_var.get())
        )
        appearance_switch.pack(side="right", padx=10, pady=10)
    
    def create_tabs(self):
        """Create tabbed interface"""
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(fill="both", expand=True)
        
        # Tabs
        self.tabview.add("Dashboard")
        self.tabview.add("Conversations")
        self.tabview.add("Settings")
        
        # Default tab
        self.tabview.set("Dashboard")
        
        # Tab content
        self.create_dashboard_tab()
        self.create_conversations_tab()
        self.create_settings_tab()
    
    def create_dashboard_tab(self):
        """Create dashboard tab with logs and stats"""
        tab = self.tabview.tab("Dashboard")
        
        # Log area
        log_frame = ctk.CTkFrame(tab)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        log_label = ctk.CTkLabel(
            log_frame, 
            text="Activity Log", 
            font=ctk.CTkFont(weight="bold")
        )
        log_label.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.log_text = ctk.CTkTextbox(
            log_frame,
            wrap="word",
            height=400
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Bottom controls
        controls_frame = ctk.CTkFrame(tab)
        controls_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        clear_log_btn = ctk.CTkButton(
            controls_frame,
            text="Clear Log",
            command=self.clear_logs,
            width=100
        )
        clear_log_btn.pack(side="right", padx=10, pady=10)
    
    def create_conversations_tab(self):
        """Create conversations tab to view and manage active conversations"""
        tab = self.tabview.tab("Conversations")
        
        # Splitview for user list and conversation content
        self.split_frame = ctk.CTkFrame(tab)
        self.split_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # User list frame (left side)
        user_frame = ctk.CTkFrame(self.split_frame, width=200)
        user_frame.pack(side="left", fill="y", padx=(0, 5), pady=0)
        user_frame.pack_propagate(False)  # Don't shrink
        
        user_label = ctk.CTkLabel(
            user_frame, 
            text="Active Users", 
            font=ctk.CTkFont(weight="bold")
        )
        user_label.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.user_list = ctk.CTkScrollableFrame(user_frame)
        self.user_list.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Conversation view frame (right side)
        conv_frame = ctk.CTkFrame(self.split_frame)
        conv_frame.pack(side="right", fill="both", expand=True, padx=(5, 0), pady=0)
        
        self.conv_title = ctk.CTkLabel(
            conv_frame, 
            text="Select a conversation", 
            font=ctk.CTkFont(weight="bold")
        )
        self.conv_title.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.conv_text = ctk.CTkTextbox(
            conv_frame,
            wrap="word",
            height=400
        )
        self.conv_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Placeholder users for testing
        self.refresh_user_list()
    
    def refresh_user_list(self):
        """Refresh the list of users with active conversations"""
        for widget in self.user_list.winfo_children():
            widget.destroy()
        
        # No users 
        if not bot.conversations:
            no_users = ctk.CTkLabel(
                self.user_list,
                text="No active conversations",
                text_color="gray"
            )
            no_users.pack(pady=10)
            return
        
        # Add buttons for each user
        for user_id in bot.conversations:
            user_name = bot.get_user_name(user_id)
            
            user_btn = ctk.CTkButton(
                self.user_list,
                text=user_name,
                command=lambda u=user_id: self.show_conversation(u),
                anchor="w",
                height=30,
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray75", "gray25")
            )
            user_btn.pack(fill="x", pady=2)
    
    def show_conversation(self, user_id):
        """Display conversation for selected user"""
        user_name = bot.get_user_name(user_id)
        self.conv_title.configure(text=f"Conversation with {user_name}")
        
        self.conv_text.delete("0.0", "end")
        
        # Display conversation
        conversation = bot.get_conversation_history(user_id)
        for message in conversation:
            if message["role"] == "system":
                continue  
            
            if message["role"] == "user":
                self.conv_text.insert("end", f"User: {message['content']}\n\n", "user")
            else:
                self.conv_text.insert("end", f"Bot: {message['content']}\n\n", "bot")
        
        clear_btn = ctk.CTkButton(
            self.conv_text,
            text="Clear Conversation",
            command=lambda: self.clear_conversation(user_id),
            width=150
        )
        self.conv_text.window_create("end", window=clear_btn)
    
    def clear_conversation(self, user_id):
        """Clear conversation for a specific user"""
        bot.clear_conversation(user_id)
        self.show_conversation(user_id)
        self.status_var.set(f"Cleared conversation for {bot.get_user_name(user_id)}")
    
    def create_settings_tab(self):
        """Create settings tab"""
        tab = self.tabview.tab("Settings")
        
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # API Key section
        api_frame = ctk.CTkFrame(settings_frame)
        api_frame.pack(fill="x", padx=10, pady=10)
        
        api_label = ctk.CTkLabel(
            api_frame, 
            text="API Settings", 
            font=ctk.CTkFont(weight="bold")
        )
        api_label.pack(anchor="w", padx=10, pady=(10, 0))
        
        # OpenAI API Key
        openai_frame = ctk.CTkFrame(api_frame, fg_color="transparent")
        openai_frame.pack(fill="x", padx=10, pady=5)
        
        openai_label = ctk.CTkLabel(openai_frame, text="OpenAI API Key:")
        openai_label.pack(side="left", padx=(0, 10))
        
        # API key for display
        api_key = bot.config.get("api_key", "")
        if api_key:
            display_key = api_key[:4] + "..." + api_key[-4:]
        else:
            display_key = ""
        
        self.api_var = ctk.StringVar(value=display_key)
        api_entry = ctk.CTkEntry(
            openai_frame,
            textvariable=self.api_var,
            width=300,
            show="•"
        )
        api_entry.pack(side="left", padx=5)
        
        api_btn = ctk.CTkButton(
            openai_frame,
            text="Update",
            command=self.update_api_key,
            width=100
        )
        api_btn.pack(side="left", padx=5)
        
        # Twilio section
        twilio_frame = ctk.CTkFrame(api_frame, fg_color="transparent")
        twilio_frame.pack(fill="x", padx=10, pady=5)
        
        twilio_label = ctk.CTkLabel(twilio_frame, text="Twilio Settings:")
        twilio_label.pack(anchor="w", padx=10, pady=(5, 0))
        
        twilio_status = "✓ Configured" if os.getenv("TWILIO_ACCOUNT_SID") else "❌ Not Configured"
        twilio_status_label = ctk.CTkLabel(
            twilio_frame,
            text=f"Status: {twilio_status}",
            text_color="green" if os.getenv("TWILIO_ACCOUNT_SID") else "red"
        )
        twilio_status_label.pack(anchor="w", padx=30, pady=0)
        
        twilio_help = ctk.CTkLabel(
            twilio_frame,
            text="Twilio credentials must be set in .env file",
            text_color="gray"
        )
        twilio_help.pack(anchor="w", padx=30, pady=0)
        
        # Model settings
        model_frame = ctk.CTkFrame(settings_frame)
        model_frame.pack(fill="x", padx=10, pady=10)
        
        model_label = ctk.CTkLabel(
            model_frame, 
            text="Model Settings", 
            font=ctk.CTkFont(weight="bold")
        )
        model_label.pack(anchor="w", padx=10, pady=(10, 0))
        
        # Model selection
        model_select_frame = ctk.CTkFrame(model_frame, fg_color="transparent")
        model_select_frame.pack(fill="x", padx=10, pady=5)
        
        model_select_label = ctk.CTkLabel(model_select_frame, text="OpenAI Model:")
        model_select_label.pack(side="left", padx=(0, 10))
        
        self.model_var = ctk.StringVar(value=bot.config.get("model", "gpt-3.5-turbo"))
        model_dropdown = ctk.CTkOptionMenu(
            model_select_frame,
            values=["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"],
            variable=self.model_var,
            command=self.update_model,
            width=200
        )
        model_dropdown.pack(side="left", padx=5)
        
        # Temperature slider
        temp_frame = ctk.CTkFrame(model_frame, fg_color="transparent")
        temp_frame.pack(fill="x", padx=10, pady=5)
        
        temp_label = ctk.CTkLabel(temp_frame, text="Temperature:")
        temp_label.pack(side="left", padx=(0, 10))
        
        self.temp_value = ctk.DoubleVar(value=bot.config.get("temperature", 0.7))
        temp_slider = ctk.CTkSlider(
            temp_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=10,
            variable=self.temp_value,
            command=self.update_temperature,
            width=200
        )
        temp_slider.pack(side="left", padx=5)
        
        temp_value_label = ctk.CTkLabel(temp_frame, textvariable=self.temp_value)
        temp_value_label.pack(side="left", padx=5)
        
        # Max tokens slider
        tokens_frame = ctk.CTkFrame(model_frame, fg_color="transparent")
        tokens_frame.pack(fill="x", padx=10, pady=5)
        
        tokens_label = ctk.CTkLabel(tokens_frame, text="Max Tokens:")
        tokens_label.pack(side="left", padx=(0, 10))
        
        self.tokens_value = ctk.IntVar(value=bot.config.get("max_tokens", 1000))
        tokens_slider = ctk.CTkSlider(
            tokens_frame,
            from_=100,
            to=4000,
            number_of_steps=39,
            variable=self.tokens_value,
            command=self.update_tokens,
            width=200
        )
        tokens_slider.pack(side="left", padx=5)
        
        tokens_value_label = ctk.CTkLabel(tokens_frame, textvariable=self.tokens_value)
        tokens_value_label.pack(side="left", padx=5)
        
        # Server settings
        server_frame = ctk.CTkFrame(settings_frame)
        server_frame.pack(fill="x", padx=10, pady=10)
        
        server_label = ctk.CTkLabel(
            server_frame, 
            text="Server Settings", 
            font=ctk.CTkFont(weight="bold")
        )
        server_label.pack(anchor="w", padx=10, pady=(10, 0))
        
        # Port setting
        port_frame = ctk.CTkFrame(server_frame, fg_color="transparent")
        port_frame.pack(fill="x", padx=10, pady=5)
        
        port_label = ctk.CTkLabel(port_frame, text="Server Port:")
        port_label.pack(side="left", padx=(0, 10))
        
        self.port_var = ctk.StringVar(value=str(bot.config.get("server_port", 5000)))
        port_entry = ctk.CTkEntry(
            port_frame,
            textvariable=self.port_var,
            width=100
        )
        port_entry.pack(side="left", padx=5)
        
        port_btn = ctk.CTkButton(
            port_frame,
            text="Update",
            command=self.update_port,
            width=100
        )
        port_btn.pack(side="left", padx=5)
        
        button_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=10)
        
        restore_btn = ctk.CTkButton(
            button_frame,
            text="Restore Defaults",
            command=self.restore_defaults,
            fg_color="gray",
            hover_color="darkgray",
            width=150
        )
        restore_btn.pack(side="left", padx=10, pady=10)
        
        save_btn = ctk.CTkButton(
            button_frame,
            text="Save Settings",
            command=self.save_settings,
            width=150
        )
        save_btn.pack(side="right", padx=10, pady=10)
    
    def update_api_key(self):
        """Update OpenAI API key"""
        dialog = ctk.CTkInputDialog(
            text="Enter your OpenAI API Key:", 
            title="Set API Key"
        )
        new_api_key = dialog.get_input()
        
        if new_api_key:
            bot.config["api_key"] = new_api_key
            openai.api_key = new_api_key
            save_config(bot.config)
            self.api_var.set(new_api_key[:4] + "..." + new_api_key[-4:])
            self.status_var.set("API key updated")
    
    def update_model(self, choice):
        """Update OpenAI model"""
        bot.config["model"] = choice
        save_config(bot.config)
        self.status_var.set(f"Model set to {choice}")
    
    def update_temperature(self, value):
        """Update temperature setting"""
        rounded = round(float(value), 1)
        bot.config["temperature"] = rounded
        self.temp_value.set(rounded)
        save_config(bot.config)
    
    def update_tokens(self, value):
        """Update max tokens setting"""
        tokens = int(value)
        bot.config["max_tokens"] = tokens
        self.tokens_value.set(tokens)
        save_config(bot.config)
    
    def update_port(self):
        """Update server port"""
        try:
            port = int(self.port_var.get())
            if port < 1 or port > 65535:
                raise ValueError("Port must be between 1 and 65535")
            
            bot.config["server_port"] = port
            save_config(bot.config)
            self.status_var.set(f"Server port updated to {port}")
            
            # Notify user to restart server
            if bot.running:
                messagebox.showinfo(
                    "Restart Required", 
                    "Please stop and restart the server for the port change to take effect."
                )
                
        except ValueError as e:
            messagebox.shower