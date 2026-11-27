import getpass
import re
import sys

from backend.core.auth import init_db, create_user

init_db()

username = input("Administrator login: ").strip()

if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,32}", username):
    sys.exit("Login 3-32 belgidan iborat bo'lsin.")

password = getpass.getpass("Yangi kuchli parol: ")
confirm = getpass.getpass("Parolni takrorlang: ")

if password != confirm:
    sys.exit("Parollar mos kelmadi.")

if len(password) < 14:
    sys.exit("Parol kamida 14 belgidan iborat bo'lishi kerak.")

try:
    create_user(username, password)
except Exception as exc:
    if "UNIQUE constraint failed" in str(exc):
        sys.exit("Bu login allaqachon mavjud.")
    raise

print("Administrator hisobi yaratildi.")
