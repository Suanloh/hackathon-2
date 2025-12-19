
import random
import streamlit as st
import tempfile
import os
import time
from jamaibase import JamAI
from jamaibase.protocol import MultiRowAddRequest
import streamlit. components.v1 as components
import math

# =============================================================================
# 1. 设置避难所数据 (给 Sidebar 用)
# =============================================================================
SHELTERS = [
    {"name": "Dewan Utama USM", "lat": 5.3565, "lon": 100.2985, "type": "Main Hall"},
    {"name": "Dewan Tuanku Syed Putra", "lat": 5.3545, "lon": 100.3005, "type": "Hall"},
    {"name": "Kompleks Sukan USM", "lat": 5.3580, "lon": 100.2995, "type": "Sports Complex"},
    {"name": "Hospital USM", "lat": 5.3598, "lon": 100.2993, "type": "Hospital"},
    {"name": "Masjid USM", "lat": 5.3552, "lon": 100.3020, "type": "Mosque"}
]

st.set_page_config(
    initial_sidebar_state="collapsed"  # This makes the sidebar closed by default
)
def calculate_distance_py(lat1, lon1, lat2, lon2):
    """Python 后台计算距离，专门给 Sidebar 列表用"""
    R = 6371000 # 地球半径 (米)
    phi1 = lat1 * math.pi / 180
    phi2 = lat2 * math.pi / 180
    dphi = (lat2 - lat1) * math.pi / 180
    dlambda = (lon2 - lon1) * math.pi / 180
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return int(R * c)

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
# 2. 定义地图组件 (只给 Tab 1 用)
# =============================================================================
def get_live_location():
    """Auto-get user's GPS with retry and manual fallback options"""
    html = """
    <! DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            #map { height: 500px; width: 100%; border-radius: 10px; margin:  10px 0; }
            #status { 
                padding: 15px; 
                background:  #f8f9fa; 
                border-radius: 8px; 
                margin: 10px 0;
                text-align: center;
                font-size: 16px;
            }
            . loading { color: #007bff; font-weight: bold; }
            .success { color: #28a745; font-weight: bold; }
            .error { color: #dc3545; font-weight: bold; }
            .btn {
                background:  #007bff;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
                margin: 5px;
                font-weight: bold;
            }
            .btn:hover { background: #0056b3; }
            .btn-danger { background: #dc3545; }
            . btn-danger:hover { background:  #c82333; }
            #controls { text-align: center; margin: 10px 0; display: none; }
        </style>
    </head>
    <body>
        <div id="status" class="loading">📡 Getting your location...</div>
        <div id="controls">
            <button class="btn" onclick="retryLocation()">🔄 Retry GPS</button>
            <button class="btn btn-danger" onclick="useFallback()">📍 Use USM Default Location</button>
        </div>
        <div id="map"></div>
        
        <script>
        let map = null;
        let retryCount = 0;
        const MAX_RETRIES = 2;
        
        const shelters = [
            {name: "Dewan Utama USM", lat: 5.3565, lon: 100.2985, capacity: "500 people", type: "Main Hall"},
            {name: "Dewan Tuanku Syed Putra", lat: 5.3545, lon: 100.3005, capacity: "300 people", type: "Hall"},
            {name: "Kompleks Sukan USM", lat: 5.3580, lon: 100.2995, capacity: "400 people", type: "Sports Complex"},
            {name: "Hospital USM", lat: 5.3598, lon: 100.2993, capacity: "Emergency Center", type: "Hospital"},
            {name: "Masjid USM", lat: 5.3552, lon: 100.3020, capacity: "200 people", type: "Mosque"}
        ];
        
        function calculateDistance(lat1, lon1, lat2, lon2) {
            const R = 6371e3;
            const φ1 = lat1 * Math.PI / 180;
            const φ2 = lat2 * Math. PI / 180;
            const Δφ = (lat2 - lat1) * Math.PI / 180;
            const Δλ = (lon2 - lon1) * Math.PI / 180;
            const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ/2) * Math.sin(Δλ/2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return R * c;
        }
        
        function createStraightPath(start, end) {
            // Just return start and end points for a straight line
            return [start, end];
        }
        
        function showPosition(position) {
            const currentLat = position.coords.latitude;
            const currentLon = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            
            // Hide controls if showing
            document.getElementById('controls').style.display = 'none';
            
            // Update status
            document.getElementById('status').className = 'success';
            document.getElementById('status').innerHTML = `✅ Location acquired! Accuracy: ±${Math.round(accuracy)}m`;
            
            displayMap(currentLat, currentLon, accuracy, true);
        }
        
        function displayMap(currentLat, currentLon, accuracy, isRealGPS) {
            // Clear existing map if any
            if (map !== null) {
                map.remove();
            }
            
            // Initialize map
            map = L.map('map').setView([currentLat, currentLon], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap',
                maxZoom: 19
            }).addTo(map);
            
            // Add user marker (red)
            const userPopupText = isRealGPS ? '<b>📍 You are here!</b>' : '<b>📍 Your approximate location</b><br>(Using default USM location)';
            L.marker([currentLat, currentLon], {
                icon:  L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                    shadowSize: [41, 41]
                })
            }).addTo(map).bindPopup(userPopupText).openPopup();
            
            // Add accuracy circle
            L.circle([currentLat, currentLon], {
                color: 'red',
                fillColor: '#f03',
                fillOpacity: 0.15,
                radius: accuracy
            }).addTo(map);
            
            // Find nearest shelter
            let nearestShelter = null;
            let minDistance = Infinity;
            
            shelters.forEach(shelter => {
                const distance = calculateDistance(currentLat, currentLon, shelter.lat, shelter.lon);
                if (distance < minDistance) {
                    minDistance = distance;
                    nearestShelter = shelter;
                }
            });
            
            // Add nearest shelter marker (green)
            if (nearestShelter) {
                L.marker([nearestShelter.lat, nearestShelter.lon], {
                    icon: L.icon({
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
                        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow. png',
                        iconSize:  [25, 41],
                        iconAnchor: [12, 41],
                        popupAnchor: [1, -34],
                        shadowSize: [41, 41]
                    })
                }).addTo(map).bindPopup(`
                    <b>🏢 ${nearestShelter. name}</b><br>
                    Type: ${nearestShelter. type}<br>
                    Distance: ${(minDistance / 1000).toFixed(2)} km<br>
                    Est. Walk: ${Math.round(minDistance / 83)} min
                `);
                
                // Draw straight path to nearest shelter
                L.polyline([
                    [currentLat, currentLon],
                    [nearestShelter.lat, nearestShelter.lon]
                ], {
                    color: '#2962FF',
                    weight: 4,
                    opacity: 0.8,
                    dashArray: '10, 5',
                    lineCap: 'round'
                }).addTo(map);
                
                // Fit map to show both markers
                const bounds = L.latLngBounds([
                    [currentLat, currentLon],
                    [nearestShelter.lat, nearestShelter.lon]
                ]);
                map.fitBounds(bounds, { padding: [50, 50] });
                
                // Send data to Streamlit
                const shelterData = {
                    name: nearestShelter.name,
                    distance: minDistance,
                    distanceKm: (minDistance / 1000).toFixed(2),
                    distanceM: Math.round(minDistance),
                    walkTime: Math. round(minDistance / 83),
                    capacity: nearestShelter.capacity,
                    type: nearestShelter.type
                };
                
                window.parent.postMessage({
                    type: 'streamlit: setComponentValue',
                    lat: currentLat,
                    lon: currentLon,
                    accuracy: accuracy,
                    shelter: shelterData,
                    gpsType: isRealGPS ? 'real' : 'fallback'
                }, '*');
            }
        }
        
        function showError(error) {
            let message = '';
            let showControls = false;
            
            switch(error. code) {
                case error.PERMISSION_DENIED:
                    message = '❌ Location access denied. Please enable location permissions or use default location.';
                    showControls = true;
                    break;
                case error. POSITION_UNAVAILABLE:
                    message = '❌ Location information unavailable. ';
                    showControls = true;
                    break;
                case error.TIMEOUT: 
                    if (retryCount < MAX_RETRIES) {
                        retryCount++;
                        message = `⏳ Location request timed out. Retrying (${retryCount}/${MAX_RETRIES})...`;
                        document.getElementById('status').className = 'loading';
                        document.getElementById('status').innerHTML = message;
                        setTimeout(getLocation, 1000);
                        return;
                    } else {
                        message = '❌ Location request timed out after multiple attempts.  Use options below.';
                        showControls = true;
                    }
                    break;
                default:
                    message = '❌ An unknown error occurred. ';
                    showControls = true;
            }
            
            document.getElementById('status').className = 'error';
            document.getElementById('status').innerHTML = message;
            
            if (showControls) {
                document. getElementById('controls').style.display = 'block';
            }
        }
        
        function getLocation() {
            if (navigator.geolocation) {
                document.getElementById('status').className = 'loading';
                document.getElementById('status').innerHTML = '📡 Getting your location...';
                
                navigator.geolocation.getCurrentPosition(showPosition, showError, {
                    enableHighAccuracy: true,
                    timeout: 15000,  // 15 seconds
                    maximumAge: 0
                });
            } else {
                document.getElementById('status').className = 'error';
                document.getElementById('status').innerHTML = '❌ Geolocation is not supported by your browser.';
                document.getElementById('controls').style.display = 'block';
            }
        }
        
        function retryLocation() {
            retryCount = 0;
            document.getElementById('controls').style.display = 'none';
            getLocation();
        }
        
        function useFallback() {
            // Use USM School of Computer Sciences as default location
            const fallbackLat = 5.3540;
            const fallbackLon = 100.3015;
            const fallbackAccuracy = 500;  // 500m radius
            
            document.getElementById('status').className = 'success';
            document.getElementById('status').innerHTML = '📍 Using default USM location (School of Computer Sciences)';
            document.getElementById('controls').style.display = 'none';
            
            displayMap(fallbackLat, fallbackLon, fallbackAccuracy, false);
        }
        
        // Auto-start GPS on load
        window.onload = function() {
            getLocation();
        };
        </script>
    </body>
    </html>
    """
    
    # Single render
    component_value = components.html(html, height=650)
    
    # Store GPS data when received
    if component_value:
        if isinstance(component_value, dict):
            st.session_state.emergency_location = {
                'lat':  component_value.get('lat'),
                'lon': component_value.get('lon'),
                'accuracy': component_value.get('accuracy'),
                'shelter': component_value.get('shelter'),
                'gps_type': component_value.get('gpsType', 'real')
            }
    
    return component_value

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
# 3. SIDEBAR (保持列表样式)
# =============================================================================
with st.sidebar:
    st. subheader("📍 Live Status")
    
    # Get coordinates status
    loc = st.session_state.get('emergency_location')
    
    if loc and loc. get('lat'):
        # 🟢 If coordinates exist, show shelter list
        user_lat = loc['lat']
        user_lon = loc['lon']
        
        st.success(f"🟢 GPS Connected")
        st.caption(f"Lat: {user_lat:.4f}, Lon: {user_lon:.4f}")
        
        st.divider()
        st.subheader("🏢 Nearby Safe Zones")
        
        # Calculate distances to all shelters
        shelter_list_with_dist = []
        for s in SHELTERS:
            dist = calculate_distance_py(user_lat, user_lon, s['lat'], s['lon'])
            shelter_list_with_dist.append({**s, "dist": dist})
        
        # Sort by distance
        shelter_list_with_dist.sort(key=lambda x: x['dist'])
        
        # Display list
        for s in shelter_list_with_dist:
            if s == shelter_list_with_dist[0]:
                st.markdown(f"**🌟 {s['name']} (NEAREST)**")
                st.progress(100, text="Recommended")
            else:
                st.markdown(f"**{s['name']}**")
            
            st.caption(f"📏 {s['dist']}m away • Type: {s['type']}")
            st.markdown("---")
            
    else:
        # 🔴 No coordinates - just show shelter database
        st.subheader("🏢 USM Shelters Database")
        for s in SHELTERS:
            st.text(f"• {s['name']}")
