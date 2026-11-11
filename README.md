# CampusMeet: Smart Event Management System

A web-based system that helps our college create and manage events. Students register for events, mark attendance by scanning a QR code, and receive certificates that the organizer approves first. Built as a Software Engineering micro-project.

## Features

**Organizer (admin)**
- Separate signup and login, protected by an admin access code
- Publish events with title, category, venue, date, seat limit and an uploaded banner image
- Unique QR code for every event (printable), plus a backup code
- Live attendance list, CSV export
- Approve certificates one by one or all at once
- Dashboard with totals for events, registrations, attendance and pending certificates

**Student**
- Separate signup and login (department, roll number, year)
- Browse events as cards, filter by category
- Register for events (seat limit enforced)
- Scan the event QR to mark attendance, or enter the code manually
- Download a printable certificate after the organizer approves it
- Certificates carry a QR code that opens a public verification page

## Tech stack

| Part | Technology |
|---|---|
| Backend | Python 3, Flask |
| Database | SQLite (relational, foreign keys enabled) |
| Frontend | HTML, CSS, Jinja2 templates |
| QR codes | `qrcode` + Pillow |
| Security | Password hashing (Werkzeug), role-based access, parameterized SQL |

## Project structure

```
vesit_events/
├── app.py            # routes and business logic
├── schema.sql        # database schema and seed data
├── requirements.txt
├── templates/        # HTML pages (Jinja2)
├── static/
│   ├── style.css
│   ├── img/          # logo, campus.jpg (add your own)
│   └── uploads/      # uploaded event banners
└── screenshots/
```

## Database design

`departments`, `categories` (lookup tables) → `users` → `events` → `registrations` → `attendance` → `certificates`

- Attendance references a registration, so only registered students can be marked present
- A certificate references an attendance record and starts as `pending` until an admin approves it
- Foreign keys, `UNIQUE` and `CHECK` constraints keep the data consistent


## Demo flow

1. Sign up as admin using the access code, then publish an event with a banner
2. Sign up as a student and register for the event
3. Open the event's QR page as admin, scan the code with the student's phone
4. Watch the student appear as present on the admin page
5. Approve the certificate, then open it from the student dashboard


## Future scope

- Rotating QR codes to prevent proxy attendance
- Event editing, waiting lists and deadlines
- Email notifications and forgot-password
- PDF certificates generated on the server
- Results and winner announcements
- PostgreSQL and cloud deployment

## Team

Software Engineering Micro-project, VESIT.

66 - Khyati Keswani

68 - Jeegnasa Makwana

69 - Leena Chavan
