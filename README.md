# 🎵 Spotify Account Migrator

A modern, web-based tool built with **Python**, **Streamlit**, and the **Spotipy SDK** (Spotify Web API). This application allows users to seamlessly transfer their entire music library from an old Spotify account to a new one, completely free and securely.

## ✨ Features
- **Liked Songs Migration:** Scans and transfers all your bookmarked tracks.
- **Followed Artists:** Automatically follows your favorite artists on the new account.
- **Playlists Transfer:** Recreates your owned playlists and copies all tracks sequentially.
- **Secure OAuth 2.0:** Uses official Spotify authentication. Access tokens expire automatically after 1 hour and are never stored.
- **Responsive UI:** Clean and modern interface that works beautifully on desktop and mobile devices (iOS & Android).

## 🛠️ Technology Stack
- **Backend:** Python 3
- **Framework:** Streamlit
- **API Wrapper:** Spotipy (Spotify Web API)

## 🚀 How to Run Locally
1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your local Streamlit secrets or environment variables for `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`.
4. Run the application:
   ```bash
   streamlit run app.py
   ```
