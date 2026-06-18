"""
Utility Helper Functions for Autonomous Data Analysis Agent Backend.

This module houses general infrastructure-related helpers, mock datasets,
database connection error parser, and local file storage caching path handlers.
"""

import os
import shutil
import re
import io
import httpx
import pandas as pd
from fastapi import HTTPException
from .config import settings
from .database import db_service

# Define and ensure cached data directories exist
TEMP_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../temp_datasets"))
os.makedirs(TEMP_DATA_DIR, exist_ok=True)

def get_local_dataset_path(session_id: str, file_name: str) -> str:
    """Helper to determine the local cached path for a session's dataset.
    
    Extracts the base session ID (ignoring thread ID extensions) and resolves 
    the absolute path inside the local temporary directory.
    """
    base_id = session_id.split(":")[0]
    ext = os.path.splitext(file_name)[-1]
    return os.path.join(TEMP_DATA_DIR, f"{base_id}_dataset{ext}")

def download_dataset_if_missing(s3_path: str, local_path: str):
    """Downloads dataset from Supabase Storage if local cache is missing.
    
    If the server is running in local fallback mock mode (no Supabase client keys),
    it will attempt to copy the file directly from the local_storage folder.
    Otherwise, it generates a signed storage URL and streams the file over HTTP.
    """
    # If the file is already cached locally, skip downloading
    if os.path.exists(local_path):
        return
        
    if not db_service.client:
        # Local mock mode fallback: copy file directly from local storage path to avoid self-request deadlock
        local_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../local_storage/datasets"))
        src_path = os.path.join(local_storage_dir, s3_path)
        if os.path.exists(src_path):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            shutil.copy(src_path, local_path)
            return
        else:
            raise HTTPException(status_code=404, detail="Dataset file not found in local storage.")
        
    # Generate signed URL to download from Supabase Storage bucket
    signed_url = db_service.generate_signed_url("datasets", s3_path)
    if not signed_url:
        raise HTTPException(status_code=404, detail="Dataset file not found in storage.")
        
    # Stream download the file bytes
    with httpx.Client() as client:
        response = client.get(signed_url)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch dataset from storage.")
        with open(local_path, "wb") as f:
            f.write(response.content)

