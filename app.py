import streamlit as st
import time
from jamaibase import JamAI, protocol as p

# --- 1. 页面配置 ---
st.set_page_config(page_title="AERN - AI Emergency Response", page_icon="🚨", layout="wide")

# --- 2. 样式优化 ---
st.markdown("""<style>.stButton>button {height: 3em; width: 100%; border-radius: 10px; font-weight: bold; font-size: 20px;} .stChatMessage {border-radius: 15px; padding: 10px;}</style>""", unsafe_allow_html=True)

# --- 3. 配置区 (自动连接 JamAI) ---
with st.expander("🛠️ Developer Configuration", expanded=True):
    col1, col2, col3 = st.columns(3)
    # 这里你可以填入默认值，这样就不用每次刷新页面都重填了
    jamai_api_key = col1.text_input("1. JamAI API Key", type="password", value="") 
    project_id = col2.text_input("2. Project ID", value="")
    table_id = col3.text_input("3. Knowledge Table ID", value="emergency-guide")

# --- 核心函数：真的去问 JamAI ---
def ask_jamai(user_text, api_key, proj_id, table_id):
    try:
        # 初始化连接
        jamai = JamAI(token=api_key, project_id=proj_id)
        
        # 发送请求 (RAG 模式 - 让它查资料回答)
        # 注意：这里假设你在 JamAI 建了一个叫 'action' 的 Action Table 或者 Knowledge Table
        # 这里的 "action" 是表格类型，如果报错，请检查你在 JamAI 网页上创建的表格类型
        response = jamai.table.add_table_rows(
            "action", 
            p.RowAddRequest(
                table_id=table_id, 
                data=[{"User": user_text}], # ⚠️ 注意：确保你的 JamAI 表格里输入列的名字叫 "User"
                stream=False
            )
        )
        
        # 提取回答 (假设输出列叫 'AI'，如果你的输出列叫 'Output'，请在这里修改)
        if response.rows:
            return response.rows[0].columns["AI"].text 
        return "Error: No response from JamAI."

    except Exception as e:
        return f"⚠️ Connection Error: {str(e)}"

# --- 4. 状态管理 ---
if "messages" not in st.session_state: st.session_state.messages = []

# --- 5. 侧边栏 (地图) ---
with st.sidebar:
    st.header("📍 Current Status")
    # 这是一个示例地图链接，你可以换成真的
    st.image("https://maps.googleapis.com/maps/api/staticmap?center=Kamunting&zoom=13&size=400x400&maptype=roadmap&markers=color:red%7Clabel:S%7CKamunting", caption="Nearby Safe Zones")

# --- 6. 主界面 ---
st.title("🚨 AERN: Emergency Response Navigator")
tab1, tab2 = st.tabs(["🔥 PANIC MODE", "💬 AI Assistant"])

# TAB 1: 恐慌模式 (简化版)
with tab1:
    st.write("### Quick Actions")
    if st.button("🌊 FLOOD (水灾)"):
        st.error("⚠️ FLOOD ALERT! 1. Turn off power. 2. Move to high ground.")
    if st.button("🔥 FIRE (火灾)"):
        st.error("⚠️ FIRE ALERT! 1. Crawl low under smoke. 2. Find exit immediately.")

# TAB 2: 真 AI 对话
with tab2:
    # 显示聊天历史
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # 处理用户输入
    if prompt := st.chat_input("Apa jadi? Type here..."):
        # 1. 显示用户的话
        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 2. 调用 JamAI
        with st.chat_message("assistant"):
            if jamai_api_key and project_id:
                with st.spinner("Connecting to HQ..."):
                    reply = ask_jamai(prompt, jamai_api_key, project_id, table_id)
                    st.write(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
            else:
                st.warning("Please enter JamAI API Key & Project ID in the settings above!")