# =============================================================================
# MAIN TABS
# =============================================================================
tab_emergency, tab_multi, tab_chat = st.tabs([
    "🔥 Emergency Response",
    "🔀 Quick Guidance",
    "💬 CareLink"
])

# =============================================================================
# 4. TAB 1: EMERGENCY RESPONSE (Trigger)
# =============================================================================
with tab_emergency:
    st.header("⚡ Quick Emergency Response")
    st.info("Select your emergency type for rapid assessment and guidance")
    
    if "selected_emergency" not in st.session_state:
        st.session_state.selected_emergency = None

    # 按钮区域
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🌊 Flood", use_container_width=True): st.session_state.selected_emergency = "Flood"
        if st. button("🏥 Medical", use_container_width=True): st.session_state.selected_emergency = "Medical Emergency"
    with col2:
        if st.button("🔥 Fire", use_container_width=True): st.session_state.selected_emergency = "Fire"
        if st.button("🌪️ Natural Disaster", use_container_width=True): st.session_state.selected_emergency = "Natural Disaster"
    with col3:
        if st. button("🚗 Accident", use_container_width=True): st.session_state.selected_emergency = "Accident"
        if st.button("🏢 Building", use_container_width=True): st.session_state.selected_emergency = "Building Emergency"
    
    emergency_selected = st.session_state. selected_emergency

    if emergency_selected:
        st.divider()
        st.markdown(f"### 🚨 Reporting: **{emergency_selected}**")
        
        if st.button("🔄 Change Type"):
            st.session_state.selected_emergency = None
            st.session_state.confirm_dialog = False  # Reset confirmation
            st.session_state.form_submitted = False  # Reset submission
            st.rerun()

        st.warning(f"⚠️ Activating Protocol for **{emergency_selected}**...")

        # Initialize confirmation state
        if "confirm_dialog" not in st.session_state:
            st.session_state.confirm_dialog = False
        
        st.write(f"**Alert Message:** CRITICAL ALERT: {emergency_selected} at USM. GPS Tracking Activated.")
        
        # First button - shows confirmation dialog
        if not st.session_state.confirm_dialog and not st.session_state.get("form_submitted"):
            if st.button("🚨 CONFIRM & REQUEST HELP", use_container_width=True, type="primary"):
                st.session_state.confirm_dialog = True
                st.rerun()
        
        # Confirmation dialog
        if st.session_state.confirm_dialog:
            st.warning("⚠️ **Are you sure you want to request emergency help?**")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ YES, SEND ALERT", use_container_width=True, type="primary"):
                    st.session_state.form_submitted = True
                    st.session_state.confirm_dialog = False
                    st.rerun()
            
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.confirm_dialog = False
                    st.rerun()
        
        # 🟢 After confirmation
        if st.session_state.get("form_submitted"):
            st.success("✅ ALERT SENT! Rescue team dispatched.")
            st.toast(f"🚨 {emergency_selected} Alert Broadcasted!", icon="📡")
            
            advice_dict = {
                "Flood": "🌊 Move to HIGHER GROUND immediately.",
                "Fire": "🔥 Evacuate via STAIRS.",
                "Medical Emergency": "🏥 Clear space for ambulance.",
                "Accident": "🚗 Do not move injured persons.",
                "Natural Disaster": "🌪️ Find cover immediately.",
                "Building Emergency": "🏢 Exit away from glass."
            }
            st.error(f"📢 **ACTION:** {advice_dict.get(emergency_selected, 'Evacuate now.')}")

            # Metrics
            st.subheader(f"🗺️ Live Evacuation Route")
            
            # Show metrics if GPS data available
            loc = st.session_state.get('emergency_location')
            if loc and loc.get('shelter'):
                shelter_info = loc['shelter']
                m1, m2, m3 = st.columns(3)
                with m1: st.metric("Hazard Level", "CRITICAL ⚠️", "Zone Active")
                with m2: st.metric("Nearest Shelter", shelter_info. get('name', 'Calculating...'), 
                                  f"{shelter_info.get('distanceM', '?')}m away")
                with m3: st.metric("Est. Walk Time", f"{shelter_info.get('walkTime', '?')} mins", "Fastest Route")
            else:
                st.info("📍 Acquiring GPS location...")

            # 🟢 Auto-start GPS map
            get_live_location()
            
            # Backend upload
            if jamai_client and "upload_done" not in st.session_state:
                try:
                    final_text = f"[{emergency_selected}] User at USM. Status: Critical."
                    add_table_row(TABLE_IDS["text"], {"text": final_text})
                    st.session_state. upload_done = True
                except: 
                    pass
