import streamlit.components.v1 as components
import streamlit as st

def show_gps_map():
    """Display GPS map (view only)"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            #map { height: 400px; width: 100%; border-radius: 10px; }
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
        if (navigator.geolocation) {
            navigator.geolocation. getCurrentPosition(function(position) {
                const lat = position.coords.latitude;
                const lon = position.coords. longitude;
                
                const map = L.map('map').setView([lat, lon], 16);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
                L.marker([lat, lon]).addTo(map).bindPopup('📍 You are here!').openPopup();
                
                // Save to localStorage
                localStorage.setItem('current_lat', lat);
                localStorage.setItem('current_lon', lon);
            });
        }
        </script>
    </body>
    </html>
    """
    components.html(html, height=450)

def get_gps_coordinates():
    """Get coordinates from user input after viewing map"""
    if st.button("📍 Get My GPS Location", use_container_width=True):
        st.session_state.gps_requested = True
    
    if st.session_state.get('gps_requested', False):
        show_gps_map()
        
        st.info("👆 See your location on the map above")
        
        if st.button("📤 Share This Location to Emergency", type="primary", use_container_width=True):
            # Since we can't directly get from JavaScript, ask user to confirm
            st.session_state.location_shared = True
            st. balloons()