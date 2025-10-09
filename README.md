# Mahindra Voice Assistant 🚗💨

**Real-time AI voice consultation for Mahindra automotive sales powered by OpenAI GPT-4o**

An intelligent voice assistant that helps customers explore Mahindra vehicles through natural conversation, with integrated conversation analysis, database storage, and personalized recommendations.

---

## ✨ Features

### Core Functionality
- 🎤 **Real-time Voice Consultation** - Natural conversation with AI assistant "Ishmael"
- 🌐 **WebRTC Audio Streaming** - Browser-based, low-latency voice communication
- 🚗 **Vehicle Recommendations** - Personalized suggestions based on customer needs
- 💬 **Conversation Storage** - All interactions saved to database for analysis
- 🧠 **Intelligence Extraction** - Automatic extraction of preferences, budget, and requirements
- 📊 **Analytics & Insights** - Customer preference tracking and conversation analytics
- 🔄 **Session Management** - Persistent conversation history and context

### Advanced Capabilities
- Multi-turn conversation tracking
- Budget and preference analysis
- Use case detection (family, commercial, adventure)
- Feature importance ranking
- Sentiment and engagement tracking
- RESTful API endpoints for integration

---

## 🚀 Quick Start

### 1. Setup Environment

Create `.env` file in the root directory:
```env
OPENAI_API_KEY=sk-your-key-here
SECRET_KEY=your-django-secret-key
DEBUG=True
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize Database

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Run Server

**Option 1** (Easy - Windows):
```bash
start_ishmael.bat
```

**Option 2** (Manual):
```bash
python manage.py runserver
```

### 5. Open Browser

Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000) and click "Start Conversation"

---

## 📁 Project Structure

```
project/
├── manage.py                    # Django management command
├── voice_assistant/             # Django project configuration
│   ├── settings.py              # Project settings
│   ├── urls.py                  # Root URL configuration
│   └── wsgi.py                  # WSGI configuration
├── assistant/                   # Main application
│   ├── models.py                # Database models (Conversation, Message)
│   ├── views.py                 # API endpoints and views
│   ├── urls.py                  # App URL patterns
│   ├── analyzer.py              # AI intelligence extraction
│   └── migrations/              # Database migrations
├── constants.py                 # OpenAI config & AI persona
├── requirements.txt             # Python dependencies
├── static/                      # Frontend assets
│   ├── css/
│   ├── js/
│   └── index.html               # Main interface
├── TESTING_GUIDE.txt            # Comprehensive testing instructions
├── start_ishmael.bat            # Windows startup script
├── .env                         # Environment variables (create this)
└── db.sqlite3                   # SQLite database (created automatically)
```

---

## 🔌 API Endpoints

### Voice Assistant
- `GET /` - Main web interface
- `POST /api/session` - Create OpenAI Realtime API session
- `GET /health` - Health check endpoint

### Conversation Management
- `POST /api/conversations/` - Create new conversation
- `GET /api/conversations/` - List all conversations
- `GET /api/conversations/<id>/` - Get specific conversation
- `POST /api/conversations/<id>/messages/` - Add message to conversation

### Intelligence & Analytics
- `GET /api/conversations/<id>/intelligence/` - Get extracted intelligence
- `GET /api/conversations/<id>/recommendations/` - Get AI recommendations
- `POST /api/analyze-conversation/` - Analyze conversation in real-time

---

## 🗄️ Database Models

### Conversation
Stores conversation metadata and intelligence:
- Session tracking
- Customer preferences
- Budget information
- Use case detection
- Feature priorities
- Engagement metrics
- Status tracking

### Message
Stores individual messages:
- Role (user/assistant/system)
- Content and metadata
- Timestamps
- Conversation relationship

---

## 🧠 Intelligence Extraction

The system automatically analyzes conversations to extract:

1. **Customer Preferences**
   - Vehicle types mentioned
   - Specific models of interest
   - Brand preferences

2. **Budget Analysis**
   - Budget range detection
   - Price sensitivity
   - Financing interest

3. **Use Case Detection**
   - Family transportation
   - Commercial usage
   - Adventure/off-road
   - Luxury/comfort

4. **Feature Priorities**
   - Safety features
   - Technology/connectivity
   - Performance
   - Fuel efficiency
   - Space/seating

5. **Engagement Metrics**
   - Message count
   - Response patterns
   - Question complexity

---

## 🛠️ Tech Stack

### Backend
- **Framework:** Django 4.x
- **Database:** SQLite (development) / PostgreSQL (production-ready)
- **API Client:** httpx (async HTTP)
- **Environment:** python-dotenv

### AI & Intelligence
- **OpenAI GPT-4o** - Conversational AI
- **OpenAI Whisper** - Speech-to-text
- **OpenAI TTS** - Text-to-speech
- **Realtime API** - Low-latency voice streaming
- **Custom Analyzer** - Intelligence extraction

### Frontend
- **HTML/CSS/JavaScript** - Web interface
- **WebRTC** - Real-time audio streaming
- **Fetch API** - Backend communication

### Dependencies
```
Django>=4.0
httpx>=0.24.0
python-dotenv>=1.0.0
django-cors-headers>=4.0.0
```

---

## 🧪 Testing

For comprehensive testing instructions, see `TESTING_GUIDE.txt`

### Quick Test

1. **Voice Interaction Test**
   - Open http://127.0.0.1:8000
   - Start conversation
   - Speak naturally about vehicle needs

2. **Database Verification**
   ```bash
   python manage.py shell
   >>> from assistant.models import Conversation, Message
   >>> Conversation.objects.all()
   >>> Message.objects.all()
   ```

3. **API Testing**
   ```bash
   # Health check
   curl http://127.0.0.1:8000/health
   
   # List conversations
   curl http://127.0.0.1:8000/api/conversations/
   ```

4. **Intelligence Extraction**
   - Have a conversation mentioning budget and preferences
   - Check conversation intelligence endpoint
   - Verify extracted data accuracy

---

## 📝 Requirements

- **Python:** 3.8 or higher
- **Browser:** Chrome, Edge, or Safari (WebRTC support required)
- **OpenAI API:** Account with GPT-4o and Realtime API access
- **Operating System:** Windows, macOS, or Linux

---

## 🔧 Configuration

### Environment Variables

```env
# Required
OPENAI_API_KEY=sk-proj-xxx

