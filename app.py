import json
import time
import requests
from pathlib import Path
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth


# ============================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Spotify Account Migrator",
    page_icon="🎵",
    layout="centered"
)

st.title("🎵 Spotify Account Migrator")
st.write(
    "Backup and transfer your Spotify music library between accounts."
)


# ============================================================
# SPOTIFY CREDENTIALS
# ============================================================

try:
    CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"]

except Exception:
    st.error(
        "❌ Spotify credentials are missing.\n\n"
        "Please add SPOTIFY_CLIENT_ID and "
        "SPOTIFY_CLIENT_SECRET to Streamlit Secrets."
    )
    st.stop()


# ============================================================
# REDIRECT URI
# ============================================================
#
# IMPORTANT:
#
# If running locally:
#
# REDIRECT_URI = "http://127.0.0.1:8501/"
#
# If using Streamlit Community Cloud, CHANGE THIS to your
# Streamlit app URL, for example:
#
# REDIRECT_URI = "https://your-app-name.streamlit.app/"
#
# The URI must EXACTLY match the URI configured in Spotify
# Developer Dashboard.
#
# ============================================================

REDIRECT_URI = "https://spotify-account-migrator.streamlit.app/"


# ============================================================
# SPOTIFY SCOPES
# ============================================================

SCOPE = (
    "user-library-read "
    "user-library-modify "
    "user-follow-read "
    "user-follow-modify "
    "playlist-read-private "
    "playlist-read-collaborative "
    "playlist-modify-private "
    "playlist-modify-public"
)


# ============================================================
# SPOTIFY API
# ============================================================

SPOTIFY_API = "https://api.spotify.com/v1"

# Persistent backup file.
# This is important for Streamlit because the browser can return
# from Spotify OAuth in a fresh Streamlit session.
BACKUP_FILE = "spotify_backup.json"


# ============================================================
# PERSISTENT BACKUP HELPERS
# ============================================================

def save_backup(library, account_id, account_name):
    data = {
        "old_account_id": account_id,
        "old_account_name": account_name,
        "library": library,
    }

    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_backup():
    path = Path(BACKUP_FILE)

    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        library = data.get("library")

        if not library:
            return None

        return data

    except Exception:
        return None


def delete_backup():
    path = Path(BACKUP_FILE)

    if path.exists():
        path.unlink()


# ============================================================
# SESSION STATE
# ============================================================

if "saved_library" not in st.session_state:
    st.session_state.saved_library = None

if "old_account_id" not in st.session_state:
    st.session_state.old_account_id = None

if "old_account_name" not in st.session_state:
    st.session_state.old_account_name = None

if "migration_finished" not in st.session_state:
    st.session_state.migration_finished = False

# Restore backup from disk if the current Streamlit session does not
# have it. This is the key fix for the OLD -> NEW OAuth redirect.
if st.session_state.saved_library is None:
    backup_data = load_backup()

    if backup_data:
        st.session_state.saved_library = backup_data.get("library")
        st.session_state.old_account_id = backup_data.get("old_account_id")
        st.session_state.old_account_name = backup_data.get("old_account_name")


# ============================================================
# OAUTH
# ============================================================

def create_oauth():
    """
    Create a fresh OAuth manager.

    No token cache is used because we want the OLD and NEW
    Spotify accounts to remain completely separate.
    """

    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        show_dialog=True,
        cache_path=None
    )


def get_auth_url(flow):
    """
    Create Spotify authorization URL.

    flow:
        "old" = old account
        "new" = new account

    We put the flow into OAuth 'state' so that after Spotify
    redirects back to Streamlit, we know which account the
    authorization belongs to.
    """

    oauth = create_oauth()

    return oauth.get_authorize_url(
        state=flow
    )


def exchange_code(code):
    """
    Exchange Spotify authorization code for an access token.

    We do this directly instead of using Spotipy's deprecated
    get_access_token(..., as_dict=True), so the app does not produce
    the deprecation warning.
    """

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=60,
    )

    if response.status_code != 200:
        try:
            details = response.json()
        except Exception:
            details = response.text

        raise RuntimeError(
            f"Spotify OAuth token exchange failed "
            f"({response.status_code}): {details}"
        )

    return response.json()



# ============================================================
# GENERIC SPOTIFY REQUEST
# ============================================================

