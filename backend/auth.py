from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from database import get_db
import secrets
import string
from typing import Optional
from config import Config

SECRET_KEY = Config.SECRET_KEY
ALGORITHME = "HS256"
DUREE_TOKEN = timedelta(days=1)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/connexion", auto_error=False)

def verifier_code(plain_code: str, hashed_code: str) -> bool:
    return pwd_context.verify(plain_code, hashed_code)

def hacher_code(plain_code: str) -> str:
    return pwd_context.hash(plain_code)

def generer_code_aleatoire(longueur: int = 7) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ''.join(secrets.choice(alphabet) for _ in range(longueur))

def creer_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + DUREE_TOKEN
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHME)

def decoder_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHME])
        return payload
    except JWTError:
        return None

async def obtenir_utilisateur_courant(token: str = Depends(oauth2_scheme)):
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant")
    payload = decoder_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Identifiant manquant")
    db = get_db()
    try:
        response = db.table("users").select("*").eq("id", int(user_id)).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur base : {str(e)}")
    if not response.data:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    user = response.data[0]
    if not user.get("est_actif"):
        raise HTTPException(status_code=403, detail="Compte désactivé")
    return user

async def obtenir_chef_courant(user = Depends(obtenir_utilisateur_courant)):
    if user.get("role") != "chef":
        raise HTTPException(status_code=403, detail="Seul un chef peut effectuer cette action.")
    return user

# --- NOUVEAU : Chef officiel uniquement ---
async def obtenir_chef_officiel_courant(user = Depends(obtenir_utilisateur_courant)):
    if user.get("role") != "chef":
        raise HTTPException(status_code=403, detail="Seul un chef peut effectuer cette action.")
    if not user.get("est_officiel"):
        raise HTTPException(status_code=403, detail="Seul le chef officiel peut effectuer cette action.")
    return user