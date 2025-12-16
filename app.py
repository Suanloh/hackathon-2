import streamlit as st
import tempfile
import os
import sys
from jamaibase import JamAI

# 你好
# --- CONFIGURATION (read secrets safely) ---
PROJECT_ID = (st.secrets.get("JAMAI_PROJECT_ID") if hasattr(st, "secrets") else None) or os.getenv("JAMAI_PROJECT_ID", "")
PAT_KEY = (st.secrets.get("JAMAI_PAT_KEY") if hasattr(st, "secrets") else None) or os.getenv("JAMAI_PAT_KEY", "")

PROJECT_ID = PROJECT_ID.strip()
PAT_KEY = PAT_KEY.strip()

# --- ACTION TABLE IDS ---
TABLE_ID_TEXT = "text_received"
TABLE_ID_AUDIO = "audio_receive"
TABLE_ID_PHOTO = "picture_receipt"
TABLE_ID_MULTI = "combined"

# --- PAGE CONFIG ---
st.set_page_config(page_title="AERN | AI Emergency Response Navigator", page_icon="🚨", layout="centered")

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

def _find_row_dict(response):
    """
    Return a best-effort dict containing the row fields from the SDK response.
    Handles common shapes:
      - dict(row={...})
      - dict(rows=[{...}])
      - list([{...}])
      - object with .row or .rows
    """
    if response is None:
        return {}
    # If it's a list, take first element
    if isinstance(response, list) and response:
        candidate = response[0]
        if isinstance(candidate, dict):
            return _normalize_row_dict(candidate)
        # else continue to inspect as object
    # If dict
    if isinstance(response, dict):
        if "row" in response and isinstance(response["row"], dict):
            return _normalize_row_dict(response["row"])
        if "rows" in response and isinstance(response["rows"], list) and response["rows"]:
            return _normalize_row_dict(response["rows"][0])
        # If SDK used 'values' or 'data' keys
        if "values" in response and isinstance(response["values"], dict):
            return _normalize_row_dict(response["values"])
        if "data" in response and isinstance(response["data"], dict):
            return _normalize_row_dict(response["data"])
        # Fallback: maybe the response itself contains fields
        return _normalize_row_dict(response)

    # If object with attributes
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

    # As a last attempt, inspect __dict__
    if hasattr(response, "__dict__"):
        d = getattr(response, "__dict__", {})
        return _find_row_dict(d)

    return {}

def _normalize_row_dict(d):
    """
    Normalize naming variations into a flat dict of fields.
    Handles nested 'values' or 'fields' keys.
    """
    if not isinstance(d, dict):
        return {}
    # If row wraps actual fields under keys like 'values' or 'fields'
    for key in ("values", "fields", "data"):
        if key in d and isinstance(d[key], dict):
            return d[key]
    return d

def _extract_field_safe(row_dict, key, default=None):
    if not isinstance(row_dict, dict):
        return default
    # Direct hit
    if key in row_dict:
        return row_dict.get(key)
    # try nested structures
    for alt in ("text", "description", "summary", "content"):
        if alt in row_dict and isinstance(row_dict[alt], str) and key in ("description","summary"):
            # not a direct mapping but return string if present when key requested
            return row_dict.get(key, default)
    # try searching nested dicts for the key
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
    Use the JamAI SDK's add_table_rows (available on jamai.table) to insert a single row.
    Returns the SDK response unchanged.
    """
    table_obj = getattr(jamai, "table", None)
    if table_obj is None:
        raise AttributeError("jamai.table is not present on the JamAI client instance.")

    # Prefer the explicit add_table_rows method found in this SDK
    if hasattr(table_obj, "add_table_rows") and callable(getattr(table_obj, "add_table_rows")):
        try:
            # Many SDKs expect rows as a list of dicts
            return table_obj.add_table_rows(table_id=table_id, rows=[data])
        except TypeError:
            # fallback positional
            return table_obj.add_table_rows(table_id, [data])
        except Exception as e:
            raise RuntimeError(f"jamai.table.add_table_rows raised an error: {e}") from e

    # As a fallback, try previous dynamic candidate approach (keeps compatibility)
    # (This code path should rarely run given add_table_rows exists.)
    candidates = ["add_row","addRow","create_row","createRow","create","add","insert","insert_row",
                  "rows.create","rows.add","create_rows","createRows","add_rows","append_row"]
    last_exceptions = []
    for name in candidates:
        parts = name.split(".")
        attr = table_obj
        found = True
        for p in parts:
            if hasattr(attr, p):
                attr = getattr(attr, p)
            else:
                found = False
                break
        if not found or not callable(attr):
            continue
        attempts = [
            lambda f: f(table_id=table_id, data=data, stream=stream),
            lambda f: f(table_id=table_id, data=data),
            lambda f: f(table_id, data, stream),
            lambda f: f(table_id, data),
            lambda f: f(data),
            lambda f: f(table_id, data, stream=stream),
        ]
        for attempt in attempts:
            try:
                return attempt(attr)
            except TypeError as te:
                last_exceptions.append((name, "TypeError", str(te)))
                continue
            except Exception as e:
                raise RuntimeError(f"Call to jamai.table method '{name}' raised an exception: {e}") from e

    available = sorted(dir(table_obj))
    raise AttributeError(
        "Could not find a compatible method to add a row on jamai.table. "
        f"Tried candidates: {', '.join(candidates)}. "
        f"Available attributes on jamai.table: {available}. "
        f"Last call errors (sample): {last_exceptions[:5]}"
    )

# --- UI ---
st.title("🚨 AERN")
st.caption("AI Emergency Response Navigator")

# Debug: show jamai.table attrs
with st.expander("JamAI table debug info (click to expand)"):
    try:
        table_obj = getattr(jamai, "table", None)
        st.write("jamai.table type:", type(table_obj))
        if table_obj is not None:
            st.write("Available attributes on jamai.table (sample):")
            st.write(sorted(dir(table_obj)))
    except Exception as e:
        st.write("Error while introspecting jamai.table:", e)

tab1, tab2 = st.tabs(["Single Modality Analysis", "Multi-Modality Fusion"])

# --- TAB 1 ---
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
                response = send_table_row(table_id=table_id_to_use, data=user_data, stream=False)
                # Show raw response for debugging
                with st.expander("Raw response from JamAI"):
                    st.write(response)

                row = _find_row_dict(response)
                desc = _extract_field_safe(row, "description", default="No description generated")
                summary = _extract_field_safe(row, "summary", default="No summary generated")

                st.subheader("📋 Situation Description")
                st.write(desc)
                st.divider()
                st.subheader("📢 Action Summary")
                st.success(summary)
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.write("Check Table IDs and column names. Expand 'JamAI table debug info' above and paste its contents if automatic resolution still fails.")

# --- TAB 2 ---
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

                    response = send_table_row(table_id=TABLE_ID_MULTI, data=multi_data, stream=False)
                    # Show raw response for debugging
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