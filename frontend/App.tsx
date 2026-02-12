import './global.css';
import { StatusBar } from 'expo-status-bar';
import { View, Text, Platform, Keyboard, AppState } from 'react-native';
import * as ExpoSplashScreen from 'expo-splash-screen';
import { useState, useEffect, useCallback, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { NavigationContainer, DarkTheme, useNavigationContainerRef } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as NavigationBar from 'expo-navigation-bar';
import * as SystemUI from 'expo-system-ui';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { GlobalErrorBoundary } from './components/common/GlobalErrorBoundary';
import CustomErrorModal from './components/common/CustomErrorModal';

import { useVehicleStore } from './store/useVehicleStore';
import { useUIStore } from './store/useUIStore';
import { useUserStore } from './store/useUserStore';
import ObdService from './services/ObdService';
import BackgroundService from './services/BackgroundService';
import fcmService from './services/fcmService';
import { authService } from './services/auth';
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
import ObdResult from './registration/active/ObdResult';
import PassiveReg from './registration/passive/PassiveReg';
import MaintenanceReg from './registration/passive/MaintenanceReg';
import MyPage from './setting/MyPage';
import DiagMain from './diagnosis/DiagMain';
import ObdDiagLoading from './diagnosis/ObdDiagLoading';

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
import ObdConnectFlow from './setting/ObdConnectFlow';
import VisualDiagnosis from './diagnosis/VisualDiagnosis';
import AiDiagChat from './diagnosis/AiDiagChat';
import DiagnosisReport from './diagnosis/DiagnosisReport';
import DiagnosisHistory from './diagnosis/DiagnosisHistory';
import Cloud from './setting/Cloud';
import Membership from './setting/Membership';
import ChatCameraScreen from './diagnosis/ChatCameraScreen';
import ChatAudioScreen from './diagnosis/ChatAudioScreen';
import MaintenanceBook from './maintenance/MaintenanceBook';
import ReceiptScan from './maintenance/ReceiptScan';
import ReceiptResult from './maintenance/ReceiptResult';
import ReceiptGallery from './maintenance/ReceiptGallery';
import PaymentSuccess from './payment/PaymentSuccess';
import MaintenanceHistory from './history/MaintenanceHistory';
import DrivingList from './history/DrivingList';
import Elm327TestScreen from './obd-test/Elm327TestScreen';
import TripDetail from './history/TripDetail';

// Deep Linking Configuration
const linking = {
  prefixes: ['frontend://', 'exp+frontend://'], // Expo Go용 접두사 포함 (필요시)
  config: {
    screens: {
      PaymentSuccess: 'payment/success',
      // 다른 화면들도 필요하면 추가
    },
  },
};

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
  const navigationRef = useNavigationContainerRef();
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

        // 1) 약관 동의는 로그인 여부와 무관하게 앱 최초/미동의 시 먼저 표시
        const hasAgreed = await AsyncStorage.getItem('hasAgreedToTos');
        if (hasAgreed !== 'true') {
          setInitialRoute('Tos');
        } else {
          // 2) 동의 후 로그인 유지 여부에 따라 초기 화면 결정 (refreshToken 기준)
          const refreshToken = await AsyncStorage.getItem('refreshToken');
          if (refreshToken) {
            try {
              const newAccessToken = await authService.refreshAccessToken();
              if (!newAccessToken) {
                await AsyncStorage.multiRemove(['accessToken', 'refreshToken']);
                setInitialRoute('Login');
              } else {
                await loadUser();
                const vehicles = await fetchVehicles();
                console.log('[App] Auto-login: loading OBD devices and starting background reconnect');
                await ObdService.loadAndCacheDevices();
                ObdService.startBackgroundReconnectIfNeeded().catch((e) => {
                  console.warn('[App] startBackgroundReconnectIfNeeded failed during auto-login', e);
                });

                // FCM 토큰 발급 및 서버 동기화 (자동 로그인 시)
                await fcmService.registerFcmToken();

                if (vehicles.length > 0) {
                  setInitialRoute('MainPage');
                } else {
                  setInitialRoute('RegisterMain');
                }
              }
            } catch (e) {
              console.error("Failed to restore session or fetch vehicles on startup", e);
              setInitialRoute('Login');
            }
          } else {
            setInitialRoute('Login');
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

    // FCM 토큰 갱신 리스너 등록
    const unsubscribe = fcmService.setupTokenRefreshListener();

    return () => {
      showListener.remove();
      hideListener.remove();
      if (unsubscribe) unsubscribe();
    };
  }, []);

  // 4. FCM Initialization (로그인 후)
  useEffect(() => {
    const initializeFcm = async () => {
      const token = await AsyncStorage.getItem('accessToken');
      if (token) {
        // 로그인된 상태에서만 FCM 초기화
        await fcmService.initialize();
        fcmService.setupForegroundHandler();
        // 알림 클릭 시 화면 이동 핸들러 (navigationRef 전달)
        fcmService.setupNotificationOpenedHandler(navigationRef);
      }
    };

    initializeFcm();
  }, [initialRoute]);

  // 3. Background Service Handling (P0: active 시 디바운스 후 stop으로 플랩핑 방지)
  const activeStopDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ACTIVE_STOP_DEBOUNCE_MS = 2500;

  useEffect(() => {
    const subscription = AppState.addEventListener('change', async (nextAppState) => {
      if (nextAppState === 'background') {
        if (activeStopDebounceRef.current) {
          clearTimeout(activeStopDebounceRef.current);
          activeStopDebounceRef.current = null;
        }
        if (ObdService.isConnected()) {
          await BackgroundService.start();
        }
      }
    });

    return () => {
      subscription.remove();
      if (activeStopDebounceRef.current) {
        clearTimeout(activeStopDebounceRef.current);
        activeStopDebounceRef.current = null;
      }
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
    <GlobalErrorBoundary>
      <SafeAreaProvider>
        <KeyboardProvider>
          <NavigationContainer theme={AppTheme} linking={linking}>
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
                  <Stack.Screen name="Elm327Test" component={Elm327TestScreen} />
                  <Stack.Screen name="SignUp" component={SignUp} />
                  <Stack.Screen name="FindPW" component={FindPW} />
                  <Stack.Screen
                    name="MainPage"
                    component={MainTabNavigator}
                    options={{ animation: 'none' }}
                  />
                  <Stack.Screen name="RegisterMain" component={RegisterMain} />
                  <Stack.Screen name="ActiveReg" component={ActiveReg} />
                  <Stack.Screen name="ObdResult" component={ObdResult} />
                  <Stack.Screen name="PassiveReg" component={PassiveReg} />
                  <Stack.Screen name="MaintenanceReg" component={MaintenanceReg} />
                  <Stack.Screen name="EngineSoundDiag" component={EngineSoundDiag} />
                  <Stack.Screen name="ObdDiagLoading" component={ObdDiagLoading} options={{ headerShown: false }} />

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
                  <Stack.Screen name="ObdConnectFlow" component={ObdConnectFlow} />
                  <Stack.Screen name="Cloud" component={Cloud} />
                  <Stack.Screen name="Membership" component={Membership} />
                  <Stack.Screen name="MaintenanceBook" component={MaintenanceBook} />
                  <Stack.Screen name="ReceiptScan" component={ReceiptScan} />
                  <Stack.Screen name="ReceiptResult" component={ReceiptResult} />
                  <Stack.Screen name="ReceiptGallery" component={ReceiptGallery} />
                  <Stack.Screen name="PaymentSuccess" component={PaymentSuccess} />
                  <Stack.Screen name="MaintenanceHistory" component={MaintenanceHistory} />
                  <Stack.Screen name="DrivingList" component={DrivingList} />
                  <Stack.Screen name="TripDetail" component={TripDetail} />
                </Stack.Navigator>
                <GlobalAlert />
                <GlobalDatePicker />
                <CustomErrorModal />
              </>
            )}
          </NavigationContainer>
        </KeyboardProvider>
      </SafeAreaProvider>
    </GlobalErrorBoundary>
  );
}
