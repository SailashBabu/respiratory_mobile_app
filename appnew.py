# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, session, redirect, url_for, flash, get_flashed_messages, jsonify
import sqlite3
import hashlib
import re
from datetime import datetime
import requests
import pandas as pd
import os
import numpy as np
import random
import joblib
import pytesseract
from PIL import Image
import pdfplumber
from docx import Document
import tempfile
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("⚠ google-generativeai not installed. AI recommendations will be basic.")

app = Flask(__name__)
app.secret_key = "spirometry-app-secret-key-2026"
DB_PATH = "app.db"

# -------------------------
# Gemini AI Configuration
# -------------------------
GEMINI_API_KEY = "AIzaSyDzzl0N8N0sAAADyFku24738xKqc5DT3vc"

if GENAI_AVAILABLE:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Configure generation settings for better responses
        generation_config = {
            "temperature": 0.9,
            "top_p": 1.0,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        # Configure safety settings to allow medical content
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
        # Use the latest Gemini 2.0 Flash model for faster responses
        gemini_model = genai.GenerativeModel(
            'gemini-2.5-flash-lite',
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        print("✓ Gemini AI 2.0 Flash configured successfully with optimized settings")
    except Exception as e:
        gemini_model = None
        print(f"⚠ Failed to configure Gemini AI: {e}")
else:
    gemini_model = None

# -------------------------
# Database helpers
# -------------------------
def init_db():
    print("\n" + "="*60)
    print("🗄️  INITIALIZING DATABASE")
    print("="*60)
    print(f"Database path: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✓ Users table created/verified")
    
    # Create patient_records table
    c.execute('''
        CREATE TABLE IF NOT EXISTS patient_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            patient_name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            location TEXT,
            smoking_status TEXT,
            physical_activity TEXT,
            occupation TEXT,
            diet TEXT,
            pm2_5 REAL,
            pm10 REAL,
            no2 REAL,
            so2 REAL,
            co REAL,
            ozone REAL,
            dust REAL,
            pollen REAL,
            indoor_pollutants REAL,
            fev1 REAL,
            fvc REAL,
            fev1_fvc_ratio REAL,
            pefr REAL,
            predicted_fev1 REAL,
            predicted_fvc REAL,
            predicted_ratio REAL,
            predicted_pefr REAL,
            aqi_value REAL DEFAULT 0,
            aqi_category TEXT DEFAULT 'Good',
            ml_prediction TEXT,
            medical_rule_prediction TEXT,
            prediction_range TEXT,
            severity_color TEXT,
            risk_level TEXT DEFAULT 'Low',
            recommendation TEXT,
            prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            spirometry_source TEXT DEFAULT 'Manual'
        )
    ''')
    print("✓ Patient records table created/verified")
    
    conn.commit()
    
    # Verify tables exist
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    print(f"✓ Database tables: {[t[0] for t in tables]}")
    
    # Count existing records
    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM patient_records")
    record_count = c.fetchone()[0]
    print(f"📊 Current data: {user_count} users, {record_count} predictions")
    print("="*60 + "\n")
    
    conn.close()

def db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# -------------------------
# Auth & utils
# -------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email: str) -> bool:
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None

def register_user(username, password, email, full_name=None):
    print("\n" + "="*60)
    print("👤 USER REGISTRATION")
    print("="*60)
    print(f"Username: {username}")
    print(f"Email: {email}")
    print(f"Full Name: {full_name}")
    
    conn = db_conn(); c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, email, full_name) VALUES (?, ?, ?, ?)",
                  (username, hash_password(password), email, full_name))
        conn.commit()
        print("✅ User registered successfully in database")
        print(f"User ID: {c.lastrowid}")
        print("="*60 + "\n")
        return True, "Registration successful"
    except sqlite3.IntegrityError as e:
        print(f"❌ Registration failed: Username or email already exists")
        print(f"Error: {e}")
        print("="*60 + "\n")
        return False, "Username or email already exists"
    except Exception as e:
        print(f"❌ Registration failed: {str(e)}")
        print("="*60 + "\n")
        return False, str(e)
    finally:
        conn.close()

def verify_user(username, password):
    print("\n" + "="*60)
    print("🔐 USER LOGIN VERIFICATION")
    print("="*60)
    print(f"Username: {username}")
    
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT id, username, full_name FROM users WHERE username = ? AND password = ?",
              (username, hash_password(password)))
    user = c.fetchone()
    conn.close()
    
    if user:
        print(f"✅ Login successful - User ID: {user[0]}, Username: {user[1]}")
    else:
        print(f"❌ Login failed - Invalid credentials")
    print("="*60 + "\n")
    
    return user


# ---------------------------
# File Upload Feature using tesseract
#-------------------------------

def extract_text_from_file(file_path, file_ext):
    text = ""

    try:
        if file_ext == ".pdf":
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""

        elif file_ext in [".docx"]:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"

        elif file_ext in [".png", ".jpg", ".jpeg"]:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)

    except Exception as e:
        print("OCR Extraction Error:", e)

    return text
def extract_spirometry_values(text):
    result = {"fev1": None, "fvc": None, "pefr": None}

    try:
        # Extract POST column (4th numeric value in row)

        fvc_match = re.search(r'FVC\s*\[L\].*?(\d+\.\d+)\s+(\d+\.\d+)\s+\d+\s*%?\s+(\d+\.\d+)', text)
        fev1_match = re.search(r'FEV\s*1\s*\[L\].*?(\d+\.\d+)\s+(\d+\.\d+)\s+\d+\s*%?\s+(\d+\.\d+)', text)
        pef_match = re.search(r'PEF\s*\[L/s\].*?(\d+\.\d+)\s+(\d+\.\d+)\s+\d+\s*%?\s+(\d+\.\d+)', text)

        if fvc_match:
            result["fvc"] = float(fvc_match.group(3))  # POST value

        if fev1_match:
            result["fev1"] = float(fev1_match.group(3))  # POST value

        if pef_match:
            pef_lps = float(pef_match.group(3))  # POST value in L/s
            result["pefr"] = round(pef_lps * 60, 1)  # Convert to L/min

    except Exception as e:
        print("Extraction error:", e)

    return result
@app.route('/upload_spirometry', methods=['POST'])
def upload_spirometry():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"})

    ext = os.path.splitext(file.filename)[1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        file.save(tmp.name)
        file_path = tmp.name

    text = extract_text_from_file(file_path, ext)
    values = extract_spirometry_values(text)

    os.remove(file_path)

    return jsonify({
        "success": True,
        "data": values
    })


# -------------------------
# Prediction storage
# -------------------------
def save_prediction_record(user_id, patient_name, inputs, predicted_values, aqi_value, aqi_category, ml_pred, medical_pred, pred_range, color, risk_level, recommendation, spirometry_source):
    print("\n" + "="*70)
    print("💾 SAVING PREDICTION TO DATABASE")
    print("="*70)
    print(f"User ID: {user_id}")
    print(f"Patient Name: {patient_name}")
    print(f"Risk Level: {risk_level}")
    print(f"ML Prediction: {ml_pred}")
    print(f"AQI: {aqi_value} ({aqi_category})")
    print(f"Spirometry Source: {spirometry_source}")
    
    conn = db_conn(); c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO patient_records
            (user_id, patient_name, age, gender, location, smoking_status, physical_activity, occupation, diet,
             pm2_5, pm10, no2, so2, co, ozone, dust, pollen, indoor_pollutants,
             fev1, fvc, fev1_fvc_ratio, pefr, predicted_fev1, predicted_fvc, predicted_ratio, predicted_pefr,
             aqi_value, aqi_category, ml_prediction, medical_rule_prediction, prediction_range, severity_color, risk_level, recommendation, spirometry_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            user_id, patient_name,
            inputs.get('age'), inputs.get('gender'), inputs.get('location'),
            inputs.get('smoking_status'), inputs.get('physical_activity'),
            inputs.get('occupation'), inputs.get('diet'),
            inputs.get('pm2_5'), inputs.get('pm10'), inputs.get('no2'),
            inputs.get('so2'), inputs.get('co'), inputs.get('ozone'),
            inputs.get('dust'), inputs.get('pollen'), inputs.get('indoor_pollutants'),
            inputs.get('fev1'), inputs.get('fvc'), inputs.get('fev1_fvc_ratio'),
            inputs.get('pefr'), 
            predicted_values.get('fev1'), predicted_values.get('fvc'), 
            predicted_values.get('ratio'), predicted_values.get('pefr'),
            aqi_value, aqi_category,
            ml_pred, medical_pred, pred_range, color, risk_level, recommendation, spirometry_source
        ))
        conn.commit()
        record_id = c.lastrowid
        print(f"✅ Prediction saved successfully - Record ID: {record_id}")
        print("="*70 + "\n")
        return True
    except Exception as e:
        print(f"❌ Save error: {e}")
        import traceback
        traceback.print_exc()
        print("="*70 + "\n")
        return False
    finally:
        conn.close()
        conn.close()

def get_user_predictions(user_id):
    conn = db_conn(); c = conn.cursor()
    try:
        c.execute('''
            SELECT id, patient_name, ml_prediction, medical_rule_prediction, prediction_range, severity_color, 
                   aqi_value, aqi_category, risk_level, prediction_date, spirometry_source
            FROM patient_records WHERE user_id = ? ORDER BY prediction_date DESC
        ''', (user_id,))
        rows = c.fetchall()
        return rows
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        return []
    finally:
        conn.close()

# -------------------------
# LOAD ASTHMA PREDICTION MODEL & SCALER
# -------------------------
asthma_model = None
asthma_scaler = None

try:
    if os.path.exists("xgboost_asthma_priority_20epochs.pkl"):
        asthma_model = joblib.load("xgboost_asthma_priority_20epochs.pkl")
        print("✓ Asthma prediction model loaded successfully")
    else:
        print("⚠ Asthma model file not found: xgboost_asthma_priority_20epochs.pkl")
except Exception as e:
    print(f"⚠ Failed to load asthma model: {e}")

try:
    if os.path.exists("xgboost_priority_scaler.pkl"):
        asthma_scaler = joblib.load("xgboost_priority_scaler.pkl")
        print("✓ Asthma scaler loaded successfully")
    else:
        print("⚠ Scaler file not found: xgboost_priority_scaler.pkl")
except Exception as e:
    print(f"⚠ Failed to load asthma scaler: {e}")

# -------------------------
# PRIORITY LEVEL LOGIC
# -------------------------
def assign_priority(fev1, pefr, pm25, dust):
    """
    Assign priority level based on FEV1, PEFR, PM2.5, and dust levels
    Priority levels: 0 = Low, 1 = Medium, 2 = High
    """
    if fev1 < 2.0 and pefr < 300 and pm25 > 60:
        return 2   # High
    elif pm25 > 40 or dust > 40 or fev1 < 2.5:
        return 1   # Medium
    else:
        return 0   # Low