# =============================================================================
# TAB 2: MULTI-MODALITY FUSION
# =============================================================================
with tab_multi: 
    st.header("What's Happening? 🔀 ")
    st.info(f"You can provide multiple inputs (text, audio, photo) for situation analysis.")
    
    col1, col2 = st. columns(2)
    
    with col1:
        multi_text = st.text_area("**Describe** the situation (Text)", height=150,
                                  placeholder="Example: I see black smoke coming from the Computer Science building, and the fire alarm is ringing..."
        )
        
        multi_audio = st.file_uploader(
            "Audio Input (Optional):",
            type=["mp3", "wav", "m4a"],
            help="Upload a voice recording describing the scene.",
            key="multi_audio"
        )
    
    with col2:
        multi_photo = st.file_uploader(
            "Upload evidence (Optional):",
            type=["jpg", "png", "jpeg"],
            key="multi_photo"
        )
        if multi_photo: 
            st.image(multi_photo, caption="Preview", width=200)
    
    if st.button("Click here to get an immediate escape plan.", use_container_width=True):
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
                            st.success("✅ Analysis Complete")

                            # Use correct field names from the API (same as Emergency tab)
                            description = get_field_value(data, "input_summary", "No description available")
                            summary = get_field_value(data, "diagonise", "No summary available")

                            # # Create a more visual layout
                            # st.markdown("### 🔍 Integrated Analysis")

                            # Use columns for better layout
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                # SWAPPED ORDER: Show diagnosis FIRST
                                st.markdown("#### 🚨 Safety Recommendations")
                                st.warning(summary)
                                
                                # THEN show situation assessment
                                st.markdown("#### 📋 Situation Overview")
                                st.info(description)

                            with col2:
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
st.markdown("""
    <style>
        .footer-text {
            text-align: center;
            color: #888; /* 灰色，在黑白背景都看得清 */
            font-size: 12px;
            padding-bottom: 20px;
        }
        .disclaimer-box {
            /* 关键修改：使用 rgba 透明度 */
            /* 红色背景，但在黑色底色上只会显出淡淡的红光 */
            background-color: rgba(255, 80, 80, 0.1); 
            
            /* 边框让它更有科技感 */
            border: 1px solid rgba(255, 80, 80, 0.3);
            
            /* 文字颜色：使用亮红色/粉色，在深色背景下更容易阅读 */
            color: #ff8a80;
            
            padding: 10px;
            border-radius: 8px;
            display: inline-block;
            max-width: 600px;
        }
    </style>
    
    <div class="footer-text">
        <p>🚨 <b>AERN - AI Emergency Response Navigator</b> | Powered by Insomniac</p>
        <div class="disclaimer-box">
            ⚠️ <b>DISCLAIMER:</b> This system is a prototype for demonstration only. <br>
            AI responses may be inaccurate. In real life-threatening situations, <b>ALWAYS CALL 999</b>.
        </div>
    </div>
""", unsafe_allow_html=True)
