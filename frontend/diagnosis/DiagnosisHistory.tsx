import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, FlatList, ActivityIndicator, StyleSheet } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import { getDiagnosisList } from '../api/aiApi';
import { getVehicleList, VehicleResponse } from '../api/vehicleApi';

export default function DiagnosisHistory() {
    const navigation = useNavigation<any>();
    const [history, setHistory] = useState<any[]>([]);
    const [vehicles, setVehicles] = useState<VehicleResponse[]>([]);
    const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [historyLoading, setHistoryLoading] = useState(false);

    useEffect(() => {
        init();
    }, []);

    const init = async () => {
        try {
            setLoading(true);
            const list = await getVehicleList();
            setVehicles(list);

            if (list.length > 0) {
                const stored = await AsyncStorage.getItem('primaryVehicle');
                let initialId = null;
                if (stored) {
                    const primary = JSON.parse(stored);
                    const isStillExist = list.some(v => v.vehicleId === primary.vehicleId);
                    if (isStillExist) {
                        initialId = primary.vehicleId;
                    }
                }

                if (!initialId) {
                    initialId = list[0].vehicleId;
                }
                setSelectedVehicleId(initialId);
                await fetchHistory(initialId);
            }
        } catch (error) {
            console.error("Failed to initialize diagnosis history:", error);
        } finally {
            setLoading(false);
        }
    };

    const fetchHistory = async (vehicleId: string) => {
        if (!vehicleId) return;
        try {
            setHistoryLoading(true);
            const data = await getDiagnosisList(vehicleId);
            setHistory(data || []);
        } catch (error) {
            console.error("Failed to load history:", error);
        } finally {
            setHistoryLoading(false);
        }
    };

    const formatDate = (dateStr: string) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
    };

    const getDisplayTitle = (item: any) => {
        if (item.status === 'ACTION_REQUIRED' || item.responseMode === 'INTERACTIVE') return '추가 정보 필요';
        if (item.status === 'DONE' || item.status === 'COMPLETED') return '진단 완료';
        if (item.status === 'PROCESSING' || item.status === 'REPLY_PROCESSING') return '진단 진행 중';
        if (item.status === 'FAILED') return '진단 실패';
        if (item.status === 'PENDING') return '진단 대기 중';
        return '종합 진단 보고서';
    };

    const getTriggerIcon = (triggerType: string) => {
        switch (triggerType) {
            case 'AUTO': return { name: 'auto-fix-high', color: '#0bda5b' }; // success
            case 'DATA': return { name: 'data-usage', color: '#00f0ff' }; // primary-glow
            case 'VISUAL': return { name: 'camera-alt', color: '#94a3b8' }; // medium gray
            case 'AUDIO': return { name: 'mic', color: '#3b82f6' }; // blue
            case 'DTC': return { name: 'warning', color: '#ff6b6b' }; // error
            case 'ROUTINE': return { name: 'event-repeat', color: '#00f2fe' }; // primary-light
            default: return { name: 'help-outline', color: '#94a3b8' }; // text-secondary
        }
    };

    return (
        <BaseScreen header={<Header />} padding={false} useBottomNav={true} scrollable={false}>
            <View className="flex-1 px-6 pt-4">
                <View className="flex-row items-center justify-between mb-4">
                    <Text className="text-white text-xl font-bold">AI 진단 내역</Text>
                    {selectedVehicleId && (
                        <TouchableOpacity onPress={() => fetchHistory(selectedVehicleId)} className="p-2">
                            <MaterialIcons name="refresh" size={20} color="#64748b" />
                        </TouchableOpacity>
                    )}
                </View>

                {/* 차량 선택기 (Minimalist) */}
                {vehicles.length > 0 && (
                    <View className="mb-6">
                        <FlatList
                            horizontal
                            showsHorizontalScrollIndicator={false}
                            data={vehicles}
                            keyExtractor={(item) => item.vehicleId}
                            renderItem={({ item }) => {
                                const isSelected = item.vehicleId === selectedVehicleId;
                                return (
                                    <TouchableOpacity
                                        onPress={() => {
                                            setSelectedVehicleId(item.vehicleId);
                                            fetchHistory(item.vehicleId);
                                        }}
                                        className={`mr-3 px-4 py-2 rounded-xl border ${isSelected
                                            ? 'border-primary bg-primary/10'
                                            : 'border-white/5 bg-surface-card'
                                            }`}
                                    >
                                        <Text className={`text-sm font-semibold ${isSelected ? 'text-primary' : 'text-text-dim'}`}>
                                            {item.nickname || item.modelName}
                                        </Text>
                                        {item.carNumber && (
                                            <Text className={`text-[10px] ${isSelected ? 'text-primary/70' : 'text-text-muted/50'}`}>
                                                {item.carNumber}
                                            </Text>
                                        )}
                                    </TouchableOpacity>
                                );
                            }}
                        />
                    </View>
                )}

                {loading ? (
                    <View className="flex-1 items-center justify-center">
                        <ActivityIndicator size="large" color="#0d7ff2" />
                    </View>
                ) : vehicles.length === 0 ? (
                    <View className="flex-1 items-center justify-center py-20">
                        <MaterialIcons name="directions-car" size={60} color="#1b2127" />
                        <Text className="text-text-dim mt-4 font-medium text-center">등록된 차량이 없습니다.</Text>
                        <TouchableOpacity
                            onPress={() => navigation.navigate('VehicleRegistration')}
                            className="mt-6 bg-primary px-6 py-3 rounded-xl"
                        >
                            <Text className="text-white font-bold">차량 등록하기</Text>
                        </TouchableOpacity>
                    </View>
                ) : (
                    <FlatList
                        data={history}
                        refreshing={historyLoading}
                        onRefresh={() => selectedVehicleId && fetchHistory(selectedVehicleId)}
                        renderItem={({ item }) => {
                            const iconData = getTriggerIcon(item.triggerType);
                            return (
                                <TouchableOpacity
                                    className="bg-surface-card rounded-2xl p-5 mb-4 border border-white/[0.05] flex-row items-center active:bg-white/[0.03]"
                                    onPress={() => {
                                        if (item.responseMode === 'INTERACTIVE' || item.status === 'ACTION_REQUIRED') {
                                            navigation.navigate('AiDiagChat', { sessionId: item.sessionId });
                                        } else {
                                            navigation.navigate('DiagnosisReport', { reportData: item });
                                        }
                                    }}
                                >
                                    <View className="w-12 h-12 rounded-full bg-white/[0.03] items-center justify-center mr-4 border border-white/[0.05]">
                                        <MaterialIcons
                                            name={iconData.name as any}
                                            size={22}
                                            color={iconData.color}
                                        />
                                    </View>
                                    <View className="flex-1">
                                        <View className="flex-row items-center justify-between mb-1">
                                            <Text className="text-text-dim text-[10px] font-medium">{formatDate(item.createdAt)}</Text>
                                            <View className={`p-1 rounded-md ${item.riskLevel === 'DANGER' ? 'bg-error/10' :
                                                (item.status === 'COMPLETED' || item.status === 'DONE' ? 'bg-success/10' :
                                                    item.status === 'ACTION_REQUIRED' ? 'bg-warning/10' : 'bg-primary/10')}`}>
                                                <MaterialIcons
                                                    name={item.riskLevel === 'DANGER' ? 'priority-high' :
                                                        (item.status === 'DONE' || item.status === 'COMPLETED' ? 'check' :
                                                            item.status === 'ACTION_REQUIRED' ? 'priority-high' : 'sync')}
                                                    size={16}
                                                    color={item.riskLevel === 'DANGER' ? '#ff6b6b' :
                                                        (item.status === 'DONE' || item.status === 'COMPLETED' ? '#0bda5b' :
                                                            item.status === 'ACTION_REQUIRED' ? '#f59e0b' : '#00f0ff')}
                                                />
                                            </View>
                                        </View>
                                        <Text className="text-white text-base font-bold mb-0.5" numberOfLines={1}>
                                            {getDisplayTitle(item)}
                                        </Text>
                                        <Text className="text-text-muted text-xs">
                                            {item.triggerTypeLabel || '진단'} · <Text className={item.riskLevel === 'DANGER' ? 'text-error' : 'text-text-muted'}>{item.riskLevel || '정상'}</Text>
                                        </Text>
                                    </View>
                                    <MaterialIcons name="chevron-right" size={20} color="#334155" />
                                </TouchableOpacity>
                            );
                        }}
                        keyExtractor={(item) => item.sessionId || item.diagnosisId || Math.random().toString()}
                        ListEmptyComponent={
                            !historyLoading ? (
                                <View className="items-center justify-center py-20">
                                    <MaterialIcons name="history" size={40} color="#1b2127" />
                                    <Text className="text-text-dim mt-4">진단 내역이 없습니다.</Text>
                                </View>
                            ) : null
                        }
                        showsVerticalScrollIndicator={false}
                        contentContainerStyle={{ paddingBottom: 20 }}
                    />
                )}
            </View>
        </BaseScreen>
    );
}
