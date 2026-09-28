# 🎵 Spotify Account Migrator

A local Streamlit application for transferring a Spotify music library from one Spotify account to another.

The application scans the **old Spotify account**, creates a local backup of the music library, and then uses a separate OAuth authorization flow to transfer the saved content to a **new Spotify account**.

---

## ✨ Features

The application can transfer:

- 🎵 Liked / saved songs
- 👤 Followed artists
- 📂 User-owned playlists
- 📝 Playlist names
- 📝 Playlist descriptions
- 🌐 Playlist public/private status
- 🎶 Tracks inside playlists

The application also includes:

- Separate OAuth flows for OLD and NEW accounts
- Protection against accidentally authorizing the same account twice
- Persistent local backup using `spotify_backup.json`
- Automatic restoration of the backup after Spotify OAuth redirects
- Spotify API rate-limit handling
- Automatic retries for temporary Spotify server errors
- Progress indicators during migration
- Ability to retry a failed migration without rescanning the old account

---

## 🖥️ How It Works

The migration consists of two main steps.

### 1. Scan & Backup Old Account

The application connects to the Spotify account containing the music you want to migrate.

It reads:

```text
Liked Songs
Followed Artists
Playlists
Playlist Tracks
```

The collected data is stored both in Streamlit's session state and in a local file:

```text
spotify_backup.json
```

The backup is important because Spotify OAuth redirects can create a fresh Streamlit session.

---

### 2. Transfer to New Account

After the old account has been backed up, switch the application to:

```text
2. Transfer to New Account
```

The application then asks Spotify to authorize the destination account.

The saved library is transferred in this order:

```text
1. Liked Songs
2. Followed Artists
3. Playlists
4. Playlist Tracks
```

A progress bar displays the migration progress.

---

# 📋 Requirements

- Python 3.10+
- A Spotify account
- A Spotify Developer application
- Spotify Client ID
- Spotify Client Secret
- Internet connection

---

# 📦 Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

Create a virtual environment:

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required packages:

```bash
pip install streamlit spotipy requests
```

---

# 🔑 Spotify Developer Setup

Create an application through the Spotify Developer Dashboard.

You will need:

```text
Client ID
Client Secret
```

The application uses the following Spotify permissions:

```text
user-library-read
user-library-modify
user-follow-read
user-follow-modify
playlist-read-private
playlist-read-collaborative
playlist-modify-private
playlist-modify-public
```

These scopes allow the application to read the source account and modify the destination account.

---

# 🔐 Streamlit Secrets

Create the following file:

```text
.streamlit/secrets.toml
```

Add:

```toml
SPOTIFY_CLIENT_ID = "YOUR_CLIENT_ID"
SPOTIFY_CLIENT_SECRET = "YOUR_CLIENT_SECRET"
```

Do **not** commit this file to GitHub.

Add it to `.gitignore`:

```gitignore
.streamlit/secrets.toml
spotify_backup.json
.venv/
__pycache__/
*.pyc
```

---

# 🔄 Redirect URI

The local application currently uses:

```text
http://127.0.0.1:8501/
```

This URI must be configured in your Spotify Developer application.

The Redirect URI configured in Spotify must match the URI used by the application **exactly**.

For local development:

```text
http://127.0.0.1:8501/
```

If deploying the application to Streamlit Community Cloud, change the redirect URI in `app_local_fixed.py` to the URL of the deployed application.

Example:

```python
REDIRECT_URI = "https://your-app-name.streamlit.app/"
```

Then add the exact same URL to the Spotify Developer Dashboard.

---

# ▶️ Running the Application

Start Streamlit:

```bash
streamlit run app_local_fixed.py
```

The application will normally be available at:

```text
http://127.0.0.1:8501/
```

---

# 🚀 Migration Guide

## Step 1 — Scan the Old Account

Select:

```text
1. Scan & Backup Old Account
```

Click:

```text
🔌 Connect & Scan Old Account
```

Log in to the Spotify account containing the music you want to transfer.

The application will scan:

- Liked songs
- Followed artists
- User-owned playlists
- Tracks inside those playlists

After the scan completes, the backup is saved locally.

---

## Step 2 — Transfer to the New Account

Change the selector to:

```text
2. Transfer to New Account
```

The application will display the number of:

```text
Songs
Artists
Playlists
```

that are ready to transfer.

Click:

```text
🚀 Connect NEW Account & Start Migration
```

### ⚠️ Important

Make sure Spotify is logged into the **new account**.

