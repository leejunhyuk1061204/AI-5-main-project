import './global.css';
import { StatusBar } from 'expo-status-bar';
import { View, Text, Platform, Keyboard, AppState } from 'react-native';
import * as ExpoSplashScreen from 'expo-splash-screen';
import { useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as NavigationBar from 'expo-navigation-bar';
import * as SystemUI from 'expo-system-ui';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

import { useVehicleStore } from './store/useVehicleStore';
import { useUIStore } from './store/useUIStore';
import { useUserStore } from './store/useUserStore';
import ObdService from './services/ObdService';
import BackgroundService from './services/BackgroundService';
import GlobalAlert from './components/common/GlobalAlert';
import GlobalDatePicker from './components/common/GlobalDatePicker';
import BottomNav from './nav/BottomNav';

import Tos from './sign/Tos';
import Login from './sign/Login';
import SignUp from './sign/SignUp';
import FindPW from './sign/FindPW';
import MainPage from './mainPage/MainPage';
import SplashScreenComponent from './splash/SplashScreen';
import RegisterMain from './registration/RegisterMain';
import ActiveReg from './registration/active/ActiveReg';
import ActiveLoading from './registration/active/ActiveLoading';
import ActiveSuccess from './registration/active/ActiveSuccess';
import ObdResult from './registration/active/ObdResult';
import PassiveReg from './registration/passive/PassiveReg';
import MaintenanceReg from './registration/passive/MaintenanceReg';
import MyPage from './setting/MyPage';
import DiagMain from './diagnosis/DiagMain';
import EngineSoundDiag from './diagnosis/EngineSoundDiag';
import AiCompositeDiag from './diagnosis/AiCompositeDiag';
import AiProfessionalDiag from './diagnosis/AiProfessionalDiag';
import Filming from './filming/Filming';
import HistoryMain from './history/HistoryMain';
import DrivingHis from './history/DrivingHis';
import RecallHis from './history/RecallHis';
import SupManage from './history/SupManage';
import AlertMain from './alert/AlertMain';
import Spec from './history/spec';
import AlertSetting from './setting/AlertSetting';
import SettingMain from './setting/SettingMain';
import CarManage from './setting/CarManage';
import CarEdit from './setting/CarEdit';
import VisualDiagnosis from './diagnosis/VisualDiagnosis';
import AiDiagChat from './diagnosis/AiDiagChat';
import DiagnosisReport from './diagnosis/DiagnosisReport';
import DiagnosisHistory from './diagnosis/DiagnosisHistory';
import Cloud from './setting/Cloud';
import Membership from './setting/Membership';
import ChatCameraScreen from './diagnosis/ChatCameraScreen';
import ChatAudioScreen from './diagnosis/ChatAudioScreen';

// Keep the splash screen visible while we fetch resources
ExpoSplashScreen.preventAutoHideAsync();

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function MainTabNavigator() {
  return (
    <Tab.Navigator
      tabBar={(props: any) => <BottomNav {...props} />}
      screenOptions={{
        headerShown: false,
      }}
    >
      <Tab.Screen name="MainHome" component={MainPage} />
      <Tab.Screen name="DiagTab" component={DiagMain} />
      <Tab.Screen name="HistoryTab" component={HistoryMain} />
      <Tab.Screen name="SettingTab" component={SettingMain} />
    </Tab.Navigator>
  );
}

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

  const loadFromStorage = useVehicleStore(state => state.loadFromStorage);
  const fetchVehicles = useVehicleStore(state => state.fetchVehicles);
  const loadUser = useUserStore(state => state.loadUser);
  const setKeyboardVisible = useUIStore(state => state.setKeyboardVisible);

  useEffect(() => {
    // 1. Initialize Global Stores
    loadFromStorage();

    // 2. Global Keyboard Listeners (keyboard-controller polyfills 'Will' events on Android)
    const showEvent = 'keyboardWillShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';

    const showListener = Keyboard.addListener(showEvent, () => setKeyboardVisible(true));
    const hideListener = Keyboard.addListener(hideEvent, () => setKeyboardVisible(false));

    async function prepare() {
      try {
        // Set Root View Background Color
        await SystemUI.setBackgroundColorAsync("#101922");

        // Set Android Navigation Bar Color
        if (Platform.OS === 'android') {
          // Edge-to-Edge support: transparent background
          await NavigationBar.setBackgroundColorAsync("transparent");
          await NavigationBar.setButtonStyleAsync("light");
        }

        // Check for persistent login
        const token = await AsyncStorage.getItem('accessToken');
        if (token) {
          try {
            await loadUser(); // 사용자 정보 미리 로드
            const vehicles = await fetchVehicles();
            if (vehicles.length > 0) {
              setInitialRoute('MainPage');
            } else {
              setInitialRoute('RegisterMain');
            }
          } catch (e) {
            console.error("Failed to fetch vehicles on startup", e);
            setInitialRoute('Login');
          }
        } else {
          // Check Tos agreement
          const hasAgreed = await AsyncStorage.getItem('hasAgreedToTos');
          if (hasAgreed === 'true') {
            setInitialRoute('Login');
          } else {
            setInitialRoute('Tos');
          }
        }
      } catch (e) {
        console.warn(e);
      } finally {
        // Tell the application to render
        setAppIsReady(true);
      }
    }

    prepare();

    return () => {
      showListener.remove();
      hideListener.remove();
    };
  }, []);

  // 3. Background Service Handling
  useEffect(() => {
    const subscription = AppState.addEventListener('change', async (nextAppState) => {
      if (nextAppState === 'background') {
        // 앱이 백그라운드로 갈 때, OBD가 연결되어 있다면 백그라운드 서비스 시작
        if (ObdService.isConnected()) {
          await BackgroundService.start();
        }
      } else if (nextAppState === 'active') {
        // 앱이 포그라운드로 오면 백그라운드 알림 제거 (서비스 중지)
        await BackgroundService.stop();
      }
    });

    return () => {
      subscription.remove();
    };
  }, []);

  const onLayoutRootView = useCallback(async () => {
    if (appIsReady) {
      await ExpoSplashScreen.hideAsync();
    }
  }, [appIsReady]);

  if (!appIsReady) {
    return null;
  }

  // NavigationContainer는 항상 마운트되어야 함 (useNavigation 등 훅이 정상 작동하도록)
  return (
    <SafeAreaProvider>
      <KeyboardProvider>
        <NavigationContainer theme={AppTheme}>
          {showCustomSplash ? (
            // 스플래시 화면 표시
            <View className="flex-1" onLayout={onLayoutRootView}>
              <SplashScreenComponent onFinish={() => setShowCustomSplash(false)} />
              <StatusBar style="light" />
            </View>
          ) : (
            // 메인 앱 네비게이션
            <>
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
                  component={MainTabNavigator}
                  options={{ animation: 'none' }}
                />
                <Stack.Screen name="RegisterMain" component={RegisterMain} />
                <Stack.Screen name="ActiveReg" component={ActiveReg} />
                <Stack.Screen name="ActiveLoading" component={ActiveLoading} />
                <Stack.Screen name="ActiveSuccess" component={ActiveSuccess} />
                <Stack.Screen name="ObdResult" component={ObdResult} />
                <Stack.Screen name="PassiveReg" component={PassiveReg} />
                <Stack.Screen name="MaintenanceReg" component={MaintenanceReg} />
                <Stack.Screen name="EngineSoundDiag" component={EngineSoundDiag} />
                <Stack.Screen
                  name="AiCompositeDiag"
                  component={AiCompositeDiag}
                  options={{ animation: 'none' }}
                />
                <Stack.Screen name="AiProfessionalDiag" component={AiProfessionalDiag} />
                <Stack.Screen name="AiDiagChat" component={AiDiagChat} />
                <Stack.Screen name="DiagnosisReport" component={DiagnosisReport} />
                <Stack.Screen name="DiagnosisHistory" component={DiagnosisHistory} />
                <Stack.Screen name="VisualDiagnosis" component={VisualDiagnosis} />
                <Stack.Screen name="Filming" component={Filming} />
                <Stack.Screen name="ChatCameraScreen" component={ChatCameraScreen} />
                <Stack.Screen name="ChatAudioScreen" component={ChatAudioScreen} />
                <Stack.Screen name="DrivingHis" component={DrivingHis} />
                <Stack.Screen name="RecallHis" component={RecallHis} />
                <Stack.Screen name="SupManage" component={SupManage} />
                <Stack.Screen
                  name="AlertMain"
                  component={AlertMain}
                  options={{ animation: 'none' }}
                />
                <Stack.Screen name="Spec" component={Spec} />
                <Stack.Screen name="MyPage" component={MyPage} />
                <Stack.Screen name="AlertSetting" component={AlertSetting} />
                <Stack.Screen name="CarManage" component={CarManage} />
                <Stack.Screen name="CarEdit" component={CarEdit} />
                <Stack.Screen name="Cloud" component={Cloud} />
                <Stack.Screen name="Membership" component={Membership} />
              </Stack.Navigator>
              <GlobalAlert />
              <GlobalDatePicker />
            </>
          )}
        </NavigationContainer>
      </KeyboardProvider>
    </SafeAreaProvider>
  );
}
