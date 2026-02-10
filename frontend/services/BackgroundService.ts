import BackgroundService from 'react-native-background-actions';
import { Platform } from 'react-native';
import ObdService from './ObdService';

const sleep = (time: number) => new Promise<void>((resolve) => setTimeout(() => resolve(), time));

const HEARTBEAT_MS = 5000;

class BackgroundTaskService {
    private isRunning = false;

    private obdBackgroundTask = async () => {
        let intervalMs = 120000;
        try {
            intervalMs = await ObdService.getReconnectIntervalMs();
        } catch (e) {
            console.warn('[BackgroundService] getReconnectIntervalMs failed, using 2min', e);
        }
        const reconnectEveryTicks = Math.max(1, Math.floor(intervalMs / HEARTBEAT_MS));
        let tick = 0;

        console.log('[BackgroundService] Task started. intervalMs=', intervalMs, 'reconnectEveryTicks=', reconnectEveryTicks);

        // 시작 직후 1회 즉시 자동 연결 시도
        try {
            console.log('[BackgroundService] Initial auto-connect from cache...');
            await ObdService.tryAutoConnectFromCache();
        } catch (e) {
            console.warn('[BackgroundService] initial tryAutoConnectFromCache failed', e);
        }

        while (BackgroundService.isRunning()) {
            await sleep(HEARTBEAT_MS);
            tick++;
            if (tick >= reconnectEveryTicks) {
                tick = 0;
                try {
                    console.log('[BackgroundService] Heartbeat tick reached. Trying auto-connect from cache...');
                    await ObdService.tryAutoConnectFromCache();
                } catch (e) {
                    console.warn('[BackgroundService] tryAutoConnectFromCache failed', e);
                }
            }
        }
    };

    private options = {
        taskName: 'ObdBackgroundService',
        taskTitle: '차봄 OBD 데이터 수집 중',
        taskDesc: '백그라운드에서도 차량 진단 데이터가 안전하게 기록되고 있습니다.',
        taskIcon: {
            name: 'ic_launcher',
            type: 'mipmap',
        },
        color: '#0d7ff2',
        linkingURI: 'frontend://obd', // 앱의 OBD 화면으로 연결되도록 설정 (확인 필요)
        parameters: {},
        // [안전망] 사용자가 알림에서 서비스를 일시정지하지 못하게 설정 (UI 옵션)
        allowPause: false,
    };

    async start() {
        if (Platform.OS !== 'android') return;
        if (this.isRunning) return;

        try {
            console.log('[BackgroundService] Starting...');
            await BackgroundService.start(this.obdBackgroundTask, this.options);
            this.isRunning = true;
            console.log('[BackgroundService] Started!');
        } catch (e) {
            console.error('[BackgroundService] Failed to start:', e);
        }
    }

    async stop() {
        if (Platform.OS !== 'android') return;
        if (!this.isRunning) return;

        try {
            console.log('[BackgroundService] Stopping...');
            await BackgroundService.stop();
            this.isRunning = false;
            console.log('[BackgroundService] Stopped!');
        } catch (e) {
            console.error('[BackgroundService] Failed to stop:', e);
        }
    }

    isActive() {
        return this.isRunning;
    }
}

export default new BackgroundTaskService();
