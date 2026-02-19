# Fix "Value is undefined / EventEmitter" in Expo Go

Follow these steps **in order**. After each step, open the app in Expo Go and see if the error is gone.

---

## Step 1: Clear everything and restart

1. **Close Expo Go** on your phone (swipe it away from recent apps).
2. On your PC, in the terminal where Expo is running, press **Ctrl+C** to stop it.
3. In **Command Prompt** (not PowerShell), run:

```bat
cd C:\Users\Murug\Documents\clg\AIR_QUALITY_RISK_PREDT\air-quality-mobile
rmdir /s /q node_modules\.cache
npx expo start --clear
```

4. When the QR code appears, open **Expo Go** again and scan.  
   Use **Tunnel** in the browser (Connection → Tunnel) if LAN doesn’t work.

---

## Step 2: Same Wi‑Fi and correct IP

1. Phone and PC must be on the **same Wi‑Fi** (not mobile data, not guest network).
2. In `App.js`, around line 20, you have:
   ```js
   const API_BASE = 'http://172.20.10.10:5000';
   ```
3. Find your PC’s IP:
   - Open Command Prompt and run: `ipconfig`
   - Under your Wi‑Fi adapter, find **IPv4 Address** (e.g. 192.168.1.5).
4. If it’s different from `192.168.9.129`, change that line in `App.js` to use your IP, save, then in Expo press **R** to reload.

---

## Step 3: Use Tunnel mode

1. After `npx expo start --clear`, a **browser tab** opens.
2. At the bottom left, set **Connection** to **Tunnel**.
3. Wait until it says **Tunnel ready**.
4. In Expo Go, scan the QR code again (or open the project from **Projects**).

---

## Step 4: Update Expo Go

1. On your phone, open **Play Store** (Android) or **App Store** (iOS).
2. Search for **Expo Go** and tap **Update** if available.
3. Open Expo Go again and try loading the project.

---

## Step 5: If it still fails – try development build (optional)

The error can sometimes be specific to Expo Go. If you have **Android Studio** installed:

1. In the Expo terminal, press **a** to run on the **Android emulator** instead of the phone.
2. See if the same error appears there.

---

## What was changed in the app

- **expo-location** is no longer loaded at startup; it loads only when you tap **“Use my location & fetch pollution”**. That avoids a possible cause of the EventEmitter error.
- **AsyncStorage** is not imported at the top; it’s required only when needed, so the first screen uses only React and React Native.

If the error is still there after Step 1–4, send the **exact error text** (or a screenshot) from the red screen so we can target the next fix.
