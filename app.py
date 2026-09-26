import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time

# --- STREAMLIT PAGE CONFIGURATION ---
st.set_page_config(page_title="Spotify Migrator v2", page_icon="🎵", layout="centered")

st.title("🎵 Spotify Account Migrator (Clean Version)")
st.write("Easily backup and restore your music library between accounts safely.")

# --- FETCH API CREDENTIALS FROM SECRETS ---
try:
    CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"]
except Exception:
    st.error("❌ Credentials missing in Streamlit Secrets! Please add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.")
    st.stop()

REDIRECT_URI = "https://spotify-account-migrator.streamlit.app/"
SCOPE = "user-library-read user-library-modify user-follow-read user-follow-modify playlist-read-private playlist-modify-private playlist-modify-public"

# --- INITIALIZE MEMORY FOR TRACKS ---
if "saved_library" not in st.session_state:
    st.session_state.saved_library = None

# --- SELECT OPERATION MODE ---
mode = st.selectbox("Choose what you want to do:", ["1. Scan & Backup Old Account", "2. Transfer to New Account"])

# Setup clean Auth Manager without messing with local system cache
auth_manager = SpotifyOAuth(
    client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
    scope=SCOPE, show_dialog=True, cache_path=None
)

query_params = st.query_params

# --- MODE 1: BACKUP OLD ACCOUNT ---
if mode == "1. Scan & Backup Old Account":
    st.subheader("Step 1: Scan your current music")
    st.write("Connect the account you want to copy songs FROM.")
    
    if st.session_state.saved_library is not None:
        lib = st.session_state.saved_library
        st.success(f"✅ Library backed up in memory! Found: {len(lib['tracks'])} Songs, {len(lib['artists'])} Artists, {len(lib['playlists'])} Playlists.")
        st.info("👉 Now, change the dropdown menu above to **'2. Transfer to New Account'**.")
    else:
        if "code" in query_params:
            try:
                token_info = auth_manager.get_access_token(query_params["code"], as_dict=True)
                sp = spotipy.Spotify(auth=token_info["access_token"])
                
                with st.spinner("⚡ Scanning your Spotify library... Please wait."):
                    # 1. Fetch Liked Songs Safely
                    liked_tracks = []
                    offset = 0
                    while True:
                        res = sp.current_user_saved_tracks(limit=50, offset=offset)
                        if not res['items']: break
                        for item in res['items']:
                            if item.get('track') and item['track'].get('id'):
                                liked_tracks.append(item['track']['id'])
                        offset += len(res['items'])
                        time.sleep(0.2)

                    # 2. Fetch Artists Safely
                    artists_to_follow = []
                    last_id = None
                    while True:
                        res = sp.current_user_followed_artists(limit=50, after=last_id)
                        artists = res['artists']['items']
                        if not artists: break
                        for artist in artists:
                            artists_to_follow.append(artist['id'])
                        if 'cursor' in res['artists'] and res['artists']['cursor'] is not None:
                            last_id = res['artists']['cursor']['after']
                        else:
                            last_id = None
                        if not last_id: break
                        time.sleep(0.2)

                    # 3. Fetch Playlists Safely
                    playlists_to_copy = []
                    offset = 0
                    u_id = sp.current_user()['id']
                    while True:
                        res = sp.current_user_playlists(limit=50, offset=offset)
                        if not res['items']: break
                        for item in res['items']:
                            if item['owner']['id'] == u_id:
                                t_ids = []
                                pl_offset = 0
                                while True:
                                    t_res = sp.playlist_tracks(item['id'], limit=100, offset=pl_offset)
                                    if not t_res['items']: break
                                    for t_item in t_res['items']:
                                        if t_item.get('track') and t_item['track'].get('id'):
                                            t_ids.append(t_item['track']['id'])
                                    pl_offset += len(t_res['items'])
                                    time.sleep(0.1)
                                
                                playlists_to_copy.append({
                                    'name': item['name'], 'description': item['description'] or "",
                                    'public': item['public'], 'tracks': t_ids
                                })
                        offset += len(res['items'])
                        time.sleep(0.2)

                st.session_state.saved_library = {
                    "tracks": liked_tracks, "artists": artists_to_follow, "playlists": playlists_to_copy
                }
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Scan failed: {e}")
        else:
            auth_url = auth_manager.get_authorize_url()
            st.link_button("🔌 Connect & Scan Old Account", auth_url, type="primary")

