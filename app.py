import streamlit as st
import tempfile
import os
import sys
import time
from jamaibase import JamAI, protocol as p  # keep teammate's import (protocol unused but preserved)

# -----------------------
# Page / UI configuration
# -----------------------
st.set_page_config(page_title="AERN | AI Emergency Response Navigator", page_icon="🚨", layout="wide")

st.markdown("""
<style>
    .stButton>button {height: 3em; width: 100%; border-radius: 10px; font-weight: bold; font-size: 20px;} 
    .stChatMessage {border-radius: 15px; padding: 10px;}
</style>
""", unsafe_allow_html=True)

# -----------------------
# Secrets / Credentials
# -----------------------
# Support both naming schemes:
# - New teammate scheme: st.secrets["JAMAI_API_KEY"], st.secrets["PROJECT_ID"], st.secrets["TABLE_ID"]
# - Existing scheme: JAMAI_PROJECT_ID / JAMAI_PAT_KEY or environment variables JAMAI_PROJECT_ID / JAMAI_PAT_KEY
def _load_secrets():
    # prefer streamlit secrets when present
    proj = None
    pat = None
    table_text = None
    table_audio = None
    table_photo = None
    table_multi = None
    table_chat = None

    if hasattr(st, "secrets") and isinstance(st.secrets, dict) and st.secrets:
        # teammate keys
        pat = st.secrets.get("JAMAI_API_KEY") or st.secrets.get("JAMAI_PAT_KEY")
        proj = st.secrets.get("PROJECT_ID") or st.secrets.get("JAMAI_PROJECT_ID")
        # optional per-table ids
        table_text = st.secrets.get("TABLE_TEXT_ID") or st.secrets.get("TABLE_ID_TEXT") or st.secrets.get("TABLE_ID")
        table_audio = st.secrets.get("TABLE_AUDIO_ID") or st.secrets.get("TABLE_ID_AUDIO")
        table_photo = st.secrets.get("TABLE_PHOTO_ID") or st.secrets.get("TABLE_ID_PHOTO")
        table_multi = st.secrets.get("TABLE_MULTI_ID") or st.secrets.get("TABLE_ID_MULTI")
        table_chat = st.secrets.get("TABLE_CHAT_ID") or st.secrets.get("TABLE_ID_CHAT") or st.secrets.get("TABLE_ID")
    # fallback to environment
    if not proj:
        proj = os.getenv("JAMAI_PROJECT_ID") or os.getenv("PROJECT_ID")
    if not pat:
        pat = os.getenv("JAMAI_PAT_KEY") or os.getenv("JAMAI_API_KEY") or os.getenv("JAMAI_PAT")
    # fallback table ids (hard-coded defaults; update to your actual table IDs)
    table_text = table_text or os.getenv("TABLE_ID_TEXT") or "text%20received"
    table_audio = table_audio or os.getenv("TABLE_ID_AUDIO") or "audio_receive"
    table_photo = table_photo or os.getenv("TABLE_ID_PHOTO") or "picture%20receipt"
    table_multi = table_multi or os.getenv("TABLE_ID_MULTI") or "combined"
    table_chat = table_chat or os.getenv("TABLE_ID_CHAT") or table_multi

    return proj.strip() if isinstance(proj, str) else proj, (pat.strip() if isinstance(pat, str) else pat), {
        "text": table_text, "audio": table_audio, "photo": table_photo, "multi": table_multi, "chat": table_chat
    }

PROJECT_ID, PAT_KEY, TABLE_IDS = _load_secrets()

# show connection status
if PROJECT_ID and PAT_KEY:
    st.sidebar.success("✅ JamAI credentials loaded")
else:
    st.sidebar.warning("⚠️ JamAI credentials missing. Set secrets or environment variables.")

# -----------------------
# Initialize JamAI client
# -----------------------
jamai = None
if PROJECT_ID and PAT_KEY:
    try:
        jamai = JamAI(token=PAT_KEY, project_id=PROJECT_ID)
    except Exception as e:
        st.sidebar.error(f"Failed to initialize JamAI client: {e}")
        jamai = None

# -----------------------
# Helpers (file save, upload, send)
# -----------------------
def save_uploaded_file(uploaded_file):
    try:
        suffix = f".{uploaded_file.name.split('.')[-1]}" if "." in uploaded_file.name else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error saving uploaded file: {e}")
        return None

