/**
 * Respiratory Health AI - Complete Mobile App
 * All features from Flask web app converted to mobile
 */
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
  ActivityIndicator,
  Switch,
} from 'react-native';
import * as Location from 'expo-location';

// API base URL - change to your computer's IP (same WiFi as phone)
const API_BASE = 'http://192.168.1.8:5000';

// Safe storage
let _token = null;
let _userData = null;
let _storageReady = false;

async function setStoredAuth(token, user) {
  _token = token;
  _userData = user;
  try {
    const AsyncStorage = require('@react-native-async-storage/async-storage').default;
    if (AsyncStorage && token && user) {
      await AsyncStorage.setItem('userToken', token);
      await AsyncStorage.setItem('userData', JSON.stringify(user));
    } else if (AsyncStorage) {
      await AsyncStorage.removeItem('userToken');
      await AsyncStorage.removeItem('userData');
    }
  } catch (e) {}
}

async function loadStoredAuth() {
  if (_storageReady) return _token && _userData ? { token: _token, user: _userData } : null;
  try {
    const AsyncStorage = require('@react-native-async-storage/async-storage').default;
    if (!AsyncStorage) return null;
    const token = await AsyncStorage.getItem('userToken');
    const data = await AsyncStorage.getItem('userData');
    _storageReady = true;
    if (token && data) {
      _token = token;
      _userData = JSON.parse(data);
      return { token, user: _userData };
    }
  } catch (e) {}
  _storageReady = true;
  return null;
}

async function api(path, options = {}) {
  const token = _token || (await (async () => {
    try {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      return await AsyncStorage.getItem('userToken');
    } catch (e) { return null; }
  })());
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: options.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    body: options.body != null ? JSON.stringify(options.body) : undefined,
  });
  const data = res.ok ? await res.json().catch(() => ({})) : null;
  if (!res.ok) throw new Error((data && data.error) || 'Request failed');
  return data;
}