# --- MODE 2: RESTORE TO NEW ACCOUNT ---
elif mode == "2. Transfer to New Account":
    st.subheader("Step 2: Inject music into new account")
    
    if st.session_state.saved_library is None:
        st.warning("⚠️ No backup data found in memory! Please go back to Mode 1 and scan your old account first.")
    else:
        lib = st.session_state.saved_library
        st.info(f"Ready to transfer: **{len(lib['tracks'])}** Songs, **{len(lib['artists'])}** Artists, **{len(lib['playlists'])}** Playlists.")
        st.warning("🚨 BEFORE clicking below: Open a new tab, go to spotify.com and log in with your NEW account!")

        if "code" in query_params:
            try:
                token_info = auth_manager.get_access_token(query_params["code"], as_dict=True)
                sp_new = spotipy.Spotify(auth=token_info["access_token"])
                
                status = st.empty()
                sub_status = st.empty()
                bar = st.progress(0)
                
                total = len(lib['tracks']) + len(lib['artists']) + len(lib['playlists'])
                current = 0
                
                # 1. Copy Songs
                if lib['tracks']:
                    status.markdown("### 📥 Injecting Liked Songs...")
                    for i in range(0, len(lib['tracks']), 50):
                        chunk = lib['tracks'][i:i+50]
                        sp_new.current_user_saved_tracks_add(tracks=chunk)
                        current += len(chunk)
                        sub_status.write(f"Processed: **{current}** / **{len(lib['tracks'])}** songs.")
                        bar.progress(min(current / total, 1.0))
                        time.sleep(0.3)

                # 2. Copy Artists
                if lib['artists']:
                    status.markdown("### 👤 Following Artists...")
                    art_curr = 0
                    for i in range(0, len(lib['artists']), 50):
                        chunk = lib['artists'][i:i+50]
                        sp_new.user_follow_artists(ids=chunk)
                        current += len(chunk)
                        art_curr += len(chunk)
                        sub_status.write(f"Followed: **{art_curr}** / **{len(lib['artists'])}** artists.")
                        bar.progress(min(current / total, 1.0))
                        time.sleep(0.3)

                # 3. Copy Playlists
                if lib['playlists']:
                    status.markdown("### 📂 Creating Playlists...")
                    u_id_new = sp_new.current_user()['id']
                    pl_idx = 0
                    for pl in lib['playlists']:
                        pl_idx += 1
                        sub_status.write(f"Creating playlist {pl_idx}/{len(lib['playlists'])}: **{pl['name']}**")
                        new_pl = sp_new.user_playlist_create(
                            user=u_id_new, name=pl['name'], public=pl['public'], description=pl['description']
                        )
                        if pl['tracks']:
                            for i in range(0, len(pl['tracks']), 100):
                                chunk = pl['tracks'][i:i+100]
                                sp_new.playlist_add_items(playlist_id=new_pl['id'], items=chunk)
                                time.sleep(0.3)
                        current += 1
                        bar.progress(min(current / total, 1.0))

                status.empty()
                sub_status.empty()
                st.balloons()
                st.success("🎉 Success! Your music library has been completely migrated!")
                st.session_state.saved_library = None
                st.query_params.clear()
            except Exception as e:
                st.error(f"Transfer failed: {e}")
        else:
            auth_url = auth_manager.get_authorize_url()
            st.link_button("🚀 Start Migration to New Account", auth_url, type="primary")