def spotify_request(
    access_token,
    method,
    endpoint,
    params=None,
    json_data=None,
    retries=5
):
    """
    Generic Spotify API request.

    Handles:
      - authorization
      - rate limiting
      - temporary Spotify errors
    """

    url = f"{SPOTIFY_API}/{endpoint.lstrip('/')}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    for attempt in range(retries):

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
            timeout=60
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if 200 <= response.status_code < 300:

            if response.status_code == 204:
                return {}

            if not response.text:
                return {}

            return response.json()

        # ----------------------------------------------------
        # RATE LIMIT
        # ----------------------------------------------------

        if response.status_code == 429:

            retry_after = response.headers.get(
                "Retry-After",
                "5"
            )

            try:
                wait_time = int(retry_after)
            except ValueError:
                wait_time = 5

            st.warning(
                f"⏳ Spotify rate limit. "
                f"Waiting {wait_time} seconds..."
            )

            time.sleep(max(wait_time, 1))

            continue

        # ----------------------------------------------------
        # TEMPORARY SERVER ERROR
        # ----------------------------------------------------

        if response.status_code in (
            500,
            502,
            503,
            504
        ):

            wait_time = 2 ** attempt

            time.sleep(wait_time)

            continue

        # ----------------------------------------------------
        # NORMAL ERROR
        # ----------------------------------------------------

        try:
            error = response.json()
        except Exception:
            error = response.text

        raise RuntimeError(
            f"Spotify API error {response.status_code}: {error}"
        )

    raise RuntimeError(
        "Spotify API request failed after multiple retries."
    )


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user(access_token):

    return spotify_request(
        access_token,
        "GET",
        "me"
    )


# ============================================================
# GET LIKED SONGS
# ============================================================

def get_saved_tracks(access_token):

    tracks = []

    offset = 0

    while True:

        data = spotify_request(
            access_token,
            "GET",
            "me/tracks",
            params={
                "limit": 50,
                "offset": offset
            }
        )

        items = data.get("items", [])

        if not items:
            break

        for item in items:

            track = item.get("track")

            if track and track.get("id"):

                tracks.append(
                    track["id"]
                )

        offset += len(items)

        total = data.get("total", 0)

        if offset >= total:
            break

    return tracks


# ============================================================
# GET FOLLOWED ARTISTS
# ============================================================

def get_followed_artists(access_token):

    artists = []

    after = None

    while True:

        params = {
            "type": "artist",
            "limit": 50
        }

        if after:
            params["after"] = after

        data = spotify_request(
            access_token,
            "GET",
            "me/following",
            params=params
        )

        artist_data = data.get(
            "artists",
            {}
        )

        items = artist_data.get(
            "items",
            []
        )

        if not items:
            break

        for artist in items:

            if artist.get("id"):

                artists.append(
                    artist["id"]
                )

        cursors = artist_data.get(
            "cursors",
            {}
        )

        after = cursors.get(
            "after"
        )

        if not after:
            break

    return artists


# ============================================================
# GET USER PLAYLISTS
# ============================================================

def get_playlists(
    access_token,
    user_id
):

    playlists = []

    offset = 0

    while True:

        data = spotify_request(
            access_token,
            "GET",
            "me/playlists",
            params={
                "limit": 50,
                "offset": offset
            }
        )

        items = data.get(
            "items",
            []
        )

        if not items:
            break

        for playlist in items:

            owner = playlist.get(
                "owner",
                {}
            )

            # Only playlists owned by the old account
            if owner.get("id") != user_id:
                continue

            playlist_id = playlist.get(
                "id"
            )

            if not playlist_id:
                continue

            tracks = get_playlist_tracks(
                access_token,
                playlist_id
            )

            playlists.append(
                {
                    "name": playlist.get(
                        "name",
                        "Untitled Playlist"
                    ),

                    "description": (
                        playlist.get(
                            "description"
                        ) or ""
                    ),

                    "public": bool(
                        playlist.get(
                            "public",
                            True
                        )
                    ),

                    "tracks": tracks
                }
            )

        offset += len(items)

        total = data.get(
            "total",
            0
        )

        if offset >= total:
            break

    return playlists


# ============================================================
# GET PLAYLIST ITEMS
# ============================================================

def get_playlist_tracks(
    access_token,
    playlist_id
):

    tracks = []

    offset = 0

    while True:

        data = spotify_request(
            access_token,
            "GET",
            f"playlists/{playlist_id}/items",
            params={
                "limit": 50,
                "offset": offset
            }
        )

        items = data.get(
            "items",
            []
        )

        if not items:
            break

        for item in items:

            track = item.get(
                "item"
            )

            if not track:
                continue

            # We only migrate music tracks,
            # not podcast episodes.
            if track.get("type") != "track":
                continue

            uri = track.get(
                "uri"
            )

            if uri:
                tracks.append(
                    uri
                )

        offset += len(items)

        total = data.get(
            "total",
            0
        )

        if offset >= total:
            break

    return tracks


