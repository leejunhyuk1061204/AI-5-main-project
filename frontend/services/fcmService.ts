import { Platform, PermissionsAndroid } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import messaging from '@react-native-firebase/messaging';
import firebase from '@react-native-firebase/app';
import { authService } from './auth';
import { useAlertStore } from '../store/useAlertStore';

/**
 * FCM 알림 데이터 타입
 */
export interface NotificationData {
    type?: string;
    sessionId?: string;
    tripId?: string;
    itemCode?: string;
    remainingKm?: string;
    score?: string;
    distance?: string;
    [key: string]: string | undefined;
}

/**
 * FCM 서비스
 */
class FcmService {
    private initialized = false;

    /**
     * FCM 권한 요청 및 초기화 (Android 13+ 대응)
     */
    public async requestUserPermission() {
        if (Platform.OS === 'android' && Platform.Version >= 33) {
            const granted = await PermissionsAndroid.request(
                PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS
            );
            if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
                console.log('[FCM] Permission for notifications denied');
                return false;
            }
        }

        const authStatus = await messaging().requestPermission();
        const enabled =
            authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
            authStatus === messaging.AuthorizationStatus.PROVISIONAL;

        if (enabled) {
            console.log('[FCM] Authorization status:', authStatus);
        }
        return enabled;
    }

    /**
     * FCM 초기화 및 토큰 등록
     */
    async initialize() {
        if (this.initialized) {
            console.log('[FCM] Already initialized');
            return;
        }

        try {
            if (firebase.apps.length === 0) {
                console.error('[FCM] Firebase App not initialized');
                return;
            }

            const enabled = await this.requestUserPermission();
            if (!enabled) return;

            await this.registerFcmToken();
            this.setupTokenRefreshListener();

            this.initialized = true;
            console.log('[FCM] Initialization complete');
        } catch (error) {
            console.error('[FCM] Initialization failed:', error);
        }
    }

    /**
     * FCM 토큰 발급 및 서버 동기화 (AsyncStorage 캐싱 포함)
     */
    async registerFcmToken() {
        try {
            // 1. 권한 확인
            const hasPermission = await this.requestUserPermission();
            if (!hasPermission) return;

            // 2. 토큰 가져오기
            const fcmToken = await messaging().getToken();

            if (fcmToken) {
                console.log('[FCM] Token issued:', fcmToken.substring(0, 20) + '...');

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
    setupTokenRefreshListener() {
        try {
            if (Platform.OS === 'web') return () => { };
            return messaging().onTokenRefresh(async (newToken) => {
                console.log('[FCM] Token refreshed:', newToken.substring(0, 20) + '...');
                const accessToken = await AsyncStorage.getItem('accessToken');
                if (accessToken) {
                    const response = await authService.updateFcmToken(newToken);
                    if (response.success) {
                        await AsyncStorage.setItem('savedFcmToken', newToken);
                    }
                }
            });
        } catch (error) {
            console.error('[FCM] setupTokenRefreshListener failed:', error);
            return () => { };
        }
    }



    /**
     * Foreground 알림 핸들러 설정
     * 앱이 실행 중일 때 알림 수신
     */
    setupForegroundHandler() {
        messaging().onMessage(async (remoteMessage) => {
            console.log('[FCM] Foreground message received:', remoteMessage);

            // 알림 표시
            if (remoteMessage.notification) {
                const { title, body } = remoteMessage.notification;

                // 글로벌 Alert 사용
                useAlertStore.getState().showAlert(
                    title || '알림',
                    body || '',
                    'INFO'
                );
            }

            // 데이터 처리
            if (remoteMessage.data) {
                this.handleNotificationData(remoteMessage.data as NotificationData);
            }
        });

        console.log('[FCM] Foreground handler set up');
    }

    /**
     * Background 알림 핸들러 설정
     * 앱이 백그라운드일 때 알림 클릭 시
     */
    setupBackgroundHandler() {
        messaging().setBackgroundMessageHandler(async (remoteMessage) => {
            console.log('[FCM] Background message received:', remoteMessage);

            if (remoteMessage.data) {
                this.handleNotificationData(remoteMessage.data as NotificationData);
            }
        });

        console.log('[FCM] Background handler set up');
    }

    /**
     * 알림 클릭 핸들러 설정
     * 알림을 클릭했을 때 처리
     */
    setupNotificationOpenedHandler(navigation: any) {
        // 앱이 종료된 상태에서 알림 클릭
        messaging()
            .getInitialNotification()
            .then((remoteMessage) => {
                if (remoteMessage) {
                    console.log('[FCM] Notification caused app to open:', remoteMessage);
                    this.handleNotificationNavigation(remoteMessage.data as NotificationData, navigation);
                }
            });

        // 앱이 백그라운드 상태에서 알림 클릭
        messaging().onNotificationOpenedApp((remoteMessage) => {
            console.log('[FCM] Notification opened app:', remoteMessage);
            this.handleNotificationNavigation(remoteMessage.data as NotificationData, navigation);
        });

        console.log('[FCM] Notification opened handler set up');
    }

    /**
     * 알림 데이터 처리
     */
    private handleNotificationData(data: NotificationData) {
        console.log('[FCM] Handling notification data:', data);

        const { type } = data;

        switch (type) {
            case 'DIAGNOSIS_COMPLETE':
            case 'DIAG_COMPLETE':
            case 'DIAG_INTERACTIVE':
                console.log('[FCM] Diagnosis complete:', data.sessionId, 'Score:', data.score);
                break;

            case 'MAINTENANCE_ALERT':
                console.log('[FCM] Maintenance alert:', data.itemCode, 'Remaining:', data.remainingKm);
                break;

            case 'TRIP_COMPLETE':
            case 'TRIP_END':
                console.log('[FCM] Trip end:', data.tripId, 'Distance:', data.distance);
                break;

            case 'TRIP_START':
                console.log('[FCM] Trip start:', data.tripId);
                break;

            default:
                console.log('[FCM] Unknown notification type:', type);
        }
    }

    /**
     * 알림 클릭 시 네비게이션 처리
     */
    private handleNotificationNavigation(data: NotificationData | undefined, navigation: any) {
        if (!data || !navigation) return;

        const { type, sessionId, tripId } = data;

        try {
            switch (type) {
                case 'DIAGNOSIS_COMPLETE':
                case 'DIAG_COMPLETE':
                case 'DIAG_INTERACTIVE':
                    if (sessionId) {
                        navigation.navigate('DiagnosisReport', { sessionId });
                    }
                    break;

                case 'MAINTENANCE_ALERT':
                    navigation.navigate('SupManage');
                    break;

                case 'TRIP_COMPLETE':
                case 'TRIP_END':
                    if (tripId) {
                        navigation.navigate('DrivingHis');
                    }
                    break;

                case 'TRIP_START':
                    navigation.navigate('MainPage');
                    break;

                default:
                    console.log('[FCM] No navigation for type:', type);
            }
        } catch (error) {
            console.error('[FCM] Navigation failed:', error);
        }
    }

    /**
     * FCM 토큰 가져오기 (외부에서 사용 가능)
     */
    async getToken(): Promise<string | null> {
        try {
            if (Platform.OS === 'web') return null;
            const token = await messaging().getToken().catch(() => null);
            return token;
        } catch (error) {
            console.error('[FCM] Failed to get token:', error);
            return null;
        }
    }

    /**
     * FCM 토큰 삭제 (로그아웃 시)
     */
    async deleteToken() {
        try {
            await messaging().deleteToken();
            console.log('[FCM] Token deleted');
            this.initialized = false;
        } catch (error) {
            console.error('[FCM] Failed to delete token:', error);
        }
    }
}

// Singleton instance
const fcmService = new FcmService();

export default fcmService;
