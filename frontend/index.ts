import 'react-native-gesture-handler';
import { registerRootComponent } from 'expo';
import { LogBox } from 'react-native';

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
