# Whatsapp-Bot
This WhatsApp bot automates tasks using the Meta API and OpenAI. It responds intelligently, sets reminders, fetches data, and interacts with APIs. Features include AI-powered replies, task automation, and custom commands. Ideal for personal assistance, business automation, and education, it enhances productivity with smooth, secure communication.


## Required Tools and Services

- **Twilio Account**: Required for accessing the WhatsApp API.
- **Flask Server**: Used to handle incoming messages and respond via Twilio.
- **Ngrok or Similar**: Needed to expose your local Flask server to the internet for Twilio to communicate.

## Setup Instructions

### 1. Create a `.env` file with the following content:
```
OPENAI_API_KEY=your_openai_api_key
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
```

### 2. Install required packages:
```
pip install openai python-dotenv twilio flask
```

### 3. Configure Twilio WhatsApp Sandbox:
- Go to the Twilio Console
- Navigate to **Messaging > Try it > WhatsApp**
- Set up the WhatsApp sandbox
- Configure the webhook URL to point to your server: `https://your-domain.com/bot`

### 4. Run the server locally and expose it using ngrok:
```
# In one terminal
python whatsapp_bot.py

# In another terminal
ngrok http 5000
```
- Update the Twilio webhook URL with the `ngrok` URL.

## Configuration File (`saved_config.json`)
The bot uses a configuration file named `saved_config.json`, which stores essential settings. Ensure this file is present in your project directory. Below is the default structure:

```json
{
  "openai_model": "gpt-3.5-turbo",  
  "max_history_length": 10,  
  "default_response": "I'm here to help! Ask me anything.",
  "allowed_commands": ["!clear", "!help", "!info"],
  "admin_users": []  
}
```

- **`openai_model`**: Defines which GPT model the bot will use.
- **`max_history_length`**: Limits stored conversation history per user.
- **`default_response`**: The message the bot sends if no meaningful response is generated.
- **`allowed_commands`**: Specifies available commands.
- **`admin_users`**: Stores admin user details (currently empty by default).

## How to Use the Bot
Once set up, users can interact with the WhatsApp bot by sending messages. The bot supports:

- **Regular AI-powered responses**
- **Special Commands:**
  - `!clear` - Clear conversation history
  - `!help` - Show help menu
  - `!info` - Show bot configuration

The bot keeps track of conversation history for each user, allowing for contextual responses.

## Notes
- Ensure your Twilio account is properly set up to send and receive WhatsApp messages.
- Use `ngrok` or deploy the Flask app to a cloud server to make it accessible.
- Keep your API keys and tokens secure by using environment variables.
