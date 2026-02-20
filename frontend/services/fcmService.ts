import messaging from '@react-native-firebase/messaging';
import firebase from '@react-native-firebase/app';
import { authService } from './auth';
import { useAlertStore } from '../store/useAlertStore';
import { Platform } from 'react-native';

/**
 * FCM 서비스
 * Firebase Cloud Messaging 초기화 및 토큰 관리
 */
class FcmService {
    private initialized = false;

    /**
     * FCM 초기화
     * - 권한 요청
     * - 토큰 가져오기
     * - 백엔드에 토큰 등록
     * - 토큰 갱신 리스너 등록
     */
    async initialize() {
        if (this.initialized) {
            console.log('[FCM] Already initialized');
            return;
        }

        try {
            // 0. Firebase App 초기화 확인 (React Native Firebase는 자동 초기화됨)
            if (firebase.apps.length === 0) {
                console.error('[FCM] Firebase App not initialized. Check google-services.json');
                return;
            }
            console.log('[FCM] Firebase App already initialized');

            // 1. 권한 요청
            const authStatus = await messaging().requestPermission();
            const enabled =
                authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
                authStatus === messaging.AuthorizationStatus.PROVISIONAL;

            if (!enabled) {
                console.log('[FCM] Permission denied');
                return;
            }

            console.log('[FCM] Permission granted');

            // 2. FCM 토큰 가져오기
            const fcmToken = await messaging().getToken();
            console.log('[FCM] Token obtained:', fcmToken.substring(0, 20) + '...');

            // 3. 백엔드에 토큰 등록
            await this.registerToken(fcmToken);

            // 4. 토큰 갱신 리스너
            messaging().onTokenRefresh(async (newToken) => {
                console.log('[FCM] Token refreshed');
                await this.registerToken(newToken);
            });

            this.initialized = true;
            console.log('[FCM] Initialization complete');
        } catch (error) {
            console.error('[FCM] Initialization failed:', error);
        }
    }

    /**
     * 백엔드에 FCM 토큰 등록
     */
    private async registerToken(fcmToken: string) {
        try {
            const response = await authService.updateFcmToken(fcmToken);
            if (response.success) {
                console.log('[FCM] Token registered successfully');
            }
        } catch (error) {
            console.error('[FCM] Token registration failed:', error);
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
                this.handleNotificationData(remoteMessage.data as unknown as { [key: string]: string });
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
                this.handleNotificationData(remoteMessage.data as unknown as { [key: string]: string });
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
                    this.handleNotificationNavigation(remoteMessage.data as unknown as { [key: string]: string }, navigation);
                }
            });

        // 앱이 백그라운드 상태에서 알림 클릭
        messaging().onNotificationOpenedApp((remoteMessage) => {
            console.log('[FCM] Notification opened app:', remoteMessage);
            this.handleNotificationNavigation(remoteMessage.data as unknown as { [key: string]: string }, navigation);
        });

        console.log('[FCM] Notification opened handler set up');
    }

    /**
     * 알림 데이터 처리
     */
    private handleNotificationData(data: { [key: string]: string }) {
        console.log('[FCM] Handling notification data:', data);

        const { type } = data;

        switch (type) {
            case 'DIAGNOSIS_COMPLETE':
                console.log('[FCM] Diagnosis complete:', data.sessionId, 'Score:', data.score);
                break;

            case 'MAINTENANCE_ALERT':
                console.log('[FCM] Maintenance alert:', data.itemCode, 'Remaining:', data.remainingKm);
                break;

            case 'TRIP_COMPLETE':
                console.log('[FCM] Trip complete:', data.tripId, 'Distance:', data.distance);
                break;

            default:
                console.log('[FCM] Unknown notification type:', type);
        }
    }

    /**
     * 알림 클릭 시 네비게이션 처리
     */
    private handleNotificationNavigation(data: { [key: string]: string } | undefined, navigation: any) {
        if (!data || !navigation) return;

        const { type, sessionId, tripId } = data;

        try {
            switch (type) {
                case 'DIAGNOSIS_COMPLETE':
                    if (sessionId) {
                        navigation.navigate('DiagnosisReport', { sessionId });
                    }
                    break;

                case 'MAINTENANCE_ALERT':
                    navigation.navigate('SupManage');
                    break;

                case 'TRIP_COMPLETE':
                    if (tripId) {
                        navigation.navigate('DrivingHis');
                    }
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