export default function App() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [screen, setScreen] = useState('login');

  // Login
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // Register
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirm, setRegConfirm] = useState('');
  const [regFullName, setRegFullName] = useState('');

  // Demographics
  const [age, setAge] = useState('35');
  const [gender, setGender] = useState('Male');
  const [location, setLocation] = useState('Urban');

  // Lifestyle
  const [smokingStatus, setSmokingStatus] = useState('Non-smoker');
  const [physicalActivity, setPhysicalActivity] = useState('Moderate');
  const [occupation, setOccupation] = useState('Office');
  const [diet, setDiet] = useState('Balanced');

  // Air Pollution
  const [pm25, setPm25] = useState('50');
  const [pm10, setPm10] = useState('80');
  const [no2, setNo2] = useState('30');
  const [so2, setSo2] = useState('10');
  const [co, setCo] = useState('1');
  const [ozone, setOzone] = useState('40');

  // Environment
  const [dust, setDust] = useState('60');
  const [pollen, setPollen] = useState('40');
  const [indoorPollutants, setIndoorPollutants] = useState('5');

  // Spirometry
  const [useManualSpirometry, setUseManualSpirometry] = useState(false);
  const [fev1, setFev1] = useState('');
  const [fvc, setFvc] = useState('');
  const [pefr, setPefr] = useState('');

  // Patient & Results
  const [patientName, setPatientName] = useState('Patient');
  const [predictLoading, setPredictLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [locationLoading, setLocationLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const auth = await loadStoredAuth();
        if (!cancelled && auth && auth.user) {
          _token = auth.token;
          setUser(auth.user);
        }
      } catch (e) {}
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const handleLogin = async () => {
    if (!username.trim() || !password) {
      Alert.alert('Error', 'Enter username and password');
      return;
    }
    try {
      const data = await api('/api/login', { method: 'POST', body: { username: username.trim(), password } });
      if (data && data.token) {
        const u = { username: data.username || username, full_name: (data.full_name || data.username || username) };
        await setStoredAuth(data.token, u);
        _token = data.token;
        setUser(u);
        setScreen('predict');
      } else Alert.alert('Error', 'Login failed');
    } catch (e) {
      Alert.alert('Login Failed', e.message || 'Check server and WiFi');
    }
  };

  const handleRegister = async () => {
    if (!regUsername.trim() || !regEmail.trim() || !regPassword || !regConfirm) {
      Alert.alert('Error', 'Fill all fields');
      return;
    }
    if (regPassword !== regConfirm) {
      Alert.alert('Error', 'Passwords do not match');
      return;
    }
    if (regPassword.length < 6) {
      Alert.alert('Error', 'Password at least 6 characters');
      return;
    }
    try {
      await api('/api/register', {
        method: 'POST',
        body: {
          username: regUsername.trim(),
          email: regEmail.trim(),
          password: regPassword,
          full_name: regFullName || regUsername,
        },
      });
      Alert.alert('Success', 'Account created. Please login.');
      setScreen('login');
    } catch (e) {
      Alert.alert('Error', e.message || 'Registration failed');
    }
  };

  const handleLogout = async () => {
    await setStoredAuth(null, null);
    _token = null;
    setUser(null);
    setScreen('login');
  };

  const fetchLocationAndPollution = async () => {
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Error', 'Allow location permission');
        return;
      }
      const loc = await Location.getCurrentPositionAsync({});
      const lat = loc.coords.latitude;
      const lon = loc.coords.longitude;
      const data = await api(`/pollution_api?lat=${lat}&lon=${lon}`);
      if (data && data.success && data.data) {
        const p = data.data;
        setPm25(String(p.pm2_5 != null ? p.pm2_5 : 50));
        setPm10(String(p.pm10 != null ? p.pm10 : 80));
        setNo2(String(p.no2 != null ? p.no2 : 30));
        setSo2(String(p.so2 != null ? p.so2 : 10));
        setCo(String(p.co != null ? p.co : 1));
        setOzone(String(p.ozone != null ? p.ozone : 40));
        Alert.alert('Done', `AQI: ${p.aqi_value} - ${p.aqi_category}`);
      }
    } catch (e) {
      Alert.alert('Error', e.message || 'Failed to fetch');
    } finally {
      setLocationLoading(false);
    }
  };

  const handlePredict = async () => {
    if (!patientName.trim()) {
      Alert.alert('Error', 'Enter patient name');
      return;
    }
    if (useManualSpirometry && (!fev1 || !fvc || !pefr)) {
      Alert.alert('Error', 'Enter all spirometry values (FEV1, FVC, PEFR)');
      return;
    }
    setPredictLoading(true);
    setResult(null);
    try {
      const data = await api('/api/predict', {
        method: 'POST',
        body: {
          patient_name: patientName.trim(),
          age: parseInt(age) || 35,
          gender: gender,
          location: location,
          smoking_status: smokingStatus,
          physical_activity: physicalActivity,
          occupation: occupation,
          diet: diet,
          pm2_5: parseFloat(pm25) || 50,
          pm10: parseFloat(pm10) || 80,
          no2: parseFloat(no2) || 30,
          so2: parseFloat(so2) || 10,
          co: parseFloat(co) || 1,
          ozone: parseFloat(ozone) || 40,
          dust: parseFloat(dust) || 60,
          pollen: parseFloat(pollen) || 40,
          indoor_pollutants: parseFloat(indoorPollutants) || 5,
          use_manual_spirometry: useManualSpirometry,
          fev1: useManualSpirometry ? parseFloat(fev1) : null,
          fvc: useManualSpirometry ? parseFloat(fvc) : null,
          pefr: useManualSpirometry ? parseFloat(pefr) : null,
        },
      });
      setResult(data);
    } catch (e) {
      Alert.alert('Error', e.message || 'Prediction failed');
    } finally {
      setPredictLoading(false);
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await api('/api/history');
      setHistory(Array.isArray(data.records) ? data.records : []);
    } catch (e) {
      Alert.alert('Error', e.message || 'Could not load history');
    } finally {
      setHistoryLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={s.loading}>
        <ActivityIndicator size="large" color="#667eea" />
        <Text style={s.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (!user) {
    if (screen === 'register') {
      return (
        <ScrollView style={s.container} contentContainerStyle={s.pad}>
          <Text style={s.title}>Create Account</Text>
          <TextInput style={s.input} placeholder="Full name (optional)" value={regFullName} onChangeText={setRegFullName} />
          <TextInput style={s.input} placeholder="Username *" value={regUsername} onChangeText={setRegUsername} autoCapitalize="none" />
          <TextInput style={s.input} placeholder="Email *" value={regEmail} onChangeText={setRegEmail} keyboardType="email-address" autoCapitalize="none" />
          <TextInput style={s.input} placeholder="Password *" value={regPassword} onChangeText={setRegPassword} secureTextEntry />
          <TextInput style={s.input} placeholder="Confirm Password *" value={regConfirm} onChangeText={setRegConfirm} secureTextEntry />
          <TouchableOpacity style={s.btn} onPress={handleRegister}>
            <Text style={s.btnText}>Register</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setScreen('login')}>
            <Text style={s.link}>Already have account? Login</Text>
          </TouchableOpacity>
        </ScrollView>
      );
    }
    return (
      <ScrollView style={s.container} contentContainerStyle={s.pad}>
        <Text style={s.bigTitle}>Respiratory Health AI</Text>
        <Text style={s.subtitle}>Air Quality & Asthma Risk</Text>
        <TextInput style={s.input} placeholder="Username" value={username} onChangeText={setUsername} autoCapitalize="none" />
        <TextInput style={s.input} placeholder="Password" value={password} onChangeText={setPassword} secureTextEntry />
        <TouchableOpacity style={s.btn} onPress={handleLogin}>
          <Text style={s.btnText}>Login</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setScreen('register')}>
          <Text style={s.link}>No account? Register</Text>
        </TouchableOpacity>
      </ScrollView>
    );
  }

  if (screen === 'history') {
    return (
      <ScrollView style={s.container} contentContainerStyle={s.pad}>
        <Text style={s.title}>Prediction History</Text>
        <TouchableOpacity style={s.btnSmall} onPress={loadHistory} disabled={historyLoading}>
          <Text style={s.btnText}>{historyLoading ? 'Loading...' : 'Refresh'}</Text>
        </TouchableOpacity>
        {history.length === 0 && !historyLoading && <Text style={s.muted}>No records yet</Text>}
        {history.map((r, i) => (
          <View key={i} style={s.card}>
            <Text style={s.bold}>{r.patient_name || 'Patient'}</Text>
            <Text>Risk: {r.risk_level} | AQI: {r.aqi_value}</Text>
            <Text style={s.small}>{String(r.prediction_date)}</Text>
          </View>
        ))}
        <TouchableOpacity style={s.btnSmall} onPress={() => setScreen('predict')}>
          <Text style={s.btnText}>Back to Predict</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={handleLogout}>
          <Text style={s.link}>Logout</Text>
        </TouchableOpacity>
      </ScrollView>
    );
  }

  // Main Predict Screen with ALL fields
  return (
    <ScrollView style={s.container} contentContainerStyle={s.pad}>
      <Text style={s.title}>Welcome, {user.full_name || user.username}</Text>

      <TouchableOpacity style={s.btnSmall} onPress={fetchLocationAndPollution} disabled={locationLoading}>
        <Text style={s.btnText}>{locationLoading ? 'Fetching...' : '📍 Use my location & fetch pollution'}</Text>
      </TouchableOpacity>

      {/* Demographics */}
      <Text style={s.sectionTitle}>👤 Demographics</Text>
      <View style={s.row}>
        <View style={s.col}>
          <Text style={s.label}>Age</Text>
          <TextInput style={s.input} value={age} onChangeText={setAge} keyboardType="numeric" />
        </View>
        <View style={s.col}>
          <Text style={s.label}>Gender</Text>
          <View style={s.row}>
            <TouchableOpacity style={[s.optionBtn, gender === 'Male' && s.optionBtnActive]} onPress={() => setGender('Male')}>
              <Text style={[s.optionText, gender === 'Male' && s.optionTextActive]}>Male</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.optionBtn, gender === 'Female' && s.optionBtnActive]} onPress={() => setGender('Female')}>
              <Text style={[s.optionText, gender === 'Female' && s.optionTextActive]}>Female</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
      <Text style={s.label}>Location</Text>
      <View style={s.row}>
        {['Urban', 'Rural', 'Semi-Urban'].map(loc => (
          <TouchableOpacity key={loc} style={[s.optionBtn, location === loc && s.optionBtnActive]} onPress={() => setLocation(loc)}>
            <Text style={[s.optionText, location === loc && s.optionTextActive]}>{loc}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Lifestyle */}
      <Text style={s.sectionTitle}>💪 Lifestyle</Text>
      <Text style={s.label}>Smoking Status</Text>
      <View style={s.row}>
        {['Non-smoker', 'Former smoker', 'Current smoker'].map(sm => (
          <TouchableOpacity key={sm} style={[s.optionBtnSmall, smokingStatus === sm && s.optionBtnActive]} onPress={() => setSmokingStatus(sm)}>
            <Text style={[s.optionTextSmall, smokingStatus === sm && s.optionTextActive]}>{sm}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={s.label}>Physical Activity</Text>
      <View style={s.row}>
        {['Low', 'Moderate', 'High'].map(act => (
          <TouchableOpacity key={act} style={[s.optionBtnSmall, physicalActivity === act && s.optionBtnActive]} onPress={() => setPhysicalActivity(act)}>
            <Text style={[s.optionTextSmall, physicalActivity === act && s.optionTextActive]}>{act}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Air Pollution */}
      <Text style={s.sectionTitle}>🌫️ Air Pollution (μg/m³)</Text>
      <View style={s.row}>
        <View style={s.col}>
          <Text style={s.label}>PM2.5</Text>
          <TextInput style={s.input} value={pm25} onChangeText={setPm25} keyboardType="numeric" />
          <Text style={s.label}>PM10</Text>
          <TextInput style={s.input} value={pm10} onChangeText={setPm10} keyboardType="numeric" />
          <Text style={s.label}>NO₂</Text>
          <TextInput style={s.input} value={no2} onChangeText={setNo2} keyboardType="numeric" />
        </View>
        <View style={s.col}>
          <Text style={s.label}>SO₂</Text>
          <TextInput style={s.input} value={so2} onChangeText={setSo2} keyboardType="numeric" />
          <Text style={s.label}>CO</Text>
          <TextInput style={s.input} value={co} onChangeText={setCo} keyboardType="numeric" />
          <Text style={s.label}>O₃</Text>
          <TextInput style={s.input} value={ozone} onChangeText={setOzone} keyboardType="numeric" />
        </View>
      </View>

      {/* Environment */}
      <Text style={s.sectionTitle}>🌍 Environment</Text>
      <View style={s.row}>
        <View style={s.col}>
          <Text style={s.label}>Dust</Text>
          <TextInput style={s.input} value={dust} onChangeText={setDust} keyboardType="numeric" />
        </View>
        <View style={s.col}>
          <Text style={s.label}>Pollen</Text>
          <TextInput style={s.input} value={pollen} onChangeText={setPollen} keyboardType="numeric" />
        </View>
        <View style={s.col}>
          <Text style={s.label}>Indoor</Text>
          <TextInput style={s.input} value={indoorPollutants} onChangeText={setIndoorPollutants} keyboardType="numeric" />
        </View>
      </View>

      {/* Spirometry */}
      <Text style={s.sectionTitle}>🫁 Spirometry</Text>
      <View style={s.switchRow}>
        <Text style={s.label}>Use Manual Values</Text>
        <Switch value={useManualSpirometry} onValueChange={setUseManualSpirometry} />
      </View>
      {useManualSpirometry && (
        <View style={s.row}>
          <View style={s.col}>
            <Text style={s.label}>FEV1 (L)</Text>
            <TextInput style={s.input} value={fev1} onChangeText={setFev1} keyboardType="numeric" placeholder="e.g. 2.5" />
          </View>
          <View style={s.col}>
            <Text style={s.label}>FVC (L)</Text>
            <TextInput style={s.input} value={fvc} onChangeText={setFvc} keyboardType="numeric" placeholder="e.g. 3.2" />
          </View>
          <View style={s.col}>
            <Text style={s.label}>PEFR (L/min)</Text>
            <TextInput style={s.input} value={pefr} onChangeText={setPefr} keyboardType="numeric" placeholder="e.g. 400" />
          </View>
        </View>
      )}

      {/* Patient Name */}
      <Text style={s.sectionTitle}>📋 Patient Information</Text>
      <TextInput style={s.input} placeholder="Patient name" value={patientName} onChangeText={setPatientName} />

      {/* Predict Button */}
      <TouchableOpacity style={s.btn} onPress={handlePredict} disabled={predictLoading}>
        {predictLoading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>🚀 Run AI Analysis</Text>}
      </TouchableOpacity>

      {/* Results */}
      {result != null && (
        <View style={s.result}>
          <Text style={s.resultTitle}>✅ Analysis Results</Text>
          
          <View style={s.resultSection}>
            <Text style={s.resultLabel}>🌬️ Air Quality Index</Text>
            <View style={[s.aqiBox, { backgroundColor: result.aqi_color || '#00e400' }]}>
              <Text style={s.aqiValue}>{result.aqi_value}</Text>
              <Text style={s.aqiCategory}>{result.aqi_category}</Text>
            </View>
            <Text style={s.resultText}>Primary Pollutant: {result.primary_pollutant}</Text>
          </View>

          <View style={s.resultSection}>
            <Text style={s.resultLabel}>🫁 Spirometry Results</Text>
            <Text style={s.resultText}>FEV1: {result.fev1} L</Text>
            <Text style={s.resultText}>FVC: {result.fvc} L</Text>
            <Text style={s.resultText}>FEV1/FVC Ratio: {result.ratio}</Text>
            <Text style={s.resultText}>PEFR: {result.pefr} L/min</Text>
            <Text style={s.resultText}>Source: {result.spirometry_source || 'AI'}</Text>
          </View>

          <View style={s.resultSection}>
            <Text style={s.resultLabel}>⚠️ Asthma Risk Assessment</Text>
            <View style={[s.riskBadge, { backgroundColor: result.severity_color || '#6c757d' }]}>
              <Text style={s.riskBadgeText}>{result.risk_level || 'N/A'}</Text>
            </View>
            <Text style={s.resultText}>Prediction: {result.ml_prediction || 'N/A'}</Text>
            {result.confidence && <Text style={s.resultText}>Confidence: {result.confidence}%</Text>}
          </View>

          <View style={s.resultSection}>
            <Text style={s.resultLabel}>💡 Recommendation</Text>
            <Text style={s.recommendationText}>{result.recommendation || 'No recommendation available'}</Text>
          </View>
        </View>
      )}

      <TouchableOpacity style={s.btnSmall} onPress={() => { setScreen('history'); loadHistory(); }}>
        <Text style={s.btnText}>📋 View History</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={handleLogout}>
        <Text style={s.link}>Logout</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  loading: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f7ff' },
  loadingText: { marginTop: 10, color: '#666' },
  container: { flex: 1, backgroundColor: '#f5f7ff' },
  pad: { padding: 20, paddingBottom: 40 },
  bigTitle: { fontSize: 26, fontWeight: 'bold', color: '#1e3c72', marginBottom: 8, textAlign: 'center' },
  title: { fontSize: 20, fontWeight: 'bold', color: '#1e3c72', marginBottom: 16 },
  subtitle: { fontSize: 14, color: '#666', marginBottom: 24, textAlign: 'center' },
  sectionTitle: { fontSize: 18, fontWeight: 'bold', color: '#1e3c72', marginTop: 20, marginBottom: 12 },
  label: { fontSize: 14, fontWeight: '600', color: '#333', marginTop: 8, marginBottom: 6 },
  input: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#ddd', borderRadius: 10, padding: 12, marginBottom: 8, fontSize: 14 },
  row: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  col: { flex: 1, marginRight: 8 },
  btn: { backgroundColor: '#667eea', borderRadius: 10, padding: 16, alignItems: 'center', marginTop: 20 },
  btnSmall: { backgroundColor: '#11998e', borderRadius: 10, padding: 12, alignItems: 'center', marginTop: 12 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  link: { color: '#667eea', textAlign: 'center', marginTop: 16, fontSize: 14 },
  card: { backgroundColor: '#fff', padding: 12, borderRadius: 10, marginBottom: 10 },
  bold: { fontWeight: 'bold', marginBottom: 4 },
  small: { fontSize: 12, color: '#666', marginTop: 4 },
  muted: { color: '#999', marginTop: 12 },
  optionBtn: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 10, marginRight: 8, alignItems: 'center' },
  optionBtnActive: { backgroundColor: '#667eea', borderColor: '#667eea' },
  optionText: { color: '#333', fontSize: 14 },
  optionTextActive: { color: '#fff', fontWeight: '600' },
  optionBtnSmall: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 8, marginRight: 4, alignItems: 'center' },
  optionTextSmall: { color: '#333', fontSize: 12 },
  switchRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  result: { backgroundColor: '#e8f4fd', padding: 16, borderRadius: 10, marginTop: 20 },
  resultTitle: { fontSize: 20, fontWeight: 'bold', color: '#1e3c72', marginBottom: 16, textAlign: 'center' },
  resultSection: { marginBottom: 16, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#ccc' },
  resultLabel: { fontSize: 16, fontWeight: '600', color: '#333', marginBottom: 8 },
  resultText: { fontSize: 14, color: '#666', marginBottom: 4 },
  aqiBox: { borderRadius: 8, padding: 16, alignItems: 'center', marginVertical: 8 },
  aqiValue: { fontSize: 32, fontWeight: 'bold', color: '#fff' },
  aqiCategory: { fontSize: 14, color: '#fff', marginTop: 4 },
  riskBadge: { borderRadius: 8, padding: 12, alignItems: 'center', marginVertical: 8 },
  riskBadgeText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  recommendationText: { fontSize: 14, color: '#333', lineHeight: 20, marginTop: 4 },
});
