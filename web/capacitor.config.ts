import type { CapacitorConfig } from "@capacitor/cli";

// Native iOS app (ADR 0015): the same React screens, bundled into an Xcode app.
// The API is called cross-origin at VITE_API_BASE (set by scripts/build_ios.sh).
// No fixed background colours: the launch screen and web view follow Light/Dark Mode (ADR 0016).
const config: CapacitorConfig = {
  appId: "com.jeyaviknan.beacon",
  appName: "Beacon",
  webDir: "dist-native",
  ios: {
    contentInset: "never", // the app handles safe areas itself with env(safe-area-inset-*)
    scrollEnabled: true,
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: false, // hidden from JS once the first screen has rendered
      launchShowDuration: 3000,
      showSpinner: false,
    },
  },
};

export default config;
