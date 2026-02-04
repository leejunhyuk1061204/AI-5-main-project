import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, Alert, ActivityIndicator, Linking } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { getVehicleDetail, updateVehicle, deleteVehicle, VehicleResponse } from '../api/vehicleApi';
import BaseScreen from '../components/layout/BaseScreen';
import { useVehicleStore } from '../store/useVehicleStore';
import { useAlertStore } from '../store/useAlertStore';
import { BASE_URL } from '../api/axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function CarEdit() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const { vehicleId } = route.params || {};

    const [loading, setLoading] = useState(true);
    const [vehicle, setVehicle] = useState<VehicleResponse | null>(null);
    const [isSyncing, setIsSyncing] = useState(false);

    // Form State
    const [nickname, setNickname] = useState('');
    const [carNumber, setCarNumber] = useState('');
    const [vin, setVin] = useState('');

    useEffect(() => {
        loadVehicle();

        // Deep Link Handler (for SmartCar Callback)
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

                // 1. targetedVehicleId가 없으면 일반 연동이므로 CarEdit에서는 무시
                // 2. 있더라도 현재 보고 있는 차량과 다르면 무시
                if (!targetedVehicleId || targetedVehicleId !== vehicleId) return;

                if (accessToken && vehicleId) { // vehicleId must exist
                    setIsSyncing(true); // 로딩 시작
                    try {
                        const jwtToken = await AsyncStorage.getItem('accessToken');

                        // Call Sync API with vehicleId
                        const response = await fetch(`${BASE_URL}/api/smartcar/sync?accessToken=${accessToken}&vehicleId=${vehicleId}`, {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${jwtToken}`
                            }
                        });

                        if (response.ok) {
                            const syncData = await response.json();
                            const result = syncData.results?.[0];
                            const hasCarNumber = result?.carNumber && result.carNumber.trim() !== '';

                            useAlertStore.getState().showAlert(
                                "연동 완료",
                                "차량 정보가 SmartCar와 성공적으로 연동되었습니다.",
                                "SUCCESS",
                                () => {
                                    if (hasCarNumber) {
                                        // 번호판이 이미 있으면 목록으로 이동
                                        navigation.navigate('CarManage');
                                    } else {
                                        // 번호판이 없으면 수정 페이지 유지하여 입력을 유도
                                        loadVehicle();
                                    }
                                }
                            );
                        } else {
                            const errorText = await response.text();
                            console.error("SmartCar Sync Failed:", errorText);
                            useAlertStore.getState().showAlert("연동 실패", "차량 연동에 실패했습니다.", "ERROR");
                        }
                    } catch (error) {
                        console.error("SmartCar Deep Link Error:", error);
                        useAlertStore.getState().showAlert("오류", "연동 중 오류가 발생했습니다.", "ERROR");
                    } finally {
                        setIsSyncing(false); // 로딩 종료
                    }
                }
            }
        };

        const subscription = Linking.addEventListener('url', handleDeepLink);
        // Check initial URL
        Linking.getInitialURL().then((url) => {
            if (url) handleDeepLink({ url });
        });

        return () => {
            subscription.remove();
        };

    }, [vehicleId]);

    const loadVehicle = async () => {
        if (!vehicleId) {
            useAlertStore.getState().showAlert('오류', '차량 정보를 찾을 수 없습니다.', 'ERROR', () => navigation.goBack());
            return;
        }

        try {
            setLoading(true);
            const data = await getVehicleDetail(vehicleId);
            setVehicle(data);
            setNickname(data.nickname || '');
            setCarNumber(data.carNumber || '');
            setVin(data.vin || '');
        } catch (error) {
            console.error('Failed to load vehicle:', error);
            useAlertStore.getState().showAlert('오류', '차량 정보를 불러오는데 실패했습니다.', 'ERROR', () => navigation.goBack());
        } finally {
            setLoading(false);
        }
    };

    const handleUpdate = async () => {
        if (!vehicleId) return;

        // 차량번호 길이 검증
        if (carNumber && carNumber.length > 20) {
            useAlertStore.getState().showAlert(
                '입력 오류',
                '차량번호는 20자를 초과할 수 없습니다.\n다시 입력해주세요.',
                'WARNING'
            );
            return;
        }

        try {
            await updateVehicle(vehicleId, {
                nickname: nickname,
                carNumber: carNumber,
                vin: vin
            });
            await useVehicleStore.getState().fetchVehicles(); // 목록 새로고침
            useAlertStore.getState().showAlert('성공', '차량 정보가 수정되었습니다.', 'SUCCESS', () => navigation.goBack());
        } catch (error) {
            console.error('Update failed:', error);
            useAlertStore.getState().showAlert('오류', '차량 정보 수정에 실패했습니다.', 'ERROR');
        }
    };

    const handleDelete = () => {
        useAlertStore.getState().showAlert(
            '차량 삭제',
            '정말로 이 차량을 삭제하시겠습니까?\n삭제된 데이터는 복구할 수 없습니다.',
            'WARNING',
            async () => {
                try {
                    await deleteVehicle(vehicleId);
                    await useVehicleStore.getState().fetchVehicles(); // 목록 새로고침
                    useAlertStore.getState().showAlert('성공', '차량이 삭제되었습니다.', 'SUCCESS', () => navigation.goBack());
                } catch (error) {
                    console.error('Delete failed:', error);
                    useAlertStore.getState().showAlert('오류', '차량 삭제에 실패했습니다.', 'ERROR');
                }
            },
            {
                confirmText: '삭제',
                cancelText: '취소',
                isDestructive: true
            }
        );
    };

    const HeaderCustom = (
        <View className="flex-row items-center justify-between px-4 py-3 pb-4">
            <TouchableOpacity
                className="w-10 h-10 items-center justify-center rounded-full hover:bg-white/10"
                onPress={() => navigation.goBack()}
            >
                <MaterialIcons name="arrow-back-ios-new" size={24} color="white" />
            </TouchableOpacity>
            <Text className="text-white text-lg font-bold tracking-tight text-center flex-1 pr-10">
                차량 정보 수정
            </Text>
        </View>
    );

    const FooterActions = (
        <View className="p-5 bg-background-dark">
            <TouchableOpacity
                onPress={handleUpdate}
                className="w-full h-14 bg-primary rounded-xl shadow-lg shadow-blue-500/30 flex-row items-center justify-center gap-2 active:opacity-90"
                activeOpacity={0.8}
            >
                <Text className="text-white font-bold text-lg">저장하기</Text>
                <MaterialIcons name="check" size={20} color="white" />
            </TouchableOpacity>
        </View>
    );

    if (loading) {
        return (
            <View className="flex-1 bg-background-dark items-center justify-center">
                <ActivityIndicator size="large" color="#0d7ff2" />
            </View>
        );
    }

    return (
        <BaseScreen
            header={HeaderCustom}
            footer={FooterActions}
            scrollable={true}
            padding={false}
            bgColor="#101922" // background-dark 토큰값
        >
            <View className="px-5 mt-6 pb-12">
                {/* Read-Only Info Card */}
                <View className="bg-surface-dark border border-white/5 rounded-2xl p-5 mb-8">
                    <View className="flex-row items-center gap-3 mb-4">
                        <View className="w-10 h-10 rounded-full bg-primary/20 items-center justify-center">
                            <MaterialIcons name="directions-car" size={24} color="#0d7ff2" />
                        </View>
                        <View>
                            <Text className="text-white font-bold text-lg">
                                {vehicle?.manufacturerKo} {vehicle?.modelNameKo}
                            </Text>
                            <Text className="text-slate-400 text-sm">
                                {vehicle?.modelYear}년식 · {vehicle?.fuelType}
                            </Text>
                        </View>
                    </View>
                    <View className="h-[1px] bg-white/5 mb-4" />
                    <View className="flex-row justify-between">
                        <View>
                            <Text className="text-xs text-slate-500 mb-1">총 주행거리</Text>
                            <Text className="text-slate-300 font-medium">{(vehicle?.totalMileage || 0).toLocaleString()} km</Text>
                        </View>
                    </View>
                </View>

                {/* Nickname Input */}
                <View className="mb-6">
                    <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">차량 별칭 (Nickname)</Text>
                    <TextInput
                        value={nickname}
                        onChangeText={setNickname}
                        placeholder="차량 별칭을 입력하세요"
                        placeholderTextColor="#94a3b8"
                        className="w-full h-14 bg-surface-dark border border-border-dark rounded-xl px-4 text-base text-white focus:border-primary"
                    />
                </View>

                {/* Car Number Input */}
                <View className="mb-6">
                    <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">차량 번호 (License Plate)</Text>
                    <TextInput
                        value={carNumber}
                        onChangeText={setCarNumber}
                        placeholder="차량 번호를 입력하세요 (예: 12가 3456)"
                        placeholderTextColor="#94a3b8"
                        className="w-full h-14 bg-surface-dark border border-border-dark rounded-xl px-4 text-base text-white focus:border-primary"
                    />
                </View>

                {/* VIN Input */}
                <View className="mb-8">
                    <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">차대번호 (VIN)</Text>
                    <TextInput
                        value={vin}
                        onChangeText={setVin}
                        placeholder="차대번호를 입력하세요"
                        placeholderTextColor="#94a3b8"
                        autoCapitalize="characters"
                        className="w-full h-14 bg-surface-dark border border-border-dark rounded-xl px-4 text-base text-white focus:border-primary"
                    />
                </View>

                {/* SmartCar Connect Button (Only if NOT linked) */}
                {!vehicle?.cloudLinked && (
                    <View className="mb-8">
                        <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">SmartCar 연동</Text>
                        <TouchableOpacity
                            className="w-full py-3 bg-green-500/10 border border-green-500/30 rounded-xl flex-row items-center justify-center gap-2 active:bg-green-500/20"
                            onPress={() => {
                                Linking.openURL(`${BASE_URL}/api/smartcar/login?vehicleId=${vehicleId}`);
                            }}
                        >
                            <MaterialIcons name="electric-car" size={20} color="#22c55e" />
                            <Text className="text-green-500 font-bold">SmartCar 계정 연동하기</Text>
                        </TouchableOpacity>
                        <Text className="text-xs text-slate-500 mt-2 pl-1">
                            * 차량이 1대인 계정만 자동 연결됩니다.
                        </Text>
                    </View>
                )}

                {/* Delete Button Area */}
                <View className="pt-4 border-t border-white/5">
                    <TouchableOpacity
                        onPress={handleDelete}
                        className="flex-row items-center justify-center gap-2 p-4"
                    >
                        <MaterialIcons name="delete-outline" size={20} color="#ef4444" />
                        <Text className="text-red-500 font-medium">차량 삭제하기</Text>
                    </TouchableOpacity>
                </View>
            </View>

            {/* Sync Loading Overlay */}
            {isSyncing && (
                <View className="absolute inset-0 bg-black/60 items-center justify-center z-50">
                    <View className="bg-surface-dark p-6 rounded-2xl border border-white/10 items-center">
                        <ActivityIndicator size="large" color="#0d7ff2" className="mb-4" />
                        <Text className="text-white font-bold text-lg mb-1">차량 연동 중</Text>
                        <Text className="text-text-dim text-sm">SmartCar 정보를 동기화하고 있습니다...</Text>
                    </View>
                </View>
            )}
        </BaseScreen>
    );
}
