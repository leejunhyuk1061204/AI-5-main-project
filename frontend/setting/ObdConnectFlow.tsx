import React, { useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import BaseScreen from '../components/layout/BaseScreen';
import { useVehicleStore } from '../store/useVehicleStore';
import { useBleStore } from '../store/useBleStore';
import { useAlertStore } from '../store/useAlertStore';
import { VehicleResponse } from '../api/vehicleApi';
import { obdDeviceApi } from '../api/obdApi';
import ObdService from '../services/ObdService';
import ObdConnect from './ObdConnect';
import { checkAndRequestBatteryOpt } from '../utils/BatteryOptConfig';

export default function ObdConnectFlow() {
    const navigation = useNavigation<any>();
    const { vehicles, fetchVehicles } = useVehicleStore();
    const showAlert = useAlertStore(state => state.showAlert);

    const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
    const [obdModalVisible, setObdModalVisible] = useState(false);

    const primaryVehicle = vehicles.find(v => v.isPrimary) || vehicles[0];
    const effectiveSelectedId = selectedVehicleId ?? primaryVehicle?.vehicleId ?? null;
    const effectiveSelectedVehicle = vehicles.find(v => v.vehicleId === effectiveSelectedId);
    const selectedVehicleLabel = effectiveSelectedVehicle
        ? `${effectiveSelectedVehicle.manufacturerKo} ${effectiveSelectedVehicle.modelNameKo}`
        : undefined;

    useFocusEffect(
        useCallback(() => {
            fetchVehicles();
        }, [fetchVehicles])
    );

    const handleConnectPress = () => {
        if (!effectiveSelectedId) {
            showAlert('차량 선택', '연결할 차량을 먼저 등록해주세요.', 'ERROR');
            return;
        }
        setObdModalVisible(true);
    };

    const handleConnected = async (device: { id: string; name: string; type: 'ble' | 'classic'; classicDevice?: { address: string } }) => {
        const vehicleId = effectiveSelectedId;
        if (!vehicleId) return;

        const deviceId = device.type === 'classic' && device.classicDevice
            ? device.classicDevice.address
            : device.id;

        await ObdService.ensureNotificationPermissionForPolling();

        ObdService.setManualConnectSession(true);

        try {
            await obdDeviceApi.registerDevice({
                deviceId,
                deviceType: device.type,
                name: device.name || deviceId,
            });
            await obdDeviceApi.recordConnect(deviceId, { vehicleId });
            ObdService.setVehicleId(vehicleId);
            useBleStore.getState().setConnectedVehicleId(vehicleId);
            await ObdService.loadAndCacheDevices();
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdConnectFlow] register/record failed:', msg);
            showAlert('연결 기록 실패', '기기 연결은 되었으나 서버 기록에 실패했습니다.', 'ERROR');
        }

        // 서버에 장치 등록·히스토리 기록 후 폴링 시작 (0904/0906 수신 시 doResolveAndConnect가 recordConnect 호출하므로 device가 이미 있어야 함)
        ObdService.startPolling(1000);

        setObdModalVisible(false);
        showAlert('연결 완료', 'OBD 어댑터가 선택한 차량에 연결되었습니다.', 'SUCCESS', async () => {
            navigation.goBack();
            await checkAndRequestBatteryOpt();
        });
    };

    const Header = (
        <View className="flex-row items-center px-4 py-3 border-b border-white/5">
            <TouchableOpacity
                className="w-10 h-10 items-center justify-center -ml-2 rounded-full active:bg-white/10"
                onPress={() => navigation.goBack()}
            >
                <MaterialIcons name="arrow-back-ios-new" size={24} color="#f1f5f9" />
            </TouchableOpacity>
            <Text className="text-xl font-bold text-white flex-1 ml-2">OBD 어댑터 연결</Text>
        </View>
    );

    if (vehicles.length === 0) {
        return (
            <BaseScreen header={Header} scrollable={true} padding={false}>
                <View className="px-5 py-8">
                    <Text className="text-text-muted text-center">등록된 차량이 없습니다. 차량을 먼저 등록해주세요.</Text>
                    <TouchableOpacity
                        className="mt-6 py-3 bg-primary/20 rounded-xl items-center border border-primary/30"
                        onPress={() => navigation.goBack()}
                    >
                        <Text className="text-primary font-semibold">설정으로 돌아가기</Text>
                    </TouchableOpacity>
                </View>
            </BaseScreen>
        );
    }

    return (
        <BaseScreen header={Header} scrollable={true} padding={false}>
            <View className="px-5 pt-6 pb-12">
                <Text className="text-white/80 text-sm mb-4">어떤 차량에 연결할까요?</Text>
                <ScrollView className="mb-6" showsVerticalScrollIndicator={false}>
                    {vehicles.map((v: VehicleResponse) => {
                        const isSelected = v.vehicleId === effectiveSelectedId;
                        return (
                            <TouchableOpacity
                                key={v.vehicleId}
                                className={`flex-row items-center gap-3 py-4 px-4 rounded-2xl mb-2 border ${isSelected ? 'bg-primary/10 border-primary/40' : 'bg-white/5 border-white/10'}`}
                                onPress={() => setSelectedVehicleId(v.vehicleId)}
                                activeOpacity={0.8}
                            >
                                <View className={`w-10 h-10 rounded-xl items-center justify-center ${isSelected ? 'bg-primary/30' : 'bg-white/10'}`}>
                                    <MaterialIcons name="directions-car" size={24} color={isSelected ? '#0d7ff2' : '#94a3b8'} />
                                </View>
                                <View className="flex-1">
                                    <Text className={`font-semibold ${isSelected ? 'text-white' : 'text-white/90'}`}>
                                        {v.manufacturerKo} {v.modelNameKo}
                                    </Text>
                                    <Text className="text-text-dim text-xs">{v.carNumber || '번호판 미등록'}</Text>
                                </View>
                                {isSelected && <MaterialIcons name="check-circle" size={24} color="#0d7ff2" />}
                            </TouchableOpacity>
                        );
                    })}
                </ScrollView>
                <TouchableOpacity
                    className="w-full py-4 bg-primary rounded-2xl flex-row items-center justify-center gap-2 active:opacity-90"
                    onPress={handleConnectPress}
                    activeOpacity={0.9}
                >
                    <MaterialIcons name="bluetooth-searching" size={24} color="white" />
                    <Text className="text-white font-bold text-base">연결하기</Text>
                </TouchableOpacity>
            </View>

            <ObdConnect
                visible={obdModalVisible}
                onClose={() => setObdModalVisible(false)}
                onConnected={handleConnected}
                onConnectionFailed={() => setObdModalVisible(true)}
                selectedVehicleId={effectiveSelectedId}
                selectedVehicleLabel={selectedVehicleLabel}
                onVehicleChangeSuccess={() => {
                    showAlert('연결 변경 완료', '선택한 차량으로 OBD 연결이 변경되었습니다.', 'SUCCESS', async () => {
                        navigation.goBack();
                        await checkAndRequestBatteryOpt();
                    });
                }}
            />
        </BaseScreen>
    );
}
