from __future__ import annotations

from datetime import datetime

import httpx
import streamlit as st


st.set_page_config(page_title="BOT GPT UI", page_icon="🤖", layout="wide")


def _error_text(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"]
            return f"{err.get('code', 'ERROR')}: {err.get('message', 'Unknown error')}"
        return str(payload)
    except Exception:
        return resp.text


def api_request(
    method: str,
    path: str,
    base_url: str,
    *,
    json_payload: dict | None = None,
    form_payload: dict | None = None,
    files_payload: dict | None = None,
    params: dict | None = None,
) -> tuple[bool, dict | list | None, str | None]:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.request(
                method=method,
                url=url,
                json=json_payload,
                data=form_payload,
                files=files_payload,
                params=params,
            )
        if response.status_code >= 400:
            return False, None, _error_text(response)
        if response.content:
            return True, response.json(), None
        return True, None, None
    except Exception as exc:
        return False, None, str(exc)


def format_ts(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return value


def fetch_conversations(base_url: str, user_id: str, page: int, page_size: int) -> list[dict]:
    ok, data, err = api_request(
        "GET",
        "/conversations",
        base_url,
        params={"user_id": user_id, "page": page, "page_size": page_size},
    )
    if not ok:
        st.error(err or "Failed to load conversations.")
        return []
    return data if isinstance(data, list) else []


def fetch_users(base_url: str, page: int = 1, page_size: int = 100) -> list[dict]:
    ok, data, err = api_request("GET", "/users", base_url, params={"page": page, "page_size": page_size})
    if not ok:
        st.error(err or "Failed to load users.")
        return []
    return data if isinstance(data, list) else []


def resolve_user_id_by_email(base_url: str, email: str) -> str | None:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return None

    users = fetch_users(base_url=base_url, page=1, page_size=100)
    for user in users:
        if str(user.get("email", "")).strip().lower() == normalized_email:
            return str(user.get("id", ""))
    return None


st.title("BOT GPT")
st.caption("Simple console with clear sections and sidebar chat selection.")

if "selected_conversation_id" not in st.session_state:
    st.session_state.selected_conversation_id = ""
if "last_email" not in st.session_state:
    st.session_state.last_email = ""

backend_url = st.text_input("Backend URL", value="http://127.0.0.1:8000")
email = st.text_input("Email", value=st.session_state.last_email)

if email != st.session_state.last_email:
    st.session_state.last_email = email
    st.session_state.selected_conversation_id = ""

user_id = resolve_user_id_by_email(backend_url, email)

conversations: list[dict] = []
if user_id:
    conversations = fetch_conversations(backend_url, user_id, 1, 100)

with st.sidebar:
    st.header("User")
    if st.button("Create User From Email", use_container_width=True):
        if not email.strip():
            st.warning("Enter an email first.")
        else:
            ok, data, err = api_request("POST", "/users", backend_url, json_payload={"email": email.strip()})
            if ok:
                st.success(f"User ready: {data['id']}")
                st.rerun()
            else:
                st.error(err or "Failed to create user.")

    if email.strip() and user_id:
        st.caption(f"Using: {email}")
    elif email.strip():
        st.caption("No user found for this email. Create one.")
    else:
        st.caption("Enter email to continue.")

    st.divider()
    st.header("Conversation")
    if not user_id:
        st.caption("Set a valid email first.")
    else:
        mode = st.selectbox("Mode", ["OPEN", "RAG"], index=0, key="sidebar_mode")
        if st.button("New Conversation", use_container_width=True):
            ok, data, err = api_request(
                "POST",
                "/conversations",
                backend_url,
                json_payload={"user_id": user_id, "mode": mode},
            )
            if ok:
                st.session_state.selected_conversation_id = data["id"]
                st.rerun()
            else:
                st.error(err or "Failed to create conversation.")

        if conversations:
            labels_to_id = {
                f"{c.get('mode')} • {format_ts(c.get('updated_at')) or c.get('id')}": c.get("id") for c in conversations
            }
            options = list(labels_to_id.keys())
            if st.session_state.selected_conversation_id not in labels_to_id.values():
                st.session_state.selected_conversation_id = next(iter(labels_to_id.values()), "")

            selected_index = 0
            for idx, label in enumerate(options):
                if labels_to_id[label] == st.session_state.selected_conversation_id:
                    selected_index = idx
                    break

            selected_label = st.radio("Select chat", options=options, index=selected_index)
            st.session_state.selected_conversation_id = labels_to_id[selected_label]

            selected_id_to_delete = st.session_state.selected_conversation_id
            if st.button("Delete Selected Conversation", use_container_width=True):
                if not selected_id_to_delete:
                    st.warning("Select a conversation first.")
                else:
                    ok, _, err = api_request("DELETE", f"/conversations/{selected_id_to_delete}", backend_url)
                    if ok:
                        st.session_state.selected_conversation_id = ""
                        st.rerun()
                    else:
                        st.error(err or "Failed to delete conversation.")
        else:
            st.caption("No conversations yet.")

    if st.button("Refresh Conversations", use_container_width=True):
        st.rerun()

chat_tab, docs_tab = st.tabs(["Chat", "Documents"])

with chat_tab:
    selected_conversation_id = st.session_state.selected_conversation_id
    if not email.strip():
        st.info("Enter your email to access conversations.")
    elif not user_id:
        st.warning("No user exists for this email. Create one from the sidebar.")
    elif not selected_conversation_id:
        st.info("Create/select a conversation from the sidebar.")
    else:
        ok, detail, err = api_request("GET", f"/conversations/{selected_conversation_id}", backend_url)
        if not ok:
            if err and "Invalid conversation ID" in err:
                st.session_state.selected_conversation_id = ""
                st.warning("Selected conversation is no longer available. Refreshed the list.")
                st.rerun()
            st.error(err or "Failed to fetch conversation details.")
        else:
            for message in detail.get("messages", []):
                role = message.get("role", "assistant")
                with st.chat_message("assistant" if role == "assistant" else "user"):
                    st.markdown(message.get("content", ""))

            prompt = st.chat_input("Type a message")
            if prompt:
                ok, _, err = api_request(
                    "POST",
                    f"/conversations/{selected_conversation_id}/messages",
                    backend_url,
                    json_payload={"content": prompt},
                )
                if not ok:
                    st.error(err or "Failed to send message.")
                else:
                    st.rerun()

with docs_tab:
    st.subheader("Upload Document")
    doc_title = st.text_input("Title (optional)", value="")
    uploaded_file = st.file_uploader("Select document", type=["pdf", "docx", "txt", "md", "csv", "json"])

    if st.button("Upload Document"):
        if not email.strip():
            st.warning("Enter an email first.")
        elif not user_id:
            st.warning("No user exists for this email. Create one from the sidebar first.")
        elif not uploaded_file:
            st.warning("Please choose a file to upload.")
        else:
            file_name = uploaded_file.name
            file_bytes = uploaded_file.getvalue()
            file_content_type = uploaded_file.type or "application/octet-stream"

            ok, data, err = api_request(
                "POST",
                "/documents/upload-file",
                backend_url,
                form_payload={
                    "user_id": user_id,
                    "title": doc_title,
                },
                files_payload={
                    "file": (file_name, file_bytes, file_content_type),
                },
            )
            if ok:
                st.success(f"Uploaded document {data['id']} with {data['chunk_count']} chunks.")
            else:
                st.error(err or "Upload failed.")
