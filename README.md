# Student File Manager

A full-stack web app where students can **upload files (50MB+)**, organize them in **folders**, and securely access them from anywhere by signing in.

## Tech Stack

| Layer    | Technology           |
|----------|----------------------|
| Frontend | React + Vite         |
| Backend  | Python + Flask       |
| Database | SQLite               |
| Auth     | bcrypt password hash |

## Features

- 🔐 Sign up / Login with hashed passwords
- 📁 Create & delete folders
- ⬆️ Upload large files (drag & drop or browse) — **50MB+ supported**
- ⬇️ Download files with one click
- 🗑️ Delete files anytime
- 📂 Files organized per folder per user

## Running Locally

### Backend
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Runs on `http://localhost:5000`

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Runs on `http://localhost:5173`
