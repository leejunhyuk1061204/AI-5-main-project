import { Buffer } from 'buffer';
global.Buffer = global.Buffer || Buffer;

import 'react-native-gesture-handler';
import { registerRootComponent } from 'expo';
import { LogBox, Platform } from 'react-native';
// Firebase는 안드로이드 네이티브(google-services 플러그인)를 통해 자동으로 초기화되므로
// 자바스크립트 단에서의 명시적 초기화는 제거했습니다.

// 개발 모드에서 처리된 네비게이션 에러 경고 숨기기 (ErrorBoundary에서 처리됨)
LogBox.ignoreLogs([
    "Couldn't find a navigation context",
    "navigation context",
]);

// 콘솔 로그를 파일로 저장할 수 있도록 LogBuffer에 복사
import { LogBuffer } from './services/LogBuffer';
const originalLog = console.log;
const originalWarn = console.warn;
const originalError = console.error;
console.log = (...args: unknown[]) => {
    LogBuffer.append('log', ...args);
    originalLog.apply(console, args);
};
console.warn = (...args: unknown[]) => {
    LogBuffer.append('warn', ...args);
    originalWarn.apply(console, args);
};
console.error = (...args: unknown[]) => {
    LogBuffer.append('error', ...args);
    originalError.apply(console, args);
};

// FCM Background Message Handler (Must be defined early and outside React lifecycle)
import fcmService from './services/fcmService';
fcmService.setupBackgroundHandler();

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