def get_demo_titanic_csv() -> bytes:
    """Generates the static mock Titanic passenger CSV bytes for quick-start demo workspace.
    
    Creates a pre-loaded sample dataset containing survived status, class, age, name, 
    fare, and details of 20 mock passengers for local sandbox execution testing.
    """
    data = [
        {"PassengerId": 1, "Survived": 0, "Pclass": 3, "Name": "Braund, Mr. Owen Harris", "Sex": "male", "Age": 22, "SibSp": 1, "Parch": 0, "Ticket": "A/5 21171", "Fare": 7.25, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 2, "Survived": 1, "Pclass": 1, "Name": "Cumings, Mrs. John Bradley (Florence Briggs Thayer)", "Sex": "female", "Age": 38, "SibSp": 1, "Parch": 0, "Ticket": "PC 17599", "Fare": 71.2833, "Cabin": "C85", "Embarked": "C"},
        {"PassengerId": 3, "Survived": 1, "Pclass": 3, "Name": "Heikkinen, Miss. Laina", "Sex": "female", "Age": 26, "SibSp": 0, "Parch": 0, "Ticket": "STON/O2. 3101282", "Fare": 7.925, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 4, "Survived": 1, "Pclass": 1, "Name": "Futrelle, Mrs. Jacques Heath (Lily May Peel)", "Sex": "female", "Age": 35, "SibSp": 1, "Parch": 0, "Ticket": "113803", "Fare": 53.1, "Cabin": "C123", "Embarked": "S"},
        {"PassengerId": 5, "Survived": 0, "Pclass": 3, "Name": "Allen, Mr. William Henry", "Sex": "male", "Age": 35, "SibSp": 0, "Parch": 0, "Ticket": "373450", "Fare": 8.05, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 6, "Survived": 0, "Pclass": 3, "Name": "Moran, Mr. James", "Sex": "male", "Age": None, "SibSp": 0, "Parch": 0, "Ticket": "330877", "Fare": 8.4583, "Cabin": None, "Embarked": "Q"},
        {"PassengerId": 7, "Survived": 0, "Pclass": 1, "Name": "McCarthy, Mr. Timothy J", "Sex": "male", "Age": 54, "SibSp": 0, "Parch": 0, "Ticket": "17463", "Fare": 51.8625, "Cabin": "E46", "Embarked": "S"},
        {"PassengerId": 8, "Survived": 0, "Pclass": 3, "Name": "Palsson, Master. Gosta Leonard", "Sex": "male", "Age": 2, "SibSp": 3, "Parch": 1, "Ticket": "349909", "Fare": 21.075, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 9, "Survived": 1, "Pclass": 3, "Name": "Johnson, Mrs. Oscar W (Elisabeth Vilhelmina Berg)", "Sex": "female", "Age": 27, "SibSp": 0, "Parch": 2, "Ticket": "347742", "Fare": 11.1333, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 10, "Survived": 1, "Pclass": 2, "Name": "Nasser, Mrs. Nicholas (Adele Achem)", "Sex": "female", "Age": 14, "SibSp": 1, "Parch": 0, "Ticket": "237736", "Fare": 30.0708, "Cabin": None, "Embarked": "C"},
        {"PassengerId": 11, "Survived": 1, "Pclass": 3, "Name": "Sandstrom, Miss. Marguerite Rut", "Sex": "female", "Age": 4, "SibSp": 1, "Parch": 1, "Ticket": "PP 9549", "Fare": 16.7, "Cabin": "G6", "Embarked": "S"},
        {"PassengerId": 12, "Survived": 1, "Pclass": 1, "Name": "Bonnell, Miss. Elizabeth", "Sex": "female", "Age": 58, "SibSp": 0, "Parch": 0, "Ticket": "113783", "Fare": 26.55, "Cabin": "C103", "Embarked": "S"},
        {"PassengerId": 13, "Survived": 0, "Pclass": 3, "Name": "Saundercock, Mr. William Henry", "Sex": "male", "Age": 20, "SibSp": 0, "Parch": 0, "Ticket": "A/5. 2151", "Fare": 8.05, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 14, "Survived": 0, "Pclass": 3, "Name": "Andersson, Mr. Anders Johan", "Sex": "male", "Age": 39, "SibSp": 1, "Parch": 5, "Ticket": "347082", "Fare": 31.275, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 15, "Survived": 0, "Pclass": 3, "Name": "Vestrom, Miss. Hulda Amanda Adolfina", "Sex": "female", "Age": 14, "SibSp": 0, "Parch": 0, "Ticket": "350406", "Fare": 7.8542, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 16, "Survived": 1, "Pclass": 2, "Name": "Hewlett, Mrs. (Mary D Kingcome) ", "Sex": "female", "Age": 55, "SibSp": 0, "Parch": 0, "Ticket": "248706", "Fare": 16.0, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 17, "Survived": 0, "Pclass": 3, "Name": "Rice, Master. Eugene", "Sex": "male", "Age": 2, "SibSp": 4, "Parch": 1, "Ticket": "382652", "Fare": 29.125, "Cabin": None, "Embarked": "Q"},
        {"PassengerId": 18, "Survived": 1, "Pclass": 2, "Name": "Williams, Mr. Charles Eugene", "Sex": "male", "Age": None, "SibSp": 0, "Parch": 0, "Ticket": "244373", "Fare": 13.0, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 19, "Survived": 0, "Pclass": 3, "Name": "Vander Planke, Mrs. Julius (Emelia Maria Vandemoortele)", "Sex": "female", "Age": 31, "SibSp": 1, "Parch": 0, "Ticket": "345763", "Fare": 18.0, "Cabin": None, "Embarked": "S"},
        {"PassengerId": 20, "Survived": 1, "Pclass": 3, "Name": "Masselmani, Mrs. Fatima", "Sex": "female", "Age": None, "SibSp": 0, "Parch": 0, "Ticket": "2649", "Fare": 7.225, "Cabin": None, "Embarked": "C"}
    ]
    df = pd.DataFrame(data)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    return stream.getvalue().encode('utf-8')

def parse_db_error(err: Exception, table_name: str) -> str:
    """Classify SQLAlchemy/driver connection errors into clear, actionable user messages.
    
    This function parses connection, authentication, DNS, SSL, and timeout errors,
    preventing direct raw stack traces from exposing database details to the frontend
    and giving clear remediation guidance instead.
    """
    msg = str(err).lower()
    # Host / network
    if any(k in msg for k in ["network is unreachable", "connection refused", "could not connect to server", "no route to host"]):
        return "Cannot reach the server. Check that the host and port are correct and that the server is accepting connections."
    # DNS / hostname
    if any(k in msg for k in ["could not translate host name", "name or service not known", "nodename nor servname"]):
        return "Hostname could not be resolved. Check for typos in the host field."
    # Authentication
    if any(k in msg for k in ["password authentication failed", "authentication failed", "access denied for user"]):
        return "Authentication failed. Your username or password is incorrect."
    # Database does not exist
    if "database" in msg and "does not exist" in msg:
        return "Database not found. Check the database name — it may be misspelled or not yet created."
    # Table does not exist
    if any(k in msg for k in ["no such table", "relation", "does not exist"]):
        return f'Table "{table_name}" was not found. Make sure the table name is correct and exists in this database.'
    # IP / firewall blocked
    if any(k in msg for k in ["no pg_hba.conf entry", "not permitted", "ip address"]):
        return "Access denied. Your IP address is not allowed to connect. Add it to the database firewall/allowlist."
    # SSL
    if "ssl" in msg:
        return "SSL error. The server may require an encrypted connection — try enabling SSL or check server settings."
    # Timeout
    if "timeout" in msg or "timed out" in msg:
        return "Connection timed out. The server is reachable but did not respond in time. Try again."
    # Empty table
    if "no data" in msg or "empty" in msg:
        return f'Table "{table_name}" exists but contains no rows to import.'
    # Fallback — strip internal stack noise, show first line only
    first_line = str(err).split("\n")[0]
    return f"Connection failed: {first_line}"
