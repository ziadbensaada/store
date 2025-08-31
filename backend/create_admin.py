from models import users_collection, create_user

# Remove any existing admin user
users_collection.delete_many({"$or": [
    {"username": "admin"},
    {"email": "admin@example.com"}
]})
print("Removed any existing admin users")

# Create a new admin user
username = "admin"
email = "admin@example.com"
password = "admin123"  # You should change this after first login

print(f"Creating admin user with username: {username} and password: {password}")
user_id, error = create_user(username, email, password, role='admin')

if user_id:
    print(f"Successfully created admin user with ID: {user_id}")
    print(f"Username: {username}")
    print(f"Password: {password}")
    print("\nIMPORTANT: Please change this password after logging in!")
    print("\nYou can now log in with these credentials.")
else:
    print(f"Error creating admin user: {error}")
