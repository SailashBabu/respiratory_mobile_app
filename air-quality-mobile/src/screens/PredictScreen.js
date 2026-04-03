// src/screens/PredictScreen.js
import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
  Switch,
  ActivityIndicator,
} from 'react-native';
import * as Location from 'expo-location';
import * as DocumentPicker from 'expo-document-picker';
import { useAuth } from '../../App';
import { apiPollution, apiPredict, apiUploadSpirometry } from '../api';

export default function PredictScreen({ navigation }) {
  const { user } = useAuth();
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [pollution, setPollution] = useState({
    pm2_5: '50',
    pm10: '80',
    no2: '30',
    so2: '10',
    co: '1',
    ozone: '40',
  });
  const [useManualSpirometry, setUseManualSpirometry] = useState(false);
  const [fev1, setFev1] = useState('');
  const [fvc, setFvc] = useState('');
  const [pefr, setPefr] = useState('');
  const [dust, setDust] = useState('60');
  const [patientName, setPatientName] = useState(`Patient_${Date.now()}`);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetchingLocation, setFetchingLocation] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState('');

  const handleGetLocation = async () => {
    try {
      setFetchingLocation(true);
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required to fetch pollution data');
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      const latStr = String(location.coords.latitude);
      const lonStr = String(location.coords.longitude);
      setLat(latStr);
      setLon(lonStr);

      // Fetch pollution data
      const json = await apiPollution(latStr, lonStr);
      if (json.success && json.data) {
        const p = json.data;
        setPollution({
          pm2_5: String(p.pm2_5 || 50),
          pm10: String(p.pm10 || 80),
          no2: String(p.no2 || 30),
          so2: String(p.so2 || 10),
          co: String(p.co || 1),
          ozone: String(p.ozone || 40),
        });
        Alert.alert(
          'Success',
          `Pollution data fetched!\nAQI: ${p.aqi_value} - ${p.aqi_category}`
        );
      } else {
        Alert.alert('Error', 'Failed to fetch pollution data');
      }
    } catch (error) {
      Alert.alert('Error', error.message || 'Failed to get location or fetch pollution data');
    } finally {
      setFetchingLocation(false);
    }
  };

  const handleUploadSpirometry = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          'application/pdf',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'image/*',
        ],
        copyToCacheDirectory: true,
      });

      if (result.canceled || result.type === 'cancel') {
        return;
      }

      const asset = result.assets ? result.assets[0] : result;
      const uri = asset.uri;
      const name = asset.name || 'spirometry_report';
      const mimeType =
        asset.mimeType ||
        (name.toLowerCase().endsWith('.pdf')
          ? 'application/pdf'
          : name.toLowerCase().endsWith('.docx')
          ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
          : 'application/octet-stream');

      if (!uri) {
        Alert.alert('Error', 'Could not read selected file');
        return;
      }

      setUploading(true);
      setSelectedFileName(name);

      const data = await apiUploadSpirometry(uri, name, mimeType);

      if (data.success && data.data) {
        const { fev1: fev1Val, fvc: fvcVal, pefr: pefrVal } = data.data;

        if (fev1Val != null || fvcVal != null || pefrVal != null) {
          setUseManualSpirometry(true);
          if (fev1Val != null) setFev1(String(fev1Val));
          if (fvcVal != null) setFvc(String(fvcVal));
          if (pefrVal != null) setPefr(String(pefrVal));
          Alert.alert('Success', 'Spirometry values extracted from report.');
        } else {
          Alert.alert('Info', 'Could not extract spirometry values from the uploaded file.');
        }
      } else {
        Alert.alert('Upload Failed', data.error || 'Server did not return extracted values.');
      }
    } catch (error) {
      Alert.alert('Upload Failed', error.message || 'Failed to upload spirometry report.');
    } finally {
      setUploading(false);
    }
  };

  const handlePredict = async () => {
    // Validation
    if (!patientName.trim()) {
      Alert.alert('Error', 'Please enter patient name');
      return;
    }

    if (useManualSpirometry) {
      if (!fev1 || !fvc || !pefr) {
        Alert.alert('Error', 'Please enter all spirometry values (FEV1, FVC, PEFR)');
        return;
      }
    }

    try {
      setLoading(true);
      const payload = {
        pm2_5: parseFloat(pollution.pm2_5) || 50,
        pm10: parseFloat(pollution.pm10) || 80,
        no2: parseFloat(pollution.no2) || 30,
        so2: parseFloat(pollution.so2) || 10,
        co: parseFloat(pollution.co) || 1,
        ozone: parseFloat(pollution.ozone) || 40,
        dust: parseFloat(dust) || 60,
        patient_name: patientName.trim(),
        use_manual_spirometry: useManualSpirometry,
        fev1: useManualSpirometry ? parseFloat(fev1) : null,
        fvc: useManualSpirometry ? parseFloat(fvc) : null,
        pefr: useManualSpirometry ? parseFloat(pefr) : null,
      };

      const data = await apiPredict(user.token, payload);
      setResult(data);
      
      // Scroll to result (if needed, you can add ref to ScrollView)
      Alert.alert('Success', 'Analysis completed! Scroll down to see results.');
    } catch (error) {
      Alert.alert('Prediction Failed', error.message || 'Server error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.welcomeText}>Welcome, {user.full_name || user.username}</Text>
      </View>

      {/* Location & Pollution Section */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>📍 Location & Air Pollution</Text>
        
        <View style={styles.row}>
          <View style={styles.col}>
            <Text style={styles.label}>Latitude</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. 12.9716"
              value={lat}
              onChangeText={setLat}
              keyboardType="numeric"
            />
          </View>
          <View style={styles.col}>
            <Text style={styles.label}>Longitude</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. 77.5946"
              value={lon}
              onChangeText={setLon}
              keyboardType="numeric"
            />
          </View>
        </View>

        <TouchableOpacity
          style={[styles.locationButton, fetchingLocation && styles.buttonDisabled]}
          onPress={handleGetLocation}
          disabled={fetchingLocation}
        >
          {fetchingLocation ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.locationButtonText}>📍 Use Current Location & Fetch Pollution</Text>
          )}
        </TouchableOpacity>

        <View style={styles.pollutionGrid}>
          <View style={styles.pollutionCol}>
            <Text style={styles.label}>PM2.5 (μg/m³)</Text>
            <TextInput
              style={styles.input}
              value={pollution.pm2_5}
              onChangeText={(v) => setPollution({ ...pollution, pm2_5: v })}
              keyboardType="numeric"
            />
            <Text style={styles.label}>PM10 (μg/m³)</Text>
            <TextInput
              style={styles.input}
              value={pollution.pm10}
              onChangeText={(v) => setPollution({ ...pollution, pm10: v })}
              keyboardType="numeric"
            />
            <Text style={styles.label}>NO₂ (μg/m³)</Text>
            <TextInput
              style={styles.input}
              value={pollution.no2}
              onChangeText={(v) => setPollution({ ...pollution, no2: v })}
              keyboardType="numeric"
            />
          </View>
          <View style={styles.pollutionCol}>
            <Text style={styles.label}>SO₂ (μg/m³)</Text>
            <TextInput
              style={styles.input}
              value={pollution.so2}
              onChangeText={(v) => setPollution({ ...pollution, so2: v })}
              keyboardType="numeric"
            />
            <Text style={styles.label}>CO (mg/m³)</Text>
            <TextInput
              style={styles.input}
              value={pollution.co}
              onChangeText={(v) => setPollution({ ...pollution, co: v })}
              keyboardType="numeric"
            />
            <Text style={styles.label}>O₃ (μg/m³)</Text>
            <TextInput
              style={styles.input}
              value={pollution.ozone}
              onChangeText={(v) => setPollution({ ...pollution, ozone: v })}
              keyboardType="numeric"
            />
          </View>
        </View>
      </View>

      {/* Spirometry Section */}
      <View style={styles.card}>
        <View style={styles.switchRow}>
          <Text style={styles.cardTitle}>🫁 Spirometry</Text>
          <View style={styles.switchContainer}>
            <Text style={styles.switchLabel}>
              {useManualSpirometry ? 'Manual' : 'AI Estimation'}
            </Text>
            <Switch
              value={useManualSpirometry}
              onValueChange={setUseManualSpirometry}
              trackColor={{ false: '#ccc', true: '#667eea' }}
              thumbColor={useManualSpirometry ? '#fff' : '#f4f3f4'}
            />
          </View>
        </View>

        {useManualSpirometry && (
          <View style={styles.spirometryRow}>
            <View style={styles.col}>
              <Text style={styles.label}>FEV1 (L)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. 2.5"
                value={fev1}
                onChangeText={setFev1}
                keyboardType="numeric"
              />
            </View>
            <View style={styles.col}>
              <Text style={styles.label}>FVC (L)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. 3.2"
                value={fvc}
                onChangeText={setFvc}
                keyboardType="numeric"
              />
            </View>
            <View style={styles.col}>
              <Text style={styles.label}>PEFR (L/min)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. 400"
                value={pefr}
                onChangeText={setPefr}
                keyboardType="numeric"
              />
            </View>
          </View>
        )}

        <View style={styles.uploadSection}>
          <Text style={styles.label}>Upload Spirometry Report (PDF/DOC/Image)</Text>
          <TouchableOpacity
            style={[styles.uploadButton, uploading && styles.buttonDisabled]}
            onPress={handleUploadSpirometry}
            disabled={uploading}
          >
            {uploading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.uploadButtonText}>
                {selectedFileName
                  ? `Uploaded: ${selectedFileName}`
                  : '📄 Choose File & Auto-Fill'}
              </Text>
            )}
          </TouchableOpacity>
        </View>

        <Text style={styles.label}>Dust Level (μg/m³)</Text>
        <TextInput
          style={styles.input}
          value={dust}
          onChangeText={setDust}
          keyboardType="numeric"
        />
      </View>

      {/* Patient Name */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>👤 Patient Information</Text>
        <Text style={styles.label}>Patient Name</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter patient name"
          value={patientName}
          onChangeText={setPatientName}
        />
      </View>

      {/* Action Buttons */}
      <TouchableOpacity
        style={[styles.predictButton, loading && styles.buttonDisabled]}
        onPress={handlePredict}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.predictButtonText}>🚀 Run AI Analysis</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.historyButton}
        onPress={() => navigation.navigate('History')}
      >
        <Text style={styles.historyButtonText}>📋 View History</Text>
      </TouchableOpacity>

      {/* Results Section */}
      {result && (
        <View style={styles.resultCard}>
          <Text style={styles.resultTitle}>✅ Analysis Results</Text>
          
          <View style={styles.resultSection}>
            <Text style={styles.resultLabel}>Air Quality Index</Text>
            <View style={[styles.aqiBox, { backgroundColor: result.aqi_color || '#00e400' }]}>
              <Text style={styles.aqiValue}>{result.aqi_value}</Text>
              <Text style={styles.aqiCategory}>{result.aqi_category}</Text>
            </View>
            <Text style={styles.resultText}>Primary Pollutant: {result.primary_pollutant}</Text>
          </View>

          <View style={styles.resultSection}>
            <Text style={styles.resultLabel}>Spirometry Results</Text>
            <Text style={styles.resultText}>FEV1: {result.fev1} L</Text>
            <Text style={styles.resultText}>FVC: {result.fvc} L</Text>
            <Text style={styles.resultText}>FEV1/FVC Ratio: {result.ratio}</Text>
            <Text style={styles.resultText}>PEFR: {result.pefr} L/min</Text>
            <Text style={styles.resultText}>Source: {result.spirometry_source || 'AI'}</Text>
          </View>

          <View style={styles.resultSection}>
            <Text style={styles.resultLabel}>Asthma Risk Assessment</Text>
            <View style={[styles.riskBadge, { backgroundColor: result.severity_color || '#6c757d' }]}>
              <Text style={styles.riskBadgeText}>{result.risk_level || 'N/A'}</Text>
            </View>
            <Text style={styles.resultText}>Prediction: {result.ml_prediction || 'N/A'}</Text>
            {result.confidence && (
              <Text style={styles.resultText}>Confidence: {result.confidence}%</Text>
            )}
          </View>

          <View style={styles.resultSection}>
            <Text style={styles.resultLabel}>💡 Recommendation</Text>
            <Text style={styles.recommendationText}>{result.recommendation || 'No recommendation available'}</Text>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f7ff',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  header: {
    marginBottom: 16,
  },
  welcomeText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1e3c72',
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1e3c72',
    marginBottom: 12,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  col: {
    flex: 1,
    marginRight: 8,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    color: '#333',
    marginBottom: 6,
    marginTop: 8,
  },
  input: {
    backgroundColor: '#f8f9fa',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: '#333',
  },
  locationButton: {
    backgroundColor: '#667eea',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
    marginBottom: 16,
  },
  locationButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  pollutionGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  pollutionCol: {
    flex: 1,
    marginRight: 8,
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  switchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  switchLabel: {
    marginRight: 8,
    fontSize: 14,
    color: '#666',
  },
  spirometryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  predictButton: {
    backgroundColor: '#11998e',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 12,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  predictButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  historyButton: {
    backgroundColor: '#667eea',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
    marginBottom: 20,
  },
  historyButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  buttonDisabled: {
    backgroundColor: '#999',
  },
  resultCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 6,
  },
  resultTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#1e3c72',
    marginBottom: 16,
    textAlign: 'center',
  },
  resultSection: {
    marginBottom: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  resultLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  resultText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  aqiBox: {
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginVertical: 8,
  },
  aqiValue: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
  },
  aqiCategory: {
    fontSize: 14,
    color: '#fff',
    marginTop: 4,
  },
  riskBadge: {
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    marginVertical: 8,
  },
  riskBadgeText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  recommendationText: {
    fontSize: 14,
    color: '#333',
    lineHeight: 20,
    marginTop: 4,
  },
  uploadSection: {
    marginTop: 8,
    marginBottom: 12,
  },
  uploadButton: {
    backgroundColor: '#ff7e5f',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: 'center',
    marginTop: 4,
  },
  uploadButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
});
