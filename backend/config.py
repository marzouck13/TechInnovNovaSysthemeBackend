import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SECRET_KEY = os.getenv("SECRET_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(" Les variables SUPABASE_URL et SUPABASE_KEY doivent être définies dans le fichier .env")
    
    if not SECRET_KEY or len(SECRET_KEY) < 32:
        print(" Attention : SECRET_KEY est trop courte. Utilisez une clé d'au moins 32 caractères en production.")

        