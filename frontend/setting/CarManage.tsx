import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, Modal, Pressable, ActivityIndicator, ScrollView } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import BaseScreen from '../components/layout/BaseScreen';
import { useAlertStore } from '../store/useAlertStore';
import { useBleStore } from '../store/useBleStore';
import ObdConnect from './ObdConnect';

import { useVehicleStore } from '../store/useVehicleStore';
import {
    setPrimaryVehicle as apiSetPrimaryVehicle,
    deleteVehicle as apiDeleteVehicle,
    VehicleResponse
} from '../api/vehicleApi';
import { obdDeviceApi } from '../api/obdApi';
import ObdService from '../services/ObdService';
import { checkAndRequestBatteryOpt } from '../utils/BatteryOptConfig';

// 차량 디스플레이용 변환 함수
const formatMileage = (mileage: number | null | undefined): string => {
    if (!mileage) return '0 km';
    return `${mileage.toLocaleString()} km`;
};

const formatFuelType = (fuelType: string | null): string => {
    const map: { [key: string]: string } = {
        'GASOLINE': '가솔린',
        'DIESEL': '디젤',
        'LPG': 'LPG',
        'EV': '전기',
        'HEV': '하이브리드',
    };
    return map[fuelType || ''] || '-';
};

export default function CarManage() {
    const navigation = useNavigation<any>();

    // Store
    const { vehicles, fetchVehicles, isLoading: isStoreLoading } = useVehicleStore();

    // Local State
    const [isLoading, setIsLoading] = useState(true);
    const [obdModalVisible, setObdModalVisible] = useState(false);
    const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
    const [selectedVehicleIdForObd, setSelectedVehicleIdForObd] = useState<string | null>(null);

    // Primary Vehicle Derived State
    const primaryVehicle = vehicles.find(v => v.isPrimary) || vehicles[0];
    // 전체 차량 목록 정렬 (대표 차량이 맨 위로)
    const sortedVehicles = [...vehicles].sort((a, b) => {
        if (a.isPrimary) return -1;
        if (b.isPrimary) return 1;
        return 0;
    });

    // 차량 목록 불러오기 (초기 선택 로직 제거, 단순히 리스트만 로드)
    const loadVehicles = async () => {
        try {
            setIsLoading(true);
            await fetchVehicles();
        } catch (error) {
            console.error('[CarManage] Failed to load vehicles:', error);
            useAlertStore.getState().showAlert('오류', '차량 목록을 불러오는데 실패했습니다.', 'ERROR');
        } finally {
            setIsLoading(false);
        }
    };

    // 화면 포커스 시 새로고침
    useFocusEffect(
        useCallback(() => {
            loadVehicles();
        }, [])
    );

    // 대표 차량 선택 핸들러 (Direct Toggle)
    const handleTogglePrimary = async (vehicle: VehicleResponse, e?: any) => {
        if (e) e.stopPropagation();

        // 이미 대표 차량이면 반응 없음 (또는 해제 로직이 필요하다면 추가, 보통은 다른걸 선택해서 변경함)
        if (vehicle.isPrimary) return;

        try {
            await apiSetPrimaryVehicle(vehicle.vehicleId);
            // 로컬 상태 즉시 업데이트 (낙관적 UI)
            const updatedVehicles = vehicles.map(v => ({
                ...v,
                isPrimary: v.vehicleId === vehicle.vehicleId
            }));
            useVehicleStore.setState({ vehicles: updatedVehicles });

            // 확실하게 하기 위해 서버 다시 조회
            await loadVehicles();
            useAlertStore.getState().showAlert('성공', '대표 차량이 변경되었습니다.', 'SUCCESS');
        } catch (error) {
            console.error('[CarManage] Failed to set primary vehicle:', error);
            useAlertStore.getState().showAlert('오류', '대표 차량 설정에 실패했습니다.', 'ERROR');
        }
    };

    // 차량 삭제 핸들러
    const handleDeleteVehicle = async (vehicleId: string) => {
        try {
            await apiDeleteVehicle(vehicleId);
            useAlertStore.getState().showAlert('성공', '차량이 삭제되었습니다.', 'SUCCESS');

            // 로컬 상태 업데이트
            const updatedVehicles = vehicles.filter(v => v.vehicleId !== vehicleId);
            useVehicleStore.setState({ vehicles: updatedVehicles });

            // 서버 동기화
            await loadVehicles();
        } catch (error) {
            console.error('[CarManage] Failed to delete vehicle:', error);
            // 에러 처리 (필요시 상세화)
            useAlertStore.getState().showAlert('오류', '차량 삭제에 실패했습니다.', 'ERROR');
        }
    };

    // OBD 연결 성공 핸들러 (차량 선택 후 연결 시 서버 기록 + 로컬 캐시 갱신)
    const handleObdConnected = async (device: { id: string; name: string; type: 'ble' | 'classic'; classicDevice?: { address: string } }) => {
        const vehicleId = selectedVehicleIdForObd;
        if (vehicleId) {
            const deviceId = device.type === 'classic' && device.classicDevice
                ? device.classicDevice.address
                : device.id;
            try {
                await ObdService.ensureNotificationPermissionForPolling();

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
                console.error('[CarManage] register/record failed:', msg);
                useAlertStore.getState().showAlert('연결 기록 실패', '기기 연결은 되었으나 서버 기록에 실패했습니다.', 'ERROR');
            }
            // 실제 앱 플로우에서 폴링 시작
            ObdService.startPolling(1000);

            setSelectedVehicleIdForObd(null);
            setObdModalVisible(false);
            useAlertStore.getState().showAlert(
                '연결 완료',
                'OBD 어댑터가 선택한 차량에 연결되었습니다.',
                'SUCCESS',
                async () => {
                    await checkAndRequestBatteryOpt();
                }
            );
            return;
        }
        setObdModalVisible(false);
        navigation.navigate('ActiveLoading', {
            isNewRegistration: true,
            deviceName: device.name
        });
    };

    const HeaderCustom = (
        <View className="flex-row items-center px-4 py-3 border-b border-white/5">
            <TouchableOpacity
                className="w-10 h-10 items-center justify-center -ml-2 rounded-full hover:bg-white/5 active:bg-white/10"
                onPress={() => navigation.goBack()}
            >
                <MaterialIcons name="arrow-back-ios-new" size={24} color="#f1f5f9" />
            </TouchableOpacity>
            <Text className="text-xl font-bold text-white flex-1 ml-2">내 차량 관리</Text>
            <TouchableOpacity onPress={loadVehicles}>
                <MaterialIcons name="refresh" size={24} color="#94a3b8" />
            </TouchableOpacity>
        </View>
    );

    // 로딩 중
    if (isLoading && vehicles.length === 0) {
        return (
            <View className="flex-1 bg-deep-black items-center justify-center">
                <ActivityIndicator size="large" color="#0d7ff2" />
                <Text className="text-text-muted mt-4">차량 정보를 불러오는 중...</Text>
            </View>
        );
    }

    return (
        <BaseScreen
            header={HeaderCustom}
            scrollable={true}
            padding={false}
        >
            <Pressable className="flex-1 min-h-full" onPress={() => setActiveMenuId(null)}>
                <View className="px-5 pt-6 pb-12">

                    {/* Main Car Card (Restored & Clickable) -> Now Non-Clickable */}
                    {primaryVehicle ? (
                        <View className="relative overflow-hidden rounded-3xl border border-white/10 mb-8">
                            <LinearGradient
                                colors={['rgba(26, 30, 35, 0.6)', 'rgba(26, 30, 35, 0.9)']}
                                className="p-6"
                            >
                                <View className="flex-row justify-between items-start mb-6">
                                    <View>
                                        <View className="flex-row items-center gap-2 mb-3">
                                            <View className="flex-row items-center gap-1.5 px-3 py-1 bg-primary/20 border border-primary/30 rounded-full">
                                                <View className="w-1.5 h-1.5 bg-primary rounded-full" />
                                                <Text className="text-[10px] font-bold text-primary uppercase tracking-wider">대표 차량</Text>
                                            </View>
                                            {primaryVehicle.cloudLinked && (
                                                <View className="bg-green-500/20 px-3 py-1 rounded-full border border-green-500/30 flex-row items-center gap-1.5">
                                                    <MaterialIcons name="bolt" size={12} color="#4ade80" />
                                                    <Text className="text-[10px] font-bold text-green-400 uppercase tracking-wider">Linked</Text>
                                                </View>
                                            )}
                                        </View>
                                        <Text className="text-2xl font-bold text-white tracking-tight mb-1">
                                            {primaryVehicle.manufacturerKo} {primaryVehicle.modelNameKo}
                                        </Text>
                                        <Text className="text-text-muted text-sm">
                                            {primaryVehicle.carNumber || '번호판 미등록'}
                                        </Text>
                                    </View>
                                </View>

                                <View className="flex-row gap-3 mt-2">
                                    <View className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md">
                                        <Text className="text-[10px] text-text-dim mb-1">총 주행거리</Text>
                                        <Text className="text-base font-bold text-white">
                                            {formatMileage(primaryVehicle.totalMileage)}
                                        </Text>
                                    </View>
                                    <View className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md">
                                        <Text className="text-[10px] text-text-dim mb-1">연료 타입</Text>
                                        <Text className="text-base font-bold text-white">
                                            {formatFuelType(primaryVehicle.fuelType)}
                                        </Text>
                                    </View>
                                </View>
                            </LinearGradient>
                        </View>
                    ) : null}

                    {/* Other Vehicle List */}
                    {sortedVehicles.length > 0 && (
                        <View className="mb-8 relative z-10">
                            <Text className="px-2 text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3">내 차량 목록</Text>
                            <View className="bg-surface-card/60 border border-white/5 rounded-2xl backdrop-blur-md">
                                {sortedVehicles.map((vehicle, index) => {
                                    const isMenuOpen = activeMenuId === vehicle.vehicleId;
                                    return (
                                        <View key={vehicle.vehicleId} className={`relative ${isMenuOpen ? 'z-50' : 'z-20'}`}>
                                            <View
                                                className={`flex-row items-center gap-4 px-5 py-4 ${index !== sortedVehicles.length - 1 ? 'border-b border-white/5' : ''}`}
                                            >
                                                {/* Icon */}
                                                <View className={`w-11 h-11 items-center justify-center rounded-xl shrink-0 bg-surface-highlight ${vehicle.isPrimary ? 'border-2 border-primary' : ''}`}>
                                                    <MaterialIcons
                                                        name="directions-car"
                                                        size={24}
                                                        color={vehicle.isPrimary ? "#0d7ff2" : "#94a3b8"}
                                                    />
                                                </View>

                                                {/* Info */}
                                                <View className="flex-1">
                                                    <Text className={`text-base font-medium mb-0.5 text-white`}>
                                                        {vehicle.manufacturerKo} {vehicle.modelNameKo}
                                                    </Text>
                                                    <View className="flex-row items-center gap-2">
                                                        <Text className="text-text-dim text-xs">
                                                            {vehicle.carNumber || '번호판 미등록'}
                                                        </Text>
                                                        {vehicle.isPrimary && (
                                                            <View className="bg-primary/20 px-2 py-0.5 rounded border border-primary/30 flex-row items-center gap-1">
                                                                <View className="w-1 h-1 bg-primary rounded-full" />
                                                                <Text className="text-[9px] font-bold text-primary uppercase tracking-wider">대표차량</Text>
                                                            </View>
                                                        )}
                                                        {vehicle.cloudLinked && (
                                                            <View className="bg-green-500/20 px-2 py-0.5 rounded border border-green-500/30 flex-row items-center gap-1">
                                                                <MaterialIcons name="bolt" size={9} color="#4ade80" />
                                                                <Text className="text-[9px] font-bold text-green-400 uppercase tracking-wider">Linked</Text>
                                                            </View>
                                                        )}
                                                    </View>
                                                </View>

                                                {/* Menu Button (replacing Star) */}
                                                <TouchableOpacity
                                                    className="p-2 -mr-2"
                                                    onPress={(e) => {
                                                        e.stopPropagation();
                                                        setActiveMenuId(isMenuOpen ? null : vehicle.vehicleId);
                                                    }}
                                                >
                                                    <MaterialIcons
                                                        name="more-vert"
                                                        size={24}
                                                        color="#94a3b8"
                                                    />
                                                </TouchableOpacity>
                                            </View>

                                            {/* Dropdown Menu */}
                                            {isMenuOpen && (
                                                <View className="absolute right-4 top-12 w-40 bg-[#1e2229] border border-white/10 rounded-xl shadow-lg z-50 overflow-hidden">
                                                    <TouchableOpacity
                                                        className="flex-row items-center gap-2 px-4 py-3 active:bg-white/5 border-b border-white/5"
                                                        onPress={(e) => {
                                                            e.stopPropagation();
                                                            navigation.navigate('CarEdit', { vehicleId: vehicle.vehicleId });
                                                            setActiveMenuId(null);
                                                        }}
                                                    >
                                                        <MaterialIcons name="edit" size={18} color="#f1f5f9" />
                                                        <Text className="text-white text-sm">수정</Text>
                                                    </TouchableOpacity>
                                                    <TouchableOpacity
                                                        className="flex-row items-center gap-2 px-4 py-3 active:bg-white/5 border-b border-white/5"
                                                        onPress={(e) => {
                                                            e.stopPropagation();
                                                            handleTogglePrimary(vehicle);
                                                            setActiveMenuId(null);
                                                        }}
                                                    >
                                                        <MaterialIcons name="star-outline" size={18} color="#f1f5f9" />
                                                        <Text className="text-white text-sm">대표 차량 설정</Text>
                                                    </TouchableOpacity>
                                                    <TouchableOpacity
                                                        className="flex-row items-center gap-2 px-4 py-3 active:bg-white/5 border-b border-white/5"
                                                        onPress={(e) => {
                                                            e.stopPropagation();
                                                            setSelectedVehicleIdForObd(vehicle.vehicleId);
                                                            setObdModalVisible(true);
                                                            setActiveMenuId(null);
                                                        }}
                                                    >
                                                        <MaterialIcons name="bluetooth" size={18} color="#f1f5f9" />
                                                        <Text className="text-white text-sm">OBD 연결</Text>
                                                    </TouchableOpacity>
                                                    <TouchableOpacity
                                                        className="flex-row items-center gap-2 px-4 py-3 active:bg-white/5"
                                                        onPress={(e) => {
                                                            e.stopPropagation();
                                                            handleDeleteVehicle(vehicle.vehicleId);
                                                            setActiveMenuId(null);
                                                        }}
                                                    >
                                                        <MaterialIcons name="delete-outline" size={18} color="#ef4444" />
                                                        <Text className="text-red-500 text-sm">삭제</Text>
                                                    </TouchableOpacity>
                                                </View>
                                            )}
                                        </View>
                                    );
                                })}
                            </View>
                        </View>
                    )}
                    {vehicles.length === 0 && (
                        <View className="rounded-3xl border border-dashed border-white/20 p-8 mb-8 items-center">
                            <MaterialIcons name="directions-car" size={48} color="#475569" />
                            <Text className="text-text-muted mt-4 text-center">
                                등록된 차량이 없습니다.{'\n'}아래 버튼으로 차량을 등록해주세요.
                            </Text>
                        </View>
                    )}

                    {/* Info Text */}
                    {/* <View className="px-4 mb-8">
                        <Text className="text-xs text-text-dim text-center leading-relaxed">
                            <MaterialIcons name="info-outline" size={12} /> 목록의 <MaterialIcons name="more-vert" size={12} color="#94a3b8" /> 버튼을 눌러 수정 및 관리를 할 수 있습니다.{'\n'}화면 빈 공간을 터치하면 메뉴가 닫힙니다.
                        </Text>
                    </View> */}

                    {/* Register Button */}
                    <TouchableOpacity
                        className="w-full py-4 bg-primary/10 rounded-2xl flex-row items-center justify-center gap-2 border border-primary/30 active:bg-primary/20 mb-10"
                        activeOpacity={0.8}
                        onPress={() => navigation.navigate('PassiveReg')}
                    >
                        <MaterialIcons name="add-circle-outline" size={24} color="#0d7ff2" />
                        <Text className="text-primary font-bold text-base">새 차량 등록하기</Text>
                    </TouchableOpacity>
                </View>
            </Pressable >

            <ObdConnect
                visible={obdModalVisible}
                onClose={() => {
                    setObdModalVisible(false);
                    setSelectedVehicleIdForObd(null);
                }}
                onConnected={handleObdConnected}
                onConnectionFailed={() => setObdModalVisible(true)}
            />
        </BaseScreen >
    );
}