# Optional
SECRET_KEY=your-secret-key          # Django secret
DEBUG=True                           # Debug mode
ALLOWED_HOSTS=localhost,127.0.0.1   # Allowed hosts
```

### OpenAI Configuration (constants.py)

- Voice model: `gpt-4o-realtime-preview-2024-12-17`
- Voice type: `verse`
- Turn detection: Server VAD
- Temperature: 0.8

---

## 🎯 Use Cases

1. **Customer Consultation**
   - Natural language vehicle exploration
   - Personalized recommendations
   - Product information delivery

2. **Sales Analytics**
   - Customer preference tracking
   - Conversation pattern analysis
   - Lead qualification

3. **Training & Development**
   - Sales script optimization
   - Common question identification
   - Response effectiveness analysis

---

## 🐛 Troubleshooting

### Common Issues

**Voice not working:**
- Check browser microphone permissions
- Ensure HTTPS or localhost
- Verify OpenAI API key

**Database errors:**
```bash
python manage.py makemigrations
python manage.py migrate
```

**API errors:**
- Verify `.env` file exists
- Check OpenAI API key validity
- Ensure internet connectivity

See `TESTING_GUIDE.txt` for detailed troubleshooting steps.

---

## 🚦 Development Status

- ✅ Voice assistant functionality
- ✅ Database integration
- ✅ Intelligence extraction
- ✅ API endpoints
- ✅ Conversation analytics
- 🔄 Production deployment (planned)
- 🔄 Admin dashboard (planned)
- 🔄 Advanced analytics (planned)

---

## 📄 License

Experimental project for educational purposes.

---

## 👥 Credits

**Built by Techjays Intern Projects Team**

**Powered by:**
- OpenAI GPT-4o & Realtime API
- Django Framework

*Note: This is an experimental educational project. Mahindra branding is used for demonstration purposes only and does not represent an official Mahindra product.*

---

## 📞 Support

For detailed testing and usage instructions, refer to `TESTING_GUIDE.txt`

For questions or issues, please refer to the troubleshooting section or contact the development team.
