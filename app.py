import random
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

# Custom CSS for emergency response theme
st.markdown("""
<style>
    .stButton>button {
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
        font-weight:  bold;
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

    st.success("🟢 System Online: Connected to Help Center")
    st.divider()
    # -------------------------------------
    st.header("⚙️ System Configuration")
    
    # # Credentials status
    # with st.expander("🔑 Credentials Status", expanded=False):
    #     st.write(f"**API Key:** {'✅ Loaded' if API_KEY else '❌ Missing'}")
    #     st.write(f"**Project ID:** {PROJECT_ID if PROJECT_ID else '❌ Missing'}")
    
    # # Table IDs
    # with st.expander("📋 Table Configuration", expanded=False):
    #     st.write("**Configured Table IDs:**")
    #     for key, value in TABLE_IDS. items():
    #         st.code(f"{key}: {value}")
    
    # # List available tables
    # if st.button("🔍 List Available Action Tables"):
    #     with st.spinner("Fetching tables..."):
    #         tables = list_action_tables()
    #         if tables:
    #             st.success(f"Found {len(tables)} tables:")
    #             for table in tables: 
    #                 st.write(f"• {table}")
    #         else:
    #             st.info("No tables found or unable to connect")
    
    # # Schema Inspector
    # st.markdown("### 🔬 Schema Inspector")
    # inspect_table = st.selectbox(
    #     "Select table to inspect:",
    #     options=list(TABLE_IDS.keys()),
    #     format_func=lambda x: f"{x. upper()} ({TABLE_IDS[x]})"
    # )
    
    # if st.button("Inspect Schema"):
    #     table_id = TABLE_IDS[inspect_table]
    #     with st.spinner(f"Inspecting {table_id}..."):
    #         schema = get_table_schema(table_id)
    #         if schema:
    #             st.success("Schema retrieved!")
                
    #             # Display input columns
    #             if hasattr(schema, "cols") and schema.cols:
    #                 st.write("**Input Columns:**")
    #                 for col in schema.cols:
    #                     st.write(f"• {col.id} ({col.dtype})")
                
    #             # Display output columns
    #             if hasattr(schema, "chat_cols") and schema.chat_cols:
    #                 st.write("**Output Columns:**")
    #                 for col in schema.chat_cols:
    #                     st. write(f"• {col. id} ({col.dtype})")
                
    #             with st.expander("Raw Schema Data"):
    #                 st.write(schema)
    #         else:
    #             st. error("Failed to retrieve schema")

# =============================================================================
# MAIN TABS
# =============================================================================
tab_emergency, tab_multi, tab_chat = st.tabs([
    "🔥 Emergency Response",
    "🔀 Quick AI Guidance",
    "💬 AI Chat Assistant"
])

# =============================================================================
# TAB 1: EMERGENCY RESPONSE
# =============================================================================
with tab_emergency:
    st.header("⚡ Quick Emergency Response")
    st.info("Select your emergency type for rapid assessment and guidance")
    
    # 1. 初始化 Session State (如果还没有记忆，先创建一个空的)
    if "selected_emergency" not in st.session_state:
        st.session_state.selected_emergency = None

    # Emergency type buttons
    col1, col2, col3 = st.columns(3)
    
    # 2. 修改按钮逻辑：点击时把结果存进 Session State
    with col1:
        if st.button("🌊 Flood", use_container_width=True):
            st.session_state.selected_emergency = "Flood"
        if st.button("🏥 Medical Emergency", use_container_width=True):
            st.session_state.selected_emergency = "Medical Emergency"
    
    with col2:
        if st.button("🔥 Fire", use_container_width=True):
            st.session_state.selected_emergency = "Fire"
        if st.button("🌪️ Natural Disaster", use_container_width=True):
            st.session_state.selected_emergency = "Natural Disaster"
    
    with col3:
        if st.button("🚗 Accident", use_container_width=True):
            st.session_state.selected_emergency = "Accident"
        if st.button("🏢 Building Emergency", use_container_width=True):
            st.session_state.selected_emergency = "Building Emergency"
    
    # 3. 从 Session State 读取当前的选择
    # 这样即使页面刷新，它依然记得你是 "Flood"
    emergency_selected = st.session_state.selected_emergency

    if emergency_selected:
        # --- 🎬 第二幕：一键求救 (用户界面) ---
        st.divider()
        st.markdown(f"### 🚨 You are reporting: **{emergency_selected}**")
        
        # 加一个重置按钮，让用户可以重新选灾害类型
        if st.button("🔄 Change Emergency Type"):
            st.session_state.selected_emergency = None
            st.rerun()

        st.warning("⚠️ Press the button below to alert Help Center immediately.")

        with st.form(key="emergency_form"):
            # --- 🎬 后台秘密：自动生成求救信 (代替用户手写) ---
            emergency_text = f"CRITICAL ALERT: {emergency_selected} reported at USM Main Campus. Immediate assistance required. Coordinates: 5.3567° N, 100.3013° E."
            
            # 红色大按钮
            submit_emergency = st.form_submit_button("🚨 CONFIRM & REQUEST HELP", use_container_width=True)
        
        if submit_emergency:
            # --- 🎬 第一秒：心理安抚 (Reassurance) ---
            st.success("✅ REPORT SENT TO Help Centre! Rescue team notified.")
            st.toast("🚨 Alert sent to nearest police station!", icon="🚓")

            # --- 🎬 第二秒：逃生指引 (Guidance) ---
            if emergency_selected == "Flood":
                st.divider()
                st.error("🚨 IMMEDIATE ACTION: Here is your evacuation route.")
                
                # 仪表盘
                st.subheader("📡 Real-time Analysis")
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric(label="Water Level", value="CRITICAL ⚠️", delta="Rising (+15cm)")
                with m2:
                    st.metric(label="Nearest Shelter", value="Dewan Utama", delta="500m")
                with m3:
                    st.metric(label="Est. Evac Time", value="8 mins", delta="Fastest Route")

                # 战术地图
                st.subheader("🗺️ Recommended Evacuation Route")
                current_path = os.path.dirname(os.path.abspath(__file__))
                map_path = os.path.join(current_path, "images", "usm_flood_map.jpg") 
                
                if os.path.exists(map_path):
                    st.image(map_path, caption="🟢 ACTION: Follow the GREEN LINE to Higher Ground!", use_container_width=True)
                else:
                    st.warning("Map loading...")
            
            # --- 🎬 后台处理：静默发送给 AI ---
            emergency_data = {}
            if emergency_text:
                emergency_data["text"] = f"[{emergency_selected}] {emergency_text}"
            
            if emergency_data and jamai_client:
                try:
                    table_id = TABLE_IDS["text"]
                    response = add_table_row(table_id, emergency_data)
                    data = parse_response_data(response)
                except Exception as e:
                    print(f"Background upload failed: {e}")
# =============================================================================
# TAB 2: MULTI-MODALITY FUSION
# =============================================================================
with tab_multi: 
    st.header("What's Happening? 🔀 ")
    st.info(f"Combine multiple inputs for analysis (Table:  {TABLE_IDS['multi']})")
    
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
            st.image(multi_photo, caption="Preview", width=200)
    
    if st.button("🔀 Let's me help you", use_container_width=True):
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
                        st.error(f"Photo upload failed:  {e}")
                    finally:  
                        cleanup_temp_file(temp_photo)
            
            # Submit to JamAI
            if multi_data: 
                messages = [
                    "Preparing your situation overview…",
                    "Identifying risks and next steps…",
                    "Checking details to keep you safe…",
                    "Creating your safety plan…",
                    "We’re reviewing your info to help right now…"
                ]
                with st.spinner(random.choice(messages)):
                    time.sleep(2)

                    try:
                        if jamai_client: 
                            response = add_table_row(TABLE_IDS["multi"], multi_data)
                            data = parse_response_data(response)
                            
                            # Display results
                            st.success("✅ Multi-Modal Analysis Complete")

                            # Use correct field names from the API (same as Emergency tab)
                            description = get_field_value(data, "input_summary", "No description available")
                            summary = get_field_value(data, "diagonise", "No summary available")

                            # Create a more visual layout
                            st.markdown("### 🔍 Integrated Analysis")

                            # Use columns for better layout
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                # SWAPPED ORDER: Show diagnosis FIRST
                                st.markdown("#### 🚨 Safety Recommendations")
                                st.warning(summary)
                                
                                # THEN show situation assessment
                                st.markdown("#### 📋 Situation Assessment")
                                st.info(description)

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
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Display chat history
    for msg in st.session_state.chat_history: 
        role = msg.get("role", "user")
        content = msg.get("content", "")
        with st.chat_message(role):
            st.write(content)
    
    # Chat input
    user_message = st.chat_input("Hello, how can I assist you today?")
    
    if user_message:
        # Add user message to history
        st.session_state.chat_history.append({"role": "user", "content":  user_message})
        
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
                    error_msg = "JamAI client not available.  Please configure credentials."
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                    with st.chat_message("assistant"):
                        st.error(error_msg)
            except Exception as e: 
                error_msg = f"Error: {e}"
                st. session_state.chat_history. append({
                    "role":  "assistant",
                    "content": error_msg
                })
                with st.chat_message("assistant"):
                    st.error(error_msg)
# =============================================================================
# FOOTER
# =============================================================================
st.divider()
st.caption("🚨 AERN - AI Emergency Response Navigator | Powered by Insomniac")