# ============================================================
# SAVE LIKED SONGS TO NEW ACCOUNT
# ============================================================

def save_tracks(
    access_token,
    track_ids
):

    if not track_ids:
        return

    # Spotify currently accepts max 40 URIs
    # per /me/library request.
    for i in range(
        0,
        len(track_ids),
        40
    ):

        chunk = track_ids[
            i:i + 40
        ]

        uris = [
            f"spotify:track:{track_id}"
            for track_id in chunk
        ]

        spotify_request(
            access_token,
            "PUT",
            "me/library",
            params={
                "uris": ",".join(uris)
            }
        )

        time.sleep(0.8)


# ============================================================
# FOLLOW ARTISTS
# ============================================================

def follow_artists(
    access_token,
    artist_ids
):

    if not artist_ids:
        return

    for i in range(
        0,
        len(artist_ids),
        40
    ):

        chunk = artist_ids[
            i:i + 40
        ]

        uris = [
            f"spotify:artist:{artist_id}"
            for artist_id in chunk
        ]

        spotify_request(
            access_token,
            "PUT",
            "me/library",
            params={
                "uris": ",".join(uris)
            }
        )

        time.sleep(0.8)


# ============================================================
# CREATE PLAYLIST
# ============================================================

def create_playlist(
    access_token,
    name,
    public,
    description
):

    return spotify_request(
        access_token,
        "POST",
        "me/playlists",
        json_data={
            "name": name,
            "public": bool(public),
            "description": description or ""
        }
    )


# ============================================================
# ADD TRACKS TO PLAYLIST
# ============================================================

def add_playlist_tracks(
    access_token,
    playlist_id,
    track_uris
):

    if not track_uris:
        return

    # Keep batches at 40.
    for i in range(
        0,
        len(track_uris),
        40
    ):

        chunk = track_uris[
            i:i + 40
        ]

        spotify_request(
            access_token,
            "POST",
            f"playlists/{playlist_id}/items",
            params={
                "uris": ",".join(chunk)
            }
        )

        time.sleep(0.8)


# ============================================================
# QUERY PARAMETERS
# ============================================================

query_params = st.query_params

authorization_code = query_params.get(
    "code"
)

authorization_state = query_params.get(
    "state"
)

authorization_error = query_params.get(
    "error"
)


# ============================================================
# AUTH ERROR
# ============================================================

if authorization_error:

    st.error(
        f"❌ Spotify authorization failed: "
        f"{authorization_error}"
    )

    if st.button("Try Again"):

        st.query_params.clear()

        st.rerun()

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Controls")

    if st.button(
        "🗑️ Clear Backup",
        use_container_width=True
    ):

        st.session_state.saved_library = None
        st.session_state.old_account_id = None
        st.session_state.old_account_name = None
        st.session_state.migration_finished = False

        delete_backup()

        st.query_params.clear()

        st.rerun()


# ============================================================
# MODE SELECTOR
# ============================================================

# If Spotify sent us back from OAuth, don't let the
# selectbox decide which flow we are in.
#
# OAuth state determines it.
# ============================================================

if authorization_code and authorization_state == "new":

    mode = "2. Transfer to New Account"

elif authorization_code and authorization_state == "old":

    mode = "1. Scan & Backup Old Account"

else:

    mode = st.selectbox(
        "Choose what you want to do:",
        [
            "1. Scan & Backup Old Account",
            "2. Transfer to New Account"
        ]
    )


# ============================================================
# MODE 1
# BACKUP OLD ACCOUNT
# ============================================================

