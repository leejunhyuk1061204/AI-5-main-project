import AsyncStorage from '@react-native-async-storage/async-storage';

const KEYS_TO_PRESERVE = ['hasSeenNotiOnboarding', 'hasAgreedToTos'];

/**
 * 로그아웃 시 사용. 저장소를 비우되, 아래 항목은 유지:
 * - hasSeenNotiOnboarding: 알림 온보딩 "한 번만 보기" 플래그
 * - hasAgreedToTos: 약관 동의 플래그 (재로그인 시 약관 화면 스킵)
 */
export async function clearStorageForLogout(): Promise<void> {
    const preserved: Record<string, string | null> = {};
    for (const key of KEYS_TO_PRESERVE) {
        preserved[key] = await AsyncStorage.getItem(key);
    }
    await AsyncStorage.clear();
    for (const [key, value] of Object.entries(preserved)) {
        if (value != null) {
            await AsyncStorage.setItem(key, value);
        }
    }
}
