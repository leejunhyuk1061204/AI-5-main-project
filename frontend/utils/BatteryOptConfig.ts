import { Alert, Linking, Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'HAS_PROMPTED_BATTERY_OPT';

/**
 * Android 배터리 최적화 제외 요청 (매뉴얼)
 * 안드로이드는 백그라운드 서비스가 길게 돌면 배터리 최적화로 인해 프로세스를 죽일 수 있음.
 * 사용자가 직접 설정에서 '제한 없음'으로 변경하도록 유도해야 함.
 */
export const checkAndRequestBatteryOpt = async () => {
    if (Platform.OS !== 'android') return;

    try {
        const hasPrompted = await AsyncStorage.getItem(STORAGE_KEY);
        if (hasPrompted === 'true') return;

        Alert.alert(
            "배터리 최적화 설정 안내",
            "백그라운드에서 끊김 없는 OBD 데이터 수집을 위해 배터리 사용량을 '제한 없음'으로 설정해주세요.\n\n설정 > 애플리케이션 > 배터리 > 제한 없음",
            [
                {
                    text: "다음에 하기",
                    style: "cancel",
                    onPress: async () => {
                        // 3일에 한 번 다시 뜨게 하거나, 이번만 건너뛰기 등 로직 추가 가능
                        // 여기서는 일단 다시 뜨지 않게 하거나, 일시적으로만 저장할 수 있음.
                        // 편의상 다음에 또 뜨도록 저장 안 함.
                    }
                },
                {
                    text: "설정하러 가기",
                    onPress: async () => {
                        await AsyncStorage.setItem(STORAGE_KEY, 'true');
                        Linking.openSettings();
                    }
                }
            ],
            { cancelable: false }
        );
    } catch (e) {
        console.error("Failed to check battery opt prompt", e);
    }
};
