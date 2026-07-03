import streamlit as st
import pandas as pd
import folium
import json
import time
from folium.plugins import HeatMap, MarkerCluster, Fullscreen
from branca.element import Template, MacroElement
from streamlit_folium import st_folium
from google import genai
from google.genai import types
import re
import scipy

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(layout="wide")

st.markdown('''
    <style>
    iframe {
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    }
    </style>
''', unsafe_allow_html=True)

# ==========================================
# 2. SCREEN 1: THE LOGIN SCREEN
# ==========================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 Access Restricted")
        user_password = st.text_input("Enter App Password:", type="password")
        if user_password:
            if user_password == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# ==========================================
# 3. SCREEN 2: THE MAIN DASHBOARD
# ==========================================

# --- Custom CSS Injection (Clean & Native) ---
st.markdown("""
<style>
  [data-testid="stHeader"] { display: none !important; }
  .block-container { padding-top: 2rem !important; max-width: 98% !important; padding-bottom: 1rem !important; }
  
  /* HOTFIX 2: Chat Text Wrapping */
  div[data-testid="stChatMessageContent"], div[data-testid="stChatMessageContent"] p {
      white-space: pre-wrap !important;
      word-wrap: break-word !important;
      overflow-wrap: break-word !important;
  }

  /* HOTFIX 4: Force st.chat_input to sit inline at the top instead of pinning to the bottom */
  [data-testid="stChatInput"] {
      position: static !important;
      padding-bottom: 15px !important;
      background-color: transparent !important;
  }
</style>
""", unsafe_allow_html=True)

# --- The Header ---
header_left, header_right = st.columns([3, 1])
with header_left:
    st.title('West Marine Store Analysis')
with header_right:
    uploaded_file = st.file_uploader('Upload CSV Data', type=['csv'])

# --- Session State Initialization ---
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
    
if 'code_history' not in st.session_state:
    st.session_state.code_history = []
    
if 'active_prompt' not in st.session_state:
    st.session_state.active_prompt = None

if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = None

