import streamlit as st
import requests

MCP_ENDPOINT = "http://localhost:3333/tools/query_enterprise_pdf"

st.set_page_config(
    page_title="Enterprise RAG Assistant",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Enterprise RAG Assistant")
st.caption("Multimodal PDF Intelligence | Local LLM | Secure")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input
query = st.chat_input("Ask a question about your PDFs...")

if query:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # Call MCP server
    payload = {
        "query": query,
        "top_k": 5
    }

    with st.chat_message("assistant"):
        with st.spinner("Analyzing documents..."):
            response = requests.post(MCP_ENDPOINT, json=payload, timeout=120)

            if response.status_code != 200:
                st.error("Failed to get response from backend.")
            else:
                data = response.json()

                docs = data.get("documents", [])

                if ( len(docs) == 1 and "I don’t know based on the provided documents" in docs[0]):
                    st.warning(docs[0])
                else:
                    st.markdown("\n\n".join(docs))

                if data.get("important_info_detected"):
                    answer = "⚠ **Important Information Detected**\n\n" + answer

                if data.get("images_present"):
                    answer += "\n\n🖼 **Images detected in source PDFs**"

                st.markdown(answer)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })
