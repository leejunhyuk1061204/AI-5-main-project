import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Linking, ActivityIndicator } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import Header from '../header/Header';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { clearStorageForLogout } from '../utils/storageLogout';
import BaseScreen from '../components/layout/BaseScreen';
import { BASE_URL } from '../api/axios';
import { useAlertStore } from '../store/useAlertStore';
import { useUserStore } from '../store/useUserStore';

export default function SettingMain() {
    const navigation = useNavigation<any>();
    const [nickname, setNickname] = React.useState<string>('사용자');
    const [isLoading, setIsLoading] = useState(false);
    const showAlert = useAlertStore(state => state.showAlert);

    React.useEffect(() => {
        const getNickname = async () => {
            const stored = await AsyncStorage.getItem('userNickname');
            if (stored) setNickname(stored);
        };
        const unsubscribe = navigation.addListener('focus', getNickname);
        return unsubscribe;
    }, [navigation]);

    // Deep Link Handler for SmartCar Sync
    useEffect(() => {
        const handleDeepLink = async (event: { url: string }) => {
            // 화면이 포커스된 상태에서만 딥링크 처리 (중복 처리 방지)
            if (!navigation.isFocused()) return;

            const { url } = event;
            if (url && url.includes('smartcar/callback')) {
                // Extract params from URL
                const regexAccessToken = /[?&]accessToken=([^&#]*)/;
                const regexVehicleId = /[?&]vehicleId=([^&#]*)/;

                const accessToken = regexAccessToken.exec(url)?.[1];
                const targetedVehicleId = regexVehicleId.exec(url)?.[1];

                // 특정 차량 지정 연동(Targeted Linking)인 경우 SettingMain(배경)에서는 무시
                if (targetedVehicleId) return;

                if (accessToken) {
                    setIsLoading(true);
                    try {
                        const jwtToken = await AsyncStorage.getItem('accessToken');

                        // Sync API Call
                        const response = await fetch(`${BASE_URL}/api/smartcar/sync?accessToken=${accessToken}`, {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${jwtToken}`
                            }
                        });

                        if (response.ok) {
                            const syncData = await response.json();
                            const results = syncData.results || [];

                            showAlert(
                                "연동 완료",
                                `총 ${syncData.totalCount}대의 차량 정보가 성공적으로 최신화되었습니다.`,
                                "SUCCESS",
                                () => {
                                    // 단일 차량 연동 시, 번호판 정보가 있으면 관리 목록으로, 없으면 수정 페이지로 이동
                                    if (results.length === 1 && results[0].vehicleId) {
                                        const hasCarNumber = results[0].carNumber && results[0].carNumber.trim() !== '';
                                        if (hasCarNumber) {
                                            navigation.navigate('CarManage');
                                        } else {
                                            navigation.navigate('CarEdit', { vehicleId: results[0].vehicleId });
                                        }
                                    } else {
                                        navigation.navigate('CarManage');
                                    }
                                }
                            );
                        } else {
                            const errorData = await response.text();
                            throw new Error(errorData || "동기화 실패");
                        }
                    } catch (error) {
                        console.error("[Smartcar Sync Error]", error);
                        showAlert("연동 오류", "차량 정보를 동기화하는 중 오류가 발생했습니다.", "ERROR");
                    } finally {
                        setIsLoading(false);
                    }
                }
            }
        };

        const subscription = Linking.addEventListener('url', handleDeepLink);
        Linking.getInitialURL().then((url) => {
            if (url) handleDeepLink({ url });
        });

        return () => {
            subscription.remove();
        };
    }, []);

    const SectionTitle = ({ title }: { title: string }) => (
        <View className="px-2 mb-3 mt-2 flex-row items-center justify-between">
            <Text className="text-[13px] font-semibold text-text-muted">{title}</Text>
        </View>
    );

    const SettingsItem = ({ icon, title, subtitle, isLast, onPress }: { icon: keyof typeof MaterialIcons.glyphMap, title: string, subtitle?: string, isLast?: boolean, onPress?: () => void }) => (
        <TouchableOpacity
            className={`flex-row items-center gap-4 px-4 py-4 active:bg-white/5 ${!isLast ? 'border-b border-white/5' : ''}`}
            activeOpacity={0.7}
            onPress={onPress}
        >
            <View className="w-11 h-11 rounded-xl bg-primary/10 border border-primary/20 items-center justify-center shrink-0">
                <MaterialIcons name={icon} size={24} color="#0d7ff2" />
            </View>
            <View className="flex-1 justify-center">
                <Text className="text-white text-base font-medium leading-tight mb-0.5">{title}</Text>
                {subtitle && <Text className="text-text-dim text-xs">{subtitle}</Text>}
            </View>
            <MaterialIcons name="chevron-right" size={24} color="#0d7ff2" />
        </TouchableOpacity>
    );

    return (
        <BaseScreen
            header={<Header />}
            padding={true}
            useBottomNav={true}
        >
            {/* Account Settings Section */}
            <View className="mb-6">
                <SectionTitle title="계정 설정" />
                <View className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                    <SettingsItem
                        icon="person"
                        title="내 프로필"
                        subtitle={`${nickname} • 프리미엄 멤버십`}
                        onPress={() => navigation.navigate('MyPage')}
                    />
                    <SettingsItem
                        icon="notifications-active"
                        title="알림 설정"
                        isLast
                        onPress={() => navigation.navigate('AlertSetting')}
                    />
                </View>
            </View>

            {/* Vehicle & Services Section */}
            <View className="mb-6">
                <SectionTitle title="차량 및 서비스" />
                <View className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                    <SettingsItem
                        icon="directions-car"
                        title="내 차량 관리"
                        subtitle="Genesis GV80 • 12가 3456"
                        onPress={() => navigation.navigate('CarManage')}
                    />
                    <SettingsItem
                        icon="bluetooth"
                        title="OBD 어댑터 연결"
                        subtitle="블루투스 OBD 스캔 및 연결"
                        onPress={() => navigation.navigate('ObdConnectFlow')}
                    />
                    <SettingsItem
                        icon="cloud-sync"
                        title="커넥티드 카 연동"
                        subtitle="SmartCar 계정 연결"
                        onPress={() => Linking.openURL(`${BASE_URL}/api/smartcar/login`)}
                    />
                    <SettingsItem
                        icon="speed"
                        title="OBD 실시간 모니터"
                        subtitle="실차 OBD 데이터 실시간 확인"
                        isLast
                        onPress={() => navigation.navigate('Elm327Test')}
                    />
                </View>
            </View>

            {/* Logout Button */}
            <TouchableOpacity
                className="w-full py-4 bg-white/5 border border-error/10 rounded-2xl flex-row items-center justify-center gap-2 mt-2 active:bg-error/10"
                activeOpacity={0.7}
                onPress={async () => {
                    try {
                        const { logout } = useUserStore.getState();
                        await logout();
                        await clearStorageForLogout();
                        navigation.reset({
                            index: 0,
                            routes: [{ name: 'Login' }],
                        });
                    } catch (e) {
                        console.error('Logout failed', e);
                        navigation.navigate('Login');
                    }
                }}
            >
                <MaterialIcons name="logout" size={18} color="#ff6b6b" />
                <Text className="text-error font-semibold text-sm">로그아웃</Text>
            </TouchableOpacity>

            {/* Loading Overlay */}
            {isLoading && (
                <View className="absolute inset-0 bg-black/60 items-center justify-center z-50">
                    <View className="bg-surface-dark p-6 rounded-2xl border border-white/10 items-center">
                        <ActivityIndicator size="large" color="#0d7ff2" className="mb-4" />
                        <Text className="text-white font-bold text-lg mb-1">차량 정보 동기화 중</Text>
                        <Text className="text-text-dim text-sm">잠시만 기다려주세요...</Text>
                    </View>
                </View>
            )}
        </BaseScreen>
    );
}
