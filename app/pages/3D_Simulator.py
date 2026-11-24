from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="3D Flood Simulator", layout="wide")
st.title("3D GLOF flood simulator")
st.caption("Click inside the scene first, then press Space to trigger the outburst. "
           "Illustrative simulation, not a hydrodynamic model.")

base = Path(__file__).resolve().parents[2] / "3d"
html = (base / "index.html").read_text()
js = (base / "scene.js").read_text()
# standalone mode: the scene has no backend inside Streamlit
js = js.replace('const r = await fetch("/lakes");',
                'if (window.GLOF_STANDALONE) throw new Error("standalone");\n    const r = await fetch("/lakes");')
html = html.replace('<script src="scene.js"></script>',
                    "<script>window.GLOF_STANDALONE = true;</script>\n<script>" + js + "</script>")
components.html(html, height=760, scrolling=False)