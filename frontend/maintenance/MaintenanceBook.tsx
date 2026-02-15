import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl, Modal, Pressable, TextInput, Alert, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { useVehicleStore } from '../store/useVehicleStore';
import { useAlertStore } from '../store/useAlertStore';
import MonthlyCostChart from './MonthlyCostChart';
import AllHistoryList, { CombinedHistoryItem } from './AllHistoryList';
import VehicleSelectModal from '../components/VehicleSelectModal';
import ocrApi, { MaintenanceHistoryResponse, FuelingHistoryResponse, FuelingHistoryRequest } from '../api/ocrApi';
import { formatInputWithCommas, parseFormattedNumber } from '../utils/formatNumber';
import { useConsumableStore } from '../store/useConsumableStore';
import { isPositionTypeCode, getPositionOptions } from './consumableItems';

// 정비 항목 입력 인터페이스 (타이어/브레이크는 positionCodes로 실제 위치 코드 저장)
interface MaintenanceFormItem {
    id: string;
    itemCode: string;
    itemName: string;
    cost: string;
    positionCodes?: string[];
}

export default function MaintenanceBook() {
    const navigation = useNavigation<any>();
    const { vehicles, primaryVehicle, setPrimaryVehicle } = useVehicleStore();
    const { showAlert } = useAlertStore();
    const consumablePickerList = useConsumableStore((s) => s.consumablePickerList);
    const getItemNameByCode = useConsumableStore((s) => s.getItemNameByCode);

    const [selectedVehicle, setSelectedVehicle] = useState<any>(null);
    const [isVehicleModalVisible, setIsVehicleModalVisible] = useState(false);

    // 탭 상태: 월간 차트(CHART) 또는 전체보기(ALL_HISTORY)
    const [tabView, setTabView] = useState<'CHART' | 'ALL_HISTORY'>('ALL_HISTORY');

    // 차트 기간 필터 (월간 차트 탭용)
    const [chartPeriod, setChartPeriod] = useState<3 | 6 | 12>(6);

    // 전체보기 필터 및 정렬
    const [historyFilter, setHistoryFilter] = useState<'ALL' | 'MAINTENANCE' | 'FUELING'>('MAINTENANCE');
    const [sortOrder, setSortOrder] = useState<'date' | 'cost'>('date');

    // 데이터 상태
    const [maintenanceList, setMaintenanceList] = useState<MaintenanceHistoryResponse[]>([]);
    const [fuelingList, setFuelingList] = useState<FuelingHistoryResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    // 상세보기 모달
    const [detailModalVisible, setDetailModalVisible] = useState(false);
    const [selectedGroup, setSelectedGroup] = useState<any | null>(null);

    // 입력 모달 관련 상태
    const [isInputTypeModalVisible, setIsInputTypeModalVisible] = useState(false);
    const [inputMode, setInputMode] = useState<'SCAN' | 'MANUAL'>('MANUAL'); // 스캔인지 직접 입력인지 구분
    const [selectedFormType, setSelectedFormType] = useState<'MAINTENANCE' | 'FUELING'>('MAINTENANCE'); // 모달에서 선택한 타입
    const [isManualModalVisible, setIsManualModalVisible] = useState(false);

    // 공통 입력 필드 (직접 입력 모달용)
    const [formDate, setFormDate] = useState(new Date().toISOString().split('T')[0]);
    const [formMileage, setFormMileage] = useState('');
    const [formShopName, setFormShopName] = useState('');
    const [formMemo, setFormMemo] = useState('');

    // 정비 항목 리스트 (동적 추가/삭제)
    const [maintenanceItems, setMaintenanceItems] = useState<MaintenanceFormItem[]>([
        { id: '1', itemCode: '', itemName: '', cost: '' }
    ]);

    // 드롭다운 상태 (직접 입력 폼 내부)
    const [activeDropdownId, setActiveDropdownId] = useState<string | null>(null);

    // 타이어/브레이크 위치 선택 모달 (수동 입력)
    const [positionModalRowId, setPositionModalRowId] = useState<string | null>(null);

    // 주유 입력 필드 (총 결제금액만 필수, 단가·주유량은 선택·저장 시 2개 있으면 나머지 계산)
    const [formFuelType, setFormFuelType] = useState('GASOLINE');
    const [formUnitPrice, setFormUnitPrice] = useState('');
    const [formFuelAmount, setFormFuelAmount] = useState('');
    const [formTotalCost, setFormTotalCost] = useState('');

    // 초기 차량 선택
    useEffect(() => {
        if (primaryVehicle) {
            setSelectedVehicle(primaryVehicle);
        } else if (vehicles.length > 0) {
            setSelectedVehicle(vehicles[0]);
        }
    }, [primaryVehicle]);

    // 정비 이력 불러오기
    const loadMaintenanceHistory = async () => {
        if (!selectedVehicle?.vehicleId) return;
        try {
            setLoading(true);
            const history = await ocrApi.getMaintenanceHistory(selectedVehicle.vehicleId);
            setMaintenanceList(history);
        } catch (error) {
            console.error('Failed to load maintenance history', error);
        } finally {
            setLoading(false);
        }
    };

    // 주유 이력 불러오기
    const loadFuelingHistory = async () => {
        if (!selectedVehicle?.vehicleId) return;
        try {
            setLoading(true);
            const history = await ocrApi.getFuelingHistory(selectedVehicle.vehicleId);
            setFuelingList(history);
        } catch (error) {
            console.error('Failed to load fueling history', error);
        } finally {
            setLoading(false);
        }
    };

    useFocusEffect(
        useCallback(() => {
            if (selectedVehicle) {
                loadMaintenanceHistory();
                loadFuelingHistory();
            }
        }, [selectedVehicle])
    );

    const onRefresh = async () => {
        setRefreshing(true);
        await Promise.all([loadMaintenanceHistory(), loadFuelingHistory()]);
        setRefreshing(false);
    };

    const handleShowDetail = (item: CombinedHistoryItem) => {
        setSelectedGroup(item.data);
        setDetailModalVisible(true);
    };

    // 포맷팅 함수
    const formatCost = (cost: number | null) => {
        if (cost === null || cost === 0) return '-';
        return `${cost.toLocaleString()}원`;
    };

    const formatDate = (dateString: string | null) => {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        }).replace(/\./g, '.').replace(/ /g, '');
    };

    // 유종 목록 (입력 폼용)
    const FUEL_TYPE_NAMES: { [key: string]: string } = {
        'GASOLINE': '휘발유',
        'DIESEL': '경유',
        'LPG': 'LPG',
        'EV': '전기',
    };

    // 폼 초기화
    const resetForm = () => {
        setFormDate(new Date().toISOString().split('T')[0]);
        setFormMileage('');
        setFormShopName('');
        setFormMemo('');
        setMaintenanceItems([{ id: '1', itemCode: '', itemName: '', cost: '' }]);
        setFormFuelType('GASOLINE');
        setFormUnitPrice('');
        setFormFuelAmount('');
        setFormTotalCost('');
        setActiveDropdownId(null);
        setPositionModalRowId(null);
    };

    // 입력 모달 열기 (스캔 vs 직접)
    const openInputTypeModal = (mode: 'SCAN' | 'MANUAL') => {
        setInputMode(mode);

        // SCAN 모드인 경우: 유형 선택 없이 바로 카메라로 이동 (사용자 요청)
        if (mode === 'SCAN') {
            if (!selectedVehicle?.vehicleId) {
                showAlert('알림', '차량을 먼저 선택해주세요.', 'WARNING');
                return;
            }
            navigation.navigate('ReceiptScan', {
                vehicleId: selectedVehicle?.vehicleId,
                // initialType은 넘기지 않거나, 필요하다면 AI가 판단하도록 흐름 개선 (ReceiptResult에서 처리)
            });
            return;
        }

        // MANUAL 모드인 경우: 기존대로 유형 선택 모달 표시
        setIsInputTypeModalVisible(true);
    };

    // 입력 타입 선택 완료 핸들러
    const handleSelectInputType = (type: 'MAINTENANCE' | 'FUELING') => {
        setSelectedFormType(type);
        setIsInputTypeModalVisible(false);

        if (inputMode === 'MANUAL') {
            resetForm(); // 폼 초기화
            setIsManualModalVisible(true);
        }
        // SCAN 모드는 위에서 바로 처리되므로 여기로 올 일 없음
    };

    // 정비 항목 추가
    const addMaintenanceItem = () => {
        const newId = Date.now().toString();
        setMaintenanceItems([...maintenanceItems, { id: newId, itemCode: '', itemName: '', cost: '' }]);
    };

    // 정비 항목 삭제
    const removeMaintenanceItem = (id: string) => {
        if (maintenanceItems.length <= 1) return;
        setMaintenanceItems(maintenanceItems.filter(item => item.id !== id));
    };

    // 정비 항목 업데이트
    const updateMaintenanceItem = (id: string, field: keyof MaintenanceFormItem, value: string) => {
        setMaintenanceItems(maintenanceItems.map(item => {
            if (item.id === id) {
                if (field === 'itemCode') {
                    const found = consumablePickerList.find(m => m.code === value);
                    return { ...item, itemCode: value, itemName: found?.name || '' };
                }
                if (field === 'cost') {
                    return { ...item, cost: formatInputWithCommas(value) };
                }
                return { ...item, [field]: value };
            }
            return item;
        }));
    };

    const setMaintenanceItemPositions = (id: string, codes: string[]) => {
        setMaintenanceItems(maintenanceItems.map(item =>
            item.id === id ? { ...item, positionCodes: codes } : item
        ));
    };

    const handleFuelPriceChange = (field: 'unitPrice' | 'amount' | 'totalCost', value: string) => {
        const formattedValue = field === 'amount' ? value.replace(/[^0-9.]/g, '') : formatInputWithCommas(value);
        if (field === 'unitPrice') setFormUnitPrice(formattedValue);
        else if (field === 'amount') setFormFuelAmount(formattedValue);
        else setFormTotalCost(formattedValue);
    };

    // 저장 핸들러
    const handleSaveManual = async () => {
        if (!selectedVehicle?.vehicleId) return;

        try {
            setLoading(true);
            if (selectedFormType === 'MAINTENANCE') {
                const basePayload = {
                    maintenanceDate: formDate,
                    mileageAtMaintenance: parseFormattedNumber(formMileage),
                    shopName: formShopName,
                    memo: formMemo,
                };
                const payload: Array<typeof basePayload & { cost: number; consumableItemCode: string; itemDescription: string }> = [];

                for (const item of maintenanceItems) {
                    if (!item.itemCode || !item.cost) continue;
                    const costNum = parseFormattedNumber(item.cost);
                    if (isPositionTypeCode(item.itemCode)) {
                        if (!item.positionCodes?.length) {
                            showAlert('위치 선택', '타이어/브레이크 패드는 교체한 위치를 선택해주세요.', 'WARNING');
                            setLoading(false);
                            return;
                        }
                        for (const code of item.positionCodes) {
                            payload.push({
                                ...basePayload,
                                cost: costNum,
                                consumableItemCode: code,
                                itemDescription: getItemNameByCode(code),
                            });
                        }
                    } else {
                        payload.push({
                            ...basePayload,
                            cost: costNum,
                            consumableItemCode: item.itemCode,
                            itemDescription: item.itemName,
                        });
                    }
                }

                if (payload.length === 0) {
                    showAlert('알림', '정비 항목을 하나 이상 입력해주세요.', 'WARNING');
                    setLoading(false);
                    return;
                }

                await ocrApi.registerMaintenanceManual(selectedVehicle.vehicleId, payload);
                await loadMaintenanceHistory();
            } else {
                const unitPriceNum = parseFormattedNumber(formUnitPrice);
                const totalCostNum = parseFormattedNumber(formTotalCost);
                const amountNum = parseFloat(formFuelAmount) || 0;
                const hasUnitPrice = unitPriceNum > 0;
                const hasTotalCost = totalCostNum > 0;
                const hasAmount = amountNum > 0;
                if (!hasTotalCost) {
                    showAlert('알림', '총 결제금액을 입력해주세요.', 'WARNING');
                    setLoading(false);
                    return;
                }
                let amount: number | null = hasAmount ? amountNum : null;
                let unitPrice: number | null = hasUnitPrice ? unitPriceNum : null;
                const totalCost = totalCostNum;
                if (!hasAmount && hasUnitPrice && hasTotalCost) amount = Math.round((totalCostNum / unitPriceNum) * 100) / 100;
                else if (!hasUnitPrice && hasTotalCost && hasAmount) unitPrice = Math.round(totalCostNum / amountNum);

                const payload: FuelingHistoryRequest = {
                    fuelingDate: formDate,
                    mileageAtFueling: null,
                    fuelType: formFuelType,
                    amount: amount ?? null,
                    unitPrice: unitPrice ?? null,
                    totalCost,
                    shopName: formShopName,
                    memo: formMemo,
                    receiptId: null
                };
                await ocrApi.registerFuelingManual(selectedVehicle.vehicleId, payload);
                await loadFuelingHistory();
            }
            setIsManualModalVisible(false);
            resetForm();
            // 저장 후 전체보기 탭으로 이동하면 사용자가 확인하기 편함 (선택사항)
        } catch (error) {
            console.error('Failed to save manual record:', error);
            showAlert('오류', '기록 저장에 실패했습니다.', 'ERROR');
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteHistory = async (group: any) => {
        showAlert(
            '삭제 확인',
            '이 기록을 삭제하시겠습니까?',
            'WARNING',
            async () => {
                if (!group.items) return;
                try {
                    setLoading(true);
                    // 그룹 내 모든 아이템 삭제
                    for (const item of group.items) {
                        await ocrApi.deleteMaintenance(item.id);
                    }
                    await loadMaintenanceHistory();
                    setDetailModalVisible(false);
                } catch (error) {
                    console.error('Failed to delete history:', error);
                } finally {
                    setLoading(false);
                }
            },
            { confirmText: '삭제', isDestructive: true }
        );
    };

    const handleDeleteFueling = async (fuelingId: string) => {
        showAlert(
            '삭제 확인',
            '이 주유 기록을 삭제하시겠습니까?',
            'WARNING',
            async () => {
                try {
                    setLoading(true);
                    await ocrApi.deleteFueling(fuelingId);
                    await loadFuelingHistory();
                    setDetailModalVisible(false);
                } catch (error) {
                    console.error('Failed to delete fueling:', error);
                } finally {
                    setLoading(false);
                }
            },
            { confirmText: '삭제', isDestructive: true }
        );
    };

    // 정비 항목 합계
    const getTotalMaintenanceCost = () => {
        return maintenanceItems.reduce((sum, item) => sum + parseFormattedNumber(item.cost), 0);
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
                    onPress={onRefresh}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="refresh" size={24} color="#94a3b8" />
                </TouchableOpacity>
            </View>

            {/* Tabs */}
            <View className="flex-row px-5 mt-2 gap-4">
                <TouchableOpacity
                    onPress={() => setTabView('ALL_HISTORY')}
                    className={`flex-1 py-3 rounded-2xl items-center border ${tabView === 'ALL_HISTORY' ? 'bg-primary border-primary' : 'bg-white/5 border-white/10'}`}
                >
                    <Text className={`font-bold ${tabView === 'ALL_HISTORY' ? 'text-white' : 'text-text-dim'}`}>내역</Text>
                </TouchableOpacity>
                <TouchableOpacity
                    onPress={() => setTabView('CHART')}
                    className={`flex-1 py-3 rounded-2xl items-center border ${tabView === 'CHART' ? 'bg-primary border-primary' : 'bg-white/5 border-white/10'}`}
                >
                    <Text className={`font-bold ${tabView === 'CHART' ? 'text-white' : 'text-text-dim'}`}>월간 차트</Text>
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
                {tabView === 'ALL_HISTORY' ? (
                    // ================= 내역 탭 =================
                    <View className="py-2 gap-4">
                        {/* 1. 입력 버튼 그룹 */}
                        <View className="flex-row gap-2 pt-4">
                            <TouchableOpacity
                                className="flex-1 flex-row items-center justify-center gap-1.5 bg-primary py-4 rounded-xl active:opacity-80"
                                onPress={() => openInputTypeModal('SCAN')}
                            >
                                <MaterialIcons name="document-scanner" size={18} color="white" />
                                <Text className="text-white font-bold text-xs">영수증 스캔</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                className="flex-1 flex-row items-center justify-center gap-1.5 bg-white/10 border border-white/5 py-4 rounded-xl active:bg-white/20"
                                onPress={() => openInputTypeModal('MANUAL')}
                            >
                                <MaterialIcons name="edit-note" size={18} color="white" />
                                <Text className="text-white font-bold text-xs">직접 입력</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                className="flex-1 flex-row items-center justify-center gap-1.5 bg-white/10 border border-white/5 py-4 rounded-xl active:bg-white/20"
                                onPress={() => navigation.navigate('ReceiptGallery', { vehicleId: selectedVehicle?.vehicleId })}
                            >
                                <MaterialIcons name="grid-view" size={18} color="white" />
                                <Text className="text-white font-bold text-xs">영수증 목록</Text>
                            </TouchableOpacity>
                        </View>

                        <Text className="text-[13px] font-semibold text-text-dim uppercase tracking-widest mt-2">
                            내역
                        </Text>

                        {/* 필터 및 정렬 */}
                        <View className="flex-row items-center justify-between mb-1">
                            <View className="flex-row gap-2">
                                <TouchableOpacity
                                    onPress={() => setHistoryFilter('MAINTENANCE')}
                                    className={`px-3 py-1.5 rounded-lg border ${historyFilter === 'MAINTENANCE' ? 'bg-primary/20 border-primary/20' : 'bg-transparent border-white/10'}`}
                                >
                                    <Text className={`text-xs ${historyFilter === 'MAINTENANCE' ? 'text-primary font-bold' : 'text-text-dim'}`}>정비</Text>
                                </TouchableOpacity>
                                <TouchableOpacity
                                    onPress={() => setHistoryFilter('FUELING')}
                                    className={`px-3 py-1.5 rounded-lg border ${historyFilter === 'FUELING' ? 'bg-orange-500/20 border-orange-500/20' : 'bg-transparent border-white/10'}`}
                                >
                                    <Text className={`text-xs ${historyFilter === 'FUELING' ? 'text-orange-500 font-bold' : 'text-text-dim'}`}>주유</Text>
                                </TouchableOpacity>
                            </View>

                            <TouchableOpacity
                                onPress={() => setSortOrder(prev => prev === 'date' ? 'cost' : 'date')}
                                className="flex-row items-center gap-1"
                            >
                                <MaterialIcons name={sortOrder === 'date' ? "calendar-today" : "attach-money"} size={14} color="#94a3b8" />
                                <Text className="text-xs text-text-dim">
                                    {sortOrder === 'date' ? '최신순' : '금액순'}
                                </Text>
                            </TouchableOpacity>
                        </View>

                        {loading ? (
                            <View className="py-20 items-center">
                                <ActivityIndicator size="large" color="#0d7ff2" />
                            </View>
                        ) : (
                            <AllHistoryList
                                maintenanceList={maintenanceList}
                                fuelingList={fuelingList}
                                filterType={historyFilter}
                                sortOrder={sortOrder}
                                onItemClick={handleShowDetail}
                            />
                        )}
                    </View>
                ) : (
                    // ================= 월간 차트 탭 =================
                    <View className="py-2 gap-5">
                        {/* 2. 차트 */}
                        {loading ? (
                            <View className="py-20 items-center">
                                <ActivityIndicator size="large" color="#0d7ff2" />
                            </View>
                        ) : (
                            <MonthlyCostChart
                                maintenanceList={maintenanceList}
                                fuelingList={fuelingList}
                            />
                        )}
                    </View>
                )}
            </ScrollView>

            {/* ===== 모달 영역 ===== */}

            {/* 1. 입력 유형 선택 모달 (정비 or 주유) */}
            <Modal
                animationType="fade"
                transparent={true}
                visible={isInputTypeModalVisible}
                onRequestClose={() => setIsInputTypeModalVisible(false)}
            >
                <Pressable
                    className="flex-1 bg-black/70 justify-center items-center px-6"
                    onPress={() => setIsInputTypeModalVisible(false)}
                >
                    <Pressable
                        className="w-full bg-surface-dark border border-white/10 rounded-3xl overflow-hidden p-6"
                        onPress={(e) => e.stopPropagation()}
                    >
                        <View className="flex-row justify-between items-center mb-6">
                            <Text className="text-lg font-bold text-white">입력 유형 선택</Text>
                            <TouchableOpacity onPress={() => setIsInputTypeModalVisible(false)}>
                                <MaterialIcons name="close" size={24} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>
                        <Text className="text-text-dim mb-6">어떤 내역을 입력하시겠습니까?</Text>

                        <View className="gap-3">
                            <TouchableOpacity
                                className="flex-row items-center p-4 bg-primary/20 rounded-2xl border border-primary/30 active:bg-primary/30"
                                onPress={() => handleSelectInputType('MAINTENANCE')}
                            >
                                <View className="w-10 h-10 rounded-full bg-primary items-center justify-center mr-4">
                                    <MaterialIcons name="build" size={20} color="white" />
                                </View>
                                <View>
                                    <Text className="text-white font-bold text-base">정비 내역</Text>
                                    <Text className="text-text-dim text-xs">엔진오일, 타이어 등 정비 기록</Text>
                                </View>
                                <MaterialIcons name="chevron-right" size={24} color="#94a3b8" className="ml-auto" />
                            </TouchableOpacity>

                            <TouchableOpacity
                                className="flex-row items-center p-4 bg-orange-500/20 rounded-2xl border border-orange-500/30 active:bg-orange-500/30"
                                onPress={() => handleSelectInputType('FUELING')}
                            >
                                <View className="w-10 h-10 rounded-full bg-orange-500 items-center justify-center mr-4">
                                    <MaterialIcons name="local-gas-station" size={20} color="white" />
                                </View>
                                <View>
                                    <Text className="text-white font-bold text-base">주유/충전 내역</Text>
                                    <Text className="text-text-dim text-xs">휘발유, 경유, 전기 충전 등</Text>
                                </View>
                                <MaterialIcons name="chevron-right" size={24} color="#94a3b8" className="ml-auto" />
                            </TouchableOpacity>
                        </View>
                    </Pressable>
                </Pressable>
            </Modal>

            {/* 2. 상세보기 모달 */}
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
                            <Text className="text-lg font-bold text-white">
                                {selectedGroup?.isFueling ? '주유 상세 정보' : '정비 상세 내역'}
                            </Text>
                            <TouchableOpacity
                                className="w-8 h-8 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                                onPress={() => setDetailModalVisible(false)}
                            >
                                <MaterialIcons name="close" size={20} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>

                        {selectedGroup && (
                            <ScrollView className="p-6">
                                <View className="gap-4 pb-6">
                                    {selectedGroup.isFueling ? (
                                        // 주유 상세
                                        <View className="bg-white/5 rounded-xl p-4 gap-3">
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">유종</Text>
                                                <Text className="text-white">
                                                    {selectedGroup.fuelType === 'GASOLINE' ? '휘발유' :
                                                        selectedGroup.fuelType === 'DIESEL' ? '경유' :
                                                            selectedGroup.fuelType === 'EV' ? '전기' : selectedGroup.fuelType}
                                                </Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">주유소</Text>
                                                <Text className="text-white">{selectedGroup.shopName || selectedGroup.stationName || '-'}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">주유일</Text>
                                                <Text className="text-white">{formatDate(selectedGroup.fuelingDate)}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">단가</Text>
                                                <Text className="text-white">{selectedGroup.unitPrice ? `${selectedGroup.unitPrice.toLocaleString()}원` : '-'}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">리터</Text>
                                                <Text className="text-white">{selectedGroup.amount ? `${selectedGroup.amount} L` : '-'}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">주행거리</Text>
                                                <Text className="text-white">{selectedGroup.mileageAtFueling ? `${selectedGroup.mileageAtFueling.toLocaleString()} km` : '-'}</Text>
                                            </View>
                                            <View className="h-[1px] bg-white/10 my-1" />
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">총액</Text>
                                                <Text className="text-orange-500 font-bold text-lg">{formatCost(selectedGroup.totalCost)}</Text>
                                            </View>
                                        </View>
                                    ) : (
                                        // 정비 상세
                                        <View className="bg-white/5 rounded-xl p-4 gap-3">
                                            <View className="flex-row justify-between border-b border-white/10 pb-2 mb-1">
                                                <Text className="text-text-secondary text-xs">품목</Text>
                                                <Text className="text-text-secondary text-xs">금액</Text>
                                            </View>
                                            {selectedGroup.items.map((item: any, idx: number) => (
                                                <View key={idx} className="flex-row justify-between py-1">
                                                    <Text className="text-white">{item.itemDescription}</Text>
                                                    <Text className="text-white">{formatCost(item.cost)}</Text>
                                                </View>
                                            ))}
                                            <View className="h-[1px] bg-white/10 my-2" />
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">정비소</Text>
                                                <Text className="text-white">{selectedGroup.shopName || '-'}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">정비일</Text>
                                                <Text className="text-white">{formatDate(selectedGroup.maintenanceDate)}</Text>
                                            </View>
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">주행거리</Text>
                                                <Text className="text-white">
                                                    {(selectedGroup.mileageAtMaintenance ?? selectedGroup.mileage) != null
                                                        ? `${(selectedGroup.mileageAtMaintenance ?? selectedGroup.mileage).toLocaleString()} km`
                                                        : '-'}
                                                </Text>
                                            </View>
                                            <View className="h-[1px] bg-white/10 my-1" />
                                            <View className="flex-row justify-between">
                                                <Text className="text-text-muted">합계</Text>
                                                <Text className="text-primary font-bold text-lg">{formatCost(selectedGroup.totalCost)}</Text>
                                            </View>
                                        </View>
                                    )}

                                    {selectedGroup.memo && (
                                        <View className="bg-white/5 rounded-xl p-4">
                                            <Text className="text-text-dim text-xs mb-2">메모</Text>
                                            <Text className="text-white leading-5">{selectedGroup.memo}</Text>
                                        </View>
                                    )}

                                    <TouchableOpacity
                                        onPress={() => {
                                            if (selectedGroup.isFueling) handleDeleteFueling(selectedGroup.id);
                                            else handleDeleteHistory(selectedGroup);
                                        }}
                                        className="bg-red-500/10 border border-red-500/20 py-4 rounded-2xl items-center mt-2"
                                    >
                                        <Text className="text-red-500 font-bold">삭제하기</Text>
                                    </TouchableOpacity>
                                </View>
                            </ScrollView>
                        )}
                    </Pressable>
                </Pressable>
            </Modal>

            {/* 3. 직접 입력 모달 */}
            <Modal
                animationType="slide"
                transparent={true}
                visible={isManualModalVisible}
                onRequestClose={() => setIsManualModalVisible(false)}
            >
                <SafeAreaView className="flex-1 bg-background-dark">
                    <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5">
                        <TouchableOpacity
                            onPress={() => setIsManualModalVisible(false)}
                            className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                        >
                            <MaterialIcons name="close" size={24} color="white" />
                        </TouchableOpacity>
                        <Text className="text-white text-lg font-bold">
                            {selectedFormType === 'MAINTENANCE' ? '정비 내역 입력' : '주유 내역 입력'}
                        </Text>
                        <View className="w-10" />
                    </View>

                    <ScrollView className="flex-1 p-5">
                        <View className="gap-5 pb-24">
                            {/* 날짜 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">날짜</Text>
                                <TextInput
                                    className="bg-white/5 text-white p-4 rounded-2xl border border-white/10"
                                    value={formDate}
                                    onChangeText={setFormDate}
                                    placeholder="YYYY-MM-DD"
                                    placeholderTextColor="#64748b"
                                />
                            </View>

                            {/* 주행거리 - 정비만 (주유는 미사용) */}
                            {selectedFormType === 'MAINTENANCE' && (
                                <View>
                                    <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">정비 시점 주행거리</Text>
                                    <View className="flex-row items-center bg-white/5 rounded-2xl border border-white/10">
                                        <TextInput
                                            className="flex-1 text-white p-4"
                                            value={formMileage}
                                            onChangeText={(v) => setFormMileage(formatInputWithCommas(v))}
                                            keyboardType="numeric"
                                            placeholder="0"
                                            placeholderTextColor="#64748b"
                                        />
                                        <Text className="text-text-dim mr-4">km</Text>
                                    </View>
                                </View>
                            )}

                            {/* 장소 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">
                                    {selectedFormType === 'MAINTENANCE' ? '정비소' : '주유소'} (선택)
                                </Text>
                                <TextInput
                                    className="bg-white/5 text-white p-4 rounded-2xl border border-white/10"
                                    value={formShopName}
                                    onChangeText={setFormShopName}
                                    placeholder="상호명 입력"
                                    placeholderTextColor="#64748b"
                                />
                            </View>

                            <View className="h-[1px] bg-white/10 my-2" />

                            {selectedFormType === 'MAINTENANCE' ? (
                                // ==== 정비 항목 입력 폼 ====
                                <View className="gap-4">
                                    <Text className="text-text-dim text-xs uppercase tracking-wider">정비 항목</Text>

                                    {maintenanceItems.map((item, index) => (
                                        <View key={item.id} className="gap-2">
                                            <View className="flex-row gap-2 z-10">
                                                {/* 항목 선택 드롭다운 */}
                                                <View className="flex-1 relative z-50">
                                                    <TouchableOpacity
                                                        onPress={() => setActiveDropdownId(activeDropdownId === item.id ? null : item.id)}
                                                        className="bg-white/5 p-4 rounded-2xl border border-white/10 flex-row justify-between items-center"
                                                    >
                                                        <Text className={item.itemCode ? 'text-white' : 'text-text-dim'}>
                                                            {item.itemName || '항목 선택'}
                                                        </Text>
                                                        <MaterialIcons name="arrow-drop-down" size={24} color="#64748b" />
                                                    </TouchableOpacity>

                                                    {/* 드롭다운 메뉴 */}
                                                    {activeDropdownId === item.id && (
                                                        <View className="absolute top-full left-0 right-0 mt-1 bg-surface-dark border border-white/10 rounded-xl z-50 max-h-48 overflow-hidden shadow-lg shadow-black">
                                                            <ScrollView nestedScrollEnabled showsVerticalScrollIndicator>
                                                                {consumablePickerList.map((data) => (
                                                                    <TouchableOpacity
                                                                        key={data.code}
                                                                        onPress={() => {
                                                                            updateMaintenanceItem(item.id, 'itemCode', data.code);
                                                                            setActiveDropdownId(null);
                                                                            if (isPositionTypeCode(data.code)) {
                                                                                setPositionModalRowId(item.id);
                                                                            }
                                                                        }}
                                                                        className="p-3 border-b border-white/5 active:bg-white/10"
                                                                    >
                                                                        <Text className="text-white">{data.name}</Text>
                                                                    </TouchableOpacity>
                                                                ))}
                                                            </ScrollView>
                                                        </View>
                                                    )}
                                                </View>

                                                {/* 비용 입력 */}
                                                <View className="flex-1 relative">
                                                    <View className="flex-row items-center bg-white/5 rounded-2xl border border-white/10">
                                                        <TextInput
                                                            className="flex-1 text-white p-4"
                                                            value={item.cost}
                                                            onChangeText={(v) => updateMaintenanceItem(item.id, 'cost', v)}
                                                            keyboardType="numeric"
                                                            placeholder="0"
                                                            placeholderTextColor="#64748b"
                                                        />
                                                        <Text className="text-text-dim mr-4">원</Text>
                                                    </View>
                                                </View>

                                                {/* 삭제 버튼 */}
                                                {maintenanceItems.length > 1 && (
                                                    <TouchableOpacity
                                                        onPress={() => removeMaintenanceItem(item.id)}
                                                        className="w-12 items-center justify-center bg-red-500/10 rounded-2xl border border-red-500/20"
                                                    >
                                                        <MaterialIcons name="remove" size={20} color="#ef4444" />
                                                    </TouchableOpacity>
                                                )}
                                            </View>

                                            {/* 타이어/브레이크 위치 선택 표시 및 편집 */}
                                            {isPositionTypeCode(item.itemCode) && (
                                                <TouchableOpacity
                                                    onPress={() => setPositionModalRowId(item.id)}
                                                    className="mt-2 flex-row items-center gap-2 bg-white/5 border border-white/10 rounded-xl px-4 py-2"
                                                >
                                                    <MaterialIcons name="edit" size={18} color="#94a3b8" />
                                                    <Text className="text-text-dim text-sm">
                                                        {item.positionCodes?.length
                                                            ? `선택: ${(item.positionCodes || [])
                                                                  .map(c => getPositionOptions(item.itemCode).find(o => o.code === c)?.name)
                                                                  .filter(Boolean)
                                                                  .join(', ')}`
                                                            : '위치 선택 (탭하여 선택)'}
                                                    </Text>
                                                </TouchableOpacity>
                                            )}
                                        </View>
                                    ))}

                                    <TouchableOpacity
                                        onPress={addMaintenanceItem}
                                        className="flex-row items-center justify-center gap-2 py-3 bg-white/5 rounded-2xl border border-white/10 border-dashed"
                                    >
                                        <MaterialIcons name="add" size={20} color="#94a3b8" />
                                        <Text className="text-text-dim">항목 추가</Text>
                                    </TouchableOpacity>

                                    <View className="flex-row justify-between items-center bg-primary/10 p-4 rounded-2xl border border-primary/20 mt-2">
                                        <Text className="text-primary font-bold">총 정비 비용</Text>
                                        <Text className="text-white font-bold text-lg">
                                            {getTotalMaintenanceCost().toLocaleString()}원
                                        </Text>
                                    </View>
                                </View>
                            ) : (
                                // ==== 주유 항목 입력 폼 ====
                                <View className="gap-5">
                                    <View>
                                        <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">유종</Text>
                                        <View className="flex-row flex-wrap gap-2">
                                            {Object.entries(FUEL_TYPE_NAMES).map(([code, name]) => (
                                                <TouchableOpacity
                                                    key={code}
                                                    onPress={() => setFormFuelType(code)}
                                                    className={`px-4 py-3 rounded-xl border ${formFuelType === code ? 'bg-orange-500 border-orange-500' : 'bg-white/5 border-white/10'}`}
                                                >
                                                    <Text className={formFuelType === code ? 'text-white font-bold' : 'text-text-dim'}>
                                                        {name}
                                                    </Text>
                                                </TouchableOpacity>
                                            ))}
                                        </View>
                                    </View>

                                    <View className="flex-row gap-3">
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">단가</Text>
                                            <View className="flex-row items-center bg-white/5 rounded-2xl border border-white/10">
                                                <TextInput
                                                    className="flex-1 text-white p-4"
                                                    value={formUnitPrice}
                                                    onChangeText={(v) => handleFuelPriceChange('unitPrice', v)}
                                                    keyboardType="numeric"
                                                    placeholder="0"
                                                    placeholderTextColor="#64748b"
                                                />
                                                <Text className="text-text-dim mr-4">원/L</Text>
                                            </View>
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">주유량</Text>
                                            <View className="flex-row items-center bg-white/5 rounded-2xl border border-white/10">
                                                <TextInput
                                                    className="flex-1 text-white p-4"
                                                    value={formFuelAmount}
                                                    onChangeText={(v) => handleFuelPriceChange('amount', v)}
                                                    keyboardType="decimal-pad"
                                                    placeholder="0"
                                                    placeholderTextColor="#64748b"
                                                />
                                                <Text className="text-text-dim mr-4">L</Text>
                                            </View>
                                        </View>
                                    </View>

                                    <View>
                                        <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">총 결제금액</Text>
                                        <View className="flex-row items-center bg-white/5 rounded-2xl border border-white/10">
                                            <TextInput
                                                className="flex-1 text-white p-4 font-bold text-lg"
                                                value={formTotalCost}
                                                onChangeText={(v) => handleFuelPriceChange('totalCost', v)}
                                                keyboardType="numeric"
                                                placeholder="0"
                                                placeholderTextColor="#64748b"
                                            />
                                            <Text className="text-text-dim mr-4">원</Text>
                                        </View>
                                        <Text className="text-text-dim text-xs mt-2">총 결제금액만 넣으면 됩니다. 단가·주유량을 함께 입력하면 저장 시 자동 계산됩니다.</Text>
                                    </View>
                                </View>
                            )}

                            <View className="h-[1px] bg-white/10 my-2" />

                            {/* 메모 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">메모 (선택)</Text>
                                <TextInput
                                    className="bg-white/5 text-white p-4 rounded-2xl border border-white/10 h-24"
                                    value={formMemo}
                                    onChangeText={setFormMemo}
                                    placeholder="내용을 입력하세요"
                                    placeholderTextColor="#64748b"
                                    multiline
                                    textAlignVertical="top"
                                />
                            </View>

                            <TouchableOpacity
                                onPress={handleSaveManual}
                                disabled={loading}
                                className={`py-4 rounded-2xl items-center mt-4 ${selectedFormType === 'MAINTENANCE' ? 'bg-primary' : 'bg-orange-500'}`}
                            >
                                {loading ? (
                                    <ActivityIndicator color="white" />
                                ) : (
                                    <Text className="text-white font-bold text-lg">기록 저장하기</Text>
                                )}
                            </TouchableOpacity>
                        </View>
                    </ScrollView>
                </SafeAreaView>
            </Modal>

            {/* 타이어/브레이크 위치 선택 모달 (수동 입력) */}
            <Modal
                visible={positionModalRowId != null}
                transparent
                animationType="fade"
                onRequestClose={() => setPositionModalRowId(null)}
            >
                <Pressable
                    className="flex-1 bg-black/60 justify-center px-6"
                    onPress={() => setPositionModalRowId(null)}
                >
                    <Pressable className="bg-surface-dark border border-white/10 rounded-2xl p-5" onPress={(e) => e.stopPropagation()}>
                        {positionModalRowId && (() => {
                            const row = maintenanceItems.find((i) => i.id === positionModalRowId);
                            if (!row || !isPositionTypeCode(row.itemCode)) return null;
                            const options = getPositionOptions(row.itemCode);
                            const selected = row.positionCodes || [];
                            const toggle = (code: string) => {
                                setMaintenanceItemPositions(
                                    positionModalRowId,
                                    selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code]
                                );
                            };
                            return (
                                <>
                                    <Text className="text-white font-bold text-lg mb-1">
                                        {row.itemCode === 'TIRE_POSITION' ? '어느 타이어를 교체했나요?' : '어느 브레이크 패드를 교체했나요?'}
                                    </Text>
                                    <Text className="text-text-dim text-sm mb-4">복수 선택 가능</Text>
                                    <View className="gap-2 mb-5">
                                        {options.map((opt) => (
                                            <TouchableOpacity
                                                key={opt.code}
                                                className={`flex-row items-center gap-3 px-4 py-3 rounded-xl border ${selected.includes(opt.code) ? 'bg-primary/20 border-primary' : 'bg-white/5 border-white/10'}`}
                                                onPress={() => toggle(opt.code)}
                                            >
                                                <MaterialIcons
                                                    name={selected.includes(opt.code) ? 'check-box' : 'check-box-outline-blank'}
                                                    size={24}
                                                    color={selected.includes(opt.code) ? '#3b82f6' : '#64748b'}
                                                />
                                                <Text className={selected.includes(opt.code) ? 'text-white font-semibold' : 'text-text-dim'}>{opt.name}</Text>
                                            </TouchableOpacity>
                                        ))}
                                    </View>
                                    <View className="flex-row gap-3">
                                        <TouchableOpacity
                                            className="flex-1 py-3 rounded-xl bg-white/10 items-center"
                                            onPress={() => setPositionModalRowId(null)}
                                        >
                                            <Text className="text-white">취소</Text>
                                        </TouchableOpacity>
                                        <TouchableOpacity
                                            className="flex-1 py-3 rounded-xl bg-primary items-center"
                                            onPress={() => {
                                                if (selected.length > 0) setPositionModalRowId(null);
                                                else showAlert('알림', '최소 1개 위치를 선택해주세요.', 'INFO');
                                            }}
                                            disabled={selected.length === 0}
                                        >
                                            <Text className="text-white font-bold">선택 완료</Text>
                                        </TouchableOpacity>
                                    </View>
                                </>
                            );
                        })()}
                    </Pressable>
                </Pressable>
            </Modal>

            {/* 차량 선택 모달 */}
            <VehicleSelectModal
                visible={isVehicleModalVisible}
                onClose={() => setIsVehicleModalVisible(false)}
                onSelect={(vehicle) => {
                    setPrimaryVehicle(vehicle.vehicleId);
                    setSelectedVehicle(vehicle);
                    setIsVehicleModalVisible(false);
                }}
            />
        </SafeAreaView>
    );
}