# -------------------------
# ML Prediction Function
# -------------------------
def predict_asthma_risk(age, gender, smoking_status, pm25, dust, fev1, fvc, pefr):
    """
    Predict asthma risk using XGBoost model if available
    Returns prediction, probability, and priority level
    """
    print("\n" + "="*70)
    print("🔬 ASTHMA RISK PREDICTION")
    print("="*70)
    
    if asthma_model is None or asthma_scaler is None:
        # Fallback if model not loaded
        print("⚠️  Model not available, using rule-based priority")
        priority = assign_priority(fev1, pefr, pm25, dust)
        priority_text = {0: "Low", 1: "Medium", 2: "High"}[priority]
        print(f"Priority: {priority_text}")
        print("="*70 + "\n")
        return None, None, priority_text, priority
    
    try:
        # Encoding
        gender_map = {"Male": 0, "Female": 1, "Other": 0}
        smoking_map = {
            "Non-smoker": 0, 
            "Former smoker": 1, 
            "Current smoker": 2,
            "Occasional": 1,
            "No": 0,
            "Yes": 2
        }
        
        gender_encoded = gender_map.get(gender, 0)
        smoking_encoded = smoking_map.get(smoking_status, 0)
        
        # Assign priority
        priority = assign_priority(fev1, pefr, pm25, dust)
        
        print(f"📊 Input Features:")
        print(f"  Age: {age}, Gender: {gender} ({gender_encoded}), Smoking: {smoking_status} ({smoking_encoded})")
        print(f"  PM2.5: {pm25}, Dust: {dust}")
        print(f"  FEV1: {fev1}, FVC: {fvc}, PEFR: {pefr}")
        print(f"  Rule-based Priority: {priority} ({['Low', 'Medium', 'High'][priority]})")
        
        # Feature order MUST MATCH training: age, pm25, dust, fev1, fvc, pefr, gender, smoking, priority
        input_data = np.array([[
            age, pm25, dust, fev1, fvc, pefr,
            gender_encoded, smoking_encoded, priority
        ]])
        
        print(f"\n🔢 Feature Vector: {input_data[0]}")
        
        input_scaled = asthma_scaler.transform(input_data)
        print(f"📐 Scaled Features: {input_scaled[0][:3]}... (first 3 shown)")
        
        prediction = asthma_model.predict(input_scaled)[0]
        probability = asthma_model.predict_proba(input_scaled)[0]
        
        print(f"\n🎯 Model Output:")
        print(f"  Raw Prediction: {prediction}")
        print(f"  Probabilities: Class 0={probability[0]:.3f}, Class 1={probability[1]:.3f}")
        print(f"  Predicted Class: {int(prediction)} ({'Asthma Risk' if int(prediction) == 1 else 'No Asthma Risk'})")
        print(f"  Confidence: {probability[1]*100:.1f}%")
        
        priority_text = {0: "Low", 1: "Medium", 2: "High"}[priority]
        
        print(f"\n✅ Final Result: Prediction={int(prediction)}, Probability={probability[1]:.3f}, Priority={priority_text}")
        print("="*70 + "\n")
        
        return int(prediction), probability[1], priority_text, priority
    except Exception as e:
        print(f"❌ Asthma prediction error: {e}")
        import traceback
        traceback.print_exc()
        priority = assign_priority(fev1, pefr, pm25, dust)
        priority_text = {0: "Low", 1: "Medium", 2: "High"}[priority]
        print(f"Fallback Priority: {priority_text}")
        print("="*70 + "\n")
        return None, None, priority_text, priority

