// src/screens/HistoryScreen.js
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Alert,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { apiHistory } from '../api';
import { useAuth } from '../../App';

export default function HistoryScreen({ navigation }) {
  const { user } = useAuth();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadHistory = async () => {
    try {
      const response = await apiHistory(user.token);
      // Handle both array format and object with records property
      const records = Array.isArray(response) ? response : (response.records || []);
      setData(records);
    } catch (error) {
      Alert.alert('Error', error.message || 'Could not load history');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadHistory();
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return dateString;
    }
  };

  const getRiskColor = (riskLevel) => {
    if (!riskLevel) return '#6c757d';
    const level = riskLevel.toLowerCase();
    if (level.includes('high')) return '#dc3545';
    if (level.includes('moderate') || level.includes('medium')) return '#fd7e14';
    if (level.includes('low')) return '#28a745';
    return '#6c757d';
  };

  const renderItem = ({ item }) => {
    // Handle both object format and array format from backend
    const patientName = item.patient_name || item[1] || 'Unknown';
    const mlPrediction = item.ml_prediction || item[2] || 'N/A';
    const riskLevel = item.risk_level || item[8] || 'N/A';
    const aqiValue = item.aqi_value || item[6] || 'N/A';
    const aqiCategory = item.aqi_category || item[7] || 'N/A';
    const spirometrySource = item.spirometry_source || item[10] || 'N/A';
    const date = item.prediction_date || item[9] || 'N/A';

    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.patientName}>{patientName}</Text>
          <View style={[styles.riskBadge, { backgroundColor: getRiskColor(riskLevel) }]}>
            <Text style={styles.riskBadgeText}>{riskLevel}</Text>
          </View>
        </View>

        <View style={styles.cardBody}>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Asthma Prediction:</Text>
            <Text style={styles.infoValue}>{mlPrediction}</Text>
          </View>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>AQI:</Text>
            <Text style={styles.infoValue}>{aqiValue} ({aqiCategory})</Text>
          </View>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Spirometry Source:</Text>
            <View style={[styles.sourceBadge, spirometrySource === 'Manual' ? styles.sourceManual : styles.sourceAI]}>
              <Text style={styles.sourceBadgeText}>{spirometrySource}</Text>
            </View>
          </View>

          <Text style={styles.dateText}>{formatDate(date)}</Text>
        </View>
      </View>
    );
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#667eea" />
        <Text style={styles.loadingText}>Loading history...</Text>
      </View>
    );
  }

  if (data.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyIcon}>📋</Text>
        <Text style={styles.emptyText}>No prediction history yet</Text>
        <Text style={styles.emptySubtext}>Make your first prediction to see results here</Text>
        <TouchableOpacity
          style={styles.emptyButton}
          onPress={() => navigation.navigate('Predict')}
        >
          <Text style={styles.emptyButtonText}>Go to Prediction</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={data}
        renderItem={renderItem}
        keyExtractor={(item, index) => String(item.id || item[0] || index)}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f7ff',
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f5f7ff',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#666',
  },
  listContent: {
    padding: 16,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  patientName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1e3c72',
    flex: 1,
  },
  riskBadge: {
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  riskBadgeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  cardBody: {
    marginTop: 8,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  infoLabel: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  infoValue: {
    fontSize: 14,
    color: '#333',
    fontWeight: '600',
  },
  sourceBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  sourceManual: {
    backgroundColor: '#e3f2fd',
  },
  sourceAI: {
    backgroundColor: '#f3e5f5',
  },
  sourceBadgeText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#333',
  },
  dateText: {
    fontSize: 12,
    color: '#999',
    marginTop: 8,
    fontStyle: 'italic',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
    backgroundColor: '#f5f7ff',
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginBottom: 24,
  },
  emptyButton: {
    backgroundColor: '#667eea',
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  emptyButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
});