# HOTFIX 1: Bulletproof Legend & Header colors (background-color: #ffffff !important; color: #0f172a !important;)
baseline_code = """
def generate_custom_map(df):
    import folium
    import pandas as pd
    import streamlit as st
    import json
    from folium.plugins import Fullscreen
    from branca.element import Template, MacroElement
    
    def build_popup_html(row):
        # 1. MANDATORY FIELDS
        name = str(row.get('STORE_NAME', 'Unknown'))
        status = str(row.get('STATUS', 'Unknown'))
        sqft = str(row.get('SQFT', 'Unknown'))
        node_type = str(row.get('TYPE', 'Unknown'))
        
        html = f"<div style='min-width: 150px;'>"
        html += f"<h4 style='margin-top:0px; margin-bottom:5px;'>{name}</h4>"
        html += f"<b>Status:</b> {status}<br>"
        html += f"<b>Square Footage:</b> {sqft}<br>"
        html += f"<b>Type:</b> {node_type}<br>"
        html += f"<hr style='margin: 5px 0px;'>"
        html += "</div>"
        return html

    # 1. Sort dataframe for Z-Ordering
    if 'TYPE' in df.columns and 'STATUS' in df.columns:
        df = df.sort_values(by=['TYPE', 'STATUS']) 

    # 2. Save to session state for the data extraction table
    st.session_state.filtered_df = df
    
    # 3. Initialize map
    custom_map = folium.Map(location=[39.8283, -98.5795], zoom_start=4, tiles=st.session_state.get('map_style_selector', 'OpenStreetMap'))
    
    legend_dict = {
        "Open Store": "#90ee90",
        "Open Hub": "#006400",
        "Closing Store": "#ff7f7f",
        "Closing Hub": "#8b0000",
        "Bubble Store": "#add8e6",
        "Bubble Hub": "#00008b",
        "DC": "#6a0dad"
    }
    
    # 4. Build markers
    for index, row in df.iterrows():
        node_type = str(row.get('TYPE', '')).upper()
        status = str(row.get('STATUS', '')).upper()
        name = str(row.get('STORE_NAME', 'Unknown'))
        
        # Uniform default size and base color
        radius = 6 
        fill_color = "#90ee90" 
        
        # Apply Matrix Logic (COLORS ONLY)
        if 'DC' in node_type or 'DISTRIBUTION' in node_type:
            fill_color = "#6a0dad" # DC Purple
        elif 'HUB' in node_type:
            if 'CLOS' in status:
                fill_color = "#8b0000" # Closing Hub
            elif 'BUBBLE' in status:
                fill_color = "#00008b" # Bubble Hub
            else:
                fill_color = "#006400" # Open Hub
        else: # Standard Store
            if 'CLOS' in status:
                fill_color = "#ff7f7f" # Closing Store
            elif 'BUBBLE' in status:
                fill_color = "#add8e6" # Bubble Store
            else:
                fill_color = "#90ee90" # Open Store
        
        if pd.notna(row.get('LAT')) and pd.notna(row.get('LONG')):
            folium.CircleMarker(
                location=[row['LAT'], row['LONG']],
                radius=radius, 
                color="white", 
                weight=1, 
                fill=True,
                fill_color=fill_color, 
                fill_opacity=0.9,
                popup=folium.Popup(build_popup_html(row), max_width=300)
            ).add_to(custom_map)
            
    # --- LEGEND BUILDER ---
    legend_html_items = ""
    for label, color in legend_dict.items():
        legend_html_items += f'<div style="display: flex; align-items: center; margin-bottom: 6px;"><span style="background-color: {color}; border-radius: 50%; width: 12px; height: 12px; display: inline-block; margin-right: 8px; border: 1px solid #cbd5e1; flex-shrink: 0;"></span><span style="color: #0f172a !important; font-size: 13px; font-family: system-ui, sans-serif; font-weight: 600;">{label}</span></div>'
    
    full_legend_html = f'''
    <div style="background-color: #ffffff !important; color: #0f172a !important; padding: 12px 16px; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.18); border: 1px solid #e2e8f0; min-width: 130px;">
        <h4 style="margin: 0 0 10px 0; font-weight: 700; font-size: 14px; color: #0f172a !important; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; font-family: system-ui, sans-serif;">Map Legend</h4>
        {legend_html_items}
    </div>
    '''
    
    legend_template = '''
    {% macro script(this, kwargs) %}
    var legend = L.control({position: 'bottomleft'});
    legend.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'info legend');
        div.innerHTML = __LEGEND_PAYLOAD__;
        L.DomEvent.disableClickPropagation(div);
        return div;
    };
    legend.addTo({{ this._parent.get_name() }});
    {% endmacro %}
    '''
    legend_macro = MacroElement()
    legend_macro._template = Template(legend_template.replace("__LEGEND_PAYLOAD__", json.dumps(full_legend_html)))
    custom_map.add_child(legend_macro)
    
    # --- TITLE BOX BUILDER ---
    map_blurb = "West Marine: Full Store Network" 
    
    blurb_html = f'''
    <div style="background-color: #ffffff !important; color: #0f172a !important; padding: 12px 16px; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.18); border: 1px solid #e2e8f0; max-width: 350px;">
        <h4 style="margin: 0; font-weight: 700; font-size: 14px; color: #0f172a !important; font-family: system-ui, sans-serif;">{map_blurb}</h4>
    </div>
    '''
    
    title_template = '''
    {% macro script(this, kwargs) %}
    var titleControl = L.control({position: 'topright'});
    titleControl.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'info title');
        div.innerHTML = __BLURB_PAYLOAD__;
        L.DomEvent.disableClickPropagation(div);
        return div;
    };
    titleControl.addTo({{ this._parent.get_name() }});
    {% endmacro %}
    '''
    title_macro = MacroElement()
    title_macro._template = Template(title_template.replace("__BLURB_PAYLOAD__", json.dumps(blurb_html)))
    custom_map.add_child(title_macro)
            
    Fullscreen().add_to(custom_map)
    return custom_map
"""

