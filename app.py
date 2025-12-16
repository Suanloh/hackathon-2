import streamlit as st
import tempfile
import os
import sys
from jamaibase import JamAI

# --- CONFIGURATION (read secrets safely) ---
# Prefer Streamlit secrets, fall back to environment variables
PROJECT_ID = (st.secrets.get("JAMAI_PROJECT_ID") if hasattr(st, "secrets") else None) or os.getenv("JAMAI_PROJECT_ID", "")
PAT_KEY = (st.secrets.get("JAMAI_PAT_KEY") if hasattr(st, "secrets") else None) or os.getenv("JAMAI_PAT_KEY", "")

PROJECT_ID = PROJECT_ID.strip()
PAT_KEY = PAT_KEY.strip()

# --- ACTION TABLE IDS ---
# Replace with your real table IDs. Avoid percent-encoding unless the platform requires it.
TABLE_ID_TEXT = "text_received"      # update to your text-only table id
TABLE_ID_AUDIO = "audio_receive"     # update to your audio-only table id
TABLE_ID_PHOTO = "picture_receipt"   # update to your photo-only table id
TABLE_ID_MULTI = "combined"          # multi-input table id

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="AERN | AI Emergency Response Navigator",
    page_icon="🚨",
    layout="centered"
)

# --- VERIFY CREDENTIALS ---
if not PROJECT_ID or not PAT_KEY:
    st.error("🚨 Missing JamAI credentials. Set JAMAI_PROJECT_ID and JAMAI_PAT_KEY in Streamlit secrets or environment variables.")
    st.stop()

# --- INITIALIZE JAMAI CLIENT ---
try:
    jamai = JamAI(token=PAT_KEY, project_id=PROJECT_ID)
except Exception as e:
    st.error(f"Failed to initialize JamAI client: {e}")
    st.stop()

# --- HELPERS ---
def save_uploaded_file(uploaded_file):
    """
    Save a Streamlit UploadedFile to a temporary file and return its path.
    """
    try:
        suffix = f".{uploaded_file.name.split('.')[-1]}" if "." in uploaded_file.name else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error saving uploaded file: {e}")
        return None

def _get_uri_from_upload(upload_resp):
    """
    Extract a 'uri' from an upload response which might be a dict or an object.
    """
    if upload_resp is None:
        return None
    if isinstance(upload_resp, dict):
        return upload_resp.get("uri") or upload_resp.get("url")
    if hasattr(upload_resp, "uri"):
        return getattr(upload_resp, "uri", None)
    if hasattr(upload_resp, "url"):
        return getattr(upload_resp, "url", None)
    # Last resort: try to read .row or .data fields
    if hasattr(upload_resp, "row") and isinstance(upload_resp.row, dict):
        return upload_resp.row.get("uri") or upload_resp.row.get("url")
    return None

def _extract_row(response):
    """
    Safely extract a 'row' dict from a jamai.table.add_row() response.
    """
    if response is None:
        return {}
    if isinstance(response, dict):
        return response.get("row") or {}
    if hasattr(response, "row"):
        try:
            return response.row or {}
        except Exception:
            return {}
    if hasattr(response, "__dict__"):
        return getattr(response, "__dict__", {}).get("row", {}) or {}
    return {}

