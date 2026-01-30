import 'react-native-gesture-handler';
import { registerRootComponent } from 'expo';
import { LogBox, Platform } from 'react-native';
import { initializeApp, getApps } from '@react-native-firebase/app';

// Firebase 명시적 초기화 (설정값 직접 주입)
const firebaseConfig = {
    apiKey: "AIzaSyCfBpPSz3_E6-CeaKaTzNdI_PAVaJ0q9dc",
    appId: "1:415824813180:android:0ba82a925a726241383df9",
    projectId: "ai-5-main-project",
    messagingSenderId: "415824813180",
};

if (Platform.OS !== 'web' && getApps().length === 0) {
    try {
        initializeApp(firebaseConfig);
        console.log('[FCM] Firebase initialized manually in index.ts');
    } catch (e) {
        console.error('[FCM] Firebase manual initialization failed:', e);
    }
}

// 개발 모드에서 처리된 네비게이션 에러 경고 숨기기 (ErrorBoundary에서 처리됨)
LogBox.ignoreLogs([
    "Couldn't find a navigation context",
    "navigation context",
]);

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
