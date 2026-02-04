import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, Modal, Pressable, ActivityIndicator, ScrollView } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import BaseScreen from '../components/layout/BaseScreen';
import { useAlertStore } from '../store/useAlertStore';
import ObdConnect from './ObdConnect';

import { useVehicleStore } from '../store/useVehicleStore';
import {
    setPrimaryVehicle as apiSetPrimaryVehicle,
    deleteVehicle as apiDeleteVehicle,
    VehicleResponse
} from '../api/vehicleApi';

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

    // Primary Vehicle Derived State
    const primaryVehicle = vehicles.find(v => v.isPrimary) || vehicles[0];
    const otherVehicles = vehicles.filter(v => v.vehicleId !== primaryVehicle?.vehicleId);

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

    // OBD 연결 성공 핸들러
    const handleObdConnected = (device: any) => {
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
            <View className="px-5 pt-6">

                {/* Main Car Card (Restored & Clickable) */}
                {primaryVehicle ? (
                    <TouchableOpacity
                        className="relative overflow-hidden rounded-3xl border border-white/10 mb-8 active:opacity-90"
                        onPress={() => navigation.navigate('CarEdit', { vehicleId: primaryVehicle.vehicleId })}
                    >
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
                                <View className="bg-white/5 p-2 rounded-xl border border-white/5">
                                    <MaterialIcons name="edit" size={20} color="#0d7ff2" />
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
                    </TouchableOpacity>
                ) : null}

                {/* Other Vehicle List */}
                {otherVehicles.length > 0 && (
                    <View className="mb-8">
                        <Text className="px-2 text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3">내 차량 목록</Text>
                        <View className="bg-surface-card/60 border border-white/5 rounded-2xl overflow-hidden backdrop-blur-md">
                            {otherVehicles.map((vehicle, index) => {
                                return (
                                    <TouchableOpacity
                                        key={vehicle.vehicleId}
                                        className={`flex-row items-center gap-4 px-5 py-4 active:bg-white/5 ${index !== otherVehicles.length - 1 ? 'border-b border-white/5' : ''}`}
                                        onPress={() => navigation.navigate('CarEdit', { vehicleId: vehicle.vehicleId })}
                                    >
                                        {/* Icon */}
                                        <View className={`w-11 h-11 items-center justify-center rounded-xl shrink-0 bg-surface-highlight`}>
                                            <MaterialIcons
                                                name="directions-car"
                                                size={24}
                                                color="#94a3b8"
                                            />
                                        </View>

                                        {/* Info */}
                                        <View className="flex-1">
                                            <View className="flex-row items-center gap-2">
                                                <Text className={`text-base font-medium mb-0.5 text-white`}>
                                                    {vehicle.manufacturerKo} {vehicle.modelNameKo}
                                                </Text>
                                                {vehicle.cloudLinked && (
                                                    <View className="bg-green-500/20 px-1.5 py-0.5 rounded flex-row items-center gap-0.5">
                                                        <MaterialIcons name="bolt" size={10} color="#4ade80" />
                                                        <Text className="text-[10px] text-green-400 font-bold">Linked</Text>
                                                    </View>
                                                )}
                                            </View>
                                            <Text className="text-text-dim text-xs">
                                                {vehicle.carNumber || '번호판 미등록'}
                                            </Text>
                                        </View>

                                        {/* Star Button (Primary Toggle) */}
                                        <TouchableOpacity
                                            className="p-2 -mr-2"
                                            onPress={(e) => handleTogglePrimary(vehicle, e)}
                                        >
                                            <MaterialIcons
                                                name="star-outline"
                                                size={28}
                                                color="#475569"
                                            />
                                        </TouchableOpacity>
                                    </TouchableOpacity>
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
                <View className="px-4 mb-8">
                    <Text className="text-xs text-text-dim text-center leading-relaxed">
                        <MaterialIcons name="info-outline" size={12} /> 목록의 <MaterialIcons name="star" size={12} color="#fbbf24" /> 아이콘을 눌러 대표 차량을 설정할 수 있습니다.{'\n'}차량을 터치하면 상세 정보를 수정할 수 있습니다.
                    </Text>
                </View>

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

            <ObdConnect
                visible={obdModalVisible}
                onClose={() => setObdModalVisible(false)}
                onConnected={handleObdConnected}
            />
        </BaseScreen>
    );
}
