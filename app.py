import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time

# --- STREAMLIT PAGE CONFIGURATION ---
st.set_page_config(page_title="Spotify Migrator", page_icon="🎵", layout="centered")

st.title("🎵 Spotify Account Migrator")
st.write("Transfer your Liked Songs, Playlists, and Followed Artists to a new account completely free.")

# --- SPOTIFY API CREDENTIALS ---
try:
    CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"]
except Exception:
    st.error("❌ Missing Spotify API Credentials in Streamlit Secrets!")
    st.stop()

REDIRECT_URI = "https://spotify-account-migrator.streamlit.app/"
SCOPE = "user-library-read user-library-modify user-follow-read user-follow-modify playlist-read-private playlist-modify-private playlist-modify-public"

# --- INITIALIZE WEB SESSION MEMORY ---
if "old_account_data" not in st.session_state:
    st.session_state.old_account_data = None
if "old_connected" not in st.session_state:
    st.session_state.old_connected = False
if "new_connected" not in st.session_state:
    st.session_state.new_connected = False
if "token_old" not in st.session_state:
    st.session_state.token_old = None
if "token_new" not in st.session_state:
    st.session_state.token_new = None

# --- SETUP OAUTH MANAGERS WITH NO CACHE FILES ---
auth_manager_old = SpotifyOAuth(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
    scope=SCOPE, show_dialog=True, cache_path=None
)

auth_manager_new = SpotifyOAuth(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
    scope=SCOPE, show_dialog=True, cache_path=None
)

# Intercept callback parameters
query_params = st.query_params

# --- AUTHENTICATION LOGIC ---
if "code" in query_params:
    code = query_params["code"]
    
    # If Step 1 is not done yet, this code belongs to the OLD account
    if not st.session_state.old_connected:
        try:
            token_info = auth_manager_old.get_access_token(code, as_dict=True)
            st.session_state.token_old = token_info["access_token"]
            sp_old = spotipy.Spotify(auth=st.session_state.token_old)
            
            with st.spinner("⚡ Fetching your music library... Please wait."):
                # Fetch Liked Songs Safely
                liked_tracks = []
                offset = 0
                while True:
                    results = sp_old.current_user_saved_tracks(limit=50, offset=offset)
                    items = results['items']
                    if not items: break
                    for item in items:
                        if item.get('track') and item['track'].get('id'):
                            liked_tracks.append(item['track']['id'])
                    offset += len(items)

                # Fetch Followed Artists Safely
                artists_to_follow = []
                last_artist_id = None
                while True:
                    results = sp_old.current_user_followed_artists(limit=50, after=last_artist_id)
                    artists = results['artists']['items']
                    if not artists: break
                    for artist in artists:
                        artists_to_follow.append(artist['id'])
                    if 'cursor' in results['artists'] and results['artists']['cursor'] is not None:
                        last_artist_id = results['artists']['cursor']['after']
                    else:
                        last_artist_id = None
                    if not last_artist_id: break

                # Fetch Playlists Safely
                playlists_to_copy = []
                offset = 0
                current_user_id = sp_old.current_user()['id']
                while True:
                    results = sp_old.current_user_playlists(limit=50, offset=offset)
                    items = results['items']
                    if not items: break
                    for item in items:
                        if item['owner']['id'] == current_user_id:
                            track_ids = []
                            playlist_tracks_offset = 0
                            while True:
                                t_results = sp_old.playlist_tracks(item['id'], limit=100, offset=playlist_tracks_offset)
                                t_items = t_results['items']
                                if not t_items: break
                                for t_item in t_items:
                                    if t_item.get('track') and t_item['track'].get('id'):
                                        track_ids.append(t_item['track']['id'])
                                playlist_tracks_offset += len(t_items)
                            
                            playlists_to_copy.append({
                                'name': item['name'],
                                'description': item['description'] or "",
                                'public': item['public'],
                                'tracks': track_ids
                            })
                    offset += len(items)

                st.session_state.old_account_data = {
                    "liked_tracks": liked_tracks,
                    "artists": artists_to_follow,
                    "playlists": playlists_to_copy
                }
                st.session_state.old_connected = True
                st.query_params.clear() # Clear URL to break the loop!
                st.rerun()
        except Exception as e:
            st.error(f"Old account authentication failed: {e}")

    # If Step 1 IS done, but Step 2 is NOT, this code belongs to the NEW account
    elif st.session_state.old_connected and not st.session_state.new_connected:
        try:
            token_info_new = auth_manager_new.get_access_token(code, as_dict=True)
            st.session_state.token_new = token_info_new["access_token"]
            st.session_state.new_connected = True
            st.query_params.clear() # Clear URL
            st.rerun()
        except Exception as e:
            st.error(f"New account authentication failed: {e}")

