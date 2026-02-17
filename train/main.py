from flask import Flask, render_template, request
import numpy as np
import joblib

app = Flask(__name__)

# -------------------------------
# LOAD MODEL & SCALER
# -------------------------------
model = joblib.load("xgboost_asthma_priority_20epochs.pkl")
scaler = joblib.load("xgboost_priority_scaler.pkl")

# -------------------------------
# PRIORITY LEVEL LOGIC
# -------------------------------
def assign_priority(fev1, pefr, pm25, dust):
    if fev1 < 2.0 and pefr < 300 and pm25 > 60:
        return 2   # High
    elif pm25 > 40 or dust > 40 or fev1 < 2.5:
        return 1   # Medium
    else:
        return 0   # Low

# -------------------------------
# ROUTES
# -------------------------------
@app.route("/", methods=["GET", "POST"])
def index():

    result = None

    if request.method == "POST":
        age = int(request.form["age"])
        gender = request.form["gender"]
        smoking = request.form["smoking"]

        pm25 = float(request.form["pm25"])
        dust = float(request.form["dust"])
        fev1 = float(request.form["fev1"])
        fvc = float(request.form["fvc"])
        pefr = float(request.form["pefr"])

        # Encoding
        gender_map = {"Male": 0, "Female": 1}
        smoking_map = {"No": 0, "Occasional": 1, "Yes": 2}

        gender_encoded = gender_map[gender]
        smoking_encoded = smoking_map[smoking]

        # Priority
        priority = assign_priority(fev1, pefr, pm25, dust)
        priority_text = {0: "Low", 1: "Medium", 2: "High"}[priority]

        # Feature Order MUST MATCH training
        input_data = np.array([[ 
            age, pm25, dust, fev1, fvc, pefr,
            gender_encoded, smoking_encoded, priority
        ]])

        input_scaled = scaler.transform(input_data)

        prediction = model.predict(input_scaled)[0]
        probability = model.predict_proba(input_scaled)[0][1]

        result = {
            "prediction": prediction,
            "probability": probability,
            "priority": priority_text
        }

    return render_template("index.html", result=result)

# -------------------------------
# RUN APP
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)