if mode == "1. Scan & Backup Old Account":

    st.subheader(
        "Step 1: Scan your current music"
    )

    st.write(
        "Connect the account you want to copy "
        "songs FROM."
    )

    # --------------------------------------------------------
    # BACKUP ALREADY EXISTS
    # --------------------------------------------------------

    if st.session_state.saved_library is not None:

        lib = st.session_state.saved_library

        st.success(
            "✅ Library backed up in memory!"
        )

        st.info(
            f"Account: **"
            f"{st.session_state.old_account_name}"
            f"**\n\n"
            f"🎵 Songs: **{len(lib['tracks'])}**\n\n"
            f"👤 Artists: **{len(lib['artists'])}**\n\n"
            f"📂 Playlists: **{len(lib['playlists'])}**"
        )

        st.success(
            "👉 Now change the dropdown to "
            "**2. Transfer to New Account**."
        )

    # --------------------------------------------------------
    # OLD ACCOUNT CALLBACK
    # --------------------------------------------------------

    elif (
        authorization_code
        and authorization_state == "old"
    ):

        try:

            with st.spinner(
                "🔐 Connecting to OLD Spotify account..."
            ):

                token_info = exchange_code(
                    authorization_code
                )

                access_token = token_info[
                    "access_token"
                ]

                old_user = get_current_user(
                    access_token
                )

            old_user_id = old_user.get(
                "id"
            )

            old_user_name = (
                old_user.get(
                    "display_name"
                )
                or old_user_id
                or "Spotify User"
            )

            st.session_state.old_account_id = (
                old_user_id
            )

            st.session_state.old_account_name = (
                old_user_name
            )

            # ------------------------------------------------
            # SCAN
            # ------------------------------------------------

            with st.spinner(
                "⚡ Scanning Spotify library..."
            ):

                st.write(
                    "🎵 Reading liked songs..."
                )

                liked_tracks = get_saved_tracks(
                    access_token
                )

                st.write(
                    "👤 Reading followed artists..."
                )

                artists_to_follow = (
                    get_followed_artists(
                        access_token
                    )
                )

                st.write(
                    "📂 Reading playlists..."
                )

                playlists_to_copy = get_playlists(
                    access_token,
                    old_user_id
                )

            # ------------------------------------------------
            # SAVE TO STREAMLIT SESSION
            # ------------------------------------------------

            st.session_state.saved_library = {
                "tracks": liked_tracks,
                "artists": artists_to_follow,
                "playlists": playlists_to_copy
            }

            # IMPORTANT:
            # Also save the backup to disk so it survives the Spotify
            # OAuth redirect / Streamlit session change.
            save_backup(
                st.session_state.saved_library,
                old_user_id,
                old_user_name
            )

            # Remove OAuth code
            st.query_params.clear()

            st.success(
                "🎉 Backup completed successfully!"
            )

            st.info(
                f"💾 Backup saved locally as **{BACKUP_FILE}**. "
                "You can now switch to Transfer."
            )

            st.rerun()

        except Exception as e:

            st.error(
                "❌ Scan failed."
            )

            st.exception(e)

    # --------------------------------------------------------
    # START OLD ACCOUNT AUTH
    # --------------------------------------------------------

    else:

        st.warning(
            "⚠️ Connect your OLD Spotify account here."
        )

        auth_url = get_auth_url(
            "old"
        )

        st.link_button(
            "🔌 Connect & Scan Old Account",
            auth_url,
            type="primary",
            use_container_width=True
        )


# ============================================================
# MODE 2
# TRANSFER TO NEW ACCOUNT
# ============================================================

