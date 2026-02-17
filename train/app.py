# =====================================================
# ASTHMA PREDICTION STREAMLIT APP
# XGBOOST + PRIORITY LEVEL FEATURE
# =====================================================

import streamlit as st
import numpy as np
import joblib

# -------------------------------
# LOAD MODEL & SCALER
# -------------------------------
model = joblib.load("xgboost_asthma_priority_20epochs.pkl")
scaler = joblib.load("xgboost_priority_scaler.pkl")

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="Asthma Prediction with Priority Level",
    layout="centered"
)

st.title("🫁 Asthma Prediction System")
st.write("XGBoost-based asthma prediction with **priority risk assessment**")

# -------------------------------
# INPUT SECTION
# -------------------------------
age = st.number_input("Age", min_value=1, max_value=100, value=30)

gender = st.selectbox("Gender", ["Male", "Female"])
smoking = st.selectbox("Smoking Habit", ["No", "Occasional", "Yes"])

pm25 = st.slider("PM2.5 Level (µg/m³)", 0.0, 150.0, 35.0)
dust = st.slider("Dust Level", 0.0, 150.0, 30.0)

fev1 = st.slider("FEV1 (L)", 0.5, 5.0, 2.5)
fvc = st.slider("FVC (L)", 1.0, 6.0, 3.5)
pefr = st.slider("PEFR (L/min)", 100, 800, 400)

# -------------------------------
# ENCODE CATEGORICAL FEATURES
# -------------------------------
gender_map = {"Male": 0, "Female": 1}
smoking_map = {"No": 0, "Occasional": 1, "Yes": 2}

gender_encoded = gender_map[gender]
smoking_encoded = smoking_map[smoking]

# -------------------------------
# PRIORITY LEVEL LOGIC
# (Must match training code exactly)
# -------------------------------
def assign_priority(fev1, pefr, pm25, dust):
    if fev1 < 2.0 and pefr < 300 and pm25 > 60:
        return 2   # High priority
    elif pm25 > 40 or dust > 40 or fev1 < 2.5:
        return 1   # Medium priority
    else:
        return 0   # Low priority

priority_level = assign_priority(fev1, pefr, pm25, dust)

priority_text = {0: "Low", 1: "Medium", 2: "High"}[priority_level]

# -------------------------------
# PREDICTION
# -------------------------------
if st.button("🔍 Predict Asthma Status"):
    
    input_data = np.array([[
        age,
        pm25,
        dust,
        fev1,
        fvc,
        pefr,
        gender_encoded,
        smoking_encoded,
        priority_level
    ]])

    # Scale input
    input_scaled = scaler.transform(input_data)

    # Model prediction
    prediction = model.predict(input_scaled)[0]
    probability = model.predict_proba(input_scaled)[0][1]

    st.markdown("---")

    # -------------------------------
    # OUTPUT SECTION
    # -------------------------------
    st.subheader("📊 Prediction Result")

    st.write(f"**Priority Level:** {priority_text}")

    if prediction == 1:
        st.error("⚠️ **Asthma Detected**")
        st.write(f"Confidence: **{probability * 100:.2f}%**")
    else:
        st.success("✅ **Normal (No Asthma)**")
        st.write(f"Confidence: **{(1 - probability) * 100:.2f}%**")

# -------------------------------
# FOOTER
# -------------------------------
st.markdown("---")
st.caption("Model: XGBoost | Feature Engineering: Priority Level | Dataset: Corrected Asthma Dataset")
