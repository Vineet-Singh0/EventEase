# EventEase: Event Management System

A modern web-based event management system built with Flask and MySQL. EventEase allows users to create, manage, and register for events, with support for user roles, file uploads, and timezone-aware scheduling.

## Features

- User authentication (register/login/logout)
- Three user roles: **Admin**, **Organizer**, **Attendee**
- Admin dashboard for managing users and events
- Organizers can create, edit, and manage their own events
- Attendees can browse, register, and view their events
- Event photo upload and management
- Timezone-aware (IST/Asia-Kolkata) event scheduling
- Responsive design (Bootstrap 5)
- ERD and architecture diagrams included

## Prerequisites

- Python 3.8 or higher
- MySQL Server (running locally)
- pip (Python package installer)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Project
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the project root with:
   ```
   SECRET_KEY=your-secret-key-here
   ```
   *(Database credentials are set directly in `app.py` by default: user `root`, no password, database `event_management`)*

5. **Create the MySQL database:**
   ```sql
   CREATE DATABASE event_management;
   ```

## Running the Application

1. Ensure your MySQL server is running and the `event_management` database exists.
2. Start the Flask app:
   ```bash
   python app.py
   ```
   The app will run on [http://localhost:5003](http://localhost:5003)

## Usage

- **Register** a new account or **login** with existing credentials.
- **Admins** can manage users and events from the admin dashboard.
- **Organizers** can create and manage their own events, including uploading event photos.
- **Attendees** can browse, register for, and view events.
- All event times are shown in IST (Asia/Kolkata).
- Uploaded event photos are stored in `static/uploads/events/`.

## File Uploads
- Allowed file types: `png`, `jpg`, `jpeg`, `gif`
- Max file size: 16MB

## Project Structure
- `app.py` — Main Flask application
- `static/` — Static files (CSS, images, uploads)
- `templates/` — HTML templates
- `requirements.txt` — Python dependencies
- `architecture_diagram.png`, `erd_diagram.png` — System and database diagrams

## Diagrams
- **ERD**: `erd_diagram.png`
- **Architecture**: `architecture_diagram.png`

## Contributing
1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your branch
5. Open a Pull Request

---

*For any issues or questions, please open an issue on the repository.* 