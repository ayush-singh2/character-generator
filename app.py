import os
import base64
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

st.set_page_config(page_title="Flux Image Generator", layout="wide")

st.title("🎨 Flux Image Generator")

prompt = st.text_area(
    "Enter your prompt",
    height=150,
    placeholder="A futuristic city at sunset..."
)

if st.button("Generate", use_container_width=True):

    if not prompt.strip():
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Generating image..."):

            response = requests.post(
                "https://openrouter.ai/api/v1/images",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "black-forest-labs/flux.2-max",
                    "prompt": prompt
                }
            )

            if response.status_code != 200:
                st.error(f"API Error ({response.status_code})")
                st.json(response.json())
            else:
                result = response.json()

                if "data" in result:
                    image = base64.b64decode(result["data"][0]["b64_json"])

                    # Replace previous image
                    st.session_state["image"] = image
                else:
                    st.error("No image returned.")
                    st.json(result)

if "image" in st.session_state:
    st.image(
        st.session_state["image"],
        caption="Generated Image",
        use_container_width=True
    )