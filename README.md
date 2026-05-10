# Engie — Engineering Team Registry

A centralised team registry web application for broadcast engineering organisations.
Built with Django (backend) + Vanilla JS single-page frontend.

## Team
**Team 1984** | 5COSC021W | 2025-26

- Aryan Paudel (W2083972)
- Shantanu Taylor
- Ashrish Magar
- Abishek Acharya

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run migrations
```bash
python manage.py migrate
```

### 3. Seed demo data (optional but recommended)
```bash
python seed_data.py
```

### 4. Run the server
```bash
python manage.py runserver
```

### 5. Open in browser
```
http://localhost:8000
```

## Demo Credentials

| Role     | Email                        | Password    |
|----------|------------------------------|-------------|
| Admin    | admin@broadcast.com          | Admin1234!  |
| Manager  | s.patel@broadcast.com        | Engineer1!  |
| Engineer | aryan.paudel@broadcast.com   | Engineer1!  |

## API Endpoints

### Authentication
- `POST /api/auth/register/` — Register new account
- `POST /api/auth/login/` — Login
- `POST /api/auth/logout/` — Logout
- `GET/PATCH /api/auth/profile/` — View/update profile
- `POST /api/auth/forgot-password/` — Request password reset
- `POST /api/auth/reset-password/` — Reset with token

### Teams & Departments
- `GET /api/dashboard/` — Engineering overview stats
- `GET /api/teams/` — List all teams (supports ?q=search, ?status=active)
- `GET/PATCH/DELETE /api/teams/<id>/` — Team detail
- `GET /api/departments/` — All departments
- `GET /api/departments/stats/` — Department stats for reports

### Dependencies
- `GET /api/dependencies/` — All active dependencies
- `POST /api/dependencies/` — Create dependency (admin only)
- `GET /api/teams/<id>/dependencies/` — Upstream/downstream for a team

### Scheduling
- `GET/POST /api/events/` — User events / create event
- `POST /api/events/<id>/respond/` — Accept/decline invite

### Messaging
- `GET/POST /api/messages/` — Messages (inbox/sent/drafts)
- `GET /api/messages/<id>/` — Message detail

### Notifications
- `GET /api/notifications/` — User notifications
- `POST /api/notifications/<id>/read/` — Mark as read
- `POST /api/notifications/read-all/` — Mark all as read

### Reports & Audit
- `GET /api/reports/` — Admin reports (admin only)
- `GET /api/audit/` — Audit log (admin only)

## Database
SQLite (`db.sqlite3`) — included after running migrations.

## Architecture
- **Backend**: Django 5.x + Django REST Framework
- **Frontend**: Single-page HTML/CSS/JS (no framework, served from templates/)
- **Database**: SQLite (development) — easily swappable to PostgreSQL
- **Auth**: Django session authentication with CSRF protection

## Features Implemented
- ✅ User registration, login, logout, password reset
- ✅ Role-based access (Engineer / Manager / Admin)
- ✅ Engineering dashboard with live stats
- ✅ Teams directory with search and filtering
- ✅ Team detail pages with members, repos, contacts, dependencies
- ✅ Organisation chart (departments → teams)
- ✅ Dependency mapping (upstream/downstream)
- ✅ Internal messaging system
- ✅ Calendar scheduling with event invites
- ✅ Notifications system
- ✅ Admin reports (team count, unmanaged teams, department summary)
- ✅ Audit log for all admin actions
- ✅ User profile management