# --- STEP 1: UI RENDER ---
st.subheader("Step 1: Connect Old Account")
if not st.session_state.old_connected:
    auth_url_old = auth_manager_old.get_authorize_url()
    st.link_button("🔌 Connect Old Account", auth_url_old, type="primary")
else:
    data = st.session_state.old_account_data
    st.success(f"✅ Successfully scanned! Found: {len(data['liked_tracks'])} Liked Songs, {len(data['artists'])} Artists, {len(data['playlists'])} Playlists.")

# --- STEP 2: UI RENDER ---
if st.session_state.old_connected:
    st.divider()
    st.subheader("Step 2: Connect New Account")
    
    if not st.session_state.new_connected:
        st.info("⚠️ Click 'Not you?' or Log Out at spotify.com before connecting the new account!")
        auth_url_new = auth_manager_new.get_authorize_url()
        st.link_button("🔌 Connect New Account", auth_url_new, type="primary")
    else:
        st.success("✅ New account connected and ready!")

# --- STEP 3: UI RENDER & EXECUTION ---
if st.session_state.new_connected:
    st.divider()
    st.subheader("Step 3: Start Transfer")
    
    if st.button("🚀 Start Migration Now", type="secondary"):
        sp_new = spotipy.Spotify(auth=st.session_state.token_new)
        data = st.session_state.old_account_data
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        total_steps = len(data['liked_tracks']) + len(data['artists']) + len(data['playlists'])
        current_step = 0
        
        if data['liked_tracks']:
            status_text.text("Copying Liked Songs...")
            for i in range(0, len(data['liked_tracks']), 50):
                chunk = data['liked_tracks'][i:i+50]
                sp_new.current_user_saved_tracks_add(tracks=chunk)
                current_step += len(chunk)
                progress_bar.progress(min(current_step / total_steps, 1.0))
                time.sleep(0.2)

        if data['artists']:
            status_text.text("Following Artists...")
            for i in range(0, len(data['artists']), 50):
                chunk = data['artists'][i:i+50]
                sp_new.user_follow_artists(ids=chunk)
                current_step += len(chunk)
                progress_bar.progress(min(current_step / total_steps, 1.0))
                time.sleep(0.2)

        if data['playlists']:
            new_user_id = sp_new.current_user()['id']
            for pl in data['playlists']:
                status_text.text(f"Creating playlist: {pl['name']}")
                new_pl = sp_new.user_playlist_create(
                    user=new_user_id, name=pl['name'], public=pl['public'], description=pl['description']
                )
                if pl['tracks']:
                    for i in range(0, len(pl['tracks']), 100):
                        chunk = pl['tracks'][i:i+100]
                        sp_new.playlist_add_items(playlist_id=new_pl['id'], items=chunk)
                        time.sleep(0.2)
                current_step += 1
                progress_bar.progress(min(current_step / total_steps, 1.0))

        status_text.empty()
        st.balloons() 
        st.success("🎉 Success! Your complete library has been migrated!")
        
        # Reset memory after success
        st.session_state.old_account_data = None
        st.session_state.old_connected = False
        st.session_state.new_connected = False
        st.session_state.token_old = None
        st.session_state.token_new = None
        st.rerun()
