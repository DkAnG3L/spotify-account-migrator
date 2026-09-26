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
if "token_new" not in st.session_state:
    st.session_state.token_new = None

# --- AUTHENTICATION LOGIC ---
query_params = st.query_params

if "code" in query_params and "state" in query_params:
    code = query_params["code"]
    state = query_params["state"]
    
    if state == "old_account" and not st.session_state.old_connected:
        try:
            auth_manager_old = SpotifyOAuth(
                client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
                scope=SCOPE, show_dialog=True, cache_path=None, state="old_account"
            )
            token_info = auth_manager_old.get_access_token(code, as_dict=True)
            sp_old = spotipy.Spotify(auth=token_info["access_token"])
            
            with st.spinner("⚡ Fetching your music library... Please wait. This might take a minute for large libraries."):
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
                st.query_params.clear() 
                st.rerun()
        except Exception as e:
            st.error(f"Old account authentication failed: {e}")

    elif state == "new_account" and st.session_state.old_connected and not st.session_state.new_connected:
        try:
            auth_manager_new = SpotifyOAuth(
                client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
                scope=SCOPE, show_dialog=True, cache_path=None, state="new_account"
            )
            token_info_new = auth_manager_new.get_access_token(code, as_dict=True)
            st.session_state.token_new = token_info_new["access_token"]
            st.session_state.new_connected = True
            st.query_params.clear() 
            st.rerun()
        except Exception as e:
            st.error(f"New account authentication failed: {e}")

# --- STEP 1: UI RENDER ---
st.subheader("Step 1: Connect Old Account")
if not st.session_state.old_connected:
    auth_manager_old = SpotifyOAuth(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
        scope=SCOPE, show_dialog=True, cache_path=None, state="old_account"
    )
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
        st.info("⚠️ Before clicking below, make sure you are logged in to your NEW account on spotify.com!")
        auth_manager_new = SpotifyOAuth(
            client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
            scope=SCOPE, show_dialog=True, cache_path=None, state="new_account"
        )
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
        detailed_stats = st.empty()
        progress_bar = st.progress(0)
        
        total_steps = len(data['liked_tracks']) + len(data['artists']) + len(data['playlists'])
        current_step = 0
        
        if data['liked_tracks']:
            status_text.markdown("### 📥 Copying Liked Songs...")
            for i in range(0, len(data['liked_tracks']), 50):
                chunk = data['liked_tracks'][i:i+50]
                sp_new.current_user_saved_tracks_add(tracks=chunk)
                current_step += len(chunk)
                detailed_stats.write(f"🔄 Progress: **{current_step}** / **{len(data['liked_tracks'])}** songs processed.")
                progress_bar.progress(min(current_step / total_steps, 1.0))
                time.sleep(0.3)

        if data['artists']:
            status_text.markdown("### 👤 Following Artists...")
            artist_step = 0
            for i in range(0, len(data['artists']), 50):
                chunk = data['artists'][i:i+50]
                sp_new.user_follow_artists(ids=chunk)
                current_step += len(chunk)
                artist_step += len(chunk)
                detailed_stats.write(f"🔄 Progress: **{artist_step}** / **{len(data['artists'])}** artists followed.")
                progress_bar.progress(min(current_step / total_steps, 1.0))
                time.sleep(0.3)

        if data['playlists']:
            status_text.markdown("### 📂 Creating Playlists...")
            new_user_id = sp_new.current_user()['id']
            playlist_count = 0
            for pl in data['playlists']:
                playlist_count += 1
                detailed_stats.write(f"🔨 Creating: **{pl['name']}** ({playlist_count} of {len(data['playlists'])}) with {len(pl['tracks'])} tracks.")
                new_pl = sp_new.user_playlist_create(
                    user=new_user_id, name=pl['name'], public=pl['public'], description=pl['description']
                )
                if pl['tracks']:
                    for i in range(0, len(pl['tracks']), 100):
                        chunk = pl['tracks'][i:i+100]
                        sp_new.playlist_add_items(playlist_id=new_pl['id'], items=chunk)
                        time.sleep(0.3)
                current_step += 1
                progress_bar.progress(min(current_step / total_steps, 1.0))
                status_text.empty()
                detailed_stats.empty()
                st.balloons()
                st.success("🎉 Success! Your complete library has been migrated!")
                st.session_state.old_account_data = Nonest.session_state.old_connected = Falsest.session_state.new_connected = Falsest.session_state.token_new = Nonetime.sleep(5)
                st.rerun()

