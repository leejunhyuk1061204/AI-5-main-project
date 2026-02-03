import messaging from '@react-native-firebase/messaging';
import { Platform, PermissionsAndroid } from 'react-native';
import { authService } from './auth';
import AsyncStorage from '@react-native-async-storage/async-storage';

class NotificationService {
    /**
     * FCM 권한 요청 및 초기화
     */
    public async requestUserPermission() {
        if (Platform.OS === 'android' && Platform.Version >= 33) {
            const granted = await PermissionsAndroid.request(
                PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS
            );
            if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
                console.log('Permission for notifications denied');
                return false;
            }
        }

        const authStatus = await messaging().requestPermission();
        const enabled =
            authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
            authStatus === messaging.AuthorizationStatus.PROVISIONAL;

        if (enabled) {
            console.log('Authorization status:', authStatus);
        }
        return enabled;
    }

    /**
     * FCM 토큰 발급 및 서버 동기화
     */
    public async registerFcmToken() {
        try {
            // 1. 권한 확인
            const hasPermission = await this.requestUserPermission();
            if (!hasPermission) return;

            // 2. 토큰 가져오기 (이미 발급된 토큰이 있으면 가져옴)
            const fcmToken = await messaging().getToken();

            if (fcmToken) {
                console.log('[FCM] Token issued:', fcmToken);

                // 3. 서버에 저장되어 있는 토큰과 비교 (불필요한 네트워크 호출 방지)
                const savedToken = await AsyncStorage.getItem('savedFcmToken');
                const accessToken = await AsyncStorage.getItem('accessToken');

                if (accessToken && fcmToken !== savedToken) {
                    // 4. 서버로 토큰 전송
                    const response = await authService.updateFcmToken(fcmToken);
                    if (response.success) {
                        console.log('[FCM] Successfully registered token to server');
                        await AsyncStorage.setItem('savedFcmToken', fcmToken);
                    }
                }
            }
        } catch (error) {
            console.error('[FCM] Failed to register token:', error);
        }
    }

    /**
     * 토큰 갱신 리스너 설정
     */
    public setupTokenRefreshListener() {
        return messaging().onTokenRefresh(async (token) => {
            console.log('[FCM] Token refreshed:', token);
            const accessToken = await AsyncStorage.getItem('accessToken');
            if (accessToken) {
                const response = await authService.updateFcmToken(token);
                if (response.success) {
                    await AsyncStorage.setItem('savedFcmToken', token);
                }
            }
        });
    }
}

export default new NotificationService();
