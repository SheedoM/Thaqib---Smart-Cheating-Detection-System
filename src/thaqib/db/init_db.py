import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.resolve()))

from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.db.models.users import User
from src.thaqib.core.security import get_password_hash
from getpass import getpass

def init_first_installation():
    db = SessionLocal()
    
    # Check if any institution exists
    if db.query(Institution).count() > 0:
        print("Database is already initialized.")
        db.close()
        return
    
    print("--- First Installation Setup ---")
    inst_name = input("Institution Name: ")
    inst_code = input("Institution Code (e.g., UNI): ")
    contact_email = input("Contact Email: ")
    logo_url = input("Logo URL (Optional): ")
    
    admin_user = input("Admin Username: ")
    admin_pwd = getpass("Admin Password: ")
    admin_name = input("Admin Full Name: ")
    admin_email = input("Admin Email: ")
    
    # Create Institution
    inst = Institution(
        name=inst_name,
        code=inst_code,
        contact_email=contact_email,
        logo_url=logo_url if logo_url else None
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    
    # Create Admin
    hashed_pwd = get_password_hash(admin_pwd)
        
    admin = User(
        institution_id=inst.id,
        username=admin_user,
        password_hash=hashed_pwd, 
        full_name=admin_name,
        email=admin_email,
        role="admin"
    )
    db.add(admin)
    db.commit()
    
    print(f"First installation completed! Institution {inst_name} and Admin {admin_user} created successfully.")
    db.close()

if __name__ == "__main__":
    init_first_installation()
