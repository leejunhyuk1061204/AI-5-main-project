import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, Modal, Pressable, ActivityIndicator, Alert, ScrollView } from 'react-native';
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
    const [selectedVehicle, setSelectedVehicle] = useState<VehicleResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [modalVisible, setModalVisible] = useState(false);
    const [specModalVisible, setSpecModalVisible] = useState(false);
    const [editModalVisible, setEditModalVisible] = useState(false);
    const [obdModalVisible, setObdModalVisible] = useState(false);

    // 다른 차량 목록 필터링
    const otherVehicles = vehicles.filter(v => v.vehicleId !== selectedVehicle?.vehicleId);

    // 차량 목록 불러오기 & 대표차량 설정
    const loadVehicles = async () => {
        try {
            setIsLoading(true);
            const list = await fetchVehicles();

            // 대표 차량 찾기
            const primary = list.find(v => v.isPrimary);
            if (primary) {
                setSelectedVehicle(primary);
            } else if (list.length > 0) {
                setSelectedVehicle(list[0]);
            } else {
                setSelectedVehicle(null);
            }
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

    // 대표 차량 선택 핸들러
    const handleSelectPrimaryVehicle = async (vehicle: VehicleResponse) => {
        try {
            await apiSetPrimaryVehicle(vehicle.vehicleId);
            setSelectedVehicle(vehicle);
            await AsyncStorage.setItem('primaryVehicle', JSON.stringify(vehicle));
            setModalVisible(false);
            await loadVehicles();
            await loadVehicles();
            useAlertStore.getState().showAlert('성공', '대표 차량이 설정되었습니다.', 'SUCCESS');
        } catch (error) {
            console.error('[CarManage] Failed to set primary vehicle:', error);
            useAlertStore.getState().showAlert('오류', '대표 차량 설정에 실패했습니다.', 'ERROR');
        }
    };

    // 차량 제원 보기 선택 핸들러 (Smart Selection)
    const handleSelectSpecVehicle = (vehicle?: VehicleResponse) => {
        setSpecModalVisible(false);
        if (vehicle) {
            navigation.navigate('Spec', { vehicleId: vehicle.vehicleId });
        } else if (vehicles.length === 1) {
            navigation.navigate('Spec', { vehicleId: vehicles[0].vehicleId });
        } else if (vehicles.length > 1) {
            setSpecModalVisible(true);
        } else {
            useAlertStore.getState().showAlert('알림', '등록된 차량이 없습니다.', 'INFO');
        }
    };

    // 차량 수정 선택 핸들러 (Smart Selection)
    const handleEditVehicle = (vehicle?: VehicleResponse) => {
        setEditModalVisible(false);
        if (vehicle) {
            navigation.navigate('CarEdit', { vehicleId: vehicle.vehicleId });
        } else if (vehicles.length === 1) {
            navigation.navigate('CarEdit', { vehicleId: vehicles[0].vehicleId });
        } else if (vehicles.length > 1) {
            setEditModalVisible(true);
        } else {
            useAlertStore.getState().showAlert('알림', '등록된 차량이 없습니다.', 'INFO');
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
                {/* Main Car Card */}
                {selectedVehicle ? (
                    <View className="relative overflow-hidden rounded-3xl border border-white/10 mb-8">
                        <LinearGradient
                            colors={['rgba(26, 30, 35, 0.6)', 'rgba(26, 30, 35, 0.9)']}
                            className="p-6"
                        >
                            <View className="flex-row justify-between items-start mb-6">
                                <View>
                                    <View className="flex-row items-center gap-1.5 px-3 py-1 bg-primary/20 border border-primary/30 rounded-full mb-3 self-start">
                                        <View className="w-1.5 h-1.5 bg-primary rounded-full" />
                                        <Text className="text-[10px] font-bold text-primary uppercase tracking-wider">대표 차량</Text>
                                    </View>
                                    <Text className="text-2xl font-bold text-white tracking-tight mb-1">
                                        {selectedVehicle.manufacturer} {selectedVehicle.modelName}
                                    </Text>
                                    <Text className="text-text-muted text-sm">
                                        {selectedVehicle.carNumber || '번호판 미등록'}
                                    </Text>
                                </View>
                                <View className="bg-white/5 p-2 rounded-xl border border-white/5">
                                    <MaterialIcons name="verified-user" size={24} color="#0d7ff2" />
                                </View>
                            </View>

                            <View className="flex-row gap-3 mt-2">
                                <View className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md">
                                    <Text className="text-[10px] text-text-dim mb-1">총 주행거리</Text>
                                    <Text className="text-base font-bold text-white">
                                        {formatMileage(selectedVehicle.totalMileage)}
                                    </Text>
                                </View>
                                <View className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md">
                                    <Text className="text-[10px] text-text-dim mb-1">연료 타입</Text>
                                    <Text className="text-base font-bold text-white">
                                        {formatFuelType(selectedVehicle.fuelType)}
                                    </Text>
                                </View>
                            </View>
                        </LinearGradient>
                    </View>
                ) : (
                    <View className="rounded-3xl border border-dashed border-white/20 p-8 mb-8 items-center">
                        <MaterialIcons name="directions-car" size={48} color="#475569" />
                        <Text className="text-text-muted mt-4 text-center">
                            등록된 차량이 없습니다.{'\n'}아래 버튼으로 차량을 등록해주세요.
                        </Text>
                    </View>
                )}

                {/* Other Vehicles List */}
                {otherVehicles.length > 0 && (
                    <View className="mb-8">
                        <Text className="px-2 text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3">보유 차량 목록</Text>
                        <View className="bg-surface-card/60 border border-white/5 rounded-2xl overflow-hidden backdrop-blur-md">
                            {otherVehicles.map((vehicle, index) => (
                                <View
                                    key={vehicle.vehicleId}
                                    className={`flex-row items-center gap-4 px-5 py-4 ${index !== otherVehicles.length - 1 ? 'border-b border-white/5' : ''}`}
                                >
                                    <View className="w-11 h-11 items-center justify-center rounded-xl bg-surface-highlight shrink-0">
                                        <MaterialIcons name="directions-car" size={24} color="#94a3b8" />
                                    </View>
                                    <View className="flex-1">
                                        <Text className="text-white text-base font-medium mb-0.5">
                                            {vehicle.manufacturer} {vehicle.modelName}
                                        </Text>
                                        <Text className="text-text-dim text-xs">
                                            {vehicle.carNumber || '번호판 미등록'}
                                        </Text>
                                    </View>
                                </View>
                            ))}
                        </View>
                    </View>
                )}

                {/* Management Menu */}
                <Text className="px-2 text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3">관리 메뉴</Text>
                <View className="bg-surface-card/60 border border-white/5 rounded-2xl overflow-hidden mb-6 backdrop-blur-md">
                    <TouchableOpacity
                        className="flex-row items-center gap-4 px-5 py-4 active:bg-white/5 border-b border-white/5"
                        onPress={() => handleSelectSpecVehicle()}
                    >
                        <View className="w-11 h-11 items-center justify-center rounded-xl bg-surface-highlight shrink-0">
                            <MaterialIcons name="list-alt" size={24} color="#cbd5e1" />
                        </View>
                        <Text className="text-white text-base font-medium flex-1">차량 상세 제원 보기</Text>
                        <MaterialIcons name="chevron-right" size={24} color="#475569" />
                    </TouchableOpacity>

                    <TouchableOpacity
                        className="flex-row items-center gap-4 px-5 py-4 active:bg-white/5 border-b border-white/5"
                        onPress={() => vehicles.length > 0 ? setModalVisible(true) : useAlertStore.getState().showAlert('알림', '등록된 차량이 없습니다.', 'INFO')}
                    >
                        <View className="w-11 h-11 items-center justify-center rounded-xl bg-surface-highlight shrink-0">
                            <MaterialIcons name="star-half" size={24} color="#cbd5e1" />
                        </View>
                        <Text className="text-white text-base font-medium flex-1">대표 차량으로 설정</Text>
                        <MaterialIcons name="chevron-right" size={24} color="#475569" />
                    </TouchableOpacity>

                    <TouchableOpacity
                        className="flex-row items-center gap-4 px-5 py-4 active:bg-white/5 border-b border-white/5"
                        onPress={() => setObdModalVisible(true)}
                    >
                        <View className="w-11 h-11 items-center justify-center rounded-xl bg-surface-highlight shrink-0">
                            <MaterialIcons name="bluetooth-connected" size={24} color="#cbd5e1" />
                        </View>
                        <Text className="text-white text-base font-medium flex-1">OBD 스캐너 등록</Text>
                        <MaterialIcons name="chevron-right" size={24} color="#475569" />
                    </TouchableOpacity>

                    <TouchableOpacity
                        className="flex-row items-center gap-4 px-5 py-4 active:bg-white/5"
                        onPress={() => handleEditVehicle()}
                    >
                        <View className="w-11 h-11 items-center justify-center rounded-xl bg-surface-highlight shrink-0">
                            <MaterialIcons name="edit" size={24} color="#cbd5e1" />
                        </View>
                        <Text className="text-white text-base font-medium flex-1">차량 정보 수정</Text>
                        <MaterialIcons name="chevron-right" size={24} color="#475569" />
                    </TouchableOpacity>
                </View>

                {/* Register Button */}
                <TouchableOpacity
                    className="w-full py-4 bg-primary/10 rounded-2xl flex-row items-center justify-center gap-2 border border-primary/30 active:bg-primary/20 mb-10"
                    activeOpacity={0.8}
                    onPress={() => navigation.navigate('RegisterMain')}
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

            {/* 대표 차량 선택 모달 */}
            <Modal
                animationType="fade"
                transparent={true}
                visible={modalVisible}
                onRequestClose={() => setModalVisible(false)}
            >
                <Pressable
                    className="flex-1 bg-black/70 justify-center items-center px-6"
                    onPress={() => setModalVisible(false)}
                >
                    <Pressable
                        className="w-full bg-surface-dark border border-white/10 rounded-3xl overflow-hidden"
                        onPress={(e) => e.stopPropagation()}
                    >
                        <View className="px-6 py-5 border-b border-white/10 flex-row items-center justify-between">
                            <Text className="text-lg font-bold text-white">대표 차량 선택</Text>
                            <TouchableOpacity
                                className="w-8 h-8 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                                onPress={() => setModalVisible(false)}
                            >
                                <MaterialIcons name="close" size={20} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>

                        <ScrollView className="max-h-80">
                            {vehicles.map((vehicle, index) => {
                                const isSelected = selectedVehicle?.vehicleId === vehicle.vehicleId;
                                const isLast = index === vehicles.length - 1;

                                return (
                                    <TouchableOpacity
                                        key={vehicle.vehicleId}
                                        className={`flex-row items-center gap-4 px-6 py-4 active:bg-white/5 ${!isLast ? 'border-b border-white/5' : ''
                                            } ${isSelected ? 'bg-primary/10' : ''}`}
                                        onPress={() => handleSelectPrimaryVehicle(vehicle)}
                                    >
                                        <View className={`w-12 h-12 items-center justify-center rounded-xl ${isSelected ? 'bg-primary/20 border border-primary/30' : 'bg-white/5 border border-white/10'
                                            }`}>
                                            <MaterialIcons
                                                name="directions-car"
                                                size={24}
                                                color={isSelected ? '#0d7ff2' : '#94a3b8'}
                                            />
                                        </View>

                                        <View className="flex-1">
                                            <Text className={`text-base font-semibold mb-0.5 ${isSelected ? 'text-primary' : 'text-white'}`}>
                                                {vehicle.manufacturer} {vehicle.modelName}
                                            </Text>
                                            <Text className="text-text-dim text-xs">{vehicle.carNumber || '번호판 미등록'}</Text>
                                        </View>

                                        {isSelected ? (
                                            <View className="w-6 h-6 items-center justify-center rounded-full bg-primary">
                                                <MaterialIcons name="check" size={16} color="#fff" />
                                            </View>
                                        ) : (
                                            <View className="w-6 h-6 rounded-full border-2 border-white/20" />
                                        )}
                                    </TouchableOpacity>
                                );
                            })}
                        </ScrollView>

                        <View className="px-6 py-4 border-t border-white/10">
                            <Text className="text-xs text-text-muted text-center">
                                대표 차량으로 설정하면 메인 화면에 해당 차량 정보가 표시됩니다.
                            </Text>
                        </View>
                    </Pressable>
                </Pressable>
            </Modal>

            {/* 차량 제원 선택 모달 */}
            <Modal
                animationType="fade"
                transparent={true}
                visible={specModalVisible}
                onRequestClose={() => setSpecModalVisible(false)}
            >
                <Pressable
                    className="flex-1 bg-black/70 justify-center items-center px-6"
                    onPress={() => setSpecModalVisible(false)}
                >
                    <Pressable
                        className="w-full bg-surface-dark border border-white/10 rounded-3xl overflow-hidden"
                        onPress={(e) => e.stopPropagation()}
                    >
                        <View className="px-6 py-5 border-b border-white/10 flex-row items-center justify-between">
                            <Text className="text-lg font-bold text-white">차량 제원 선택</Text>
                            <TouchableOpacity
                                className="w-8 h-8 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                                onPress={() => setSpecModalVisible(false)}
                            >
                                <MaterialIcons name="close" size={20} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>
                        <ScrollView className="max-h-80">
                            {vehicles.map((vehicle, index) => {
                                const isLast = index === vehicles.length - 1;
                                return (
                                    <TouchableOpacity
                                        key={vehicle.vehicleId}
                                        className={`flex-row items-center gap-4 px-6 py-4 active:bg-white/5 ${!isLast ? 'border-b border-white/5' : ''}`}
                                        onPress={() => handleSelectSpecVehicle(vehicle)}
                                    >
                                        <View className="w-10 h-10 items-center justify-center rounded-xl bg-white/5 border border-white/10">
                                            <MaterialIcons name="directions-car" size={20} color="#94a3b8" />
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-base font-semibold text-white">
                                                {vehicle.manufacturer} {vehicle.modelName}
                                            </Text>
                                            <Text className="text-text-dim text-xs">{vehicle.carNumber}</Text>
                                        </View>
                                        <MaterialIcons name="chevron-right" size={20} color="#475569" />
                                    </TouchableOpacity>
                                );
                            })}
                        </ScrollView>
                    </Pressable>
                </Pressable>
            </Modal>

            {/* 차량 수정 선택 모달 */}
            <Modal
                animationType="fade"
                transparent={true}
                visible={editModalVisible}
                onRequestClose={() => setEditModalVisible(false)}
            >
                <Pressable
                    className="flex-1 bg-black/70 justify-center items-center px-6"
                    onPress={() => setEditModalVisible(false)}
                >
                    <Pressable
                        className="w-full bg-surface-dark border border-white/10 rounded-3xl overflow-hidden"
                        onPress={(e) => e.stopPropagation()}
                    >
                        <View className="px-6 py-5 border-b border-white/10 flex-row items-center justify-between">
                            <Text className="text-lg font-bold text-white">수정할 차량 선택</Text>
                            <TouchableOpacity
                                className="w-8 h-8 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                                onPress={() => setEditModalVisible(false)}
                            >
                                <MaterialIcons name="close" size={20} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>
                        <ScrollView className="max-h-80">
                            {vehicles.map((vehicle, index) => {
                                const isLast = index === vehicles.length - 1;
                                return (
                                    <TouchableOpacity
                                        key={vehicle.vehicleId}
                                        className={`flex-row items-center gap-4 px-6 py-4 active:bg-white/5 ${!isLast ? 'border-b border-white/5' : ''}`}
                                        onPress={() => handleEditVehicle(vehicle)}
                                    >
                                        <View className="w-10 h-10 items-center justify-center rounded-xl bg-white/5 border border-white/10">
                                            <MaterialIcons name="edit" size={20} color="#94a3b8" />
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-base font-semibold text-white">
                                                {vehicle.manufacturer} {vehicle.modelName}
                                            </Text>
                                            <Text className="text-text-dim text-xs">{vehicle.carNumber}</Text>
                                        </View>
                                        <MaterialIcons name="chevron-right" size={20} color="#475569" />
                                    </TouchableOpacity>
                                );
                            })}
                        </ScrollView>
                    </Pressable>
                </Pressable>
            </Modal>
        </BaseScreen>
    );
}
