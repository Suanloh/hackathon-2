import streamlit as st
import tempfile
import os
import time
from jamaibase import JamAI
from jamaibase.protocol import MultiRowAddRequest

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="AERN | AI Emergency Response Navigator",
    page_icon="🚨",
    layout="wide"
)

# =============================================================================
# UI DESIGN & CSS (FORCE VERSION)
# =============================================================================
st.markdown("""
<style>
    /* 1. 强制修改全局背景颜色 */
    .stApp {
        background-color: #faf5f5 !important; /* 加了 !important 强制变红 */
    }
    
    /* 2. 标题颜色 */
    h1, h2, h3 {
        color: #d32f2f !important;
    }

    /* 3. 按钮样式 (普通按钮) */
    .stButton>button {
        background-color: white !important;
        color: #333 !important;
        border: 2px solid #ffcccc !important;
        height: 80px;
        font-size: 20px !important;
        font-weight: bold !important;
        border-radius: 12px !important;
    }
    
    /* 4. 针对 type="primary" 的红色按钮进行特训 */
    /* 当你写 st.button(..., type="primary") 时会用到这个 */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #ff4444 !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        height: 3em;
        width: 100%;
        border-radius: 10px;
        font-weight: bold;
        font-size: 20px;
    }
    .stChatMessage {
        border-radius: 15px;
        padding: 10px;
    }
    .emergency-button {
        background-color: #ff4444;
        color: white;
        padding: 20px;
        border-radius: 15px;
        font-size: 24px;
        font-weight: bold;
        margin:  10px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SECRETS AND CREDENTIALS LOADING
# =============================================================================
def load_secrets():
    """Load secrets from . streamlit/secrets.toml or environment variables"""
    # Try Streamlit secrets first
    api_key = None
    project_id = None
    table_text_id = None
    table_audio_id = None
    table_photo_id = None
    table_multi_id = None
    table_chat_id = None
    
    # Load from Streamlit secrets
    if hasattr(st, "secrets") and st.secrets:
        api_key = st.secrets.get("JAMAI_API_KEY") or st.secrets.get("JAMAI_PAT_KEY")
        project_id = st.secrets.get("PROJECT_ID") or st.secrets.get("JAMAI_PROJECT_ID")
        table_text_id = st. secrets.get("TABLE_TEXT_ID")
        table_audio_id = st.secrets.get("TABLE_AUDIO_ID")
        table_photo_id = st.secrets.get("TABLE_PHOTO_ID")
        table_multi_id = st.secrets.get("TABLE_MULTI_ID")
        table_chat_id = st.secrets.get("TABLE_CHAT_ID")
    
    # Fallback to environment variables
    if not api_key:
        api_key = os.getenv("JAMAI_API_KEY") or os.getenv("JAMAI_PAT_KEY")
    if not project_id:
        project_id = os.getenv("PROJECT_ID") or os.getenv("JAMAI_PROJECT_ID")
    
    # Fallback table IDs (clean names without URL encoding)
    table_text_id = table_text_id or os.getenv("TABLE_TEXT_ID") or "text_received"
    table_audio_id = table_audio_id or os.getenv("TABLE_AUDIO_ID") or "audio_receive"
    table_photo_id = table_photo_id or os.getenv("TABLE_PHOTO_ID") or "picture_receipt"
    table_multi_id = table_multi_id or os.getenv("TABLE_MULTI_ID") or "combined"
    table_chat_id = table_chat_id or os. getenv("TABLE_CHAT_ID") or "chat"
    
    return {
        "api_key": api_key. strip() if api_key else None,
        "project_id": project_id.strip() if project_id else None,
        "tables": {
            "text": table_text_id,
            "audio": table_audio_id,
            "photo": table_photo_id,
            "multi":  table_multi_id,
            "chat": table_chat_id
        }
    }

config = load_secrets()
API_KEY = config["api_key"]
PROJECT_ID = config["project_id"]
TABLE_IDS = config["tables"]

# =============================================================================
# JAMAI CLIENT INITIALIZATION
# =============================================================================
jamai_client = None
if API_KEY and PROJECT_ID:
    try:
        jamai_client = JamAI(token=API_KEY, project_id=PROJECT_ID)
        st.sidebar.success("✅ Connected to JamAI")
    except Exception as e:
        st.sidebar.error(f"❌ JamAI Connection Failed: {e}")
        jamai_client = None
else:
    st.sidebar. warning("⚠️ JamAI credentials not configured")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def save_uploaded_file(uploaded_file):
    """Save uploaded file to temporary location"""
    try:
        suffix = f".{uploaded_file.name.split('.')[-1]}" if "." in uploaded_file.name else ""
        with tempfile. NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error saving file: {e}")
        return None

def cleanup_temp_file(file_path):
    """Clean up temporary file"""
    try: 
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception: 
        pass

def extract_uri_from_response(response):
    """Extract URI from JamAI upload response"""
    if response is None:
        return None
    if isinstance(response, dict):
        return response.get("uri") or response.get("url")
    if hasattr(response, "uri"):
        return getattr(response, "uri", None)
    if hasattr(response, "url"):
        return getattr(response, "url", None)
    return None

def parse_response_data(response):
    """Parse JamAI response to extract row data"""
    if response is None:
        return {}
    
    # Handle list responses
    if isinstance(response, list) and response:
        response = response[0]
    
    # Handle dict responses
    if isinstance(response, dict):
        # Check for common patterns
        if "row" in response:
            return parse_response_data(response["row"])
        if "rows" in response and isinstance(response["rows"], list) and response["rows"]:
            return parse_response_data(response["rows"][0])
        if "values" in response and isinstance(response["values"], dict):
            return response["values"]
        if "data" in response and isinstance(response["data"], dict):
            return response["data"]
        if "columns" in response and isinstance(response["columns"], dict):
            return response["columns"]
        return response
    
    # Handle object responses
    if hasattr(response, "rows"):
        rows = getattr(response, "rows")
        if isinstance(rows, list) and rows:
            first_row = rows[0]
            # Extract columns from the row
            if hasattr(first_row, "columns"):
                return parse_columns_data(first_row.columns)
            return parse_response_data(first_row)
    
    if hasattr(response, "columns"):
        return parse_columns_data(response. columns)
    
    if hasattr(response, "__dict__"):
        return parse_response_data(getattr(response, "__dict__", {}))
    
    return {}

def parse_columns_data(columns):
    """Extract text content from columns data structure"""
    result = {}
    
    if isinstance(columns, dict):
        for col_name, col_value in columns.items():
            # Extract text from column value
            if isinstance(col_value, dict):
                result[col_name] = col_value.get("text") or col_value.get("value") or str(col_value)
            elif hasattr(col_value, "text"):
                result[col_name] = col_value.text
            elif hasattr(col_value, "value"):
                result[col_name] = col_value.value
            else:
                result[col_name] = str(col_value)
    
    return result

def extract_chat_completion_content(value):
    """Extract content from ChatCompletion object or dict"""
    # If value is a ChatCompletion object, extract the content
    if hasattr(value, "choices") and value.choices:
        try:
            return value.choices[0].message.content
        except (AttributeError, IndexError):
            pass
    
    # If value is a dict with ChatCompletion structure
    if isinstance(value, dict) and "choices" in value: 
        try:
            choices = value["choices"]
            if isinstance(choices, list) and choices:
                first_choice = choices[0]
                if isinstance(first_choice, dict) and "message" in first_choice:
                    return first_choice["message"]. get("content")
                elif hasattr(first_choice, "message"):
                    return first_choice. message.content
        except (AttributeError, IndexError, KeyError):
            pass
    
    # If it's already a string, return it
    if isinstance(value, str):
        return value if value else None
    
    # Convert to string if needed
    return str(value) if value is not None else None

def get_field_value(data, field_name, default=None):
    """Safely extract field value from response data with comprehensive search"""
    if not isinstance(data, dict):
        return default
    
    # Direct lookup
    if field_name in data:
        value = data[field_name]
        extracted = extract_chat_completion_content(value)
        return extracted if extracted else default
    
    # Try alternative field names (case-insensitive and with variations)
    alternative_names = [
        field_name.lower(),
        field_name.upper(),
        field_name.replace("_", " "),
        field_name.replace(" ", "_"),
    ]
    
    for key, value in data.items():
        if key.lower() in [name.lower() for name in alternative_names]:
            extracted = extract_chat_completion_content(value)
            return extracted if extracted else default
    
    # Recursive search for nested structures
    for key, value in data.items():
        if isinstance(value, dict):
            result = get_field_value(value, field_name, None)
            if result is not None:
                return result
    
    return default

def add_table_row(table_id, row_data):
    """Add a row to a JamAI Action Table"""
    if jamai_client is None:
        raise RuntimeError("JamAI client not initialized")
    
    try:
        # Create proper MultiRowAddRequest object
        request = MultiRowAddRequest(
            table_id=table_id,
            data=[row_data],
            stream=False
        )
        
        response = jamai_client.table. add_table_rows(
            table_type="action",
            request=request
        )
        return response
    except Exception as e: 
        raise RuntimeError(f"Failed to add table row: {e}")

def list_action_tables():
    """List all available Action Tables"""
    if jamai_client is None:
        return []
    
    try: 
        response = jamai_client. table.list_tables(table_type="action")
        if hasattr(response, "items"):
            return [table. id for table in response.items]
        return []
    except Exception as e:
        st.error(f"Error listing tables: {e}")
        return []

def get_table_schema(table_id):
    """Get schema information for a table"""
    if jamai_client is None:
        return None
    
    try: 
        response = jamai_client. table.get_table(table_type="action", table_id=table_id)
        return response
    except Exception as e:
        st.error(f"Error getting table schema: {e}")
        return None

# =============================================================================
# PAGE HEADER
# =============================================================================
st.title("🚨 AERN - AI Emergency Response Navigator")
st.markdown("""
**AI-Powered Emergency Response System** — AERN uses advanced AI to analyze emergency situations 
in real-time through text, audio, and images. Get instant situational assessments, 
recommended actions, and connect with emergency services faster. 
""")

st.divider()

# =============================================================================
# SIDEBAR - DEBUG AND CONFIGURATION
# =============================================================================
with st.sidebar:
    current_path = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(current_path, "images", "usm_flood_map.jpg") 
    
    if os.path.exists(image_path):
        st.image(image_path, caption="📍 Current Location: USM", use_container_width=True)
    else:
        # 如果还是找不到，用备用网络地图
        st.error("Local image not found, using alternative map.")
        st.image("https://maps.googleapis.com/maps/api/staticmap?center=USM+Penang&zoom=15&size=600x400&maptype=roadmap&markers=color:red%7Clabel:S%7CUSM", use_container_width=True)
    # -------------------

    st.success("🟢 System Online: Connected to HQ")
    st.divider()
    # -------------------------------------
    st.header("⚙️ System Configuration")
    
    # Credentials status
    with st.expander("🔑 Credentials Status", expanded=False):
        st.write(f"**API Key:** {'✅ Loaded' if API_KEY else '❌ Missing'}")
        st.write(f"**Project ID:** {PROJECT_ID if PROJECT_ID else '❌ Missing'}")
    
    # Table IDs
    with st.expander("📋 Table Configuration", expanded=False):
        st.write("**Configured Table IDs:**")
        for key, value in TABLE_IDS.items():
            st.code(f"{key}: {value}")
    
    # List available tables
    if st.button("🔍 List Available Action Tables"):
        with st.spinner("Fetching tables..."):
            tables = list_action_tables()
            if tables:
                st.success(f"Found {len(tables)} tables:")
                for table in tables: 
                    st.write(f"• {table}")
            else:
                st.info("No tables found or unable to connect")
    
    # Schema Inspector
    st.markdown("### 🔬 Schema Inspector")
    inspect_table = st.selectbox(
        "Select table to inspect:",
        options=list(TABLE_IDS.keys()),
        format_func=lambda x: f"{x. upper()} ({TABLE_IDS[x]})"
    )
    
    if st.button("Inspect Schema"):
        table_id = TABLE_IDS[inspect_table]
        with st.spinner(f"Inspecting {table_id}..."):
            schema = get_table_schema(table_id)
            if schema:
                st.success("Schema retrieved!")
                
                # Display input columns
                if hasattr(schema, "cols") and schema.cols:
                    st.write("**Input Columns:**")
                    for col in schema.cols:
                        st.write(f"• {col.id} ({col.dtype})")
                
                # Display output columns
                if hasattr(schema, "chat_cols") and schema.chat_cols:
                    st.write("**Output Columns:**")
                    for col in schema.chat_cols:
                        st. write(f"• {col. id} ({col.dtype})")
                
                with st.expander("Raw Schema Data"):
                    st.write(schema)
            else:
                st. error("Failed to retrieve schema")

# =============================================================================
# MAIN TABS
# =============================================================================
tab_emergency, tab_multi, tab_chat = st.tabs([
    "🔥 Emergency Response",
    "🔀 Multi-Modality Fusion",
    "💬 AI Chat Assistant"
])

# =============================================================================
# TAB 1: EMERGENCY RESPONSE
# =============================================================================
with tab_emergency:
    st.header("⚡ Quick Emergency Response")
    st.info("Select your emergency type for rapid assessment and guidance")
    
    # Emergency type buttons
    col1, col2, col3 = st.columns(3)
    
    emergency_selected = None
    
    with col1:
        if st.button("🌊 Flood", use_container_width=True):
            emergency_selected = "Flood"
        if st.button("🏥 Medical Emergency", use_container_width=True):
            emergency_selected = "Medical Emergency"
    
    with col2:
        if st.button("🔥 Fire", use_container_width=True):
            emergency_selected = "Fire"
        if st.button("🌪️ Natural Disaster", use_container_width=True):
            emergency_selected = "Natural Disaster"
    
    with col3:
        if st.button("🚗 Accident", use_container_width=True):
            emergency_selected = "Accident"
        if st.button("🏢 Building Emergency", use_container_width=True):
            emergency_selected = "Building Emergency"
    
    if emergency_selected:
        st. markdown(f"### Selected: **{emergency_selected}**")
        
        # Emergency input form
        with st.form(key="emergency_form"):
            st.write("Provide additional details:")
            
            # Text input
            emergency_text = st.text_area(
                "Describe the situation:",
                placeholder=f"Example: {emergency_selected} emergency at my location..."
            )
            
            # Optional file uploads
            col_a, col_b = st.columns(2)
            with col_a:
                emergency_audio = st.file_uploader(
                    "Optional: Audio recording",
                    type=["mp3", "wav", "m4a"],
                    key="emerg_audio"
                )
            with col_b:
                emergency_photo = st.file_uploader(
                    "Optional: Scene photo",
                    type=["jpg", "png", "jpeg"],
                    key="emerg_photo"
                )
                if emergency_photo:
                    st.image(emergency_photo, width=200)
            
            submit_emergency = st.form_submit_button("🚨 SUBMIT EMERGENCY REPORT", use_container_width=True)
        
        if submit_emergency:
            # Determine which table to use based on inputs
            if emergency_audio or emergency_photo:
                # Use multi-modal table
                table_id = TABLE_IDS["multi"]
                st.info(f"Using multi-modal table:  {table_id}")
                
                emergency_data = {}
                
                # Add text
                if emergency_text:
                    emergency_data["text"] = f"[{emergency_selected}] {emergency_text}"
                
                # Upload audio
                if emergency_audio: 
                    temp_audio = save_uploaded_file(emergency_audio)
                    if temp_audio and jamai_client:
                        try:
                            upload_resp = jamai_client.file.upload_file(temp_audio)
                            uri = extract_uri_from_response(upload_resp)
                            if uri:
                                emergency_data["audio text"] = uri
                        except Exception as e: 
                            st.error(f"Audio upload failed: {e}")
                        finally:
                            cleanup_temp_file(temp_audio)
                
                # Upload photo
                if emergency_photo: 
                    temp_photo = save_uploaded_file(emergency_photo)
                    if temp_photo and jamai_client:
                        try:
                            upload_resp = jamai_client.file.upload_file(temp_photo)
                            uri = extract_uri_from_response(upload_resp)
                            if uri: 
                                emergency_data["image"] = uri
                        except Exception as e:
                            st.error(f"Photo upload failed: {e}")
                        finally: 
                            cleanup_temp_file(temp_photo)
                
            else:
                # Use text-only table
                table_id = TABLE_IDS["text"]
                st.info(f"Using text table: {table_id}")
                # Note: text_received table uses 'text_receive' column, different from combined table's 'text' column
                emergency_data = {"text_receive": f"[{emergency_selected}] {emergency_text}"}
            
            # Submit to JamAI
            if emergency_data:
                with st.spinner("🚨 Processing emergency report..."):
                    try:
                        if jamai_client:
                            response = add_table_row(table_id, emergency_data)
                            data = parse_response_data(response)
                            # Display results
                            st.success("✅ Emergency Report Processed")

                            # Use correct field names from the API
                            description = get_field_value(data, "input_summary", "No description available")
                            summary = get_field_value(data, "diagonise", "No summary available")

                            st.subheader("📋 Situation Assessment")
                            st.markdown(description)

                            st.divider()

                            st.subheader("🚨 Recommended Actions")
                            st.warning(summary)

                            # Optional: Add action buttons based on the analysis
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.button("📞 Call Emergency Services", type="primary", use_container_width=True)
                            with col2:
                                st.button("📍 Share Location", use_container_width=True)
                            with col3:
                                st.button("👥 Alert Contacts", use_container_width=True)

                            # Keep debug data hidden by default
                            with st.expander("🔍 Debug Data (Developer Only)"):
                                st.json(data)
                        else: 
                            st.error("JamAI client not available")
                    except Exception as e:
                        st.error(f"Error processing emergency:  {e}")
            else:
                st.warning("Please provide emergency details")

# =============================================================================
# TAB 2: MULTI-MODALITY FUSION
# =============================================================================
with tab_multi:
    st.header("🔀 Multi-Modality Fusion")
    st.info(f"Combine multiple inputs for comprehensive analysis (Table: {TABLE_IDS['multi']})")
    
    col1, col2 = st. columns(2)
    
    with col1:
        multi_text = st.text_area("Text Description:", height=150)
        multi_audio = st.file_uploader(
            "Audio Input:",
            type=["mp3", "wav", "m4a"],
            key="multi_audio"
        )
    
    with col2:
        multi_photo = st.file_uploader(
            "Photo Input:",
            type=["jpg", "png", "jpeg"],
            key="multi_photo"
        )
        if multi_photo:
            st. image(multi_photo, caption="Preview", width=200)
    
    if st.button("🔀 Analyze Combined Data", use_container_width=True):
        if not (multi_text or multi_audio or multi_photo):
            st.error("Please provide at least one input")
        else:
            multi_data = {}
            
            # Add text
            if multi_text:
                multi_data["text"] = multi_text
            
            # Upload audio
            if multi_audio: 
                temp_audio = save_uploaded_file(multi_audio)
                if temp_audio and jamai_client:
                    try:
                        upload_resp = jamai_client.file.upload_file(temp_audio)
                        uri = extract_uri_from_response(upload_resp)
                        if uri:
                            multi_data["audio text"] = uri
                    except Exception as e:
                        st.error(f"Audio upload failed: {e}")
                    finally: 
                        cleanup_temp_file(temp_audio)
            
            # Upload photo
            if multi_photo:
                temp_photo = save_uploaded_file(multi_photo)
                if temp_photo and jamai_client:
                    try:
                        upload_resp = jamai_client.file.upload_file(temp_photo)
                        uri = extract_uri_from_response(upload_resp)
                        if uri: 
                            multi_data["image"] = uri
                    except Exception as e:
                        st. error(f"Photo upload failed:  {e}")
                    finally: 
                        cleanup_temp_file(temp_photo)
            
            # Submit to JamAI
            if multi_data:
                with st.spinner("Processing multi-modal data..."):
                    try:
                        if jamai_client: 
                            response = add_table_row(TABLE_IDS["multi"], multi_data)
                            data = parse_response_data(response)
                            
                            # Display results
                            st.success("✅ Multi-Modal Analysis Complete")

                            # Use correct field names from the API
                            description = get_field_value(data, "input_summary", "No description available")
                            summary = get_field_value(data, "diagonise", "No summary available")

                            # Create a more visual layout
                            st.markdown("### 🔍 Integrated Analysis")

                            # Use columns for better layout
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                st.markdown("#### 📋 Situation Assessment")
                                st. info(description)
                                
                                st.markdown("#### 🚨 Safety Recommendations")
                                st.warning(summary)

                            with col2:
                                st.markdown("#### 📊 Analysis Summary")
                                st.metric("Input Types", len([k for k in multi_data.keys()]))
                                st.metric("Confidence", "High ✅")
                                st.button("📞 Emergency Services", type="primary", use_container_width=True)
                                st.button("📍 Share Location", use_container_width=True)

                            with st.expander("🔧 Debug Information"):
                                st.json(data)
                        else: 
                            st.error("JamAI client not available")
                    except Exception as e:
                        st.error(f"Multi-modal analysis error: {e}")

# =============================================================================
# TAB 3: AI CHAT ASSISTANT
# =============================================================================
with tab_chat:  
    st.header("💬 AI Chat Assistant")
    st.info("Ask questions and get real-time guidance from the AI assistant")
    
    # Initialize chat history
    if "chat_history" not in st. session_state:
        st. session_state.chat_history = []
    
    # Display chat history
    for msg in st.session_state.chat_history:  
        role = msg. get("role", "user")
        content = msg.get("content", "")
        with st.chat_message(role):
            st.write(content)
    
    # Chat input
    user_message = st.chat_input("Type your message here...")
    
    if user_message:
        # Add user message to history
        st.session_state. chat_history.append({"role": "user", "content": user_message})
        
        # Display user message
        with st.chat_message("user"):
            st.write(user_message)
        
        # Prepare data for JamAI (input column is "chat")
        chat_data = {"chat": user_message}
        
        # Get AI response
        with st.spinner("Thinking..."):
            try:
                if jamai_client:
                    response = add_table_row(TABLE_IDS["chat"], chat_data)
                    data = parse_response_data(response)
                    
                    # Extract assistant reply from the "output" column
                    assistant_reply = get_field_value(data, "output", "I'm sorry, I couldn't generate a response.")
                    
                    # Add to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": assistant_reply
                    })
                    
                    # Display assistant message
                    with st.chat_message("assistant"):
                        st.write(assistant_reply)
                    
                    # Debug info
                    with st.expander("🔍 Debug Data"):
                        st.json(data)
                else:
                    error_msg = "JamAI client not available. Please configure credentials."
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                    with st.chat_message("assistant"):
                        st.error(error_msg)
            except Exception as e:
                error_msg = f"Error:  {e}"
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content":  error_msg
                })
                with st.chat_message("assistant"):
                    st.error(error_msg)

# =============================================================================
# FOOTER
# =============================================================================
st.divider()
st.caption("🚨 AERN - AI Emergency Response Navigator | Powered by Insomniac")