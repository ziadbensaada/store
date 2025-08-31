import streamlit as st
from models import verify_user, create_user, get_user, AVAILABLE_DOMAINS
from datetime import datetime

def show_login_form():
    """Display login form and handle authentication."""
    st.title("Login")
    
    with st.form("login_form"):
        username = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
    
    if submit_button:
        if not username or not password:
            st.error("Please enter both username and password")
            return None
            
        user = verify_user(username, password)
        if user:
            # Update last login time
            st.session_state['user'] = user
            st.session_state['authenticated'] = True
            st.session_state['last_login'] = datetime.now().isoformat()
            st.rerun()
            return user
        else:
            st.error("Invalid username or password")
            return None
    
    return None

def show_register_form():
    """Display the registration form with domain interests selection."""
    with st.form("register_form"):
        st.subheader("Create a New Account")
        
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        # Add domain interests selection
        st.subheader("Select Your Interests")
        st.write("Choose at least one domain you're interested in:")
        
        # Create two columns for better layout
        col1, col2 = st.columns(2)
        
        # Get available domains from models
        from models import AVAILABLE_DOMAINS
        
        # Split domains into two columns
        half = len(AVAILABLE_DOMAINS) // 2
        interests = []
        
        with col1:
            for domain in AVAILABLE_DOMAINS[:half]:
                if st.checkbox(domain, key=f"int_{domain}"):
                    interests.append(domain)
                    
        with col2:
            for domain in AVAILABLE_DOMAINS[half:]:
                if st.checkbox(domain, key=f"int_{domain}"):
                    interests.append(domain)
        
        if st.form_submit_button("Register"):
            if not all([username, email, password, confirm_password]):
                st.error("All fields are required!")
                return False
                
            if password != confirm_password:
                st.error("Passwords do not match!")
                return False
                
            if len(password) < 8:
                st.error("Password must be at least 8 characters long!")
                return False
                
            if not interests:
                st.error("Please select at least one area of interest")
                return False
            
            # Create the user with interests
            user_id, error = create_user(
                username=username,
                email=email,
                password=password,
                interests=interests
            )
            
            if user_id:
                st.success("Registration successful! Please log in.")
                return True
            else:
                st.error(f"Registration failed: {error}")
                return False
    return False

def show_logout_button():
    """Display logout button and handle logout."""
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

def check_authentication():
    """Check if user is authenticated."""
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
        st.session_state['user'] = None
    
    return st.session_state['authenticated']

def get_current_user():
    """Get the current authenticated user."""
    return st.session_state.get('user')

def require_login():
    """Redirect to login if user is not authenticated."""
    if not check_authentication():
        st.warning("Please log in to access this page.")
        if show_login_form() is not None:
            st.rerun()
        st.stop()
    
    return get_current_user()

def require_admin():
    """Require admin privileges."""
    user = require_login()
    if user.get('role') != 'admin':
        st.error("You don't have permission to access this page.")
        st.stop()
    return user
