import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import BaseScreen from '../components/layout/BaseScreen';
import { useVehicleStore } from '../store/useVehicleStore';
import { useAlertStore } from '../store/useAlertStore';
import maintenanceApi, { MaintenanceHistoryResponse } from '../api/maintenanceApi';

export default function MaintenanceHistory() {
    const navigation = useNavigation<any>();
    const { vehicles, primaryVehicle } = useVehicleStore();

    const [selectedVehicle, setSelectedVehicle] = useState<any>(null);
    const [maintenanceList, setMaintenanceList] = useState<MaintenanceHistoryResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    // 초기 차량 선택
    useEffect(() => {
        if (primaryVehicle) {
            setSelectedVehicle(primaryVehicle);
        } else if (vehicles.length > 0) {
            setSelectedVehicle(vehicles[0]);
        }
    }, [primaryVehicle, vehicles]);

    // 정비 이력 불러오기
    const loadMaintenanceHistory = async () => {
        if (!selectedVehicle?.vehicleId) return;

        try {
            setLoading(true);
            const history = await maintenanceApi.getMaintenanceHistory(selectedVehicle.vehicleId);
            // 날짜 최신순으로 정렬
            const sorted = history.sort((a, b) =>
                new Date(b.maintenanceDate).getTime() - new Date(a.maintenanceDate).getTime()
            );
            setMaintenanceList(sorted);
        } catch (error) {
            console.error('[MaintenanceHistory] Failed to load maintenance history:', error);
            useAlertStore.getState().showAlert('오류', '정비 이력을 불러오는데 실패했습니다.', 'ERROR');
            setMaintenanceList([]);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    // 화면 포커스 시 새로고침
    useFocusEffect(
        useCallback(() => {
            if (selectedVehicle?.vehicleId) {
                loadMaintenanceHistory();
            }
        }, [selectedVehicle?.vehicleId])
    );

    const onRefresh = () => {
        setRefreshing(true);
        loadMaintenanceHistory();
    };

    // 날짜 포맷 (YYYY.MM.DD)
    const formatDate = (dateStr: string) => {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
    };


    // 소모품 코드를 한글로 변환
    const getConsumableName = (code: string, name?: string) => {
        if (name) return name;

        const nameMap: { [key: string]: string } = {
            'ENGINE_OIL': '엔진 오일',
            'BRAKE_PAD': '브레이크 패드',
            'TIRE': '타이어',
            'AIR_FILTER': '에어 필터',
            'CABIN_FILTER': '캐빈 필터',
            'BRAKE_FLUID': '브레이크액',
            'COOLANT': '냉각수',
            'BATTERY': '배터리',
            'TRANSMISSION_OIL': '미션 오일',
            'WIPER': '와이퍼',
            'SPARK_PLUG': '점화 플러그',
            'BELT': '벨트'
        };

        return nameMap[code] || code;
    };

    const HeaderCustom = (
        <View className="flex-row items-center px-4 py-3 border-b border-white/5">
            <TouchableOpacity
                className="w-10 h-10 items-center justify-center -ml-2 rounded-full hover:bg-white/5 active:bg-white/10"
                onPress={() => navigation.goBack()}
            >
                <MaterialIcons name="arrow-back-ios-new" size={24} color="#f1f5f9" />
            </TouchableOpacity>
            <View className="flex-1 items-center">
                <Text className="text-xl font-bold text-white">정비 이력</Text>
                {selectedVehicle && (
                    <Text className="text-xs text-text-dim mt-0.5">
                        {selectedVehicle.manufacturer} {selectedVehicle.modelName}
                    </Text>
                )}
            </View>
            <TouchableOpacity
                className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                onPress={loadMaintenanceHistory}
            >
                <MaterialIcons name="refresh" size={24} color="#94a3b8" />
            </TouchableOpacity>
        </View>
    );

    return (
        <BaseScreen
            header={HeaderCustom}
            scrollable={false}
            padding={false}
        >
            <ScrollView
                className="flex-1 px-5"
                contentContainerStyle={{ paddingBottom: 20 }}
                refreshControl={
                    <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0d7ff2" />
                }
            >
                <Text className="text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3 mt-6">
                    소모품 교체 내역
                </Text>

                {loading ? (
                    <View className="py-20 items-center">
                        <ActivityIndicator size="large" color="#0d7ff2" />
                        <Text className="text-text-muted mt-4">정비 이력을 불러오는 중...</Text>
                    </View>
                ) : maintenanceList.length === 0 ? (
                    <View className="items-center justify-center py-20 gap-4">
                        <View className="w-16 h-16 rounded-full bg-white/5 items-center justify-center mb-2 border border-white/10">
                            <MaterialIcons name="build-circle" size={32} color="#64748b" />
                        </View>
                        <Text className="text-text-secondary text-base font-medium text-center">
                            등록된 정비 이력이 없습니다.
                        </Text>
                        <Text className="text-text-muted text-sm text-center px-8">
                            소모품 교체 시 자동으로 기록됩니다.
                        </Text>
                    </View>
                ) : (
                    <View className="gap-3">
                        {maintenanceList.map((item, index) => {
                            const isStandardized = item.isStandardized;

                            return (
                                <View
                                    key={item.maintenanceId || index}
                                    className="bg-white/5 border border-white/10 rounded-2xl p-5 backdrop-blur-md"
                                >
                                    {/* Header */}
                                    <View className="flex-row justify-between items-start mb-4">
                                        <View className="flex-row items-center gap-3 flex-1">
                                            <View className="w-12 h-12 rounded-xl bg-primary/20 border border-primary/30 items-center justify-center shrink-0">
                                                <MaterialIcons name="build" size={24} color="#0d7ff2" />
                                            </View>
                                            <View className="flex-1">
                                                <Text className="text-white font-bold text-base">
                                                    {getConsumableName(item.consumableItemCode, item.consumableItemName)}
                                                </Text>
                                                <View className="flex-row items-center gap-2 mt-1">
                                                    <View className={`px-2 py-0.5 rounded ${isStandardized ? 'bg-green-500/20' : 'bg-gray-500/20'}`}>
                                                        <Text className={`text-[10px] font-bold ${isStandardized ? 'text-green-400' : 'text-gray-400'}`}>
                                                            {isStandardized ? '정규 소모품' : '커스텀 교체'}
                                                        </Text>
                                                    </View>
                                                </View>
                                            </View>
                                        </View>
                                    </View>

                                    {/* Details */}
                                    <View className="flex-row gap-4 pt-4 border-t border-white/5">
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-[10px] mb-1 uppercase tracking-wider">교체일</Text>
                                            <View className="flex-row items-center gap-1">
                                                <MaterialIcons name="event" size={14} color="#94a3b8" />
                                                <Text className="text-white text-sm font-medium">
                                                    {formatDate(item.maintenanceDate)}
                                                </Text>
                                            </View>
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-[10px] mb-1 uppercase tracking-wider">주행거리</Text>
                                            <View className="flex-row items-center gap-1">
                                                <MaterialIcons name="speed" size={14} color="#94a3b8" />
                                                <Text className="text-white text-sm font-medium">
                                                    {item.mileageAtMaintenance ? `${item.mileageAtMaintenance.toLocaleString()} km` : '-'}
                                                </Text>
                                            </View>
                                        </View>
                                    </View>
                                </View>
                            );
                        })}
                    </View>
                )}
            </ScrollView>
        </BaseScreen>
    );
}