if 'last_code' not in st.session_state:
    st.session_state.last_code = baseline_code.strip()

# --- Data Upload Check ---
if not uploaded_file:
    st.info("Please upload your West Marine CSV data in the top right to begin.")
    st_folium(folium.Map(location=[39.8283, -98.5795], zoom_start=4), use_container_width=True, height=700)
    st.stop()

# --- Data Preprocessing & Sanitization ---
try:
    df = pd.read_csv(uploaded_file, skiprows=3)
    
    df.columns = df.columns.str.replace(r'\n', ' ', regex=True)
    df.columns = df.columns.str.replace(r'[^\w\s]', '', regex=True)
    df.columns = df.columns.str.strip().str.replace(r'\s+', '_', regex=True).str.upper()

    if 'FORMAT' in df.columns:
        df['TYPE'] = df['FORMAT'].astype(str).str.lower()
    if 'GROUP' in df.columns:
        def determine_status(group_val):
            group_val = str(group_val).upper()
            if 'CLOSE' in group_val: return 'closing'
            elif 'BUBBLE' in group_val: return 'bubble'
            return 'open'
        df['STATUS'] = df['GROUP'].apply(determine_status)
except Exception as e:
    st.error(f"Error processing the CSV file: {e}")
    st.stop()

if st.session_state.get('filtered_df') is None:
    st.session_state.filtered_df = df

def get_dataframe_summary(df):
    summary_lines = []
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_numeric_dtype(df[col]):
            summary_lines.append(f"- {col} ({dtype}): Numeric range = {df[col].min()} to {df[col].max()}")
        elif dtype == 'object' or dtype.name == 'category':
            unique_vals = df[col].dropna().unique()
            summary_lines.append(f"- {col} ({dtype}): Categorical sample = {list(unique_vals[:5])}")
        else:
            summary_lines.append(f"- {col} ({dtype})")
    return "\n".join(summary_lines)

# --- Gemini AI Configuration ---
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

