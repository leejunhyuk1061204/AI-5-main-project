import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, FlatList, ActivityIndicator, StyleSheet } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import { getDiagnosisList } from '../api/aiApi';

export default function DiagnosisHistory() {
    const navigation = useNavigation<any>();
    const [history, setHistory] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadHistory();
    }, []);

    const loadHistory = async () => {
        try {
            setLoading(true);
            const stored = await AsyncStorage.getItem('primaryVehicle');
            if (stored) {
                const vehicle = JSON.parse(stored);
                const data = await getDiagnosisList(vehicle.vehicleId);
                setHistory(data || []);
            }
        } catch (error) {
            console.error("Failed to load history:", error);
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateStr: string) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
    };

    const getDisplayTitle = (item: any) => {
        // progressMessage가 있으면 사용
        if (item.progressMessage) return item.progressMessage;

        // 상태에 따라 기본 제목 생성
        if (item.status === 'ACTION_REQUIRED' || item.responseMode === 'INTERACTIVE') {
            return '추가 정보 필요';
        }
        if (item.status === 'DONE' || item.status === 'COMPLETED') {
            return '진단 완료';
        }
        if (item.status === 'PROCESSING') {
            return '진단 진행 중';
        }
        return '종합 진단 보고서';
    };


    return (
        <BaseScreen header={<Header />} padding={false} useBottomNav={true} scrollable={false}>
            <View className="flex-1 px-6 pt-4">
                <View className="flex-row items-center justify-between mb-6">
                    <Text className="text-white text-xl font-bold">AI 진단 내역</Text>
                    <TouchableOpacity onPress={loadHistory} className="p-2">
                        <MaterialIcons name="refresh" size={20} color="#64748b" />
                    </TouchableOpacity>
                </View>

                {loading ? (
                    <View className="flex-1 items-center justify-center">
                        <ActivityIndicator size="large" color="#0d7ff2" />
                    </View>
                ) : history.length > 0 ? (
                    <FlatList
                        data={history}
                        renderItem={({ item }) => (
                            <TouchableOpacity
                                className="bg-surface-card rounded-2xl p-5 mb-4 border border-white/10 flex-row items-center justify-between active:bg-white/5"
                                onPress={() => {
                                    if (item.responseMode === 'INTERACTIVE' || item.status === 'ACTION_REQUIRED') {
                                        navigation.navigate('AiDiagChat', { sessionId: item.sessionId });
                                    } else {
                                        navigation.navigate('DiagnosisReport', { reportData: item });
                                    }
                                }}
                            >
                                <View className="flex-1">
                                    <View className="flex-row items-center gap-2 mb-1">
                                        <Text className="text-text-dim text-xs font-bold">{formatDate(item.createdAt)}</Text>
                                        <View className={`px-2 py-0.5 rounded-full ${item.status === 'COMPLETED' ? 'bg-success/10' : 'bg-primary/10'}`}>
                                            <Text className={`text-[10px] font-bold ${item.status === 'COMPLETED' ? 'text-success' : 'text-primary'}`}>
                                                {item.status || '진단완료'}
                                            </Text>
                                        </View>
                                    </View>
                                    <Text className="text-white text-base font-bold mb-1" numberOfLines={1}>
                                        {getDisplayTitle(item)}
                                    </Text>
                                    <Text className="text-text-muted text-sm" numberOfLines={1}>
                                        {item.triggerType === 'MANUAL' ? '수동 진단' : '자동 진단'} · {item.riskLevel || '분석 중'}
                                    </Text>
                                </View>
                                <MaterialIcons name="chevron-right" size={24} color="#64748b" />
                            </TouchableOpacity>
                        )}
                        keyExtractor={(item) => item.sessionId || item.diagnosisId || Math.random().toString()}
                        showsVerticalScrollIndicator={false}
                        contentContainerStyle={{ paddingBottom: 20 }}
                    />
                ) : (
                    <View className="flex-1 items-center justify-center py-20">
                        <MaterialIcons name="history" size={48} color="#1b2127" />
                        <Text className="text-text-dim mt-4 font-medium">진단 내역이 없습니다.</Text>
                    </View>
                )}
            </View>
        </BaseScreen>
    );
}
