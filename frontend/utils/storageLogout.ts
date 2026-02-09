import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY_PRESERVE = 'hasSeenNotiOnboarding';

/**
 * 로그아웃 시 사용. 저장소를 비우되, 알림 온보딩 "한 번만 보기" 플래그는 유지하여
 * 재로그인 시마다 알림 설정 안내가 뜨지 않도록 함.
 */
export async function clearStorageForLogout(): Promise<void> {
    const preserved = await AsyncStorage.getItem(KEY_PRESERVE);
    await AsyncStorage.clear();
    if (preserved != null) {
        await AsyncStorage.setItem(KEY_PRESERVE, preserved);
    }
}
