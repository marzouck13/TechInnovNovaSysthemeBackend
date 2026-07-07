from supabase import create_client, Client
from config import Config

class BaseDeDonnees:
    _instance: Client = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._instance is None:
            cls._instance = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
            print("Connexion à Supabase établie avec succès.")
        return cls._instance

def get_db():
    return BaseDeDonnees.get_client()