system_instruction = """
You are a geospatial data expert and Python analyst. The user will ask you to modify a Folium map based on their data. You must output ONLY raw, executable Python code. Do NOT wrap the code in markdown.
Assume folium, pandas, and streamlit as st are already imported. You have access to HeatMap, MarkerCluster, and Fullscreen from folium.plugins, as well as Template and MacroElement from branca.element.

VISUAL & STYLING RULES:
- UNIFORM SIZING: By default, ALL nodes (Stores, Hubs, DCs) must have a radius=6. Do not change the size of nodes based on their type. Only change node sizes if the user explicitly asks you to scale them by a specific data metric.
- MASTER CSS STYLING (DARK MODE PREVENTION): Streamlit heavily injects dark mode into iframes. You MUST NOT rely on inline styles. Instead, you MUST inject this exact global CSS block into the map's header using `custom_map.get_root().header.add_child(folium.Element(style_html))` right before returning the map. This styles the Legend, Title, and Layer Controls perfectly:

    style_html = '''<style>
    /* Force all Leaflet Info Boxes (Legend & Title) to be White with Dark Text */
    .info { 
        background-color: #ffffff !important; 
        color: #0f172a !important; 
        border-radius: 8px !important; 
        box-shadow: 0 4px 14px rgba(0,0,0,0.18) !important; 
        border: 1px solid #e2e8f0 !important; 
        padding: 12px 16px !important; 
    }
    /* Force all text elements INSIDE the boxes to be dark */
    .info h4, .info span, .info div, .info b, .info * { 
        color: #0f172a !important; 
    }

    /* Layer Control Styling */
    .leaflet-control-layers { 
        background-color: #ffffff !important; 
        border-radius: 8px !important; 
        box-shadow: 0 4px 14px rgba(0,0,0,0.18) !important; 
        border: 1px solid #e2e8f0 !important; 
        padding: 10px 14px !important; 
    }
    .leaflet-control-layers label, .leaflet-control-layers span {
        color: #0f172a !important;
        font-weight: 600 !important;
        display: flex !important;
        align-items: center !important;
        margin-bottom: 4px !important;
    }
    .leaflet-control-layers-selector {
        accent-color: #0f172a !important;
        width: 15px !important;
        height: 15px !important;
        margin-right: 8px !important;
    }
    .leaflet-control-layers-separator, .leaflet-control-layers-base {
        display: none !important;
    }
    </style>'''
    
- You must use these strict default styles unless the user explicitly asks for different colors/sizes:
  Open Store: #90ee90
  Open Hub: #006400
  Closing Store: #ff7f7f
  Closing Hub: #8b0000
  Bubble Store: #add8e6
  Bubble Hub: #00008b
  DC: #6a0dad
- Z-Ordering: If plotting multiple types, sort the dataframe so larger/background nodes (DCs, Hubs) are plotted first, and smaller/important nodes (Stores, Closing Stores) are plotted last so they appear on top.
- DYNAMIC SIZING (MIN/MAX BOUNDS): If the user asks to size bubbles by a metric (like Sales or SqFt), you must use min-max normalization to scale the radius. ALWAYS bound the calculated radius between a minimum of 6 and a maximum of 35. This ensures the smallest dots are easily visible and clickable, and the contrast between small and large is highly obvious.
- SPATIAL MATH RULE: If the user asks you to calculate distances, find nearest neighbors, or draw arrows/lines, you MUST use correct spatial library imports. If using cdist, you MUST import it exactly as from scipy.spatial.distance import cdist. Ensure you do not import it directly from scipy.spatial.
- ADVANCED GEOMETRY & SHAPES RULE: You have full permission to draw lines, shapes, and directional flows if the user asks to see relationships. You have two ways to show directional flow; use whichever the user requests, or choose the one that makes the most sense:
  - Animated Flow (AntPath): Use from folium.plugins import AntPath. Example: AntPath(locations=[[lat1, lon1], [lat2, lon2]], color='red', dash_array=[10, 20], delay=1000).add_to(custom_map)
  - Static Arrows: Draw a line, then add arrowheads using PolyLineTextPath. Example:
    from folium.plugins import PolyLineTextPath
    line = folium.PolyLine(locations=[[lat1, lon1], [lat2, lon2]], color='blue').add_to(custom_map)
    PolyLineTextPath(line, '►', repeat=True, offset=6, attributes={'fill': 'blue', 'font-size': '18'}).add_to(custom_map)
  - Geographic Coverage: Use folium.Circle (not CircleMarker) if the user asks for a real-world radius (like a 50-mile coverage zone).
  If you use plugins, you MUST import them inside your generated function (e.g., from folium.plugins import AntPath).

DATA RULES (STRICT FILTERING & INLINE CASTING):
- If the user asks for math/comparisons (e.g., "> 50%"), you MUST safely cast the row value to a float. Strip %, $, and , using str(val).replace()... and handle errors gracefully.
- STRICT FILTERING: If the user asks to filter, find, or show specific stores, you MUST completely exclude the non-matching stores from the map. Do not draw grey circles for them. Either filter the dataframe before your loop, or use if not match: continue inside your loop.
- DATA EXTRACTION: Always save the final filtered subset of data that appears on the map to st.session_state.filtered_df before returning the map.
- DATA CONTEXT NOTE: Distribution Centers (DCs) and Closing Stores often have missing data (NaN or 'N/A') for secondary retail metrics (like Pro Penetration, Seasonality, Climate, etc.). When writing filtering logic or math for these secondary metrics, ALWAYS use .fillna() or .isna() to handle these rows safely so they are either cleanly excluded or bypassed without crashing the script.
- LEGEND RULE: A default legend_dict is provided in the template. If the user asks you to apply custom colors or highlight a specific metric, you MUST update or add to this dictionary before the HTML builder runs. (e.g., legend_dict["Profitable"] = "#10b981").
- MAP BLURB RULE: A map_blurb variable exists in the template. You MUST dynamically rewrite this string to briefly describe the current map view based on the user's request (e.g., if they ask for high-revenue stores, update it to map_blurb = "Stores with Revenue > $2M"). Keep it concise, professional, and under 20 words.
- DYNAMIC SIZING MATH RULE: If you need to find the min/max of a column for normalization (e.g., sizing bubbles by SQFT or Sales), you MUST safely extract and clean the entire column first. Example:
  clean_series = pd.to_numeric(df['SQFT'].astype(str).str.replace(',', '').str.replace('$', '').str.replace('%', ''), errors='coerce')
  min_val, max_val = clean_series.min(), clean_series.max()
  Never do math directly on the raw column without safely casting it to numeric and handling NaNs.

ADVANCED INTERACTIVITY & UI RULES:
- NO STREAMLIT WIDGETS (STRICT BAN): You are strictly forbidden from generating Streamlit widgets (e.g., `st.sidebar`, `st.selectbox`, `st.slider`). All data filtering must be handled purely via Pandas logic based on the user's prompt before building the map. The UI must remain entirely contained within the Folium iframe.

- NATIVE LAYER CONTROL (VISUAL TOGGLING): If the user asks to "toggle layers", "group the map", or "add layer controls", you must use Folium's native grouping. Create groups (`group = folium.FeatureGroup(name="Layer Name")`), add markers to their respective groups, and add the groups to `custom_map`. 
CRITICAL LAYER RULES:
- POSITION: You MUST explicitly set the position using `folium.LayerControl(position='bottomright').add_to(custom_map)` at the very end.
- ANTI-DELETION LOCK: You are strictly forbidden from removing the `# --- LEGEND BUILDER ---` and `# --- TITLE BOX BUILDER ---` sections. The layer control is an ADDITION. The Legend, the Title Box, and the Layer Control MUST ALL seamlessly coexist on the final map.

- CRITICAL UI FIX FOR NATIVE LAYERS: If you use LayerControl, you MUST style it to match the custom legend and title boxes. You must inject this exact CSS block into the map's header before returning the map to make the checkboxes beautiful:
  
style_html = '''<style>
.leaflet-control-layers { 
    background-color: #ffffff !important; 
    color: #0f172a !important; 
    border-radius: 8px !important; 
    box-shadow: 0 4px 14px rgba(0,0,0,0.18) !important; 
    border: 1px solid #e2e8f0 !important; 
    font-family: system-ui, sans-serif !important; 
    padding: 10px 14px !important; 
} 
.leaflet-control-layers-list { 
    font-size: 13px !important; 
    font-weight: 600 !important; 
    margin: 0 !important; 
}
.leaflet-control-layers label {
    display: flex !important;
    align-items: center !important;
    margin-bottom: 6px !important;
    cursor: pointer !important;
}
.leaflet-control-layers-selector {
    accent-color: #0f172a !important;
    width: 15px !important;
    height: 15px !important;
    margin-right: 8px !important;
    cursor: pointer !important;
    margin-top: 0px !important;
}
.leaflet-control-layers-separator, .leaflet-control-layers-base {
    display: none !important;
}
</style>'''
custom_map.get_root().header.add_child(folium.Element(style_html))

- CLUSTERING: If and only if the user asks to cluster the data, use `from folium.plugins import MarkerCluster`. Initialize it via `marker_cluster = MarkerCluster().add_to(custom_map)`, and then add your CircleMarkers directly to `marker_cluster` instead of `custom_map`.
  
CODE STRUCTURE MANDATE: You MUST define a nested helper function named build_popup_html(row) directly INSIDE your generate_custom_map(df) function. You are strictly required to include the mandatory fields (Store Name, Status, and SqFt) at the top of every single popup you generate, followed by an HTML horizontal rule <hr>. Your output must always follow this exact structure:
- MACRO TEMPLATE RULE: You MUST NEVER use an f-string (e.g., f\"\"\") for legend_template or title_template. Doing so will cause a Python "name 'this' is not defined" error because it misinterprets the {{ this._parent }} Jinja tag. You MUST use standard strings (\"\"\") and use .replace() to inject the HTML payloads, exactly as shown in your template.

def generate_custom_map(df):
    import json
    
    def build_popup_html(row):
        # 1. MANDATORY FIELDS (Do not alter or remove these)
        name = str(row.get('STORE_NAME', 'Unknown'))
        status = str(row.get('STATUS', 'Unknown'))
        sqft = str(row.get('SQFT', 'Unknown'))
        node_type = str(row.get('TYPE', 'Unknown'))
        
        html = f"<div style='min-width: 150px;'>"
        html += f"<h4 style='margin-top:0px; margin-bottom:5px;'>{name}</h4>"
        html += f"<b>Status:</b> {status}<br>"
        html += f"<b>Square Footage:</b> {sqft}<br>"
        html += f"<b>Type:</b> {node_type}<br>"
        html += f"<hr style='margin: 5px 0px;'>"
        
        # 2. DYNAMIC FIELDS (Add user-requested data here)
        # [Add your custom HTML for the user's specific request here]
        
        html += "</div>"
        return html

    # 1. Sort dataframe for Z-Ordering (e.g., closing stores at the bottom of the df so they draw last/on top)
    # Example: df = df.sort_values(by=['TYPE', 'STATUS']) 

    # 2. Filter data if requested, and save to session state
    # st.session_state.filtered_df = df

    # 3. Initialize map
    custom_map = folium.Map(location=[39.8283, -98.5795], zoom_start=4, tiles=st.session_state.get('map_style_selector', 'OpenStreetMap'))
    
    legend_dict = {
        "Open Store": "#90ee90",
        "Open Hub": "#006400",
        "Closing Store": "#ff7f7f",
        "Closing Hub": "#8b0000",
        "Bubble Store": "#add8e6",
        "Bubble Hub": "#00008b",
        "DC": "#6a0dad"
    }

    # 4. Build markers
    for _, row in df.iterrows():
        node_type = str(row.get('TYPE', '')).upper()
        status = str(row.get('STATUS', '')).upper()
        name = str(row.get('STORE_NAME', 'Unknown'))
        
        # Uniform default size and base color
        radius = 6 
        fill_color = "#90ee90" 
        
        # Apply Matrix Logic (COLORS ONLY)
        if 'DC' in node_type or 'DISTRIBUTION' in node_type:
            fill_color = "#6a0dad" # DC Purple
        elif 'HUB' in node_type:
            if 'CLOS' in status:
                fill_color = "#8b0000" # Closing Hub
            elif 'BUBBLE' in status:
                fill_color = "#00008b" # Bubble Hub
            else:
                fill_color = "#006400" # Open Hub
        else: # Standard Store
            if 'CLOS' in status:
                fill_color = "#ff7f7f" # Closing Store
            elif 'BUBBLE' in status:
                fill_color = "#add8e6" # Bubble Store
            else:
                fill_color = "#90ee90" # Open Store
        
        # Override with user requested styles here if applicable
        
        if pd.notna(row.get('LAT')) and pd.notna(row.get('LONG')):
            folium.CircleMarker(
                location=[row['LAT'], row['LONG']],
                radius=radius,
                color="white",
                weight=1,
                fill_color=fill_color,
                fill_opacity=0.9,
                popup=folium.Popup(build_popup_html(row), max_width=300)
            ).add_to(custom_map)
            
    # --- LEGEND BUILDER ---
    # 1. Build the styled inner rows
    legend_html_items = ""
    for label, color in legend_dict.items():
        legend_html_items += f'<div style="display: flex; align-items: center; margin-bottom: 6px;"><span style="background-color: {color}; border-radius: 50%; width: 12px; height: 12px; display: inline-block; margin-right: 8px; border: 1px solid #cbd5e1; flex-shrink: 0;"></span><span style="color: #0f172a !important; font-size: 13px; font-family: system-ui, sans-serif; font-weight: 600;">{label}</span></div>'
    
    # 2. Combine into the final HTML string
    full_legend_html = f'''
    <div style="background-color: #ffffff !important; color: #0f172a !important; padding: 12px 16px; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.18); border: 1px solid #e2e8f0; min-width: 130px;">
        <h4 style="margin: 0 0 10px 0; font-weight: 700; font-size: 14px; color: #0f172a !important; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; font-family: system-ui, sans-serif;">Map Legend</h4>
        {legend_html_items}
    </div>
    '''
    
    legend_template = '''
    {% macro script(this, kwargs) %}
    var legend = L.control({position: 'bottomleft'});
    legend.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'info legend');
        div.innerHTML = __LEGEND_PAYLOAD__;
        L.DomEvent.disableClickPropagation(div);
        return div;
    };
    legend.addTo({{ this._parent.get_name() }});
    {% endmacro %}
    '''
    legend_macro = MacroElement()
    legend_macro._template = Template(legend_template.replace("__LEGEND_PAYLOAD__", json.dumps(full_legend_html)))
    custom_map.add_child(legend_macro)


    # --- TITLE BOX BUILDER ---
    map_blurb = "West Marine: Full Store Network" # AI will dynamically update this
    
    blurb_html = f'''
    <div style="background-color: #ffffff !important; color: #0f172a !important; padding: 12px 16px; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.18); border: 1px solid #e2e8f0; max-width: 350px;">
        <h4 style="margin: 0; font-weight: 700; font-size: 14px; color: #0f172a !important; font-family: system-ui, sans-serif;">{map_blurb}</h4>
    </div>
    '''
    
    title_template = '''
    {% macro script(this, kwargs) %}
    var titleControl = L.control({position: 'topright'});
    titleControl.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'info title');
        div.innerHTML = __BLURB_PAYLOAD__;
        L.DomEvent.disableClickPropagation(div);
        return div;
    };
    titleControl.addTo({{ this._parent.get_name() }});
    {% endmacro %}
    '''
    title_macro = MacroElement()
    title_macro._template = Template(title_template.replace("__BLURB_PAYLOAD__", json.dumps(blurb_html)))
    custom_map.add_child(title_macro)

    Fullscreen().add_to(custom_map)
    return custom_map

Never assume the helper function already exists. You must write it out completely every single time you generate code.
"""

