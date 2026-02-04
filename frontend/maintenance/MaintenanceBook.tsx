import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl, Modal, Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { useVehicleStore } from '../store/useVehicleStore';
import { useAlertStore } from '../store/useAlertStore';
import VehicleSelectModal from '../components/VehicleSelectModal';
import ocrApi, { MaintenanceHistoryResponse } from '../api/ocrApi';

export default function MaintenanceBook() {
    const navigation = useNavigation<any>();
    const { vehicles, primaryVehicle, setPrimaryVehicle } = useVehicleStore();

    const [selectedVehicle, setSelectedVehicle] = useState<any>(null);
    const [isVehicleModalVisible, setIsVehicleModalVisible] = useState(false);
    const [maintenanceList, setMaintenanceList] = useState<MaintenanceHistoryResponse[]>([]);
    const [monthlyTotal, setMonthlyTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [detailModalVisible, setDetailModalVisible] = useState(false);
    const [selectedHistory, setSelectedHistory] = useState<MaintenanceHistoryResponse | null>(null);

    // 초기 차량 선택
    useEffect(() => {
        if (primaryVehicle) {
            setSelectedVehicle(primaryVehicle);
        } else if (vehicles.length > 0) {
            setSelectedVehicle(vehicles[0]);
        }
    }, [primaryVehicle]);

    // 이번 달 합계 계산
    useEffect(() => {
        if (maintenanceList.length > 0) {
            const now = new Date();
            const currentMonth = now.getMonth();
            const currentYear = now.getFullYear();

            const sum = maintenanceList
                .filter(item => {
                    const d = new Date(item.maintenanceDate);
                    return d.getMonth() === currentMonth && d.getFullYear() === currentYear;
                })
                .reduce((acc, item) => acc + (item.cost || 0), 0);
            setMonthlyTotal(sum);
        } else {
            setMonthlyTotal(0);
        }
    }, [maintenanceList]);

    // 정비 이력 불러오기
    const loadMaintenanceHistory = async () => {
        if (!selectedVehicle?.vehicleId) return;

        try {
            setLoading(true);
            const history = await ocrApi.getMaintenanceHistory(selectedVehicle.vehicleId);
            setMaintenanceList(history);
        } catch (error) {
            console.error('Failed to load maintenance history:', error);
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

    // 날짜 포맷
    const formatDate = (dateStr: string) => {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
    };

    // 비용 포맷
    const formatCost = (cost: number | null) => {
        if (!cost) return '-';
        return `${cost.toLocaleString()}원`;
    };

    // 상세 보기 핸들러
    const handleShowDetail = (item: MaintenanceHistoryResponse) => {
        setSelectedHistory(item);
        setDetailModalVisible(true);
    };

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>

                <TouchableOpacity
                    className="flex-1 items-center"
                    activeOpacity={0.7}
                    onPress={() => setIsVehicleModalVisible(true)}
                >
                    <View className="flex-row items-center gap-1">
                        <Text className="text-white text-lg font-bold">차계부</Text>
                        <MaterialIcons name="keyboard-arrow-down" size={18} color="#94a3b8" />
                    </View>
                    {selectedVehicle && (
                        <Text className="text-xs text-text-dim">
                            {selectedVehicle.manufacturerKo} {selectedVehicle.modelNameKo}
                        </Text>
                    )}
                </TouchableOpacity>

                <TouchableOpacity
                    onPress={loadMaintenanceHistory}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="refresh" size={24} color="#94a3b8" />
                </TouchableOpacity>
            </View>

            {/* Scan Button */}
            <View className="px-5 pt-4 pb-2">
                <TouchableOpacity
                    className="flex-row items-center justify-center gap-3 bg-primary py-4 rounded-2xl active:opacity-80"
                    onPress={() => navigation.navigate('ReceiptScan', { vehicleId: selectedVehicle?.vehicleId })}
                >
                    <MaterialIcons name="document-scanner" size={24} color="white" />
                    <Text className="text-white font-bold text-base">영수증 스캔</Text>
                </TouchableOpacity>
            </View>

            {/* Content */}
            <ScrollView
                className="flex-1 px-5"
                contentContainerStyle={{ paddingBottom: 100 }}
                refreshControl={
                    <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0d7ff2" />
                }
            >
                <Text className="text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3 mt-4">
                    정비 이력
                </Text>

                {loading ? (
                    <View className="py-20 items-center">
                        <ActivityIndicator size="large" color="#0d7ff2" />
                    </View>
                ) : maintenanceList.length === 0 ? (
                    <View className="items-center justify-center py-20 gap-4">
                        <View className="w-16 h-16 rounded-full bg-gray-800 items-center justify-center mb-2">
                            <MaterialIcons name="receipt-long" size={32} color="#64748b" />
                        </View>
                        <Text className="text-gray-400 text-base font-medium text-center">
                            등록된 정비 이력이 없습니다.
                        </Text>
                        <Text className="text-gray-500 text-sm text-center">
                            영수증을 스캔하여 정비 이력을 등록해보세요.
                        </Text>
                    </View>
                ) : (
                    <View className="gap-3">
                        {maintenanceList.map((item, index) => (
                            <TouchableOpacity
                                key={item.id || index}
                                className="bg-white/5 border border-white/10 rounded-2xl p-4 active:bg-white/10"
                                onPress={() => handleShowDetail(item)}
                            >
                                {/* Header */}
                                <View className="flex-row justify-between items-start mb-3">
                                    <View className="flex-row items-center gap-3">
                                        <View className="w-10 h-10 rounded-xl bg-primary/20 items-center justify-center">
                                            <MaterialIcons name="build" size={20} color="#0d7ff2" />
                                        </View>
                                        <View>
                                            <Text className="text-white font-bold text-base">
                                                {item.itemDescription || '정비'}
                                            </Text>
                                            <Text className="text-text-dim text-xs">
                                                {item.shopName || '정비소 미기록'}
                                            </Text>
                                        </View>
                                    </View>
                                    <View className="items-end">
                                        <Text className="text-primary font-bold">
                                            {formatCost(item.cost)}
                                        </Text>
                                        <Text className="text-text-dim text-[10px] mt-1">상세보기 &gt;</Text>
                                    </View>
                                </View>

                                {/* Details */}
                                <View className="flex-row gap-4 mt-2 pt-3 border-t border-white/5">
                                    <View className="flex-1">
                                        <Text className="text-text-dim text-[10px] mb-1">정비일</Text>
                                        <Text className="text-white text-sm">
                                            {formatDate(item.maintenanceDate)}
                                        </Text>
                                    </View>
                                    <View className="flex-1">
                                        <Text className="text-text-dim text-[10px] mb-1">주행거리</Text>
                                        <Text className="text-white text-sm">
                                            {item.mileageAtMaintenance ? `${item.mileageAtMaintenance.toLocaleString()} km` : '-'}
                                        </Text>
                                    </View>
                                </View>

                                {/* Memo Preview */}
                                {item.memo && (
                                    <View className="mt-3 pt-3 border-t border-white/5">
                                        <Text className="text-text-muted text-xs" numberOfLines={1}>
                                            {item.memo}
                                        </Text>
                                    </View>
                                )}
                            </TouchableOpacity>
                        ))}
                    </View>
                )}
            </ScrollView>

            {/* 상세 정보 모달 */}
            <Modal
                animationType="fade"
                transparent={true}
                visible={detailModalVisible}
                onRequestClose={() => setDetailModalVisible(false)}
            >
                <Pressable
                    className="flex-1 bg-black/70 justify-center items-center px-6"
                    onPress={() => setDetailModalVisible(false)}
                >
                    <Pressable
                        className="w-full bg-surface-dark border border-white/10 rounded-3xl overflow-hidden max-h-[80%]"
                        onPress={(e) => e.stopPropagation()}
                    >
                        <View className="px-6 py-5 border-b border-white/10 flex-row items-center justify-between">
                            <Text className="text-lg font-bold text-white">정비 상세 정보</Text>
                            <TouchableOpacity
                                className="w-8 h-8 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                                onPress={() => setDetailModalVisible(false)}
                            >
                                <MaterialIcons name="close" size={20} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>

                        {selectedHistory && (
                            <ScrollView className="p-6">
                                <View className="gap-6">
                                    <View>
                                        <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">정비 정보</Text>
                                        <View className="bg-white/5 rounded-xl p-4 gap-3">
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">항목</Text>
                                                <Text className="text-white font-bold">{selectedHistory.itemDescription}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">정비소</Text>
                                                <Text className="text-white">{selectedHistory.shopName || '-'}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">정비일</Text>
                                                <Text className="text-white">{formatDate(selectedHistory.maintenanceDate)}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">주행거리</Text>
                                                <Text className="text-white">
                                                    {selectedHistory.mileageAtMaintenance ? `${selectedHistory.mileageAtMaintenance.toLocaleString()} km` : '-'}
                                                </Text>
                                            </View>
                                            <View className="h-[1px] bg-white/10 my-1" />
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">비용</Text>
                                                <Text className="text-primary font-bold text-lg">{formatCost(selectedHistory.cost)}</Text>
                                            </View>
                                        </View>
                                    </View>

                                    {/* 메모 */}
                                    {selectedHistory.memo && (
                                        <View>
                                            <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">메모</Text>
                                            <View className="bg-white/5 rounded-xl p-4">
                                                <Text className="text-white leading-5">{selectedHistory.memo}</Text>
                                            </View>
                                        </View>
                                    )}

                                    {/* 영수증 원본 데이터 (OCR) */}
                                    {selectedHistory.ocrData && (
                                        <View>
                                            <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">영수증 상세 내역</Text>
                                            <View className="bg-white/5 rounded-xl p-4">
                                                {(() => {
                                                    try {
                                                        const parsed = JSON.parse(selectedHistory.ocrData);

                                                        // [수정] 구조화된 items 배열이 있으면 우선적으로 표시
                                                        if (parsed.items && Array.isArray(parsed.items) && parsed.items.length > 0) {
                                                            return (
                                                                <View>
                                                                    <View className="flex-row justify-between pb-2 border-b border-white/20 mb-2">
                                                                        <Text className="text-text-secondary text-xs font-bold">품목</Text>
                                                                        <Text className="text-text-secondary text-xs font-bold">금액</Text>
                                                                    </View>
                                                                    {parsed.items.map((item: any, idx: number) => (
                                                                        <View key={idx} className="flex-row justify-between py-1.5">
                                                                            <Text className="text-text-muted text-xs flex-1 mr-2">{item.name}</Text>
                                                                            <Text className="text-white text-xs">
                                                                                {typeof item.cost === 'number'
                                                                                    ? `${item.cost.toLocaleString()}원`
                                                                                    : item.cost}
                                                                            </Text>
                                                                        </View>
                                                                    ))}
                                                                </View>
                                                            );
                                                        }

                                                        const rawText = parsed.text || selectedHistory.ocrData;

                                                        // 기존 로직: 텍스트에서 정규식으로 추출
                                                        const pricePattern = /([가-힣a-zA-Z0-9\s\(\)\-]+?)[\s]*[-:]+[\s]*([\d,]+)원/g;
                                                        const items: { name: string; price: string; isTotal: boolean }[] = [];

                                                        let match;
                                                        while ((match = pricePattern.exec(rawText)) !== null) {
                                                            let name = match[1].trim();
                                                            const price = match[2];
                                                            const isTotal = name.includes('합계') || name.includes('총') || name.includes('소계');

                                                            // 품목명에서 날짜 패턴 제거 (YYYY-MM-DD 또는 YYYY.MM.DD 등)
                                                            name = name.replace(/^\d{4}[-./]\d{2}[-./]\d{2}\s*/, '').trim();

                                                            // 빈 이름 제외
                                                            if (name.length > 0) {
                                                                items.push({ name, price: price + '원', isTotal });
                                                            }
                                                        }

                                                        // 파싱된 항목이 있으면 테이블로 표시
                                                        if (items.length > 0) {
                                                            return (
                                                                <View>
                                                                    {/* 테이블 헤더 */}
                                                                    <View className="flex-row justify-between pb-2 border-b border-white/20 mb-2">
                                                                        <Text className="text-text-secondary text-xs font-bold">품목</Text>
                                                                        <Text className="text-text-secondary text-xs font-bold">금액</Text>
                                                                    </View>

                                                                    {/* 품목 리스트 */}
                                                                    {items.map((item, idx) => (
                                                                        <View key={idx} className={`flex-row justify-between py-1.5 ${item.isTotal ? 'border-t border-white/20 mt-1 pt-2' : ''
                                                                            }`}>
                                                                            <Text className={`text-xs flex-1 mr-2 ${item.isTotal ? 'text-white font-bold' : 'text-text-muted'
                                                                                }`}>{item.name}</Text>
                                                                            <Text className={`text-xs ${item.isTotal ? 'text-primary font-bold' : 'text-white'
                                                                                }`}>{item.price}</Text>
                                                                        </View>
                                                                    ))}
                                                                </View>
                                                            );
                                                        }

                                                        // 파싱 실패 시 원본 텍스트 표시
                                                        return <Text className="text-text-muted text-xs leading-5">{typeof rawText === 'string' ? rawText : JSON.stringify(parsed)}</Text>;
                                                    } catch (e) {
                                                        return <Text className="text-text-muted text-xs leading-5">{selectedHistory.ocrData}</Text>;
                                                    }
                                                })()}
                                            </View>
                                        </View>
                                    )}
                                </View>
                            </ScrollView>
                        )}
                    </Pressable>
                </Pressable>
            </Modal>
            {/* Vehicle Selection Modal */}
            <VehicleSelectModal
                visible={isVehicleModalVisible}
                onClose={() => setIsVehicleModalVisible(false)}
                onSelect={(vehicle) => {
                    setSelectedVehicle(vehicle);
                    setIsVehicleModalVisible(false);
                }}
                title="차량 선택"
                description="정비 내역을 확인할 차량을 선택해주세요."
            />
        </SafeAreaView>
    );
}
