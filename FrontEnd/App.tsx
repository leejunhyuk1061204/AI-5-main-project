import './global.css';
import { StatusBar } from 'expo-status-bar';
import { View, Text, Platform } from 'react-native';
import * as ExpoSplashScreen from 'expo-splash-screen';
import { useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as NavigationBar from 'expo-navigation-bar';
import * as SystemUI from 'expo-system-ui';

import Tos from './sign/Tos';
import Login from './sign/Login';
import SignUp from './sign/SignUp';
import FindPW from './sign/FindPW';
import MainPage from './mainPage/MainPage';
import SplashScreenComponent from './splash/SplashScreen';
import RegisterMain from './ register/RegisterMain';
import ActiveReg from './ register/active/ActiveReg';
import ActiveLoading from './ register/active/ActiveLoading';
import ActiveSuccess from './ register/active/ActiveSuccess';
import PassiveReg from './ register/passive/PassiveReg';
import DiagMain from './diagnosis/DiagMain';
import HistoryMain from './history/HistoryMain';
import AlertMain from './alert/AlertMain';

// Keep the splash screen visible while we fetch resources
ExpoSplashScreen.preventAutoHideAsync();

const Stack = createNativeStackNavigator();

const AppTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: '#101922', // Match app background-dark
  },
};

export default function App() {
  const [appIsReady, setAppIsReady] = useState(false);
  const [initialRoute, setInitialRoute] = useState<string>('Tos');
  const [showCustomSplash, setShowCustomSplash] = useState(true);

  useEffect(() => {
    async function prepare() {
      try {
        // Set Root View Background Color
        await SystemUI.setBackgroundColorAsync("#101922");

        // Set Android Navigation Bar Color
        if (Platform.OS === 'android') {
          await NavigationBar.setBackgroundColorAsync("#101922");
          await NavigationBar.setButtonStyleAsync("light");
        }

        // Check Tos agreement
        const hasAgreed = await AsyncStorage.getItem('hasAgreedToTos');
        if (hasAgreed === 'true') {
          setInitialRoute('Login');
        } else {
          setInitialRoute('Tos');
        }
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
      await ExpoSplashScreen.hideAsync();
    }
  }, [appIsReady]);

  if (!appIsReady) {
    return null;
  }

  // Show Custom Splash until animation finishes
  if (showCustomSplash) {
    return (
      <SafeAreaProvider>
        <View className="flex-1" onLayout={onLayoutRootView}>
          <SplashScreenComponent onFinish={() => setShowCustomSplash(false)} />
          <StatusBar style="light" />
        </View>
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <NavigationContainer theme={AppTheme}>
        <StatusBar style="auto" />
        <Stack.Navigator
          initialRouteName={initialRoute}
          screenOptions={{
            headerShown: false,
            animation: 'slide_from_right',
            contentStyle: { backgroundColor: '#101922' }
          }}
        >
          <Stack.Screen name="Tos" component={Tos} />
          <Stack.Screen name="Login" component={Login} />
          <Stack.Screen name="SignUp" component={SignUp} />
          <Stack.Screen name="FindPW" component={FindPW} />
          <Stack.Screen
            name="MainPage"
            component={MainPage}
          />
          <Stack.Screen name="RegisterMain" component={RegisterMain} />
          <Stack.Screen name="ActiveReg" component={ActiveReg} />
          <Stack.Screen name="ActiveLoading" component={ActiveLoading} />
          <Stack.Screen name="ActiveSuccess" component={ActiveSuccess} />
          <Stack.Screen name="PassiveReg" component={PassiveReg} />
          <Stack.Screen name="DiagMain" component={DiagMain} />
          <Stack.Screen name="HistoryMain" component={HistoryMain} />
          <Stack.Screen name="AlertMain" component={AlertMain} />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