def _get_uri_from_upload(upload_resp):
    if upload_resp is None:
        return None
    if isinstance(upload_resp, dict):
        return upload_resp.get("uri") or upload_resp.get("url")
    if hasattr(upload_resp, "uri"):
        return getattr(upload_resp, "uri", None)
    if hasattr(upload_resp, "url"):
        return getattr(upload_resp, "url", None)
    if hasattr(upload_resp, "row") and isinstance(upload_resp.row, dict):
        return upload_resp.row.get("uri") or upload_resp.row.get("url")
    return None

def _normalize_row_dict(d):
    if not isinstance(d, dict):
        return {}
    for key in ("values", "fields", "data"):
        if key in d and isinstance(d[key], dict):
            return d[key]
    return d

def _find_row_dict(response):
    if response is None:
        return {}
    if isinstance(response, list) and response:
        candidate = response[0]
        if isinstance(candidate, dict):
            return _normalize_row_dict(candidate)
    if isinstance(response, dict):
        if "row" in response and isinstance(response["row"], dict):
            return _normalize_row_dict(response["row"])
        if "rows" in response and isinstance(response["rows"], list) and response["rows"]:
            return _normalize_row_dict(response["rows"][0])
        if "values" in response and isinstance(response["values"], dict):
            return _normalize_row_dict(response["values"])
        if "data" in response and isinstance(response["data"], dict):
            return _normalize_row_dict(response["data"])
        return _normalize_row_dict(response)
    if hasattr(response, "row"):
        try:
            r = getattr(response, "row")
            if isinstance(r, dict):
                return _normalize_row_dict(r)
        except Exception:
            pass
    if hasattr(response, "rows"):
        try:
            rlist = getattr(response, "rows")
            if isinstance(rlist, list) and rlist:
                return _normalize_row_dict(rlist[0])
        except Exception:
            pass
    if hasattr(response, "__dict__"):
        d = getattr(response, "__dict__", {})
        return _find_row_dict(d)
    return {}

def _extract_field_safe(row_dict, key, default=None):
    if not isinstance(row_dict, dict):
        return default
    if key in row_dict:
        return row_dict.get(key)
    # search nested
    def search(obj):
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            for v in obj.values():
                res = search(v)
                if res is not None:
                    return res
        if isinstance(obj, list):
            for item in obj:
                res = search(item)
                if res is not None:
                    return res
        return None
    found = search(row_dict)
    return found if found is not None else default

