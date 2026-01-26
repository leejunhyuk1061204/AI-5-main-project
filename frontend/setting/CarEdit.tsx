import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, Alert, ActivityIndicator } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { getVehicleDetail, updateVehicle, deleteVehicle, VehicleResponse } from '../api/vehicleApi';
import BaseScreen from '../components/layout/BaseScreen';
import { useVehicleStore } from '../store/useVehicleStore';
import { useAlertStore } from '../store/useAlertStore';

export default function CarEdit() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const { vehicleId } = route.params || {};

    const [loading, setLoading] = useState(true);
    const [vehicle, setVehicle] = useState<VehicleResponse | null>(null);

    // Form State
    const [nickname, setNickname] = useState('');
    const [carNumber, setCarNumber] = useState('');
    const [vin, setVin] = useState('');

    useEffect(() => {
        loadVehicle();
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
                                {vehicle?.manufacturer} {vehicle?.modelName}
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
        </BaseScreen>
    );
}
