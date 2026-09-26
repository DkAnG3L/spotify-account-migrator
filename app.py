import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time

# --- STREAMLIT PAGE CONFIG ---
st.set_page_config(page_title="Spotify Migrator", page_icon="🎵", layout="centered")

st.title("🎵 Spotify Account Migrator")
st.write("Transfer your Liked Songs, Playlists, and Followed Artists to a new account completely free.")

# --- SPOTIFY API CONFIG (From Streamlit Secrets) ---
# When deployed, you will add these in the Streamlit Cloud Dashboard settings
try:
    CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"]
except Exception:
    st.error("❌ Missing Spotify API Credentials in Streamlit Secrets!")
    st.stop()

# Streamlit URL format (Replace with your actual streamlit app URL once deployed)
REDIRECT_URI = "http://localhost:8501/" # Change this to your live URL later, e.g., https://streamlit.app

SCOPE = "user-library-read user-library-modify user-follow-read user-follow-modify playlist-read-private playlist-modify-private playlist-modify-public"

# --- INITIALIZE SESSION STATE ---
# This acts as a temporary memory for each user browsing the website
if "old_account_data" not in st.session_state:
    st.session_state.old_account_data = None
if "old_connected" not in st.session_state:
    st.session_state.old_connected = False
if "new_connected" not in st.session_state:
    st.session_state.new_connected = False

# --- STEP 1: CONNECT & FETCH FROM OLD ACCOUNT ---
st.subheader("Step 1: Connect Old Account")

# Spotify OAuth Setup
auth_manager_old = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    show_dialog=True,
    cache_path=".cache-old"
)

# Check if Spotify redirected back with an auth code
query_params = st.query_params
if "code" in query_params and not st.session_state.old_connected and not st.session_state.new_connected:
    try:
        token_info = auth_manager_old.get_access_token(query_params["code"], as_dict=False)
        sp_old = spotipy.Spotify(auth=token_info)
        
        with st.spinner("⚡ Fetching your music library... Please wait."):
            # 1. Fetch Liked Songs
            liked_tracks = []
            offset = 0
            while True:
                results = sp_old.current_user_saved_tracks(limit=50, offset=offset)
                items = results['items']
                if not items: break
                for item in items:
                    liked_tracks.append(item['track']['id'])
                offset += len(items)

            # 2. Fetch Artists
            artists_to_follow = []
            last_artist_id = None
            while True:
                results = sp_old.current_user_followed_artists(limit=50, after=last_artist_id)
                artists = results['artists']['items']
                if not artists: break
                for artist in artists:
                    artists_to_follow.append(artist['id'])
                last_artist_id = results['artists']['cursor']['after']
                if not last_artist_id: break

            # 3. Fetch Playlists
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
                                if t_item['track'] and t_item['track']['id']:
                                    track_ids.append(t_item['track']['id'])
                            playlist_tracks_offset += len(t_items)
                        
                        playlists_to_copy.append({
                            'name': item['name'],
                            'description': item['description'] or "",
                            'public': item['public'],
                            'tracks': track_ids
                        })
                offset += len(items)

            # Save everything to the temporary session memory
            st.session_state.old_account_data = {
                "liked_tracks": liked_tracks,
                "artists": artists_to_follow,
                "playlists": playlists_to_copy
            }
            st.session_state.old_connected = True
            st.query_params.clear() # Clear the code from URL
    except Exception as e:
        st.error(f"Authentication failed: {e}")

# Display UI based on connection state
if not st.session_state.old_connected:
    auth_url_old = auth_manager_old.get_authorize_url()
    st.link_button("🔌 Connect Old Account", auth_url_old, type="primary")
else:
    data = st.session_state.old_account_data
    st.success(f"✅ Successfully scanned! Found: {len(data['liked_tracks'])} Liked Songs, {len(data['artists'])} Artists, {len(data['playlists'])} Playlists.")

# --- STEP 2: CONNECT TO NEW ACCOUNT ---
if st.session_state.old_connected:
    st.divider()
    st.subheader("Step 2: Connect New Account")
    st.info("⚠️ Before clicking below, open a new browser tab, go to spotify.com and LOG OUT from your old account!")
    
    auth_manager_new = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        show_dialog=True,
        cache_path=".cache-new"
    )

    if "code" in query_params and st.session_state.old_connected and not st.session_state.new_connected:
        try:
            token_info_new = auth_manager_new.get_access_token(query_params["code"], as_dict=False)
            st.session_state.sp_new = spotipy.Spotify(auth=token_info_new)
            st.session_state.new_connected = True
            st.query_params.clear()
        except Exception as e:
            st.error(f"Failed to connect new account: {e}")

    if not st.session_state.new_connected:
        auth_url_new = auth_manager_new.get_authorize_url()
        st.link_button("🔌 Connect New Account", auth_url_new, type="primary")
    else:
        st.success("✅ New account connected and ready!")

# --- STEP 3: EXECUTE MIGRATION ---
if st.session_state.new_connected:
    st.divider()
    st.subheader("Step 3: Start Transfer")
    
    if st.button("🚀 Start Migration Now", type="secondary"):
        sp_new = st.session_state.sp_new
        data = st.session_state.old_account_data
        
        # UI Progress elements built into Streamlit
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        total_steps = len(data['liked_tracks']) + len(data['artists']) + len(data['playlists'])
        current_step = 0
        
        # 1. Transfer Liked Songs
        if data['liked_tracks']:
            status_text.text("Copying Liked Songs...")
            for i in range(0, len(data['liked_tracks']), 50):
                chunk = data['liked_tracks'][i:i+50]
                sp_new.current_user_saved_tracks_add(tracks=chunk)
                current_step += len(chunk)
                progress_bar.progress(min(current_step / total_steps, 1.0))
                time.sleep(0.2)

        # 2. Transfer Artists
        if data['artists']:
            status_text.text("Following Artists...")
            for i in range(0, len(data['artists']), 50):
                chunk = data['artists'][i:i+50]
                sp_new.user_follow_artists(ids=chunk)
                current_step += len(chunk)
                progress_bar.progress(min(current_step / total_steps, 1.0))
                time.sleep(0.2)

        # 3. Transfer Playlists
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
        st.balloons() # Fun Streamlit feature that throws digital balloons on screen!
        st.success("🎉 Success! Your complete library has been migrated!")
        
        # Reset memory after success
        st.session_state.old_account_data = None
        st.session_state.old_connected = False
        st.session_state.new_connected = False
