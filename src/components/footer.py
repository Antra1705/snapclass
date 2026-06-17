import streamlit as st

def footer_home():
    st.markdown(
        '<div style="display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 2rem;">'
        '<p style="font-weight: bold; color: white;">Created with ❤️ by Antra</p>'
        '</div>',
        unsafe_allow_html=True
    )

def footer_dashboard():
    st.markdown(
        '<div style="display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 2rem;">'
        '<p style="font-weight: bold; color: black;">Created with ❤️ by Antra</p>'
        '</div>',
        unsafe_allow_html=True
    )