import './global.css';
import { StatusBar } from 'expo-status-bar';
import { View, Text } from 'react-native';
import SplashScreen from './splash/SplashScreen';
import * as ExpoSplashScreen from 'expo-splash-screen';
import { useState, useEffect, useCallback } from 'react';

// Keep the splash screen visible while we fetch resources
ExpoSplashScreen.preventAutoHideAsync();

export default function App() {
  const [appIsReady, setAppIsReady] = useState(false);
  const [showCustomSplash, setShowCustomSplash] = useState(true);

  useEffect(() => {
    async function prepare() {
      try {
        // Pre-load fonts, make any API calls you need to do here
        // Artificially delay for demonstration if needed, but here we just proceed
      } catch (e) {
        console.warn(e);
      } finally {
        // Tell the application to render
        setAppIsReady(true);
      }
    }

    prepare();
  }, []);

  const onLayoutRootView = useCallback(async () => {
    if (appIsReady) {
      // This tells the native splash screen to hide immediately!
      // We do this as soon as we are ready to show our custom splash
      await ExpoSplashScreen.hideAsync();
    }
  }, [appIsReady]);

  if (!appIsReady) {
    return null;
  }

  // Show Custom Splash until animation finishes
  if (showCustomSplash) {
    return (
      <View className="flex-1" onLayout={onLayoutRootView}>
        <SplashScreen onFinish={() => setShowCustomSplash(false)} />
        <StatusBar style="light" />
      </View>
    );
  }

  // Main App Content
  return (
    <View className="flex-1 items-center justify-center bg-white">
      <Text className="text-xl font-bold text-black">Main App Content</Text>
      <StatusBar style="dark" />
    </View>
  );
}
