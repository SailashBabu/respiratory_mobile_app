// src/api.js - API helper functions
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ⚠️ IMPORTANT: Change this to your Flask server IP address
// For Android emulator: use http://10.0.2.2:5000
// For iOS simulator: use http://localhost:5000
// For physical device: use http://YOUR_COMPUTER_IP:5000 (e.g., http://192.168.1.5:5000)
const API_BASE_URL = 'http://172.20.10.10:5000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests if available
api.interceptors.request.use(
  async (config) => {
    try {
      const token = await AsyncStorage.getItem('userToken');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (e) {
      // ignore
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Login API
export async function apiLogin(username, password) {
  try {
    const response = await api.post('/api/login', {
      username: username.trim(),
      password: password,
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.error || 'Login failed');
    } else if (error.request) {
      throw new Error('Network error. Check if Flask server is running.');
    } else {
      throw new Error('Login request failed');
    }
  }
}

// Register API
export async function apiRegister(data) {
  try {
    const response = await api.post('/api/register', {
      username: data.username.trim(),
      email: data.email.trim(),
      password: data.password,
      full_name: data.full_name || '',
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.error || 'Registration failed');
    } else if (error.request) {
      throw new Error('Network error. Check if Flask server is running.');
    } else {
      throw new Error('Registration request failed');
    }
  }
}

// Predict API
export async function apiPredict(token, payload) {
  try {
    const response = await api.post('/predict', payload, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.error || 'Prediction failed');
    } else if (error.request) {
      throw new Error('Network error. Check if Flask server is running.');
    } else {
      throw new Error('Prediction request failed');
    }
  }
}

// History API
export async function apiHistory(token) {
  try {
    const response = await api.get('/history', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.error || 'Failed to fetch history');
    } else if (error.request) {
      throw new Error('Network error. Check if Flask server is running.');
    } else {
      throw new Error('History request failed');
    }
  }
}

// Pollution API (already exists in your Flask app)
export async function apiPollution(lat, lon) {
  try {
    const response = await api.get('/pollution_api', {
      params: {
        lat: lat,
        lon: lon,
      },
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.error || 'Failed to fetch pollution data');
    } else if (error.request) {
      throw new Error('Network error. Check if Flask server is running.');
    } else {
      throw new Error('Pollution API request failed');
    }
  }
}

export default api;