# -------------------------
# Gemini AI Recommendation Generator
# -------------------------
def generate_ai_recommendation(patient_data, priority_level, aqi_data, spirometry_data):
    """
    Generate personalized AI recommendation using Google Gemini based on patient data and priority level
    """
    print(f"\n{'='*60}")
    print(f"🤖 Generating AI Recommendation...")
    print(f"Priority Level: {priority_level}")
    print(f"Gemini Model Available: {gemini_model is not None}")
    print(f"{'='*60}\n")
    
    if not GENAI_AVAILABLE or gemini_model is None:
        print("⚠️  Gemini not available, using fallback recommendations")
        # Fallback to comprehensive recommendations
        if priority_level == "High":
            return "⚠️ HIGH PRIORITY: Immediate medical consultation strongly recommended. Your lung function tests indicate significant respiratory concerns combined with poor air quality. Avoid all outdoor activities, stay indoors with air purifiers, and seek emergency care if you experience severe breathing difficulty, chest pain, or persistent coughing."
        elif priority_level in ["Medium", "Moderate"]:
            return "⚡ MODERATE RISK: Schedule an appointment with your healthcare provider soon. Limit outdoor activities during high pollution hours (morning and evening rush), use N95 masks when outdoors, and monitor your symptoms closely. Consider using air purifiers indoors and avoid strenuous exercise when air quality is poor."
        else:
            return "✓ LOW RISK: Continue your current health practices. Maintain regular check-ups with your healthcare provider, stay active with appropriate exercise, and monitor local air quality reports. Stay indoors during high pollution days and maintain good indoor air quality. Keep rescue inhalers accessible if prescribed."
    
    try:
        # Create detailed prompt for Gemini 2.0 Flash
        prompt = f"""You are a respiratory health advisor. Provide a personalized health recommendation (3-4 sentences maximum) for this patient:

PATIENT PROFILE:
- Age: {patient_data.get('age', 'N/A')} years, Gender: {patient_data.get('gender', 'N/A')}
- Smoking Status: {patient_data.get('smoking_status', 'N/A')}
- Physical Activity: {patient_data.get('physical_activity', 'N/A')}
- Location: {patient_data.get('location', 'N/A')}

LUNG FUNCTION TEST RESULTS:
- FEV1: {spirometry_data.get('fev1', 'N/A')} liters (Forced Expiratory Volume)
- FVC: {spirometry_data.get('fvc', 'N/A')} liters (Forced Vital Capacity)
- FEV1/FVC Ratio: {spirometry_data.get('ratio', 'N/A')}
- PEFR: {spirometry_data.get('pefr', 'N/A')} L/min (Peak Expiratory Flow Rate)

ENVIRONMENTAL CONDITIONS:
- Air Quality Index: {aqi_data.get('aqi_value', 'N/A')} - {aqi_data.get('aqi_category', 'N/A')}
- Primary Pollutant: {aqi_data.get('primary_pollutant', 'N/A')}
- PM2.5 Level: {patient_data.get('pm2_5', 'N/A')} ug/m3

RISK ASSESSMENT: {priority_level} Priority

Please provide specific, actionable health recommendations that address:
1. Immediate actions needed for this {priority_level} priority level
2. Environmental precautions based on current air quality
3. Lifestyle modifications considering lung function results
4. When to seek medical consultation

Keep the response practical, clear, and concise. Do not include disclaimers about not being a doctor."""

        print("📤 Sending request to Gemini AI 2.0 Flash...")
        print(f"Prompt length: {len(prompt)} characters")
        
        response = gemini_model.generate_content(prompt)
        print("📥 Received response from Gemini AI")
        
        # Extract text from response
        ai_recommendation = None
        
        # Primary method: Use response.text
        try:
            if hasattr(response, 'text'):
                ai_recommendation = response.text.strip()
                if ai_recommendation:
                    print(f"✓ Successfully extracted recommendation via response.text ({len(ai_recommendation)} chars)")
                else:
                    print("⚠️  response.text is empty")
        except ValueError as ve:
            print(f"⚠️  response.text raised ValueError: {ve}")
            # This usually means the response was blocked or has no valid parts
            if hasattr(response, 'prompt_feedback'):
                print(f"Prompt feedback: {response.prompt_feedback}")
        except Exception as e:
            print(f"⚠️  Error accessing response.text: {type(e).__name__}: {e}")
        
        # Fallback: Extract from candidates
        if not ai_recommendation:
            print("Attempting to extract from candidates...")
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        parts = candidate.content.parts
                        if parts and len(parts) > 0:
                            ai_recommendation = parts[0].text.strip()
                            print(f"✓ Extracted from candidates ({len(ai_recommendation)} chars)")
            except Exception as e:
                print(f"✗ Error extracting from candidates: {e}")
        
        # Verify we got a valid recommendation
        if not ai_recommendation or len(ai_recommendation) < 10:
            error_msg = "No valid recommendation text received from Gemini"
            print(f"\n❌ {error_msg}")
            print(f"Response type: {type(response)}")
            
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                print(f"Candidate finish_reason: {candidate.finish_reason}")
                if hasattr(candidate, 'safety_ratings'):
                    print(f"Safety ratings: {candidate.safety_ratings}")
            
            raise ValueError(error_msg)
        
        # Format recommendation with priority emoji
        if priority_level == "High":
            if not ai_recommendation.startswith(("⚠️", "🚨", "HIGH")):
                ai_recommendation = "⚠️ HIGH PRIORITY: " + ai_recommendation
        elif priority_level == "Moderate" or priority_level == "Medium":
            if not ai_recommendation.startswith(("⚡", "⚠", "MODERATE", "MEDIUM")):
                ai_recommendation = "⚡ MODERATE RISK: " + ai_recommendation
        else:  # Low
            if not ai_recommendation.startswith(("✓", "✅", "LOW")):
                ai_recommendation = "✓ LOW RISK: " + ai_recommendation
        
        print(f"\n✅ AI Recommendation Generated Successfully!")
        print(f"📝 Length: {len(ai_recommendation)} characters")
        print(f"📄 Preview: {ai_recommendation[:200]}{'...' if len(ai_recommendation) > 200 else ''}")
        print(f"{'='*60}\n")
        
        return ai_recommendation
        
    except Exception as e:
        print(f"❌ Gemini AI recommendation error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        # Fallback to detailed recommendations based on priority
        if priority_level == "High":
            return "⚠️ HIGH PRIORITY: Immediate medical consultation strongly recommended. Your lung function tests indicate significant respiratory concerns combined with poor air quality. Avoid all outdoor activities, stay indoors with air purifiers, and seek emergency care if you experience severe breathing difficulty, chest pain, or persistent coughing."
        elif priority_level in ["Medium", "Moderate"]:
            return "⚡ MODERATE RISK: Schedule an appointment with your healthcare provider soon. Limit outdoor activities during high pollution hours (morning and evening rush), use N95 masks when outdoors, and monitor your symptoms closely. Consider using air purifiers indoors and avoid strenuous exercise when air quality is poor."
        else:
            return "✓ LOW RISK: Continue your current health practices. Maintain regular check-ups with your healthcare provider, stay active with appropriate exercise, and monitor local air quality reports. Stay indoors during high pollution days and maintain good indoor air quality. Keep rescue inhalers accessible if prescribed."

def predict_spirometry_from_pollution(inputs):
    """
    Predict spirometry values (FEV1, FVC, Ratio, PEFR) based on pollution data and patient factors
    with realistic variations based on actual medical data
    """
    try:
        # Extract input parameters with defaults
        age = inputs.get('age', 35)
        gender = inputs.get('gender', 'Male')
        smoking_status = inputs.get('smoking_status', 'Non-smoker')
        physical_activity = inputs.get('physical_activity', 'Moderate')
        location = inputs.get('location', 'Urban')
        
        # Pollution parameters
        pm2_5 = inputs.get('pm2_5', 50)
        pm10 = inputs.get('pm10', 80)
        no2 = inputs.get('no2', 30)
        so2 = inputs.get('so2', 10)
        co = inputs.get('co', 1)
        ozone = inputs.get('ozone', 40)
        dust = inputs.get('dust', 60)
        pollen = inputs.get('pollen', 40)
        indoor_pollutants = inputs.get('indoor_pollutants', 5)
        
        # Base values for healthy adult (based on medical literature)
        # Normal ranges: FEV1 2.5-4.0L, FVC 3.0-5.0L, FEV1/FVC >0.75, PEFR 400-600 L/min
        
        # Age adjustment (decline after age 25)
        age_factor = max(0.6, 1.0 - (max(age - 25, 0) * 0.002))
        
        # Gender adjustment (typically females have 10-15% lower lung volumes)
        gender_factor = 0.85 if gender.lower() in ['female', 'f'] else 1.0
        
        # Base values adjusted for age and gender
        base_fev1 = (3.5 * age_factor * gender_factor)
        base_fvc = (4.5 * age_factor * gender_factor)
        base_pefr = (500 * age_factor * gender_factor)
        
        # Pollution impact factors (based on epidemiological studies)
        pollution_impact = {
            'pm2_5': max(0, (pm2_5 - 15) * 0.0015),  # 1.5% reduction per 10μg/m³ above 15
            'pm10': max(0, (pm10 - 30) * 0.0010),    # 1.0% reduction per 10μg/m³ above 30
            'no2': max(0, (no2 - 20) * 0.0012),      # 1.2% reduction per 10μg/m³ above 20
            'so2': max(0, (so2 - 5) * 0.0018),       # 1.8% reduction per 10μg/m³ above 5
            'co': max(0, (co - 0.5) * 0.0020),       # 2.0% reduction per 1mg/m³ above 0.5
            'ozone': max(0, (ozone - 30) * 0.0010),  # 1.0% reduction per 10μg/m³ above 30
            'dust': max(0, (dust - 50) * 0.0005),    # 0.5% reduction per 10μg/m³ above 50
            'pollen': max(0, (pollen - 30) * 0.0008),# 0.8% reduction per 10μg/m³ above 30
            'indoor': max(0, (indoor_pollutants - 2) * 0.0015) # 1.5% reduction per unit above 2
        }
        
        # Calculate total pollution impact (capped at 40% maximum reduction)
        total_pollution_impact = min(0.4, sum(pollution_impact.values()))
        
        # Smoking impact (based on smoking status)
        smoking_impact = 0
        if smoking_status == 'Current smoker':
            smoking_impact = 0.20  # 20% reduction for current smokers
        elif smoking_status == 'Former smoker':
            smoking_impact = 0.08  # 8% reduction for former smokers
        
        # Physical activity impact
        activity_impact = 0
        if physical_activity == 'Low':
            activity_impact = -0.10  # 10% reduction for low activity
        elif physical_activity == 'High':
            activity_impact = 0.05   # 5% improvement for high activity
        
        # Location impact
        location_impact = 0
        if location == 'Industrial':
            location_impact = -0.15  # Additional 15% reduction for industrial areas
        elif location == 'Urban':
            location_impact = -0.08  # 8% reduction for urban areas
        
        # Calculate total impact (pollution + smoking + activity + location)
        total_negative_impact = total_pollution_impact + smoking_impact + abs(min(activity_impact, 0)) + abs(location_impact)
        total_positive_impact = max(activity_impact, 0)
        
        # Apply impacts with different sensitivity for each parameter
        # FEV1 is most sensitive to pollution and smoking
        predicted_fev1 = base_fev1 * (1 - total_negative_impact * 1.2 + total_positive_impact * 0.8)
        
        # FVC is moderately sensitive
        predicted_fvc = base_fvc * (1 - total_negative_impact * 0.9 + total_positive_impact * 0.6)
        
        # FEV1/FVC ratio - obstructive pattern worsens with pollution/smoking
        base_ratio = 0.78  # Normal ratio
        ratio_reduction = total_negative_impact * 0.3  # Ratio decreases with impairment
        predicted_ratio = max(0.45, base_ratio - ratio_reduction)
        
        # PEFR is very sensitive to acute exposure
        predicted_pefr = base_pefr * (1 - total_negative_impact * 1.4 + total_positive_impact * 0.7)
        
        # Add some random variation (±5%) to simulate real-world variability
        variation = 0.05
        predicted_fev1 *= (1 + random.uniform(-variation, variation))
        predicted_fvc *= (1 + random.uniform(-variation, variation))
        predicted_ratio *= (1 + random.uniform(-variation, variation * 0.5))  # Less variation for ratio
        predicted_pefr *= (1 + random.uniform(-variation, variation))
        
        # Ensure physiologically reasonable bounds
        predicted_fev1 = max(1.2, min(5.5, predicted_fev1))
        predicted_fvc = max(1.5, min(6.5, predicted_fvc))
        predicted_ratio = max(0.4, min(0.85, predicted_ratio))
        predicted_pefr = max(150, min(800, predicted_pefr))
        
        # Debug output to understand the calculations
        print(f"DEBUG: Age: {age}, Gender: {gender}, PM2.5: {pm2_5}")
        print(f"DEBUG: Total pollution impact: {total_pollution_impact:.3f}")
        print(f"DEBUG: Smoking impact: {smoking_impact:.3f}")
        print(f"DEBUG: Predicted FEV1: {predicted_fev1:.2f}, FVC: {predicted_fvc:.2f}")
        
        return {
            'fev1': round(predicted_fev1, 2),
            'fvc': round(predicted_fvc, 2),
            'ratio': round(predicted_ratio, 3),
            'pefr': round(predicted_pefr, 0)
        }
        
    except Exception as e:
        print(f"Spirometry prediction error: {e}")
        # Fallback values that still vary slightly
        return {
            'fev1': round(3.0 + random.uniform(-0.5, 0.5), 2),
            'fvc': round(4.0 + random.uniform(-0.6, 0.6), 2),
            'ratio': round(0.75 + random.uniform(-0.05, 0.05), 3),
            'pefr': round(400 + random.uniform(-50, 50), 0)
        }

# -------------------------
# ML Prediction Function
# -------------------------
# Asthma/ML prediction removed. The app continues to provide
# spirometry estimation from pollution and AQI analysis only.

# -------------------------
# AQI Calculation
# -------------------------
def calculate_comprehensive_aqi(pm2_5, pm10, no2, so2, co, ozone):
    aqi_breakpoints = {
        'pm2_5': [(0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150), 
                  (55.5, 150.4, 151, 200), (150.5, 250.4, 201, 300), (250.5, 500.4, 301, 500)],
        'pm10': [(0, 54, 0, 50), (55, 154, 51, 100), (155, 254, 101, 150),
                 (255, 354, 151, 200), (355, 424, 201, 300), (425, 604, 301, 500)],
        'no2': [(0, 53, 0, 50), (54, 100, 51, 100), (101, 360, 101, 150),
                (361, 649, 151, 200), (650, 1249, 201, 300), (1250, 2049, 301, 500)],
        'so2': [(0, 35, 0, 50), (36, 75, 51, 100), (76, 185, 101, 150),
                (186, 304, 151, 200), (305, 604, 201, 300), (605, 1004, 301, 500)],
        'co': [(0, 4.4, 0, 50), (4.5, 9.4, 51, 100), (9.5, 12.4, 101, 150),
               (12.5, 15.4, 151, 200), (15.5, 30.4, 201, 300), (30.5, 50.4, 301, 500)],
        'ozone': [(0, 54, 0, 50), (55, 70, 51, 100), (71, 85, 101, 150),
                  (86, 105, 151, 200), (106, 200, 201, 300), (201, 500, 301, 500)]
    }
    
    def calculate_individual_aqi(pollutant, value):
        if value is None or value <= 0:
            return 0
        for bp_low, bp_high, aqi_low, aqi_high in aqi_breakpoints[pollutant]:
            if bp_low <= value <= bp_high:
                return ((aqi_high - aqi_low) / (bp_high - bp_low)) * (value - bp_low) + aqi_low
        return 500
    
    aqi_values = [
        calculate_individual_aqi('pm2_5', pm2_5),
        calculate_individual_aqi('pm10', pm10),
        calculate_individual_aqi('no2', no2),
        calculate_individual_aqi('so2', so2),
        calculate_individual_aqi('co', co),
        calculate_individual_aqi('ozone', ozone)
    ]
    
    final_aqi = max(aqi_values)
    
    if final_aqi <= 50:
        category, color = "Good", "#00e400"
    elif final_aqi <= 100:
        category, color = "Moderate", "#ffff00"
    elif final_aqi <= 150:
        category, color = "Unhealthy for Sensitive Groups", "#ff7e00"
    elif final_aqi <= 200:
        category, color = "Unhealthy", "#ff0000"
    elif final_aqi <= 300:
        category, color = "Very Unhealthy", "#8f3f97"
    else:
        category, color = "Hazardous", "#7e0023"
    
    return {
        'aqi_value': round(final_aqi, 1),
        'aqi_category': category,
        'aqi_color': color,
        'primary_pollutant': get_primary_pollutant(pm2_5, pm10, no2, so2, co, ozone)
    }

def get_primary_pollutant(pm2_5, pm10, no2, so2, co, ozone):
    pollutants = {
        'PM2.5': pm2_5,
        'PM10': pm10,
        'NO2': no2,
        'SO2': so2,
        'CO': co,
        'Ozone': ozone
    }
    return max(pollutants, key=pollutants.get)

# -------------------------
# Real-time Pollution Data Fetching using WAQI API
# -------------------------
WAQI_API_KEY = "0d32398dc178e2806d08e3c01c58621cf827453f"

def fetch_live_pollution(lat, lon):
    """
    Fetch real-time pollution data from WAQI API
    """
    try:
        # Try to get data by coordinates first
        url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={WAQI_API_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('status') == 'ok' and 'data' in data:
            aqi_data = data['data']
            iaqi = aqi_data.get('iaqi', {})
            
            # Extract pollutant values
            pm2_5 = iaqi.get('pm25', {}).get('v', 0)
            pm10 = iaqi.get('pm10', {}).get('v', 0)
            no2 = iaqi.get('no2', {}).get('v', 0)
            so2 = iaqi.get('so2', {}).get('v', 0)
            co = iaqi.get('co', {}).get('v', 0)
            ozone = iaqi.get('o3', {}).get('v', 0)
            
            # Get AQI value and category from WAQI
            aqi_value = aqi_data.get('aqi', 0)
            
            # Map WAQI AQI to US EPA categories
            if aqi_value <= 50:
                category, color = "Good", "#00e400"
            elif aqi_value <= 100:
                category, color = "Moderate", "#ffff00"
            elif aqi_value <= 150:
                category, color = "Unhealthy for Sensitive Groups", "#ff7e00"
            elif aqi_value <= 200:
                category, color = "Unhealthy", "#ff0000"
            elif aqi_value <= 300:
                category, color = "Very Unhealthy", "#8f3f97"
            else:
                category, color = "Hazardous", "#7e0023"
            
            # Determine primary pollutant
            pollutants = {
                'PM2.5': pm2_5,
                'PM10': pm10,
                'NO2': no2,
                'SO2': so2,
                'CO': co,
                'Ozone': ozone
            }
            primary_pollutant = max(pollutants, key=pollutants.get) if any(pollutants.values()) else "Unknown"
            
            return {
                "pm2_5": pm2_5,
                "pm10": pm10,
                "so2": so2,
                "co": co,
                "no2": no2,
                "ozone": ozone,
                "aqi_value": aqi_value,
                "aqi_category": category,
                "aqi_color": color,
                "primary_pollutant": primary_pollutant,
                "station": aqi_data.get('city', {}).get('name', 'Unknown Station')
            }
        else:
            raise Exception("WAQI API returned error or no data")
            
    except Exception as e:
        print(f"WAQI API error: {e}")
        # Fallback to calculated AQI with default values
        return calculate_comprehensive_aqi(50, 80, 30, 10, 1, 40)

def fetch_pollution_by_city(city_name):
    """
    Fetch pollution data by city name using WAQI API
    """
    try:
        url = f"https://api.waqi.info/feed/{city_name}/?token={WAQI_API_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('status') == 'ok' and 'data' in data:
            aqi_data = data['data']
            iaqi = aqi_data.get('iaqi', {})
            
            # Extract pollutant values
            pm2_5 = iaqi.get('pm25', {}).get('v', 0)
            pm10 = iaqi.get('pm10', {}).get('v', 0)
            no2 = iaqi.get('no2', {}).get('v', 0)
            so2 = iaqi.get('so2', {}).get('v', 0)
            co = iaqi.get('co', {}).get('v', 0)
            ozone = iaqi.get('o3', {}).get('v', 0)
            
            # Get AQI value
            aqi_value = aqi_data.get('aqi', 0)
            
            # Map to US EPA categories
            if aqi_value <= 50:
                category, color = "Good", "#00e400"
            elif aqi_value <= 100:
                category, color = "Moderate", "#ffff00"
            elif aqi_value <= 150:
                category, color = "Unhealthy for Sensitive Groups", "#ff7e00"
            elif aqi_value <= 200:
                category, color = "Unhealthy", "#ff0000"
            elif aqi_value <= 300:
                category, color = "Very Unhealthy", "#8f3f97"
            else:
                category, color = "Hazardous", "#7e0023"
            
            pollutants = {
                'PM2.5': pm2_5,
                'PM10': pm10,
                'NO2': no2,
                'SO2': so2,
                'CO': co,
                'Ozone': ozone
            }
            primary_pollutant = max(pollutants, key=pollutants.get) if any(pollutants.values()) else "Unknown"
            
            return {
                "pm2_5": pm2_5,
                "pm10": pm10,
                "so2": so2,
                "co": co,
                "no2": no2,
                "ozone": ozone,
                "aqi_value": aqi_value,
                "aqi_category": category,
                "aqi_color": color,
                "primary_pollutant": primary_pollutant,
                "station": aqi_data.get('city', {}).get('name', city_name)
            }
        else:
            raise Exception("WAQI API returned error or no data")
            
    except Exception as e:
        print(f"WAQI city API error: {e}")
        return None

# City coordinates database (enhanced with more global cities)
CITY_COORDINATES = {
    "New York": {"lat": 40.7128, "lon": -74.0060},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
    "Chicago": {"lat": 41.8781, "lon": -87.6298},
    "London": {"lat": 51.5074, "lon": -0.1278},
    "Tokyo": {"lat": 35.6762, "lon": 139.6503},
    "Delhi": {"lat": 28.7041, "lon": 77.1025},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777},
    "Beijing": {"lat": 39.9042, "lon": 116.4074},
    "Shanghai": {"lat": 31.2304, "lon": 121.4737},
    "Bangalore": {"lat": 12.9716, "lon": 77.5946},
    "Chennai": {"lat": 13.0827, "lon": 80.2707},
    "Kolkata": {"lat": 22.5726, "lon": 88.3639},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867},
    "Paris": {"lat": 48.8566, "lon": 2.3522},
    "Berlin": {"lat": 52.5200, "lon": 13.4050},
    "Singapore": {"lat": 1.3521, "lon": 103.8198},
    "Sydney": {"lat": -33.8688, "lon": 151.2093},
    "Dubai": {"lat": 25.2048, "lon": 55.2708},
    "Moscow": {"lat": 55.7558, "lon": 37.6173},
    "Cairo": {"lat": 30.0444, "lon": 31.2357}
}