elif mode == "2. Transfer to New Account":

    st.subheader(
        "Step 2: Inject music into new account"
    )

    # --------------------------------------------------------
    # NO BACKUP
    # --------------------------------------------------------

    if st.session_state.saved_library is None:

        st.warning(
            "⚠️ No backup data was found.\n\n"
            "Please scan the OLD Spotify account first. "
            "The scan will be saved locally so it survives "
            "the OAuth redirect."
        )

    else:

        lib = st.session_state.saved_library

        st.info(
            f"Ready to transfer:\n\n"
            f"🎵 **{len(lib['tracks'])}** Songs\n\n"
            f"👤 **{len(lib['artists'])}** Artists\n\n"
            f"📂 **{len(lib['playlists'])}** Playlists"
        )

        st.warning(
            "🚨 IMPORTANT\n\n"
            "You are about to authorize the NEW "
            "Spotify account.\n\n"
            "If Spotify is already logged into your "
            "old account in the browser, log out first "
            "or use an Incognito/Private window."
        )

        # ----------------------------------------------------
        # NEW ACCOUNT CALLBACK
        # ----------------------------------------------------

        if (
            authorization_code
            and authorization_state == "new"
        ):

            try:

                with st.spinner(
                    "🔐 Connecting to NEW Spotify account..."
                ):

                    token_info = exchange_code(
                        authorization_code
                    )

                    new_access_token = token_info[
                        "access_token"
                    ]

                    new_user = get_current_user(
                        new_access_token
                    )

                new_user_id = new_user.get(
                    "id"
                )

                new_user_name = (
                    new_user.get(
                        "display_name"
                    )
                    or new_user_id
                    or "Spotify User"
                )

                # ------------------------------------------------
                # SAFETY CHECK
                # ------------------------------------------------

                if (
                    st.session_state.old_account_id
                    and
                    new_user_id
                    ==
                    st.session_state.old_account_id
                ):

                    st.error(
                        "🛑 SAME ACCOUNT DETECTED!"
                    )

                    st.warning(
                        "You authorized the OLD account "
                        "again. No changes were made."
                    )

                    st.info(
                        "Log out from Spotify and then "
                        "authorize the NEW account."
                    )

                    st.query_params.clear()

                    st.stop()

                # ------------------------------------------------
                # TOTAL
                # ------------------------------------------------

                total = (
                    len(lib["tracks"])
                    +
                    len(lib["artists"])
                    +
                    len(lib["playlists"])
                )

                current = 0

                status = st.empty()

                sub_status = st.empty()

                progress = st.progress(
                    0
                )

                # =================================================
                # 1. LIKED SONGS
                # =================================================

                if lib["tracks"]:

                    status.markdown(
                        "### 📥 Injecting Liked Songs..."
                    )

                    total_tracks = len(
                        lib["tracks"]
                    )

                    for i in range(
                        0,
                        total_tracks,
                        40
                    ):

                        chunk = lib[
                            "tracks"
                        ][
                            i:i + 40
                        ]

                        save_tracks(
                            new_access_token,
                            chunk
                        )

                        current += len(
                            chunk
                        )

                        sub_status.write(
                            f"Songs: **"
                            f"{min(i + len(chunk), total_tracks)}"
                            f"** / **"
                            f"{total_tracks}"
                            f"**"
                        )

                        progress.progress(
                            min(
                                current / total,
                                1.0
                            )
                        )

                # =================================================
                # 2. ARTISTS
                # =================================================

                if lib["artists"]:

                    status.markdown(
                        "### 👤 Following Artists..."
                    )

                    total_artists = len(
                        lib["artists"]
                    )

                    for i in range(
                        0,
                        total_artists,
                        40
                    ):

                        chunk = lib[
                            "artists"
                        ][
                            i:i + 40
                        ]

                        follow_artists(
                            new_access_token,
                            chunk
                        )

                        current += len(
                            chunk
                        )

                        sub_status.write(
                            f"Artists: **"
                            f"{min(i + len(chunk), total_artists)}"
                            f"** / **"
                            f"{total_artists}"
                            f"**"
                        )

                        progress.progress(
                            min(
                                current / total,
                                1.0
                            )
                        )

                # =================================================
                # 3. PLAYLISTS
                # =================================================

                if lib["playlists"]:

                    status.markdown(
                        "### 📂 Creating Playlists..."
                    )

                    total_playlists = len(
                        lib["playlists"]
                    )

                    for index, playlist in enumerate(
                        lib["playlists"],
                        start=1
                    ):

                        name = playlist[
                            "name"
                        ]

                        sub_status.write(
                            f"Creating playlist "
                            f"**{index}/{total_playlists}**: "
                            f"**{name}**"
                        )

                        # ----------------------------------------
                        # CREATE
                        # ----------------------------------------

                        new_playlist = create_playlist(
                            new_access_token,
                            name,
                            playlist["public"],
                            playlist["description"]
                        )

                        new_playlist_id = (
                            new_playlist.get(
                                "id"
                            )
                        )

                        if not new_playlist_id:

                            raise RuntimeError(
                                f"Could not create playlist: "
                                f"{name}"
                            )

                        # ----------------------------------------
                        # ADD TRACKS
                        # ----------------------------------------

                        playlist_tracks = (
                            playlist["tracks"]
                        )

                        if playlist_tracks:

                            add_playlist_tracks(
                                new_access_token,
                                new_playlist_id,
                                playlist_tracks
                            )

                        current += 1

                        progress.progress(
                            min(
                                current / total,
                                1.0
                            )
                        )

                # =================================================
                # FINISHED
                # =================================================

                status.empty()

                sub_status.empty()

                progress.progress(
                    1.0
                )

                st.balloons()

                st.success(
                    "🎉 Migration completed successfully!"
                )

                st.info(
                    f"NEW account: **{new_user_name}**"
                )

                st.write(
                    "Your liked songs, followed artists "
                    "and playlists have been transferred."
                )

                st.session_state.migration_finished = (
                    True
                )

                # IMPORTANT:
                # Do NOT immediately delete the backup.
                # This allows another attempt if necessary.
                st.query_params.clear()

            except Exception as e:

                st.error(
                    "❌ Transfer failed."
                )

                st.exception(e)

                st.warning(
                    f"The backup is still available in **{BACKUP_FILE}** "
                    "and can be used for another attempt."
                )

        # --------------------------------------------------------
        # START NEW ACCOUNT AUTH
        # --------------------------------------------------------

        else:

            auth_url = get_auth_url(
                "new"
            )

            st.link_button(
                "🚀 Connect NEW Account & Start Migration",
                auth_url,
                type="primary",
                use_container_width=True
            )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Spotify Account Migrator • "
    "Backup is stored in the current Streamlit session."
)