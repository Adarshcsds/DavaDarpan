📌 Overview
Davadarpan is a web-based hospital management system designed to improve transparency, communication, and accessibility of medical data between patients, families, nurses, and doctors.
In many hospitals, patient updates are fragmented and difficult to access. This system provides a centralized platform where medical information, reports, and expenses can be tracked in real-time.

🎯 Problem Statement
Healthcare systems often suffer from:
Lack of transparency between staff and patient families
Scattered and unorganized medical records
No clear tracking of treatment expenses
Overload of minor patient queries on doctors
Privacy concerns in document handling

💡 Solution
Davadarpan solves these problems by providing:
Role-based access control (RBAC)
Centralized medical record storage
Secure document sharing with privacy layers
AI-powered chatbot for basic assistance
Real-time patient updates
Financial tracking system

🛠️ Tech Stack
Frontend:
HTML, CSS (Glassy UI Theme)
Backend:
Python (Flask)
Database:
SQLite
AI Integration:
Gemini API
Deployment:
Render

🔑 Key Features
👥 Role-Based Access System
Nurse: Upload patient data and updates
Doctor: Modify and manage critical medical information
Family/Patient: View real-time updates

📁 Secure Document Management
Shared Documents: Accessible by medical staff
Private Documents: Only accessible by the patient

🤖 AI Chatbot
Handles basic medical queries
Helps interpret simple blood reports
Note: Not a replacement for professional medical advice

🧾 Medical Locker
Central storage for patient medical history
Easy access and retrieval

💰 Expense Tracker (Supply Ledger)
Tracks treatment costs
Helps families understand financial flow

🧠 System Design (High Level)
Flask handles routing, authentication, and API integration
SQLite stores users, medical records, and transactions
Role-based middleware restricts access to endpoints
Gemini API powers chatbot responses

⚙️ Installation & Setup
1. Clone the Repository
git clone https://github.com/your-username/davadarpan.git⁠�
cd davadarpan

2. Create Virtual Environment
python -m venv venv
venv\Scripts\activate   (Windows)
source venv/bin/activate   (Linux/Mac)

3. Install Dependencies
pip install -r requirements.txt

4. Setup Environment Variables
Create a .env file and add:
GEMINI_API_KEY=your_api_key_here
SECRET_KEY=your_secret_key

5. Run the Application
flask run
🌐 Live Demo
Deployed Link:
https://davadarpan.onrender.com

⚠️ Challenges Faced
Secure document-level authentication
Managing role-based CRUD operations
Handling multi-user data flow
Designing backend logic for real hospital scenarios

🚧 Limitations
Not production-ready (basic security)
SQLite is not scalable for large systems
AI chatbot may give incorrect responses
No real hospital integration

🔮 Future Improvements
JWT / OAuth authentication
Migration to PostgreSQL or MongoDB
Advanced analytics dashboard
Integration with real hospital systems
More reliable AI with validation layers


📄 License
This project is for educational and hackathon purposes only.