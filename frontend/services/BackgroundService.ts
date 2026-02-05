import BackgroundService from 'react-native-background-actions';
import { Platform } from 'react-native';

const sleep = (time: number) => new Promise<void>((resolve) => setTimeout(() => resolve(), time));

class BackgroundTaskService {
    private isRunning = false;

    // 백그라운드에서 실행될 작업 (무한 루프)
    private obdBackgroundTask = async (taskDataArguments?: any) => {
        const { delay } = taskDataArguments || { delay: 1000 };

        while (BackgroundService.isRunning()) {
            // ObdService의 Polling은 별도의 Timer(setInterval/setTimeout)로 동작하지만,
            // 이 무한 루프가 돌아가야 Android Foreground Service가 유지됨.
            // 필요하다면 여기서 ObdService의 상태를 체크하거나 특정 작업을 수행할 수 있음.

            // console.log('[BackgroundService] Heartbeat...');
            await sleep(delay);
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
        parameters: {
            delay: 5000, // 하트비트 간격 (5초)
        },
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
