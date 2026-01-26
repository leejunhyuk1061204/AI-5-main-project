import BackgroundService from 'react-native-background-actions';
import { Platform } from 'react-native';

const sleep = (time: number) => new Promise<void>((resolve) => setTimeout(() => resolve(), time));

class BackgroundTaskService {
    private isRunning = false;

    // 백그라운드에서 실행될 작업 (무한 루프)
    private veryIntensiveTask = async (taskDataArguments?: any) => {
        // Example of an infinite loop task
        const { delay } = taskDataArguments || { delay: 1000 };

        while (BackgroundService.isRunning()) {
            // 여기서 실제 로직을 실행하거나, 단순히 스레드를 살려두기 위해 sleep만 할 수도 있음
            // ObdService의 Polling은 별도의 Timer로 동작하므로, 여기서는 스레드 유지 목적이 강함
            // 다만, 확실한 동작을 위해 ObdService 상태를 체크하거나 로그를 찍을 수 있음

            // console.log('[BackgroundService] Running...');
            await sleep(delay);
        }
    };

    private options = {
        taskName: 'ObdBackgroundService',
        taskTitle: 'OBD 데이터 수집 중',
        taskDesc: '백그라운드에서 차량 데이터를 모니터링하고 있습니다.',
        taskIcon: {
            name: 'ic_launcher',
            type: 'mipmap',
        },
        color: '#0d7ff2',
        linkingURI: 'yourSchemeHere://chat/jane', // deep link
        parameters: {
            delay: 2000,
        },
    };

    async start() {
        if (Platform.OS !== 'android') return; // iOS는 다른 방식(Background Modes) 필요 (제한적)
        if (this.isRunning) return;

        try {
            console.log('[BackgroundService] Starting...');
            await BackgroundService.start(this.veryIntensiveTask, this.options);
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
