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
        taskTitle: '차봄 OBD 실행 중',
        taskDesc: '백그라운드에서 차량 데이터를 수집하고 있습니다.',
        taskIcon: {
            name: 'ic_launcher',
            type: 'mipmap',
        },
        color: '#0d7ff2',
        linkingURI: 'yourSchemeHere://chat/jane', // deep link setup if needed
        parameters: {
            delay: 2000,
        },
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
