from typing import List

import streamlit as st


def render_file_list(files: List[str], max_display: int = 50) -> None:
    with st.expander("📋 Files to be scanned", expanded=True):
        for f in files[:max_display]:
            st.code(str(f), language=None)
        if len(files) > max_display:
            st.caption(f"... and {len(files) - max_display} more files")
