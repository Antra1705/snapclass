import streamlit as st

def footer_home():
    logo_url="https://i.bb.co/YTYGn5qV/logo.png"
    st.markdown("""
                <div style="display: flex;items-align: center; justify-content: center; gap:6px; margin-top: 2rem;">
                    <p style="font-weight:bold; color:white;"> Created with ❤️ by Antra</>
                </div>
    """, unsafe_allow_html=True)

def footer_dashboard():
    logo_url="https://i.bb.co/YTYGn5qV/logo.png"
    st.markdown("""
                <div style="display: flex;items-align: center; justify-content: center; gap:6px; margin-top: 2rem;">
                    <p style="font-weight:bold; color:black;"> Created with ❤️ by Antra</>
                </div>
    """, unsafe_allow_html=True)