@app.route('/pollution_api')
def pollution_api():
    lat_raw = request.args.get('lat')
    lon_raw = request.args.get('lon')
    city = request.args.get('city')
    
    # If city is provided, try to get data by city name first
    if city:
        data = fetch_pollution_by_city(city)
        if data:
            return jsonify({'success': True, 'data': data, 'source': 'WAQI_CITY'})
    
    # Fall back to coordinates if city not found or no city provided
    if not lat_raw or not lon_raw:
        return jsonify({'success': False, 'error': 'Missing lat/lon or valid city'}), 400
    
    def clean_coord(s):
        if s is None:
            return None
        s = s.strip()
        s = s.replace('\u00B0', '').replace('°', '')
        m = re.search(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', s)
        return m.group(0) if m else None

    lat = clean_coord(lat_raw)
    lon = clean_coord(lon_raw)
    if not lat or not lon:
        return jsonify({'success': False, 'error': 'Invalid lat or lon'}), 400
    
    try:
        data = fetch_live_pollution(lat, lon)
        if not data:
            return jsonify({'success': False, 'error': 'Failed to fetch pollution data'}), 502
        return jsonify({'success': True, 'data': data, 'source': 'WAQI_GEO'})
    except Exception as e:
        print('pollution_api error:', e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/city_coordinates')
def city_coordinates():
    city = request.args.get('city', '').strip()
    if city in CITY_COORDINATES:
        return jsonify({'success': True, 'data': CITY_COORDINATES[city]})
    else:
        return jsonify({'success': False, 'error': 'City not found'}), 404

# -------------------------
# Templates
# -------------------------
LOGIN_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <title>Login - AI Spirometry Prediction</title>
</head>
<body class="bg-light">
<div class="container py-5">
  <div class="row justify-content-center">
    <div class="col-md-5">
        <div class="card shadow">
            <div class="card-header bg-primary text-white">
                <h5 class="mb-0">Login</h5>
            </div>
            <div class="card-body">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% for category, msg in messages %}
                        <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ msg }}</div>
                    {% endfor %}
                {% endwith %}
                <form method="post">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input class="form-control" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password</label>
                        <input type="password" class="form-control" name="password" required>
                    </div>
                    <button class="btn btn-primary w-100">Login</button>
                </form>
                <hr>
                <p class="mb-0">No account? <a href="{{ url_for('register') }}">Register</a></p>
            </div>
        </div>
    </div>
  </div>
</div>
</body>
</html>
"""

REGISTER_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <title>Register - AI Spirometry Prediction</title>
</head>
<body class="bg-light">
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card shadow">
                <div class="card-header bg-success text-white">
                    <h5 class="mb-0">Create Account</h5>
                </div>
                <div class="card-body">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% for category, msg in messages %}
                            <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ msg }}</div>
                        {% endfor %}
                    {% endwith %}
                    <form method="post">
                        <div class="mb-3">
                            <label class="form-label">Full name (optional)</label>
                            <input class="form-control" name="full_name">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input class="form-control" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Email</label>
                            <input class="form-control" name="email" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Confirm Password</label>
                            <input type="password" class="form-control" name="confirm_password" required>
                        </div>
                        <button class="btn btn-success w-100">Register</button>
                    </form>
                    <hr>
                    <p class="mb-0">Already have account? <a href="{{ url_for('login') }}">Login</a></p>
                </div>
            </div>
        </div>
    </div>
</div>
</body>
</html>
"""

