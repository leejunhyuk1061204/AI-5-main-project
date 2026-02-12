import React, { useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Platform, Linking, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import BaseScreen from '../components/layout/BaseScreen';

import { useUserStore } from '../store/useUserStore';
import { useAlertStore } from '../store/useAlertStore';
import { BASE_URL } from '../api/axios';

export default function RegisterMain() {
    const insets = useSafeAreaInsets();
    const navigation = useNavigation<any>();
    const logout = useUserStore(state => state.logout);
    const showAlert = useAlertStore(state => state.showAlert);

    const handleBack = () => {
        if (navigation.canGoBack()) {
            navigation.goBack();
        } else {
            // 루트에서 뒤로가기 시에는 로그인 화면으로 보낸다.
            navigation.reset({
                index: 0,
                routes: [{ name: 'Login' }],
            });
        }
    };

    const handleLogout = async () => {
        Alert.alert(
            "로그아웃",
            "정말 로그아웃 하시겠습니까?",
            [
                { text: "취소", style: "cancel" },
                {
                    text: "로그아웃",
                    style: "destructive",
                    onPress: async () => {
                        await logout();
                        navigation.reset({
                            index: 0,
                            routes: [{ name: 'Login' }],
                        });
                    }
                }
            ]
        );
    };

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

                // 특정 차량 지정 연동(Targeted Linking)인 경우 RegisterMain(배경)에서는 무시
                if (targetedVehicleId) return;

                if (accessToken) {
                    try {
                        const jwtToken = await AsyncStorage.getItem('accessToken');

                        // 단순 조회가 아닌 백엔드 sync API 호출 (POST)
                        const response = await fetch(`${BASE_URL}/api/smartcar/sync?accessToken=${accessToken}`, {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${jwtToken}`
                            }
                        });

                        if (response.ok) {
                            const syncData = await response.json();
                            const results = syncData.results || [];

                            let detailMessage = `총 ${syncData.totalCount}대의 차량 정보가 성공적으로 최신화되었습니다.\n\n`;
                            let targetVehicleId: string | null = null;
                            results.forEach((res: any) => {
                                if (res.vehicleId) targetVehicleId = res.vehicleId;
                            });

                            showAlert(
                                "연동 완료",
                                detailMessage,
                                "SUCCESS",
                                () => {
                                    // 연동된 차량이 1대이고 번호판 정보가 있으면 관리 목록으로, 없으면 수정 페이지로 이동
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
                        showAlert("연동 오류", "차량 정보를 동기화하는 중 오류가 발생했습니다.", "ERROR");
                        console.error("[Smartcar Sync Error]", error);
                    }
                }
            }
        };

        // Add event listener
        const subscription = Linking.addEventListener('url', handleDeepLink);

        // Check if app was opened by a link
        Linking.getInitialURL().then((url) => {
            if (url) handleDeepLink({ url });
        });

        return () => {
            subscription.remove();
        };
    }, []);

    // Custom Header for BaseScreen
    const renderHeader = () => (
        <View
            className="bg-background-dark/95 backdrop-blur-md z-50 border-b border-white/5"
            style={{ paddingTop: 10, paddingBottom: 16 }} // BaseScreen handles safe area, just add internal padding
        >
            <View className="flex-row items-center justify-between px-4">
                <TouchableOpacity
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                    activeOpacity={0.7}
                    onPress={handleBack}
                >
                    <MaterialIcons name="arrow-back" size={24} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">차량 등록</Text>

                <TouchableOpacity
                    onPress={handleLogout}
                    className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 active:bg-white/10"
                >
                    <Text className="text-xs text-slate-300 font-medium">로그아웃</Text>
                </TouchableOpacity>
            </View>
        </View>
    );

    return (
        <BaseScreen
            header={renderHeader()}
            scrollable={true}
            padding={false} // Custom padding handling in ScrollView
            bgColor="#101922"
        >
            <View className="px-5 pb-10">
                {/* Page Title */}
                <View className="mt-4 mb-8">
                    <Text className="text-2xl font-bold text-white leading-tight mb-2">
                        등록 방식을 선택해주세요
                    </Text>
                    <Text className="text-slate-400 text-sm">
                        정확한 진단을 위해 차량 정보가 필요합니다.
                    </Text>
                </View>

                {/* Selection Grid */}
                <View className="gap-4">
                    {/* Card 1: Manual Entry */}
                    <TouchableOpacity
                        className="group relative flex flex-col items-start gap-4 rounded-2xl border border-white/10 bg-white/5 p-6 active:bg-white/10 active:scale-[0.98]"
                        activeOpacity={0.9}
                        onPress={() => navigation.navigate('PassiveReg')}
                    >
                        <View className="rounded-full bg-surface-highlight p-3">
                            <MaterialIcons name="description" size={32} color="#94a3b8" className="text-slate-400" />
                        </View>
                        <View>
                            <Text className="text-lg font-bold text-white mb-1">수동 정보 입력</Text>
                            <Text className="text-sm text-slate-400 leading-relaxed">
                                차량 등록증을 보고{'\n'}연식, 모델명 등을 직접 입력합니다.
                            </Text>
                        </View>
                        {/* Arrow Icon */}
                        <View className="absolute top-6 right-6 opacity-50">
                            <MaterialIcons name="arrow-forward" size={24} color="#0d7ff2" />
                        </View>
                    </TouchableOpacity>

                    {/* Card 2: SmartCar Connection */}
                    <TouchableOpacity
                        className="relative flex flex-col items-start gap-4 rounded-2xl border border-green-500/30 bg-white/5 p-6 shadow-lg shadow-green-500/10 active:bg-white/10 active:border-green-500 active:scale-[0.98]"
                        activeOpacity={0.9}
                        onPress={() => {
                            Linking.openURL(`${BASE_URL}/api/smartcar/login`);
                        }}
                    >
                        {/* New Badge */}
                        <View className="absolute top-0 right-0 rounded-bl-xl rounded-tr-xl bg-green-500 px-3 py-1 shadow-sm">
                            <Text className="text-[10px] font-bold text-white">NEW</Text>
                        </View>

                        <View className="rounded-full bg-green-500/10 p-3">
                            <MaterialIcons name="electric-car" size={32} color="#22c55e" />
                        </View>
                        <View>
                            <Text className="text-lg font-bold text-white mb-1">SmartCar 연결</Text>
                            <Text className="text-sm text-slate-400 leading-relaxed">
                                Smartcar 계정을 연결하여{'\n'}차량 정보를 불러옵니다.
                            </Text>
                        </View>
                        <View className="absolute top-6 right-6 opacity-50">
                            <MaterialIcons name="arrow-forward" size={24} color="#22c55e" />
                        </View>
                    </TouchableOpacity>
                </View>

                {/* Info Panel */}
                <View className="mt-12">
                    <View className="flex flex-col gap-3 rounded-xl border border-surface-highlight bg-surface-dark/50 p-4">
                        <View className="flex-row items-center gap-2">
                            <MaterialIcons name="info" size={20} color="#0d7ff2" />
                            <Text className="text-sm font-bold text-white">차량 등록이 필요한 이유</Text>
                        </View>
                        <Text className="text-xs text-slate-400 leading-relaxed">
                            정확한 AI 진단과 소모품 교체 주기를 예측하기 위해 차량 정보가 필수적입니다. 등록된 데이터는 암호화되어 안전하게 보관됩니다.
                        </Text>
                    </View>
                </View>

                <View className="h-10" />
            </View>
        </BaseScreen>
    );
}
