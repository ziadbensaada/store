from models import users_collection, create_user
import os

def reset_admin():
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    # Delete existing admin user if exists
    users_collection.delete_one({"username": admin_username})
    print(f"Deleted existing admin user: {admin_username}")
    
    # Create new admin user
    user_id, error = create_user(
        username=admin_username,
        email=admin_email,
        password=admin_password,
        role='admin'
    )
    
    if user_id:
        print(f"Admin user created successfully with username: {admin_username}")
        print(f"Password: {admin_password}")
    else:
        print(f"Failed to create admin user: {error}")

if __name__ == "__main__":
    reset_admin()