# ==========================================
# 4. THE SPLIT DASHBOARD
# ==========================================
left_panel, right_panel = st.columns([1, 3])

# --- LEFT PANEL: The Chat UI ---
with left_panel:
    st.markdown("#### 🤖 AI Map Coder")

    ctrl_col1, ctrl_col2 = st.columns(2)
    with ctrl_col1:
        if st.button("Undo Last Request", use_container_width=True, disabled=len(st.session_state.code_history) == 0):
            st.session_state.last_code = st.session_state.code_history.pop()
            if len(st.session_state.chat_history) >= 2:
                st.session_state.chat_history = st.session_state.chat_history[:-2]
            st.rerun()
            
    with ctrl_col2:
        if st.button("Reset Map", use_container_width=True):
            st.session_state.code_history.clear()
            st.session_state.chat_history.clear()
            st.session_state.last_code = baseline_code.strip()
            st.session_state.filtered_df = None
            st.rerun()
            
    st.markdown("---")
    
    map_style = st.selectbox(
        "Map Style", 
        ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"], 
        key="map_style_selector"
    )

    # HOTFIX 4: Native Streamlit chat_input with CSS hack un-pinning it from the bottom
    prompt_input = st.chat_input('Ask the AI to update the map...')
    if prompt_input:
        st.session_state.active_prompt = prompt_input

    chat_container = st.container(height=950, border=True)

    # HOTFIX 3: Reverse Chat History (Newest on top) and Handle Active Processing
    with chat_container:
        if st.session_state.active_prompt:
            user_prompt = st.session_state.active_prompt
            
            # 1. Create a placeholder at the top for the active assistant processing
            assistant_placeholder = st.empty()
            
            # 2. Render the user's new prompt right below the placeholder
            with st.chat_message("user"):
                st.markdown(user_prompt)
            
            # 3. Render previous history below the active interaction
            for msg in reversed(st.session_state.chat_history):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            
            # 4. Process the API logic inside the top placeholder
            with assistant_placeholder.container():
                with st.chat_message("assistant"):
                    with st.spinner("Writing and testing code..."):
                        try:
                            # Context uses the original chronological list order
                            history_transcript = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.chat_history[-6:]])
                            data_dictionary = get_dataframe_summary(df)
                            
                            mega_prompt = f"""
                            User Request: {user_prompt}

                            --- DATA DICTIONARY ---
                            {data_dictionary}
                            
                            --- RECENT CHAT HISTORY ---
                            {history_transcript}
                            
                            --- CURRENT PYTHON CODE ---
                            {st.session_state.last_code}
                            
                            --- INSTRUCTION ---
                            Here is the current Python code powering the map. Modify this existing code to fulfill the user's newest request. 
                            Only output the full, revised executable code for generate_custom_map(df).
                            """
                            
                            max_retries = 3
                            retry_delay = 2
                            
                            for attempt in range(max_retries):
                                try:
                                    response = client.models.generate_content(
                                        model='gemini-3.1-flash-lite',
                                        contents=mega_prompt,
                                        config=types.GenerateContentConfig(
                                            system_instruction=system_instruction
                                        )
                                    )
                                    break 
                                except Exception as e:
                                    error_msg = str(e).lower()
                                    if any(keyword in error_msg for keyword in ["busy", "exhausted", "quota", "503", "429", "overloaded"]):
                                        if attempt < max_retries - 1:
                                            st.warning(f"AI server is busy. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                                            time.sleep(retry_delay)
                                            retry_delay *= 2 
                                        else:
                                            raise Exception("The AI server is currently overloaded. Please try again in a few minutes.")
                                    else:
                                        raise Exception(f"An unexpected API error occurred: {e}")
                            
                            raw_code = response.text.strip()
                            
                            md_fence = "`" * 3
                            if raw_code.startswith(md_fence + "python"):
                                raw_code = raw_code[9:]
                            elif raw_code.startswith(md_fence):
                                raw_code = raw_code[3:]
                            if raw_code.endswith(md_fence):
                                raw_code = raw_code[:-3]
                                
                            new_code_candidate = raw_code.strip()
                            
                            test_namespace = {}
                            exec(new_code_candidate, globals(), test_namespace)
                            
                            if 'generate_custom_map' not in test_namespace:
                                raise ValueError("The AI failed to define the 'generate_custom_map(df)' function.")
                            
                            test_map = test_namespace['generate_custom_map'](df)
                            
                            st.session_state.code_history.append(st.session_state.last_code)
                            st.session_state.last_code = new_code_candidate
                            
                            success_msg = "Map updated successfully!"
                            
                            # Append to actual chronological history list
                            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
                            st.session_state.chat_history.append({"role": "assistant", "content": success_msg})
                            
                            st.session_state.active_prompt = None
                            st.rerun()
                            
                        except Exception as e:
                            error_msg = f"Failed to execute AI code. Error: {e}\n\n*Falling back to previous map.*"
                            st.error(error_msg)
                            
                            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
                            st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
                            
                            st.session_state.active_prompt = None
                            time.sleep(1.5)
                            st.rerun()
        else:
            # If no active prompt, just render history reversed
            for msg in reversed(st.session_state.chat_history):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

# --- RIGHT PANEL: Map & Code Output ---
with right_panel:
    execution_namespace = {}
    try:
        exec(st.session_state.last_code, globals(), execution_namespace)
        active_map = execution_namespace['generate_custom_map'](df)
        
        st_folium(active_map, use_container_width=True, height=700)
        
        map_html = active_map.get_root().render()

        st.download_button(
            label="📥 Download Interactive Map (HTML)",
            data=map_html,
            file_name="West_Marine_Strategy_Map.html",
            mime="text/html"
        )
    except Exception as e:
        st.error(f"Critical error rendering map: {e}")
        
    with st.expander("View Active Python Code", expanded=False):
        st.code(st.session_state.last_code, language="python")

    if st.session_state.filtered_df is not None and not st.session_state.filtered_df.empty:
        st.markdown("### 📊 Extracted Data")
        st.dataframe(st.session_state.filtered_df, use_container_width=True)