PREDICT_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Spirometry, AQI & Asthma Prediction</title>

  <!-- Bootstrap & Font Awesome -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"/>
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"/>

  <style>
    * { transition: all 0.3s ease; }
    body { 
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      min-height: 100vh;
      background-attachment: fixed;
    }
    .navbar { 
      background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
      box-shadow: 0 4px 20px rgba(0,0,0,0.2);
      backdrop-filter: blur(10px);
    }
    .navbar-brand { 
      font-weight: 700; 
      font-size: 1.5rem;
      text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .card { 
      border-radius: 20px; 
      border: none; 
      box-shadow: 0 10px 40px rgba(0,0,0,0.15);
      backdrop-filter: blur(10px);
      background: rgba(255, 255, 255, 0.95);
      overflow: hidden;
      animation: fadeInUp 0.6s ease;
    }
    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(30px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .card-header { 
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;
      padding: 20px 25px;
      font-weight: 600;
    }
    .card-header.bg-success { 
      background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%) !important;
    }
    .card-header.bg-info { 
      background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
    }
    .card-body { padding: 30px; }
    .feature-section { 
      padding: 25px; 
      background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
      border-radius: 15px; 
      margin-bottom: 25px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.08);
      border-left: 5px solid #667eea;
    }
    .feature-section:hover {
      transform: translateY(-3px);
      box-shadow: 0 8px 25px rgba(0,0,0,0.12);
    }
    .feature-section h6 { 
      color: #1e3c72;
      font-weight: 700;
      margin-bottom: 20px;
      font-size: 1.1rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .form-control, .form-select { 
      border-radius: 12px; 
      padding: 12px 18px;
      border: 2px solid #e0e6ed;
      background: white;
      font-size: 0.95rem;
    }
    .form-control:focus, .form-select:focus { 
      border-color: #667eea;
      box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
      transform: translateY(-2px);
    }
    .form-label { 
      font-weight: 600;
      color: #2c3e50;
      margin-bottom: 8px;
      font-size: 0.9rem;
    }
    .btn-primary { 
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none; 
      padding: 14px 30px;
      font-weight: 600;
      font-size: 1.1rem;
      border-radius: 12px;
      box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }
    .btn-primary:hover { 
      transform: translateY(-3px);
      box-shadow: 0 6px 25px rgba(102, 126, 234, 0.6);
      background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    .btn-success { 
      background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
      border: none; 
      padding: 12px 25px;
      font-weight: 600;
      border-radius: 12px;
      box-shadow: 0 4px 15px rgba(17, 153, 142, 0.3);
    }
    .btn-success:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(17, 153, 142, 0.5);
    }
    .btn-warning { 
      background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
      border: none; 
      padding: 12px 25px;
      font-weight: 600;
      border-radius: 12px;
      color: white;
      box-shadow: 0 4px 15px rgba(245, 87, 108, 0.3);
    }
    .btn-warning:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(245, 87, 108, 0.5);
      color: white;
    }
    .success { 
      color: #11998e; 
      font-weight: 700;
      text-shadow: 1px 1px 2px rgba(17, 153, 142, 0.2);
    }
    .error { 
      color: #e74c3c; 
      font-weight: 700;
      text-shadow: 1px 1px 2px rgba(231, 76, 60, 0.2);
    }
    .predicted-value { 
      background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
      border-left: 5px solid #2196f3;
      padding: 15px 20px;
      margin: 10px 0;
      border-radius: 12px;
      box-shadow: 0 3px 10px rgba(33, 150, 243, 0.15);
    }
    .predicted-value strong { color: #1565c0; }
    .aqi-display { 
      padding: 18px 20px;
      border-radius: 15px;
      color: white;
      font-weight: 700;
      text-align: center;
      font-size: 1.3rem;
      box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .risk-badge { 
      padding: 10px 20px;
      border-radius: 10px;
      color: white;
      font-weight: 700;
      display: inline-block;
      box-shadow: 0 3px 10px rgba(0,0,0,0.2);
      font-size: 1.05rem;
    }
    .alert { 
      border-radius: 12px;
      border: none;
      box-shadow: 0 3px 15px rgba(0,0,0,0.1);
      padding: 15px 20px;
    }
    .alert-warning { 
      background: linear-gradient(135deg, #fff3cd 0%, #ffe5b4 100%);
      color: #856404;
      border-left: 5px solid #ffc107;
    }
    .alert-info { 
      background: linear-gradient(135deg, #d1ecf1 0%, #bee5eb 100%);
      color: #0c5460;
      border-left: 5px solid #17a2b8;
    }
    .nav-links { 
      display: flex;
      gap: 20px;
      align-items: center;
    }
    .nav-links a { 
      color: white;
      text-decoration: none;
      font-weight: 500;
      padding: 8px 16px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.1);
    }
    .nav-links a:hover { 
      background: rgba(255, 255, 255, 0.25);
      transform: translateY(-2px);
      box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    .row { margin-bottom: 15px; }
    hr { 
      border: none;
      height: 2px;
      background: linear-gradient(90deg, transparent, #667eea, transparent);
      margin: 30px 0;
    }
    .container { animation: fadeIn 0.8s ease; }
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
  </style>
</head>

<body>

<!-- ================= NAVBAR ================= -->
<nav class="navbar navbar-expand-lg navbar-dark bg-primary">
  <div class="container">
    <a class="navbar-brand" href="{{ url_for('predict') }}">
      <i class="fas fa-lungs me-2"></i>Respiratory Health AI
    </a>
    <div class="navbar-text text-white ms-auto d-flex align-items-center">
      <span class="me-3">
        <i class="fas fa-user-circle me-2"></i>{{ session.get('full_name', session.get('username', 'User')) }}
      </span>
      <div class="nav-links">
        <a href="{{ url_for('predict') }}" title="New Prediction"><i class="fas fa-plus-circle me-1"></i>New</a>
        <a href="{{ url_for('history') }}" title="View History"><i class="fas fa-history me-1"></i>History</a>
        <a href="{{ url_for('logout') }}" title="Logout"><i class="fas fa-sign-out-alt me-1"></i>Logout</a>
      </div>
    </div>
  </div>
</nav>

<div class="container my-4">

  <!-- ================= FLASH MESSAGES ================= -->
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% for category, msg in messages %}
      <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show">
        {{ msg }}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      </div>
    {% endfor %}
  {% endwith %}

  <!-- ================= SPIROMETRY & AQI RESULT ================= -->
  {% if prediction_result and prediction_result.success %}
  <div class="card mb-4">
    <div class="card-header bg-success text-white">
      <h5><i class="fas fa-chart-line me-2"></i>AQI & Spirometry Analysis Results</h5>
    </div>
    <div class="card-body">
      <div class="row">
        <div class="col-md-6">
          <h6><i class="fas fa-wind me-2" style="color: #667eea;"></i>Air Quality Index</h6>
          <div class="aqi-display" style="background-color: {{ prediction_result.aqi_color }};">
            {{ prediction_result.aqi_value }} - {{ prediction_result.aqi_category }}
          </div>
          <p class="mt-2"><strong>Primary Pollutant:</strong> {{ prediction_result.primary_pollutant }}</p>
          <p><strong>Source:</strong> <span class="badge bg-info">{{ prediction_result.spirometry_source }}</span></p>
        </div>
        <div class="col-md-6">
          <h6><i class="fas fa-heartbeat me-2" style="color: #e74c3c;"></i>Spirometry Results</h6>
          <div class="predicted-value">
            <p><strong>FEV1:</strong> {{ prediction_result.fev1 }} L</p>
            <p><strong>FVC:</strong> {{ prediction_result.fvc }} L</p>
            <p><strong>FEV1/FVC Ratio:</strong> {{ prediction_result.ratio }}</p>
            <p><strong>PEFR:</strong> {{ prediction_result.pefr }} L/min</p>
          </div>
        </div>
      </div>
      
      <hr>
      
      <!-- ================= ASTHMA PREDICTION RESULT ================= -->
      <div class="row mt-3">
        <div class="col-md-6">
          <h6><i class="fas fa-brain me-2" style="color: #667eea;"></i>ML Asthma Assessment</h6>
          <p><strong>Prediction:</strong> 
            {% if prediction_result.ml_prediction == "Asthma Risk" %}
              <span class="error"><i class="fas fa-exclamation-triangle me-1"></i>{{ prediction_result.ml_prediction }}</span>
            {% else %}
              <span class="success"><i class="fas fa-check-circle me-1"></i>{{ prediction_result.ml_prediction }}</span>
            {% endif %}
          </p>
          {% if prediction_result.confidence != "N/A" %}
            <p><strong>Confidence:</strong> {{ prediction_result.confidence }}%</p>
          {% endif %}
          <p><strong>Priority Level:</strong> 
            <span class="risk-badge" style="background-color: {{ prediction_result.severity_color }};">
              {{ prediction_result.priority }}
            </span>
          </p>
        </div>
        <div class="col-md-6">
          <h6><i class="fas fa-shield-alt me-2" style="color: #11998e;"></i>Risk Assessment</h6>
          <p><strong>Risk Level:</strong> 
            <span class="risk-badge" style="background-color: {{ prediction_result.severity_color }};">
              {{ prediction_result.risk_level }}
            </span>
          </p>
          <div class="alert alert-info mt-2">
            <strong>Recommendation:</strong> {{ prediction_result.recommendation }}
          </div>
        </div>
      </div>
    </div>
  </div>
  {% endif %}

  <!-- ================= MAIN PREDICTION FORM ================= -->
  <div class="row">
    <div class="col-lg-8 mx-auto">
      <div class="card">
        <div class="card-header bg-info text-white text-center">
          <h4><i class="fas fa-stethoscope me-2"></i>Spirometry, AQI & Asthma Prediction</h4>
        </div>

        <div class="card-body">
          <form method="POST" action="{{ url_for('predict') }}">
            
            <!-- ================= POLLUTION DATA ================= -->
            <div class="feature-section">
              <h6><i class="fas fa-smog me-2"></i>Air Pollution Data (μg/m³)</h6>
              <div class="alert alert-warning">
                <strong><i class="fas fa-lightbulb me-1"></i>Tip:</strong> Use the "Auto-Fetch" button below to get real-time data from your location
              </div>
              <div class="row">
                <div class="col-md-6">
                  <label class="form-label">PM2.5</label>
                  <input type="number" step="0.1" class="form-control" id="pm2_5" name="pm2_5" value="{{ pollution.pm2_5 if pollution else 50 }}" required>
                </div>
                <div class="col-md-6">
                  <label class="form-label">PM10</label>
                  <input type="number" step="0.1" class="form-control" id="pm10" name="pm10" value="{{ pollution.pm10 if pollution else 80 }}" required>
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">NO2</label>
                  <input type="number" step="0.1" class="form-control" id="no2" name="no2" value="{{ pollution.no2 if pollution else 30 }}" required>
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">SO2</label>
                  <input type="number" step="0.1" class="form-control" id="so2" name="so2" value="{{ pollution.so2 if pollution else 10 }}" required>
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">CO</label>
                  <input type="number" step="0.1" class="form-control" id="co" name="co" value="{{ pollution.co if pollution else 1 }}" required>
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">Ozone (O3)</label>
                  <input type="number" step="0.1" class="form-control" id="ozone" name="ozone" value="{{ pollution.ozone if pollution else 40 }}" required>
                </div>
              </div>
              <div class="mt-3">
                <button type="button" class="btn btn-warning w-100" onclick="autoFetch()">
                  <i class="fas fa-sync-alt me-2"></i>Auto-Fetch Pollution Data
                </button>
              </div>
            </div>

            <!-- ================= LOCATION FOR AQI FETCH ================= -->
            <div class="feature-section">
              <h6><i class="fas fa-map-marker-alt me-2"></i>Location (for Auto-Fetch)</h6>
              <div class="row">
                <div class="col-md-6">
                  <label class="form-label">Location Control</label>
                  <div class="d-flex align-items-center gap-2">
                    <button type="button" id="autoLocBtn" class="btn btn-outline-primary btn-sm" onclick="toggleAutoLocation()">Start Auto-Location</button>
                    <button type="button" id="getLocNowBtn" class="btn btn-outline-secondary btn-sm" onclick="fetchAndUpdateWithGeolocation()">Get Location Now</button>
                    <small class="text-muted ms-2" id="autoLocStatus"></small>
                  </div>
                </div>
                <div class="col-md-3">
                  <label class="form-label">Latitude</label>
                  <input type="text" class="form-control" id="lat" placeholder="e.g. 12.97">
                </div>
                <div class="col-md-3">
                  <label class="form-label">Longitude</label>
                  <input type="text" class="form-control" id="lon" placeholder="e.g. 77.59">
                </div>
              </div>
            </div>

            <!-- ================= SPIROMETRY ================= -->
            <div class="feature-section">
              <h6>Spirometry Measurements</h6>
              <div class="alert alert-info">
                <strong><i class="fas fa-info-circle me-1"></i>Note:</strong> If you have actual spirometry test results, enter them below. Otherwise, values will be estimated from pollution data.
              </div>
              <div class="row">
                <div class="col-md-6">
                  <label class="form-label">FEV1 (L)</label>
                  <input type="number" step="0.01" class="form-control" name="fev1" placeholder="e.g. 3.2">
                </div>
                <div class="col-md-6">
                  <label class="form-label">FVC (L)</label>
                  <input type="number" step="0.01" class="form-control" name="fvc" placeholder="e.g. 4.0">
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">PEFR (L/min)</label>
                  <input type="number" step="0.1" class="form-control" name="pefr" placeholder="e.g. 450">
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">Dust Level (ug/m3)</label>
                  <input type="number" step="0.1" class="form-control" name="dust" placeholder="e.g. 60.0" value="60.0">
                </div>
              </div>
              <div class="mt-3">
                    <label class="form-label">Upload Spirometry Report (PDF/DOC/Image)</label>
                    <input type="file" id="spirometryFile" class="form-control">
                    <button type="button" class="btn btn-success mt-2" onclick="uploadSpirometryFile()">
                      Upload & Auto-Fill
                    </button>
              </div>
              <div class="form-check mt-2">
                <input class="form-check-input" type="checkbox" id="useManualSpirometry" name="use_manual_spirometry">
                <label class="form-check-label" for="useManualSpirometry">
                  I have actual spirometry test results (uncheck to use AI estimation)
                </label>
              </div>
            </div>

            <!-- ================= PATIENT NAME ================= -->
            <div class="feature-section">
              <label class="form-label"><i class="fas fa-id-card me-2"></i>Patient Name</label>
              <input type="text" class="form-control" name="patient_name" value="{{ current_patient_name }}" required>
            </div>

            <!-- ================= SUBMIT BUTTON ================= -->
            <button class="btn btn-primary w-100 btn-lg" type="submit">
              <i class="fas fa-brain me-2"></i>Run Complete AI Analysis
            </button>
            <small class="d-block text-center mt-2 text-muted">
              <i class="fas fa-check-circle me-1"></i>Provides spirometry estimation, AQI analysis, and asthma risk assessment
            </small>
          </form>
        </div>
      </div>
    </div>
  </div>

</div>

<!-- ================= SCRIPTS ================= -->
<script>

function uploadSpirometryFile() {
          const fileInput = document.getElementById('spirometryFile');
          const file = fileInput.files[0];

          if (!file) {
              alert("Please select a file");
              return;
          }

          const formData = new FormData();
          formData.append("file", file);

          fetch("/upload_spirometry", {
              method: "POST",
              body: formData
          })
          .then(res => res.json())
          .then(data => {
              if (data.success) {
                  const values = data.data;

                  if (values.fev1) 
                      document.querySelector('[name="fev1"]').value = values.fev1;

                  if (values.fvc) 
                      document.querySelector('[name="fvc"]').value = values.fvc;

                  if (values.pefr) 
                      document.querySelector('[name="pefr"]').value = values.pefr;

                  alert("Spirometry values auto-filled successfully!");
              } else {
                  alert("Extraction failed: " + data.error);
              }
          })
          .catch(err => alert("Upload failed: " + err));
      }
const pollution = {{ pollution | tojson | default('null') }};

// Using GPS or manual lat/lon only; city-based lookup removed.
function autoFetch(){
  let lat = document.getElementById('lat').value || '';
  let lon = document.getElementById('lon').value || '';
  lat = lat.trim(); lon = lon.trim();

  const sanitize = s => (s||'').replace(/\u00B0/g,'').replace(/°/g,'').replace(/[^0-9\.\-\+eE]/g,'');
  const lat_s = sanitize(lat), lon_s = sanitize(lon);

  if (!lat_s || !lon_s) {
    alert('Please provide valid latitude and longitude or use Get Location Now / Start Auto-Location');
    return;
  }

  const url = '/pollution_api?lat=' + encodeURIComponent(lat_s) + '&lon=' + encodeURIComponent(lon_s);

  fetch(url)
    .then(r => r.json())
    .then(json => {
      if (json && json.success && json.data) {
        const p = json.data;
        document.getElementById('pm2_5').value = Math.round(p.pm2_5 * 100) / 100;
        document.getElementById('pm10').value = Math.round(p.pm10 * 100) / 100;
        document.getElementById('no2').value = Math.round(p.no2 * 100) / 100;
        document.getElementById('so2').value = Math.round(p.so2 * 100) / 100;
        document.getElementById('co').value = Math.round(p.co * 100) / 100;
        document.getElementById('ozone').value = Math.round(p.ozone * 100) / 100;

        let message = `✅ Pollution data updated!\\nAQI: ${p.aqi_value} - ${p.aqi_category}`;
        if (p.station) message += `\\nStation: ${p.station}`;
        alert(message);
      } else {
        alert('❌ Failed to fetch pollution data');
      }
    })
    .catch(e => alert('❌ Network error: ' + e));
}

// Geolocation helper and auto-location controls
function fetchAndUpdateWithGeolocation(){
  if (!navigator.geolocation) { alert('Geolocation not supported'); return; }
  navigator.geolocation.getCurrentPosition(function(position){
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;
    if (document.getElementById('lat')) document.getElementById('lat').value = String(lat);
    if (document.getElementById('lon')) document.getElementById('lon').value = String(lon);
    autoFetch();
  }, function(err){
    console.warn('Geolocation error', err);
    if (err.code === 1) alert('Location permission denied'); else alert('Unable to determine location');
  }, { enableHighAccuracy: true, maximumAge: 60*1000, timeout: 10000 });
}

let autoLocationIntervalId = null;
function updateAutoLocButton(running){
  const btn = document.getElementById('autoLocBtn');
  const status = document.getElementById('autoLocStatus');
  if (!btn) return;
  if (running) {
    btn.textContent = 'Stop Auto-Location'; btn.classList.remove('btn-outline-primary'); btn.classList.add('btn-danger');
    if (status) status.textContent = 'Running (every 10 min)';
  } else {
    btn.textContent = 'Start Auto-Location'; btn.classList.remove('btn-danger'); btn.classList.add('btn-outline-primary');
    if (status) status.textContent = '';
  }
}

function startAutoLocation(){ fetchAndUpdateWithGeolocation(); autoLocationIntervalId = setInterval(fetchAndUpdateWithGeolocation, 10*60*1000); updateAutoLocButton(true); }
function stopAutoLocation(){ if (autoLocationIntervalId) { clearInterval(autoLocationIntervalId); autoLocationIntervalId = null; } updateAutoLocButton(false); }
function toggleAutoLocation(){ if (autoLocationIntervalId) stopAutoLocation(); else startAutoLocation(); }
</script>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

HISTORY_HTML = r"""
                <strong>💡 Tip:</strong> Use the "Auto-Fetch" button below to get real-time data from your location
              </div>
              <div class="row">
                <div class="col-md-6">
                  <label class="form-label">PM2.5</label>
                  <input type="number" step="0.1" class="form-control" id="pm2_5" name="pm2_5" value="{{ pollution.pm2_5 if pollution else 50 }}" required>
                </div>
                <div class="col-md-6">
                  <label class="form-label">PM10</label>
                  <input type="number" step="0.1" class="form-control" id="pm10" name="pm10" value="{{ pollution.pm10 if pollution else 80 }}" required>
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">NO2</label>
                  <input type="number" step="0.1" class="form-control" id="no2" name="no2" value="{{ pollution.no2 if pollution else 30 }}" required>
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">SO2</label>
                  <input type="number" step="0.1" class="form-control" id="so2" name="so2" value="{{ pollution.so2 if pollution else 10 }}" required>
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">CO</label>
                  <input type="number" step="0.1" class="form-control" id="co" name="co" value="{{ pollution.co if pollution else 1 }}" required>
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">Ozone (O3)</label>
                  <input type="number" step="0.1" class="form-control" id="ozone" name="ozone" value="{{ pollution.ozone if pollution else 40 }}" required>
                </div>
              </div>
              <div class="mt-3">
                <button type="button" class="btn btn-warning w-100" onclick="autoFetch()">
                  <i class="fas fa-sync-alt"></i> Auto-Fetch Pollution Data
                </button>
              </div>
            </div>

            <!-- ================= LOCATION FOR AQI FETCH ================= -->
            <div class="feature-section">
              <h6><i class="fas fa-map-marker-alt"></i> Location (for Auto-Fetch)</h6>
              <div class="row">
                <div class="col-md-6">
                  <label class="form-label">Location Control</label>
                  <div class="d-flex align-items-center gap-2">
                    <button type="button" id="autoLocBtn" class="btn btn-outline-primary btn-sm" onclick="toggleAutoLocation()">Start Auto-Location</button>
                    <button type="button" id="getLocNowBtn" class="btn btn-outline-secondary btn-sm" onclick="fetchAndUpdateWithGeolocation()">Get Location Now</button>
                    <small class="text-muted ms-2" id="autoLocStatus"></small>
                  </div>
                </div>
                <div class="col-md-3">
                  <label class="form-label">Latitude</label>
                  <input type="text" class="form-control" id="lat" placeholder="e.g. 12.97">
                </div>
                <div class="col-md-3">
                  <label class="form-label">Longitude</label>
                  <input type="text" class="form-control" id="lon" placeholder="e.g. 77.59">
                </div>
              </div>
            </div>

            <!-- ================= SPIROMETRY ================= -->
            <div class="feature-section">
              <h6>Spirometry Measurements</h6>
              <div class="alert alert-info">
                <strong><i class="fas fa-info-circle me-1"></i>Note:</strong> If you have actual spirometry test results, enter them below. Otherwise, values will be estimated from pollution data.
              </div>
              <div class="row">
                <div class="col-md-6">
                  <label class="form-label">FEV1 (L)</label>
                  <input type="number" step="0.01" class="form-control" name="fev1" placeholder="e.g. 3.2">
                </div>
                <div class="col-md-6">
                  <label class="form-label">FVC (L)</label>
                  <input type="number" step="0.01" class="form-control" name="fvc" placeholder="e.g. 4.0">
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">PEFR (L/min)</label>
                  <input type="number" step="0.1" class="form-control" name="pefr" placeholder="e.g. 450">
                </div>
                <div class="col-md-6 mt-2">
                  <label class="form-label">Dust Level (ug/m3)</label>
                  <input type="number" step="0.1" class="form-control" name="dust" placeholder="e.g. 60.0" value="60.0">
                </div>
              </div>
              <div class="form-check mt-2">
                <input class="form-check-input" type="checkbox" id="useManualSpirometry" name="use_manual_spirometry">
                <label class="form-check-label" for="useManualSpirometry">
                  I have actual spirometry test results (uncheck to use AI estimation)
                </label>
              </div>
            </div>

            <!-- ================= PATIENT NAME ================= -->
            <div class="feature-section">
              <label class="form-label"><i class="fas fa-id-card me-2"></i>Patient Name</label>
              <input type="text" class="form-control" name="patient_name" value="{{ current_patient_name }}" required>
            </div>

            <!-- ================= SUBMIT BUTTON ================= -->
            <button class="btn btn-primary w-100 btn-lg" type="submit">
              <i class="fas fa-brain me-2"></i>Run Complete AI Analysis
            </button>
            <small class="d-block text-center mt-2 text-muted">
              <i class="fas fa-check-circle me-1"></i>Provides spirometry estimation, AQI analysis, and asthma risk assessment
            </small>
          </form>
        </div>
      </div>
    </div>
  </div>

</div>

<!-- ================= SCRIPTS ================= -->
<script>
const pollution = {{ pollution | tojson | default('null') }};

// Using GPS or manual lat/lon only; city-based lookup removed.
function autoFetch(){
  let lat = document.getElementById('lat').value || '';
  let lon = document.getElementById('lon').value || '';
  lat = lat.trim(); lon = lon.trim();

  const sanitize = s => (s||'').replace(/\u00B0/g,'').replace(/°/g,'').replace(/[^0-9\.\-\+eE]/g,'');
  const lat_s = sanitize(lat), lon_s = sanitize(lon);

  if (!lat_s || !lon_s) {
    alert('Please provide valid latitude and longitude or use Get Location Now / Start Auto-Location');
    return;
  }

  const url = '/pollution_api?lat=' + encodeURIComponent(lat_s) + '&lon=' + encodeURIComponent(lon_s);

  fetch(url)
    .then(r => r.json())
    .then(json => {
      if (json && json.success && json.data) {
        const p = json.data;
        document.getElementById('pm2_5').value = Math.round(p.pm2_5 * 100) / 100;
        document.getElementById('pm10').value = Math.round(p.pm10 * 100) / 100;
        document.getElementById('no2').value = Math.round(p.no2 * 100) / 100;
        document.getElementById('so2').value = Math.round(p.so2 * 100) / 100;
        document.getElementById('co').value = Math.round(p.co * 100) / 100;
        document.getElementById('ozone').value = Math.round(p.ozone * 100) / 100;

        let message = `✅ Pollution data updated!\\nAQI: ${p.aqi_value} - ${p.aqi_category}`;
        if (p.station) message += `\\nStation: ${p.station}`;
        alert(message);
      } else {
        alert('❌ Failed to fetch pollution data');
      }
    })
    .catch(e => alert('❌ Network error: ' + e));
}

// Geolocation helper and auto-location controls
function fetchAndUpdateWithGeolocation(){
  if (!navigator.geolocation) { alert('Geolocation not supported'); return; }
  navigator.geolocation.getCurrentPosition(function(position){
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;
    if (document.getElementById('lat')) document.getElementById('lat').value = String(lat);
    if (document.getElementById('lon')) document.getElementById('lon').value = String(lon);
    autoFetch();
  }, function(err){
    console.warn('Geolocation error', err);
    if (err.code === 1) alert('Location permission denied'); else alert('Unable to determine location');
  }, { enableHighAccuracy: true, maximumAge: 60*1000, timeout: 10000 });
}

let autoLocationIntervalId = null;
function updateAutoLocButton(running){
  const btn = document.getElementById('autoLocBtn');
  const status = document.getElementById('autoLocStatus');
  if (!btn) return;
  if (running) {
    btn.textContent = 'Stop Auto-Location'; btn.classList.remove('btn-outline-primary'); btn.classList.add('btn-danger');
    if (status) status.textContent = 'Running (every 10 min)';
  } else {
    btn.textContent = 'Start Auto-Location'; btn.classList.remove('btn-danger'); btn.classList.add('btn-outline-primary');
    if (status) status.textContent = '';
  }
}

function startAutoLocation(){ fetchAndUpdateWithGeolocation(); autoLocationIntervalId = setInterval(fetchAndUpdateWithGeolocation, 10*60*1000); updateAutoLocButton(true); }
function stopAutoLocation(){ if (autoLocationIntervalId) { clearInterval(autoLocationIntervalId); autoLocationIntervalId = null; } updateAutoLocButton(false); }
function toggleAutoLocation(){ if (autoLocationIntervalId) stopAutoLocation(); else startAutoLocation(); }
</script>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

HISTORY_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <title>Prediction History</title>
</head>
<body class="bg-light">
<nav class="navbar navbar-expand-lg navbar-dark bg-primary">
    <div class="container">
        <a class="navbar-brand" href="{{ url_for('predict') }}">🤖 AI Spirometry Prediction</a>
        <div class="ms-auto">
            <a class="nav-link text-white" href="{{ url_for('predict') }}">New Prediction</a>
            <a class="nav-link text-white" href="{{ url_for('logout') }}">Logout</a>
        </div>
    </div>
</nav>

<div class="container my-4">
    <div class="card">
        <div class="card-header">
            <h5>Prediction History</h5>
        </div>
        <div class="card-body">
            {% if records %}
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Patient</th>
                            <th>ML Prediction</th>
                            <th>Risk Level</th>
                            <th>Spirometry Source</th>
                            <th>AQI</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for r in records %}
                        <tr>
                            <td>{{ r[1] }}</td>
                            <td><span style="color:{{ r[5] }}">{{ r[2] }}</span></td>
                            <td>
                                <span class="badge {% if r[8] == 'Low' %}bg-success{% elif r[8] == 'Mild' %}bg-warning{% elif r[8] == 'Moderate' %}bg-warning text-dark{% elif r[8] == 'High' %}bg-danger{% else %}bg-dark{% endif %}">
                                    {{ r[8] }}
                                </span>
                            </td>
                            <td>
                                <span class="badge {% if r[10] == 'AI' %}bg-info{% else %}bg-secondary{% endif %}">
                                    {{ r[10] }}
                                </span>
                            </td>
                            <td><small>{{ r[6] }} ({{ r[7] }})</small></td>
                            <td>{{ r[9] }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <div class="text-center py-4">
                <h5 class="text-muted">No prediction records yet</h5>
                <a class="btn btn-primary" href="{{ url_for('predict') }}">Make Your First Prediction</a>
            </div>
            {% endif %}
        </div>
    </div>
</div>
</body>
</html>
"""

# -------------------------
# Routes
# -------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('predict'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        if not username or not password:
            flash("Enter username and password", "error")
        else:
            user = verify_user(username, password)
            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['full_name'] = user[2] or user[1]
                return redirect(url_for('predict'))
            else:
                flash("Invalid credentials", "error")
    return render_template_string(LOGIN_HTML)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email = request.form.get('email','').strip()
        password = request.form.get('password','')
        confirm = request.form.get('confirm_password','')
        full_name = request.form.get('full_name','').strip()
        if not username or not email or not password or not confirm:
            flash("Fill required fields", "error")
        elif password != confirm:
            flash("Passwords do not match", "error")
        elif len(password) < 6:
            flash("Password min 6 chars", "error")
        elif not validate_email(email):
            flash("Invalid email", "error")
        else:
            ok,msg = register_user(username, password, email, full_name)
            flash(msg, "success" if ok else "error")
            if ok:
                return redirect(url_for('login'))
    return render_template_string(REGISTER_HTML)

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

# -------------------------
# Simple JSON APIs for mobile app (login/register)
# -------------------------

@app.route('/api/login', methods=['POST'])
def api_login():
    """
    JSON login endpoint for the mobile app.
    Expects: { "username": "...", "password": "..." }
    Returns: { "token": "...", "username": "...", "full_name": "..." }
    """
    try:
        data = request.get_json() or {}
        username = (data.get('username') or "").strip()
        password = (data.get('password') or "").strip()

        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        user = verify_user(username, password)
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401

        # We are not validating this token on the server side for now.
        # Mobile app just needs some token string to store.
        token = f"token-{user[0]}"

        return jsonify({
            'token': token,
            'username': user[1],
            'full_name': user[2] or user[1]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/register', methods=['POST'])
def api_register():
    """
    JSON registration endpoint for the mobile app.
    Expects: { "username": "...", "email": "...", "password": "...", "full_name": "..." }
    """
    try:
        data = request.get_json() or {}
        username = (data.get('username') or "").strip()
        email = (data.get('email') or "").strip()
        password = data.get('password') or ""
        full_name = (data.get('full_name') or "").strip()

        if not username or not email or not password:
            return jsonify({'error': 'Username, email and password are required'}), 400
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400

        ok, msg = register_user(username, password, email, full_name)
        if not ok:
            return jsonify({'error': msg}), 400

        return jsonify({'message': 'Registration successful'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict', methods=['POST'])
def api_predict():
    """
    JSON prediction endpoint for mobile app.
    Expects JSON with pollution data, optional manual spirometry, patient name.
    Returns JSON with full prediction results including FEV1, FVC, Ratio, PEFR.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '').strip() if auth_header.startswith('Bearer ') else None
        
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Extract user_id from token (simple format: "token-<user_id>")
        try:
            user_id = int(token.replace('token-', ''))
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        # Get JSON data
        data = request.get_json() or {}
        
        # Extract inputs with defaults
        inputs = {
            'age': int(data.get('age', 35)),
            'gender': data.get('gender', 'Male'),
            'location': data.get('location', 'Urban'),
            'smoking_status': data.get('smoking_status', 'Non-smoker'),
            'physical_activity': data.get('physical_activity', 'Moderate'),
            'occupation': data.get('occupation', 'Office'),
            'diet': data.get('diet', 'Balanced'),
            'pm2_5': float(data.get('pm2_5', 50)),
            'pm10': float(data.get('pm10', 80)),
            'no2': float(data.get('no2', 30)),
            'so2': float(data.get('so2', 10)),
            'co': float(data.get('co', 1)),
            'ozone': float(data.get('ozone', 40)),
            'dust': float(data.get('dust', 60)),
            'pollen': float(data.get('pollen', 40)),
            'indoor_pollutants': float(data.get('indoor_pollutants', 5)),
        }
        
        # Handle spirometry
        use_manual = data.get('use_manual_spirometry', False)
        predicted_spirometry = None
        spirometry_source = "AI"
        
        if use_manual:
            try:
                manual_fev1 = float(data.get('fev1', 0))
                manual_fvc = float(data.get('fvc', 0))
                manual_pefr = float(data.get('pefr', 0))
                manual_ratio = round((manual_fev1 / manual_fvc) if manual_fvc > 0 else 0.0, 3)
                predicted_spirometry = {
                    'fev1': manual_fev1,
                    'fvc': manual_fvc,
                    'ratio': manual_ratio,
                    'pefr': manual_pefr
                }
                inputs['fev1'] = manual_fev1
                inputs['fvc'] = manual_fvc
                inputs['fev1_fvc_ratio'] = manual_ratio
                inputs['pefr'] = manual_pefr
                spirometry_source = "Manual"
            except:
                predicted_spirometry = predict_spirometry_from_pollution(inputs)
                inputs['fev1'] = predicted_spirometry['fev1']
                inputs['fvc'] = predicted_spirometry['fvc']
                inputs['fev1_fvc_ratio'] = predicted_spirometry['ratio']
                inputs['pefr'] = predicted_spirometry['pefr']
                spirometry_source = "AI"
        else:
            predicted_spirometry = predict_spirometry_from_pollution(inputs)
            inputs['fev1'] = predicted_spirometry['fev1']
            inputs['fvc'] = predicted_spirometry['fvc']
            inputs['fev1_fvc_ratio'] = predicted_spirometry['ratio']
            inputs['pefr'] = predicted_spirometry['pefr']
            spirometry_source = "AI"
        
        patient_name = data.get('patient_name', f"Patient_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Calculate AQI
        aqi_data = calculate_comprehensive_aqi(
            inputs.get('pm2_5', 0), inputs.get('pm10', 0), inputs.get('no2', 0),
            inputs.get('so2', 0), inputs.get('co', 0), inputs.get('ozone', 0)
        )
        
        # Asthma ML prediction
        asthma_pred, asthma_prob, priority_text, priority_level = predict_asthma_risk(
            inputs.get('age', 35),
            inputs.get('gender', 'Male'),
            inputs.get('smoking_status', 'Non-smoker'),
            inputs.get('pm2_5', 0),
            inputs.get('dust', 0),
            predicted_spirometry['fev1'],
            predicted_spirometry['fvc'],
            predicted_spirometry['pefr']
        )
        
        # Determine risk level and color
        if asthma_pred is not None:
            ml_prediction = int(asthma_pred)
            confidence = round(asthma_prob * 100, 1) if asthma_prob is not None else 0
            
            if ml_prediction == 1:
                if priority_level == 2:
                    severity_color = "#dc3545"
                    risk_level = "High"
                elif priority_level == 1:
                    severity_color = "#fd7e14"
                    risk_level = "Moderate"
                else:
                    severity_color = "#ffc107"
                    risk_level = "Low-Moderate"
            else:
                severity_color = "#28a745"
                risk_level = "Low"
        else:
            ml_prediction = "N/A"
            confidence = "N/A"
            severity_color = "#6c757d"
            risk_level = priority_text
        
        # Generate AI recommendation
        recommendation = generate_ai_recommendation(
            patient_data=inputs,
            priority_level=risk_level,
            aqi_data=aqi_data,
            spirometry_data=predicted_spirometry
        )
        
        # Save prediction
        save_prediction_record(
            user_id, patient_name, inputs,
            predicted_spirometry,
            aqi_data['aqi_value'], aqi_data['aqi_category'],
            ml_prediction, None,
            ("Manual spirometry provided" if spirometry_source == 'Manual' else "Estimated spirometry from pollution"),
            severity_color, risk_level, recommendation, spirometry_source
        )
        
        # Return JSON result
        return jsonify({
            'success': True,
            'ml_prediction': "Asthma Risk" if ml_prediction == 1 else "No Asthma Risk" if isinstance(ml_prediction, int) else ml_prediction,
            'medical_prediction': priority_text if priority_text else "N/A",
            'prediction_range': ("Manual spirometry provided" if spirometry_source == 'Manual' else "Estimated spirometry from pollution"),
            'severity_color': severity_color,
            'risk_level': risk_level,
            'recommendation': recommendation,
            'aqi_value': aqi_data['aqi_value'],
            'aqi_category': aqi_data['aqi_category'],
            'aqi_color': aqi_data['aqi_color'],
            'primary_pollutant': aqi_data['primary_pollutant'],
            'confidence': confidence,
            'fev1': inputs['fev1'],
            'fvc': inputs['fvc'],
            'ratio': inputs['fev1_fvc_ratio'],
            'pefr': inputs['pefr'],
            'spirometry_source': spirometry_source,
            'patient_name': patient_name,
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET'])
def api_history():
    """
    JSON history endpoint for mobile app.
    Returns list of user's prediction records.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '').strip() if auth_header.startswith('Bearer ') else None
        
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Extract user_id from token
        try:
            user_id = int(token.replace('token-', ''))
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        records = get_user_predictions(user_id)
        
        # Convert to list of dictionaries
        history_list = []
        for record in records:
            history_list.append({
                'id': record[0],
                'patient_name': record[1],
                'ml_prediction': record[2],
                'medical_prediction': record[3],
                'prediction_range': record[4],
                'severity_color': record[5],
                'aqi_value': record[6],
                'aqi_category': record[7],
                'risk_level': record[8],
                'prediction_date': record[9],
                'spirometry_source': record[10],
            })
        
        return jsonify({'records': history_list}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/predict', methods=['GET','POST'])
def predict():
    if 'user_id' not in session:
        flash("Please login first", "error")
        return redirect(url_for('login'))

    feature_groups = request.values.getlist('feature_groups') or ['Demographics','Lifestyle','Air Pollution','Spirometry']

    pollution = None
    lat = request.args.get('lat') or request.values.get('lat')
    lon = request.args.get('lon') or request.values.get('lon')
    city = request.args.get('city')
    
    if city:
        pollution = fetch_pollution_by_city(city)
    elif lat and lon:
        try:
            pollution = fetch_live_pollution(lat, lon)
        except Exception as e:
            print("pollution fetch error", e)

    prediction_result = None

    if request.method == 'POST':
        try:
            # collect inputs with default values for demographics and lifestyle
            inputs = {}
            # Set default demographics (no longer user input)
            inputs['age'] = 35
            inputs['gender'] = 'Male'
            inputs['location'] = 'Urban'
            # Set default lifestyle (no longer user input)
            inputs['smoking_status'] = 'Non-smoker'
            inputs['physical_activity'] = 'Moderate'
            inputs['occupation'] = 'Office'
            inputs['diet'] = 'Balanced'
            
            if 'Air Pollution' in feature_groups:
                inputs['pm2_5'] = float(request.form.get('pm2_5') or 0)
                inputs['pm10'] = float(request.form.get('pm10') or 0)
                inputs['no2'] = float(request.form.get('no2') or 0)
                inputs['so2'] = float(request.form.get('so2') or 0)
                inputs['co'] = float(request.form.get('co') or 0)
                inputs['ozone'] = float(request.form.get('ozone') or 0)
            if 'Environment' in feature_groups:
                inputs['dust'] = float(request.form.get('dust') or 0)
                inputs['pollen'] = float(request.form.get('pollen') or 0)
                inputs['indoor_pollutants'] = float(request.form.get('indoor_pollutants') or 0)
            
            # Spirometry: allow manual input (if provided) or server-side estimation
            use_manual = request.form.get('use_manual_spirometry') in ('on', 'true', '1')
            predicted_spirometry = None
            spirometry_source = "AI"
            if use_manual:
                try:
                    manual_fev1 = float(request.form.get('fev1') or 0)
                    manual_fvc = float(request.form.get('fvc') or 0)
                    manual_pefr = float(request.form.get('pefr') or 0)
                    # compute ratio if possible
                    manual_ratio = round((manual_fev1 / manual_fvc) if manual_fvc > 0 else 0.0, 2)
                    predicted_spirometry = {'fev1': manual_fev1, 'fvc': manual_fvc, 'ratio': manual_ratio, 'pefr': manual_pefr}
                    inputs['fev1'] = manual_fev1
                    inputs['fvc'] = manual_fvc
                    inputs['fev1_fvc_ratio'] = manual_ratio
                    inputs['pefr'] = manual_pefr
                    spirometry_source = "Manual"
                except Exception:
                    # fallback to AI estimation if parsing fails
                    predicted_spirometry = predict_spirometry_from_pollution(inputs)
                    inputs['fev1'] = predicted_spirometry['fev1']
                    inputs['fvc'] = predicted_spirometry['fvc']
                    inputs['fev1_fvc_ratio'] = predicted_spirometry['ratio']
                    inputs['pefr'] = predicted_spirometry['pefr']
                    spirometry_source = "AI"
            else:
                predicted_spirometry = predict_spirometry_from_pollution(inputs)
                inputs['fev1'] = predicted_spirometry['fev1']
                inputs['fvc'] = predicted_spirometry['fvc']
                inputs['fev1_fvc_ratio'] = predicted_spirometry['ratio']
                inputs['pefr'] = predicted_spirometry['pefr']
                spirometry_source = "AI"

            patient_name = request.form.get('patient_name') or f"Patient_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Calculate AQI for reference
            aqi_data = calculate_comprehensive_aqi(
                inputs.get('pm2_5', 0), inputs.get('pm10', 0), inputs.get('no2', 0),
                inputs.get('so2', 0), inputs.get('co', 0), inputs.get('ozone', 0)
            )

            # Asthma ML prediction
            print("\n" + "🔍"*35)
            print("CALLING ASTHMA PREDICTION...")
            asthma_pred, asthma_prob, priority_text, priority_level = predict_asthma_risk(
                inputs.get('age', 35),
                inputs.get('gender', 'Male'),
                inputs.get('smoking_status', 'Non-smoker'),
                inputs.get('pm2_5', 0),
                inputs.get('dust', 0),
                predicted_spirometry['fev1'],
                predicted_spirometry['fvc'],
                predicted_spirometry['pefr']
            )
            
            print(f"\n📋 RECEIVED FROM PREDICTION FUNCTION:")
            print(f"  asthma_pred: {asthma_pred}")
            print(f"  asthma_prob: {asthma_prob}")
            print(f"  priority_text: {priority_text}")
            print(f"  priority_level: {priority_level}")
            
            # Determine prediction and color based on model output
            if asthma_pred is not None:
                ml_prediction = int(asthma_pred)  # Ensure integer
                confidence = round(asthma_prob * 100, 1) if asthma_prob is not None else 0
                
                print(f"\n🎨 DETERMINING UI DISPLAY:")
                print(f"  ML Prediction: {ml_prediction} ({'Asthma Risk' if ml_prediction == 1 else 'No Asthma Risk'})")
                print(f"  Confidence: {confidence}%")
                
                # Determine severity color and risk level based on BOTH prediction AND priority
                # If model predicts asthma risk (1), use priority for severity
                # If model predicts no risk (0), always show low risk
                if ml_prediction == 1:
                    # Asthma risk detected - use priority for severity
                    if priority_level == 2:  # High
                        severity_color = "#dc3545"
                        risk_level = "High"
                    elif priority_level == 1:  # Medium
                        severity_color = "#fd7e14"
                        risk_level = "Moderate"
                    else:  # Low
                        severity_color = "#ffc107"
                        risk_level = "Low-Moderate"
                else:
                    # No asthma risk detected
                    severity_color = "#28a745"
                    risk_level = "Low"
                    
                print(f"  Final Risk Level: {risk_level}")
                print(f"  Color: {severity_color}")
            else:
                ml_prediction = "N/A"
                confidence = "N/A"
                severity_color = "#6c757d"
                risk_level = priority_text
                print(f"\n⚠️  No ML prediction available, using priority: {risk_level}")
            
            print("🔍"*35 + "\n")
            
            # Generate AI-powered recommendation using Gemini
            print("\n" + "="*60)
            print("CALLING generate_ai_recommendation function...")
            print(f"Risk Level: {risk_level}")
            print("="*60 + "\n")
            
            recommendation = generate_ai_recommendation(
                patient_data=inputs,
                priority_level=risk_level,
                aqi_data=aqi_data,
                spirometry_data=predicted_spirometry
            )
            
            print("\n" + "="*60)
            print(f"RECOMMENDATION RECEIVED: {recommendation[:200] if recommendation else 'None'}...")
            print("="*60 + "\n")

            # Save prediction with spirometry values
            save_prediction_record(
                session['user_id'], patient_name, inputs,
                predicted_spirometry,
                aqi_data['aqi_value'], aqi_data['aqi_category'],
                ml_prediction, None,
                ("Manual spirometry provided" if spirometry_source == 'Manual' else "Estimated spirometry from pollution"),
                severity_color, risk_level, recommendation, spirometry_source
            )
            
            print("\n" + "🔍" + "="*60)
            print(f"ADDING TO PREDICTION RESULT:")
            print(f"recommendation = {recommendation[:200] if recommendation else 'None'}...")
            print(f"Type: {type(recommendation)}")
            print("="*60 + "\n")

            prediction_result = {
                'success': True,
                'ml_prediction': "Asthma Risk" if ml_prediction == 1 else "No Asthma Risk" if isinstance(ml_prediction, int) else ml_prediction,
                'medical_prediction': priority_text if priority_text else "N/A",
                'prediction_range': ("Manual spirometry provided" if spirometry_source == 'Manual' else "Estimated spirometry from pollution"),
                'severity_color': severity_color,
                'risk_level': risk_level,
                'recommendation': recommendation,
                'aqi_value': aqi_data['aqi_value'],
                'aqi_category': aqi_data['aqi_category'],
                'aqi_color': aqi_data['aqi_color'],
                'primary_pollutant': aqi_data['primary_pollutant'],
                'confidence': confidence,
                'fev1': inputs['fev1'],
                'fvc': inputs['fvc'],
                'ratio': inputs['fev1_fvc_ratio'],
                'pefr': inputs['pefr'],
                'spirometry_source': spirometry_source,
                'patient_name': patient_name,
                'feature_groups': feature_groups,
                'priority': priority_text
            }
            flash("AI analysis completed successfully!", "success")
        except Exception as e:
            print("Prediction error:", e)
            flash(f"Prediction failed: {str(e)}", "error")

    current_patient_name = f"Patient_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return render_template_string(PREDICT_HTML,
                                  session=session,
                                  prediction_result=prediction_result,
                                  feature_groups=feature_groups,
                                  current_patient_name=current_patient_name,
                                  pollution=pollution,
                                  get_flashed_messages=get_flashed_messages)


# -------------------------
# Simple asthma prediction page (standalone form)
# -------------------------
# Note: the standalone /asthma route and its template were removed per user request.

@app.route('/history')
def history():
    if 'user_id' not in session:
        flash("Please login first", "error")
        return redirect(url_for('login'))
    records = get_user_predictions(session['user_id'])
    return render_template_string(HISTORY_HTML, records=records)

# -------------------------
# Boot
# -------------------------
if __name__ == "__main__":
    # Initialize database (don't delete existing data)
    init_db()
    print("✓ Database initialized successfully")
    print("🚀 Starting AI Spirometry Prediction App on http://0.0.0.0:5000")
    print("🤖 Features: Manual Spirometry Input + AI Prediction Option + Asthma Risk Assessment")
    print(f"📊 ML Model Status: {'✓ Enabled' if asthma_model is not None else '⚠ Disabled (model files not found)'}")
    print(f"🤖 Gemini AI Status: {'✓ Enabled' if gemini_model is not None else '⚠ Disabled (API not configured)'}")
    print("🌍 AQI Data Source: World Air Quality Index (WAQI)")
    print("🫁 Spirometry Input: Users can enter actual test results or use AI prediction")
    print("🔄 Auto-update: Spirometry values update automatically when AI prediction is enabled")
    print("💡 AI Recommendations: Personalized health advice powered by Google Gemini")
    print("📋 Available Routes:")
    print("  /                 -> Home (redirects to login/predict)")
    print("  /login            -> User login")
    print("  /register         -> User registration") 
    print("  /predict          -> Main prediction page")
    print("  /history          -> Prediction history")
    print("  /logout           -> User logout")
    print("  /pollution_api    -> API for real-time pollution data (WAQI)")
    print("  /city_coordinates -> API for city coordinates")
    app.run(debug=True, host="0.0.0.0", port=5000)