def _cleanup_temp(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

# --- UI ---
st.title("🚨 AERN")
st.caption("AI Emergency Response Navigator")

tab1, tab2 = st.tabs(["Single Modality Analysis", "Multi-Modality Fusion"])

# --- TAB 1: Single Modality ---
with tab1:
    st.header("Single Input Analysis (3 Dedicated Tables)")
    st.info("Pick the modality and submit — the app routes the input to the corresponding table.")

    input_type = st.radio("Select Input Type", ["Text", "Audio", "Photo"], horizontal=True)

    user_data = {}
    table_id_to_use = None
    ready_to_send = False

    if input_type == "Text":
        text_input = st.text_area("Describe the emergency situation:")
        if text_input:
            user_data = {"text": text_input}
            table_id_to_use = TABLE_ID_TEXT
            ready_to_send = True

    elif input_type == "Audio":
        audio_file = st.file_uploader("Upload Audio Recording", type=["mp3", "wav", "m4a"])
        if audio_file:
            temp_path = save_uploaded_file(audio_file)
            if temp_path:
                with st.spinner("Uploading audio..."):
                    try:
                        upload_resp = jamai.file.upload_file(temp_path)
                        uploaded_uri = _get_uri_from_upload(upload_resp)
                        if not uploaded_uri:
                            st.error("Upload succeeded but no URI was returned.")
                        else:
                            user_data = {"audio": uploaded_uri}
                            table_id_to_use = TABLE_ID_AUDIO
                            ready_to_send = True
                    except Exception as e:
                        st.error(f"Audio upload failed: {e}")
                    finally:
                        _cleanup_temp(temp_path)

    elif input_type == "Photo":
        photo_file = st.file_uploader("Upload Scene Photo", type=["jpg", "png", "jpeg"])
        if photo_file:
            st.image(photo_file, caption="Preview", width=300)
            temp_path = save_uploaded_file(photo_file)
            if temp_path:
                with st.spinner("Uploading photo..."):
                    try:
                        upload_resp = jamai.file.upload_file(temp_path)
                        uploaded_uri = _get_uri_from_upload(upload_resp)
                        if not uploaded_uri:
                            st.error("Upload succeeded but no URI was returned.")
                        else:
                            user_data = {"photo": uploaded_uri}
                            table_id_to_use = TABLE_ID_PHOTO
                            ready_to_send = True
                    except Exception as e:
                        st.error(f"Photo upload failed: {e}")
                    finally:
                        _cleanup_temp(temp_path)

    if st.button("Analyze Single Input", disabled=not ready_to_send):
        with st.spinner(f"Consulting AERN Brain via table: {table_id_to_use}..."):
            try:
                response = jamai.table.add_row(
                    table_id=table_id_to_use,
                    data=user_data,
                    stream=False
                )
                row = _extract_row(response)
                desc = row.get("description", "No description generated")
                summary = row.get("summary", "No summary generated")

                st.subheader("📋 Situation Description")
                st.write(desc)
                st.divider()
                st.subheader("📢 Action Summary")
                st.success(summary)
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.write("Check Table IDs and column names. If the SDK structure differs, paste the traceback for help.")

# --- TAB 2: Multi-Modality Fusion ---
with tab2:
    st.header("Multi-Modality Fusion")
    st.info(f"Connected to Table: `{TABLE_ID_MULTI}` (One table handles multiple inputs)")

    col1, col2 = st.columns(2)
    with col1:
        multi_text = st.text_area("Text Input", height=150)
        multi_audio = st.file_uploader("Audio Input", type=["mp3", "wav", "m4a"], key="m_audio")
    with col2:
        multi_photo = st.file_uploader("Photo Input", type=["jpg", "png", "jpeg"], key="m_photo")
        if multi_photo:
            st.image(multi_photo, width=200)

    if st.button("Analyze Combined Data"):
        if not (multi_text or multi_audio or multi_photo):
            st.error("Please provide at least one input.")
        else:
            with st.spinner("Processing multi-modal emergency data..."):
                try:
                    multi_data = {}
                    if multi_text:
                        multi_data["text"] = multi_text

                    if multi_audio:
                        temp_audio = save_uploaded_file(multi_audio)
                        if temp_audio:
                            try:
                                upload_audio = jamai.file.upload_file(temp_audio)
                                uri_audio = _get_uri_from_upload(upload_audio)
                                if uri_audio:
                                    multi_data["audio"] = uri_audio
                                else:
                                    st.warning("Audio uploaded but no uri returned.")
                            except Exception as e:
                                st.error(f"Audio upload failed: {e}")
                            finally:
                                _cleanup_temp(temp_audio)

                    if multi_photo:
                        temp_photo = save_uploaded_file(multi_photo)
                        if temp_photo:
                            try:
                                upload_photo = jamai.file.upload_file(temp_photo)
                                uri_photo = _get_uri_from_upload(upload_photo)
                                if uri_photo:
                                    multi_data["photo"] = uri_photo
                                else:
                                    st.warning("Photo uploaded but no uri returned.")
                            except Exception as e:
                                st.error(f"Photo upload failed: {e}")
                            finally:
                                _cleanup_temp(temp_photo)

                    response = jamai.table.add_row(
                        table_id=TABLE_ID_MULTI,
                        data=multi_data,
                        stream=False
                    )
                    row = _extract_row(response)
                    desc = row.get("description", "No description generated")
                    summary = row.get("summary", "No summary generated")

                    st.subheader("📋 Integrated Description")
                    st.write(desc)
                    st.divider()
                    st.subheader("📢 Strategic Summary")
                    st.success(summary)
                except Exception as e:
                    st.error(f"An error occurred during fusion: {e}")