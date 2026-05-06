import streamlit as st

_CSS = """
<style>
body { background-color: #0d1117; }
.stApp { background-color: #0d1117; color: #c9d1d9; }
.stButton>button { background-color: #238636; color: white; border: none; }
.stButton>button:hover { background-color: #2ea043; }
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