If your browser is still logged into the old Spotify account, log out first or use a private/incognito browser window.

The application contains a safety check that compares the old and new Spotify account IDs.

If the same account is detected, the migration is stopped and no changes are made.

---

# 💾 Backup File

The application creates:

```text
spotify_backup.json
```

This file contains the migration data collected from the old account.

The backup allows the application to survive the OAuth redirect between the old and new account.

It also allows another migration attempt if the first transfer fails.

The backup is **not automatically deleted after a successful migration**.

---

# 🛡️ Rate Limits & Retries

The application includes handling for Spotify API rate limits.

When Spotify returns:

```text
HTTP 429
```

the application reads Spotify's:

```text
Retry-After
```

header and waits before trying again.

Temporary server errors such as:

```text
500
502
503
504
```

are also retried automatically using increasing delays.

The application additionally pauses briefly between batches of operations.

This helps reduce unnecessary API requests during large migrations.

---

# 📦 Batch Processing

Spotify operations are processed in batches rather than sending every track individually.

The application processes up to:

```text
40 tracks
```

per batch for library and playlist operations.

This significantly reduces the number of API requests required for large libraries.

---

# 📂 Playlists

Only playlists owned by the old account are migrated.

Collaborative or playlists owned by another account are not copied as user-owned playlists.

For each migrated playlist, the application preserves:

- Playlist name
- Description
- Public/private status
- Tracks

Podcast episodes are excluded from playlist migration.

Only Spotify music tracks are transferred.

---

# 🔒 Security

Spotify credentials are loaded through Streamlit Secrets:

```python
st.secrets["SPOTIFY_CLIENT_ID"]
st.secrets["SPOTIFY_CLIENT_SECRET"]
```

The application does not store Spotify access tokens in a persistent cache.

OAuth tokens are exchanged directly and the OAuth cache is disabled.

Do not publish:

```text
SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET
spotify_backup.json
.streamlit/secrets.toml
```

in a public GitHub repository.

---

# 🧹 Clear Backup

The sidebar contains:

```text
🗑️ Clear Backup
```

This removes the locally stored:

```text
spotify_backup.json
```

and clears the migration data from the Streamlit session.

Use this when you want to start a completely new migration.

---

# ⚠️ Important Limitations

This application is designed specifically for transferring the library data supported by the implemented Spotify API endpoints.

It does **not** transfer every possible piece of Spotify account data.

For example, the application does not migrate:

- Spotify account profile information
- Listening history
- Spotify Wrapped history
- Recommendations
- Account settings
- Subscription information
- Local files
- Other unsupported Spotify account data

---

# 🗂️ Project Structure

A minimal project can look like this:

```text
spotify-account-migrator/
│
├── app_local_fixed.py
├── README.md
├── .gitignore
│
└── .streamlit/
    └── secrets.toml
```

The following files should remain local and should not be committed:

```text
.streamlit/secrets.toml
spotify_backup.json
```

---

# 🧪 Troubleshooting

## Spotify credentials are missing

If you see:

```text
Spotify credentials are missing.
```

check:

```text
.streamlit/secrets.toml
```

and make sure both values exist:

```toml
SPOTIFY_CLIENT_ID = "..."
SPOTIFY_CLIENT_SECRET = "..."
```

---

## Redirect URI Error

Make sure the Redirect URI in Spotify Developer Dashboard is exactly the same as:

```text
http://127.0.0.1:8501/
```

Do not accidentally use:

```text
http://localhost:8501/
```

unless the application and Spotify configuration are both changed to use that URI.

---

## Same Account Detected

If the application reports:

```text
SAME ACCOUNT DETECTED!
```

you authorized the old Spotify account again.

Log out of Spotify and authorize the destination account.

Using a private/incognito browser window can help prevent the browser from automatically selecting the wrong Spotify session.

---

## Transfer Failed

If a transfer fails, the backup remains available:

```text
spotify_backup.json
```

This means you can attempt the migration again without rescanning the old account.

---

# 🧰 Technologies

This project uses:

- Python
- Streamlit
- Spotipy
- Requests
- Spotify Web API

---

# 📜 License

Add the license you want to use for this project.

For example:

```text
MIT License
```

If no license has been selected, the repository should not claim to be open-source licensed until a license is added.

---

# 👤 Author

Created for personal Spotify library migration between accounts.

---

## ⭐ Notes

This project is intended to make account-to-account library migration easier while keeping the source account and destination account OAuth flows separate.

Always verify the destination Spotify account before starting a migration.