def _cleanup_temp(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def send_table_row(table_id, data, stream=False):
    """
    Use jamai.table.add_table_rows with explicit stream parameter to avoid SDK errors.
    """
    if jamai is None:
        raise RuntimeError("JamAI client not initialized.")
    table_obj = getattr(jamai, "table", None)
    if hasattr(table_obj, "add_table_rows"):
        try:
            # Try passing table_type="action" and stream=False (Common in v0.3+)
            return table_obj.add_table_rows(
                table_type="action", 
                table_id=table_id, 
                rows=[data], 
                stream=False
            )
        except TypeError:

            try:
                return table_obj.add_table_rows(table_id, [data], stream=False)
            except TypeError:
                 # Absolute fallback for older versions
                return table_obj.add_table_rows(table_id, [data])
        except Exception as e:
            raise RuntimeError(f"jamai.table.add_table_rows error: {e}")

    raise AttributeError("Could not find add_table_rows on jamai.table")

# -----------------------
# Main UI: Tabs (merged)
# -----------------------
st.title("🚨 AERN")
st.caption("AI Emergency Response Navigator")

# Create top-level tabs:
tab_panic, tab_single, tab_multi, tab_chat = st.tabs(["🔥 PANIC MODE", "Single Modality Analysis", "Multi-Modality Fusion", "💬 AI Assistant"])

# === PANIC MODE (teammate features) ===
# === Single Modality Analysis ===
with tab_single:
    st.header("Single Input Analysis (3 Dedicated Tables)")
    st.info("Input will be sent to the table matching the input type.")

    input_type = st.radio("Select Input Type", ["Text", "Audio", "Photo"], horizontal=True)

    # --- START OF FORM ---

    with st.form(key="single_modality_form"):
        user_data = {}
        # We need a placeholder for file uploads because we process them after the form is submitted
        # or we accept that the file_uploader is inside the form.
        
        text_input = None
        audio_file = None
        photo_file = None

        if input_type == "Text":
            # Note: Ensure the key 'text' matches your JamAI Table Input Column Name
            text_input = st.text_area("Describe the emergency situation:")
        
        elif input_type == "Audio":
            audio_file = st.file_uploader("Upload Audio Recording", type=["mp3", "wav", "m4a"])
            
        elif input_type == "Photo":
            photo_file = st.file_uploader("Upload Scene Photo", type=["jpg", "png", "jpeg"])

        # The Form Submit Button
        submitted = st.form_submit_button("Analyze Single Input")

    # --- PROCESS AFTER SUBMISSION ---
    if submitted:
        table_id_to_use = None
        ready_to_send = False

        # 1. Prepare Data based on selection
        if input_type == "Text" and text_input:
            # ⚠️ CHECK: Column name must match your JamAI table input column
            user_data = {"text_receive": text_input}  # <-- CHECK COLUMN NAME: "text_recceive"
            table_id_to_use = TABLE_IDS["text"]  # <-- CHECK TABLE ID: TABLE_IDS["text"]
            ready_to_send = True

        elif input_type == "Audio" and audio_file:
            temp_path = save_uploaded_file(audio_file)
            if temp_path:
                with st.spinner("Uploading audio..."):
                    try:
                        upload_resp = jamai.file.upload_file(temp_path) if jamai else None
                        uploaded_uri = _get_uri_from_upload(upload_resp)
                        if uploaded_uri:
                            # ⚠️ CHECK: Column name must match your JamAI table input column
                            user_data = {"audio": uploaded_uri}  # <-- CHECK COLUMN NAME: "audio"
                            table_id_to_use = TABLE_IDS["audio"]  # <-- CHECK TABLE ID: TABLE_IDS["audio"]
                            ready_to_send = True
                        else:
                            st.error("Upload succeeded but no URI returned.")
                    except Exception as e:
                        st.error(f"Audio upload failed: {e}")
                    finally:
                        _cleanup_temp(temp_path)

        elif input_type == "Photo" and photo_file:
            # Show preview (re-displaying technically, but helpful)
            st.image(photo_file, caption="Preview", width=300)
            temp_path = save_uploaded_file(photo_file)
            if temp_path:
                with st.spinner("Uploading photo..."):
                    try:
                        upload_resp = jamai.file.upload_file(temp_path) if jamai else None
                        uploaded_uri = _get_uri_from_upload(upload_resp)
                        if uploaded_uri:
                            # ⚠️ CHECK: Column name must match your JamAI table input column
                            user_data = {"picture": uploaded_uri}  # <-- CHECK COLUMN NAME: "photo"
                            table_id_to_use = TABLE_IDS["photo"]  # <-- CHECK TABLE ID: TABLE_IDS["photo"]
                            ready_to_send = True
                        else:
                            st.error("Upload succeeded but no URI returned.")
                    except Exception as e:
                        st.error(f"Photo upload failed: {e}")
                    finally:
                        _cleanup_temp(temp_path)

        # 2. Send to JamAI
        if ready_to_send and table_id_to_use:
            with st.spinner(f"Consulting AERN Brain via table: {table_id_to_use}..."):
                try:
                    # Pass stream=False explicitly
                    if jamai:
                        response = send_table_row(table_id=table_id_to_use, data=user_data, stream=False)
                    else:
                        response = {"row": {"description": "Offline Mode", "summary": "Offline Mode"}}

                    # Show results
                    row = _find_row_dict(response)
                    desc = _extract_field_safe(row, "description", default="No description generated")
                    summary = _extract_field_safe(row, "summary", default="No summary generated")
                    
                    st.subheader("📋 Situation Description")
                    st.write(desc)
                    st.divider()
                    st.subheader("📢 Action Summary")
                    st.success(summary)
                    
                    # Optional: Show debug only if needed
                    with st.expander("Raw Debug Data"):
                        st.write(response)

                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    st.caption("Tip: Check if your Table ID and Column Names (keys in user_data) match your JamAI project exactly.")
        else:
            st.warning("Please provide input data before analyzing.")

# === Multi-Modality Fusion (original features) ===
with tab_multi:
    st.header("Multi-Modality Fusion")
    st.info(f"Connected to Table: `{TABLE_IDS['multi']}` (One table handles multiple inputs)")

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
                    # ⚠️ CHECK: All column names below must match your JamAI multi-modal table
                    multi_data = {}
                    if multi_text:
                        multi_data["text"] = multi_text  # <-- CHECK COLUMN NAME: "text"
                    if multi_audio:
                        temp_audio = save_uploaded_file(multi_audio)
                        if temp_audio:
                            try:
                                upload_audio = jamai.file.upload_file(temp_audio) if jamai else None
                                uri_audio = _get_uri_from_upload(upload_audio)
                                if uri_audio:
                                    multi_data["audio text"] = uri_audio  # <-- CHECK COLUMN NAME: "audio text"
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
                                upload_photo = jamai.file.upload_file(temp_photo) if jamai else None
                                uri_photo = _get_uri_from_upload(upload_photo)
                                if uri_photo:
                                    multi_data["image"] = uri_photo  # <-- CHECK COLUMN NAME: "image"
                                else:
                                    st.warning("Photo uploaded but no uri returned.")
                            except Exception as e:
                                st.error(f"Photo upload failed: {e}")
                            finally:
                                _cleanup_temp(temp_photo)

                    if jamai:
                        # <-- CHECK TABLE ID: TABLE_IDS["multi"]
                        response = send_table_row(table_id=TABLE_IDS["multi"], data=multi_data, stream=False)
                    else:
                        response = {"row": {"description": "Simulated integrated description (offline)", "summary": "Simulated strategic summary"}}
                    with st.expander("Raw response from JamAI (multi)"):
                        st.write(response)
                    row = _find_row_dict(response)
                    desc = _extract_field_safe(row, "description", default="No description generated")
                    summary = _extract_field_safe(row, "summary", default="No summary generated")
                    st.subheader("📋 Integrated Description")
                    st.write(desc)
                    st.divider()
                    st.subheader("📢 Strategic Summary")
                    st.success(summary)
                except Exception as e:
                    st.error(f"An error occurred during fusion: {e}")

# === AI Assistant ===
with tab_chat:
    st.header("AI Assistant")
    st.info("Type a message below. If JamAI is configured, it will be sent to the configured chat/table; otherwise a simulated reply is shown.")

    # Use chat table id from secrets or fallback to multi table
    CHAT_TABLE_ID = TABLE_IDS.get("chat", TABLE_IDS["multi"])

    # Display simple chat history in session_state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render previous messages
    for msg in st.session_state.chat_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        st.chat_message(role).write(content)

    # Chat input
    prompt = st.chat_input("Hello, how can I help you ? Type here...")
    if prompt:
        # show user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        # Prepare data row to send - adjust column name 'chat' to match your table
        data = {"chat": prompt}

        with st.spinner("Contacting AI assistant..."):
            try:
                if jamai:
                    # send as a table row to the chat/table (JamAI expects rows list)
                    response = send_table_row(table_id=CHAT_TABLE_ID, data=data, stream=False)
                else:
                    response = {"row": {"description": None, "summary": None, "assistant_reply": f"Simulated reply: {prompt}"}}

                # show raw response for debugging
                with st.expander("Raw response from JamAI (chat)"):
                    st.write(response)

                row = _find_row_dict(response)
                # prefer assistant_reply, then summary, then description
                assistant_text = _extract_field_safe(row, "assistant_reply")
                if not assistant_text:
                    assistant_text = _extract_field_safe(row, "summary")
                if not assistant_text:
                    assistant_text = _extract_field_safe(row, "description")
                if not assistant_text:
                    assistant_text = "No assistant reply returned."

                # append and show assistant message
                st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
                st.chat_message("assistant").write(assistant_text)
            except Exception as e:
                st.error(f"Chat failed: {e}")
                # fallback simulated reply
                sim = f"Simulated reply due to error: {str(e)}"
                st.session_state.chat_history.append({"role": "assistant", "content": sim})
                st.chat_message("assistant").write(sim)

# -----------------------
# Sidebar: JamAI debug info
# -----------------------
with st.sidebar.expander("JamAI debug info / Table API"):
    if jamai is None:
        st.write("JamAI client not initialized.")
    else:
        table_obj = getattr(jamai, "table", None)
        st.write("jamai.table type:", type(table_obj))
        if table_obj is not None:
            st.write(sorted(dir(table_obj)))
        st.write("Project ID:", PROJECT_ID)
        st.write("Table IDs (resolved):", TABLE_IDS)

