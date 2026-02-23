import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, FlatList, ActivityIndicator, Image } from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import { getDiagnosisList } from '../api/aiApi';
import { getVehicleList, VehicleResponse } from '../api/vehicleApi';
import { DiagType } from '../store/useAiDiagnosisStore';

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

    const formatTime = (dateStr: string) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    };

    const getStatusInfo = (item: any) => {
        if (item.status === 'ACTION_REQUIRED' || item.responseMode === 'INTERACTIVE') {
            return { label: '확인 필요', color: '#f59e0b', icon: 'priority-high', bg: 'bg-warning/10' };
        }
        if (item.status === 'FAILED') {
            return { label: '실패', color: '#ef4444', icon: 'error', bg: 'bg-error/10' };
        }
        if (item.status === 'PROCESSING') {
            return { label: '진단중', color: '#3b82f6', icon: 'sync', bg: 'bg-primary/10' };
        }

        switch (item.riskLevel) {
            case 'DANGER': return { label: '위험', color: '#ef4444', icon: 'warning', bg: 'bg-error/10' };
            case 'WARNING': return { label: '주의', color: '#f59e0b', icon: 'error-outline', bg: 'bg-warning/10' };
            default: return { label: '정상', color: '#10b981', icon: 'check-circle', bg: 'bg-success/10' };
        }
    };

    const getTriggerInfo = (triggerType: string) => {
        switch (triggerType) {
            case 'AUTO': return { label: '자동', icon: 'auto-fix-high', color: '#0bda5b' };
            case 'DATA': return { label: '데이터', icon: 'analytics', color: '#00f0ff' };
            case 'VISUAL': return { label: '시각', icon: 'camera-alt', color: '#94a3b8' };
            case 'AUDIO': return { label: '청각', icon: 'graphic-eq', color: '#3b82f6' };
            case 'DTC': return { label: 'DTC', icon: 'build', color: '#ef4444' };
            default: return { label: '종합', icon: 'car-repair', color: '#00f2fe' };
        }
    };

    const mapTriggerToDiagType = (triggerType?: string): DiagType => {
        switch (triggerType) {
            case 'VISUAL':
                return 'PHOTO';
            case 'AUDIO':
                return 'SOUND';
            default:
                return 'OBD';
        }
    };

    const handlePressItem = (item: any) => {
        const diagType = mapTriggerToDiagType(item.triggerType);
        if (item.responseMode === 'INTERACTIVE' || item.status === 'ACTION_REQUIRED') {
            navigation.navigate('AiDiagChat', {
                sessionId: item.sessionId,
                diagType,
                vehicleId: selectedVehicleId ?? undefined
            });
        } else {
            navigation.navigate('DiagnosisReport', { reportData: item, fromHistory: true, diagType });
        }
    };

    return (
        <BaseScreen padding={false} useBottomNav={true} scrollable={false}>
            <View className="flex-1 px-6">
                <Header title="진단 내역" />

                {/* Vehicle Filter */}
                {vehicles.length > 0 && (
                    <View className="mb-6 h-10">
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
                                        className={`mr-3 px-4 py-2 rounded-full border ${isSelected
                                            ? 'bg-primary/20 border-primary'
                                            : 'bg-surface-card border-white/5'
                                            }`}
                                    >
                                        <Text className={`text-xs font-bold ${isSelected ? 'text-primary' : 'text-text-dim'}`}>
                                            {item.nickname || item.modelNameKo}
                                        </Text>
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
                ) : history.length === 0 ? (
                    <View className="flex-1 items-center justify-center pb-20">
                        <View className="w-20 h-20 bg-surface-card rounded-full items-center justify-center mb-6 border border-white/5">
                            <MaterialCommunityIcons name="clipboard-text-outline" size={40} color="#64748b" />
                        </View>
                        <Text className="text-text-dim font-bold text-lg mb-2">진단 내역이 없습니다</Text>
                        <Text className="text-text-muted text-sm text-center px-10 mb-8">
                            차량의 상태를 주기적으로 진단하고 기록을 관리해보세요.
                        </Text>
                        <TouchableOpacity
                            onPress={() => navigation.navigate('DiagTab')}
                            className="bg-primary px-8 py-3 rounded-xl"
                        >
                            <Text className="text-white font-bold">진단 시작하기</Text>
                        </TouchableOpacity>
                    </View>
                ) : (
                    <FlatList
                        data={history}
                        refreshing={historyLoading}
                        onRefresh={() => selectedVehicleId && fetchHistory(selectedVehicleId)}
                        renderItem={({ item }) => {
                            const statusInfo = getStatusInfo(item);
                            const triggerInfo = getTriggerInfo(item.triggerType);

                            return (
                                <TouchableOpacity
                                    className="bg-surface-card border border-white/5 rounded-2xl p-4 mb-3 active:bg-white/5"
                                    onPress={() => handlePressItem(item)}
                                    activeOpacity={0.7}
                                >
                                    <View className="flex-row justify-between items-start mb-3">
                                        <View className="flex-row items-center gap-2">
                                            <View className={`w-8 h-8 rounded-full items-center justify-center bg-white/5`}>
                                                <MaterialIcons name={triggerInfo.icon as any} size={16} color={triggerInfo.color} />
                                            </View>
                                            <View>
                                                <Text className="text-white font-bold text-sm">{triggerInfo.label} 진단</Text>
                                                <Text className="text-text-muted text-[10px]">{formatDate(item.createdAt)}</Text>
                                            </View>
                                        </View>

                                        <View className={`px-2.5 py-1 rounded-lg flex-row items-center gap-1 ${statusInfo.bg}`}>
                                            <MaterialIcons name={statusInfo.icon as any} size={12} color={statusInfo.color} />
                                            <Text style={{ color: statusInfo.color }} className="text-[10px] font-bold">
                                                {statusInfo.label}
                                            </Text>
                                        </View>
                                    </View>

                                    <Text className="text-text-dim text-xs leading-5 pl-1" numberOfLines={2}>
                                        {item.summary || '상세 진단 리포트를 확인하세요.'}
                                    </Text>

                                    <View className="flex-row justify-end mt-3 border-t border-white/5 pt-3">
                                        <Text className="text-text-muted text-[10px]">
                                            {formatTime(item.createdAt)}
                                        </Text>
                                    </View>
                                </TouchableOpacity>
                            );
                        }}
                        keyExtractor={(item) => item.sessionId || String(Math.random())}
                        contentContainerStyle={{ paddingBottom: 30 }}
                        showsVerticalScrollIndicator={false}
                    />
                )}
            </View>
        </BaseScreen>
    );
}
