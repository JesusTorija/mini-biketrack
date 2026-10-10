import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

def init_firebase():
    """Inicializa la app de Firebase de forma segura."""
    if not firebase_admin._apps:
        # Puedes guardar tu archivo JSON de credenciales de Firebase en la raíz
        cred_path = "firebase_credentials.json"
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            # Si usas variables de entorno en el servidor de despliegue (ej. Render/HuggingFace)
            # También se puede inicializar mediante un secret de Streamlit.
            if "firebase" in st.secrets:
                secret_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(secret_dict)
                firebase_admin.initialize_app(cred)

def get_firestore_db():
    """Retorna la instancia de Firestore si Firebase está inicializado."""
    try:
        return firestore.client()
    except Exception:
        return None

def init_firebase_auth():
    """Gestiona el estado de sesión del usuario en Streamlit."""
    init_firebase()
    if "user" not in st.session_state:
        st.session_state["user"] = None

def render_auth_sidebar():
    """Renderiza el panel de inicio de sesión en la barra lateral."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔐 Cuenta de Usuario")
    
    db = get_firestore_db()
    
    if st.session_state["user"] is None:
        st.sidebar.markdown("Inicia sesión para guardar tu perfil físico y rutas favoritas en la nube.")
        
        # Campo de simulación o formulario de login por email/contraseña o Google Auth
        with st.sidebar.form("login_form"):
            email_input = st.text_input("Correo electrónico")
            pass_input = st.text_input("Contraseña", type="password")
            login_submitted = st.form_submit_button("🔑 Iniciar Sesión")
            
            if login_submitted:
                # Lógica básica de validación o conexión con Firebase Auth
                if email_input:
                    st.session_state["user"] = {
                        "email": email_input,
                        "name": email_input.split("@")[0].capitalize()
                    }
                    st.sidebar.success(f"¡Bienvenido, {st.session_state['user']['name']}!")
                    st.rerun()
                else:
                    st.error("Introduce un correo válido.")
    else:
        user = st.session_state["user"]
        st.sidebar.success(f"Conectado como:\n**{user['name']}**")
        
        if db:
            # Ejemplo de guardado de perfil en Firestore
            if st.sidebar.button("💾 Guardar configuración en la nube"):
                try:
                    user_ref = db.collection("users").document(user["email"])
                    user_ref.set({"last_active": firestore.SERVER_TIMESTAMP}, merge=True)
                    st.sidebar.success("¡Perfil guardado en Firestore!")
                except Exception as e:
                    st.sidebar.error(f"Error al guardar: {e}")

        if st.sidebar.button("🚪 Cerrar sesión"):
            st.session_state["user"] = None
            st.rerun()