import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl, Modal, Pressable } from 'react-native';
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
import { parseFormattedNumber } from '../utils/formatNumber';
import { isPositionTypeRow } from './consumableItems';
import MaintenanceForm, { type MaintenanceFormRow } from './MaintenanceForm';
import FuelingForm from './FuelingForm';

const initialMaintenanceFormRows = (): MaintenanceFormRow[] => [
    { id: `init-${Date.now()}`, consumableItemCode: 'OTHER', consumableItemName: '기타 정비', quantity: '1', amount: '', positionCodes: undefined },
];

export default function MaintenanceBook() {
    const navigation = useNavigation<any>();
    const { vehicles, primaryVehicle, setPrimaryVehicle } = useVehicleStore();
    const { showAlert } = useAlertStore();

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

    // 정비 항목 (MaintenanceForm과 동기화)
    const [formMaintenanceRows, setFormMaintenanceRows] = useState<MaintenanceFormRow[]>(() => initialMaintenanceFormRows());

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
        // YYYY-MM-DD 형식의 문자열이 들어온다고 가정하고 처리
        // new Date() 사용 시 타임존 문제로 하루 전 날짜가 나올 수 있음
        const parts = dateString.split('-');
        if (parts.length === 3) {
            return `${parts[0]}.${parts[1]}.${parts[2]}`;
        }

        // 형식이 맞지 않는 경우 fallback (기존 로직 유지하되 안전하게)
        try {
            const date = new Date(dateString);
            if (isNaN(date.getTime())) return dateString; // 파싱 실패 시 원본 반환

            return date.toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
            }).replace(/\./g, '.').replace(/ /g, '');
        } catch (e) {
            return dateString;
        }
    };

    // 폼 초기화
    const resetForm = () => {
        setFormDate(new Date().toISOString().split('T')[0]);
        setFormMileage('');
        setFormShopName('');
        setFormMemo('');
        setFormMaintenanceRows(initialMaintenanceFormRows());
        setFormFuelType('GASOLINE');
        setFormUnitPrice('');
        setFormFuelAmount('');
        setFormTotalCost('');
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

    // 저장 핸들러
    const handleSaveManual = async () => {
        if (!selectedVehicle?.vehicleId) return;

        try {
            setLoading(true);
            if (selectedFormType === 'MAINTENANCE') {
                const hasPositionRowWithoutSelection = formMaintenanceRows.some(
                    (r) =>
                        (r.consumableItemCode === 'TIRE_POSITION' || r.consumableItemCode === 'BRAKE_POSITION') &&
                        (!r.positionCodes || r.positionCodes.length === 0)
                );
                if (hasPositionRowWithoutSelection) {
                    showAlert('위치 선택', '타이어/브레이크 항목에 교체한 위치를 선택해 주세요.', 'WARNING');
                    setLoading(false);
                    return;
                }

                const base = {
                    maintenanceDate: formDate || new Date().toISOString().split('T')[0],
                    mileageAtMaintenance: formMileage.trim() ? parseFormattedNumber(formMileage) : null,
                    shopName: formShopName || null,
                    memo: formMemo || null,
                };
                const requests: Array<{
                    maintenanceDate: string;
                    mileageAtMaintenance: number | null;
                    shopName: string | null;
                    memo: string | null;
                    consumableItemCode: string;
                    quantity: number;
                    cost: number | null;
                }> = [];
                for (const row of formMaintenanceRows) {
                    const positionCodesToUse = row.positionCodes?.length
                        ? row.positionCodes
                        : isPositionTypeRow(row.consumableItemCode) &&
                            ['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR', 'BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'].includes(row.consumableItemCode)
                            ? [row.consumableItemCode]
                            : null;
                    if (positionCodesToUse && positionCodesToUse.length > 0) {
                        const rowCost = row.amount ? Math.round(parseFormattedNumber(row.amount)) : null;
                        const costPer = rowCost != null ? Math.floor(rowCost / positionCodesToUse.length) : null;
                        for (const code of positionCodesToUse) {
                            requests.push({ ...base, consumableItemCode: code, quantity: 1, cost: costPer });
                        }
                    } else {
                        requests.push({
                            ...base,
                            consumableItemCode: row.consumableItemCode,
                            quantity: parseInt(row.quantity, 10) || 1,
                            cost: row.amount ? Math.round(parseFormattedNumber(row.amount)) : null,
                        });
                    }
                }
                if (requests.length === 0 || requests.every((r) => r.cost == null || r.cost === 0)) {
                    showAlert('알림', '정비 항목을 하나 이상 입력해주세요.', 'WARNING');
                    setLoading(false);
                    return;
                }
                await ocrApi.registerMaintenanceManual(selectedVehicle.vehicleId, requests);
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
                    mileageAtFueling: formMileage.trim() ? parseFormattedNumber(formMileage) : null,
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

                    <ScrollView className="flex-1" contentContainerStyle={{ paddingBottom: 100 }}>
                        {selectedFormType === 'MAINTENANCE' ? (
                            <MaintenanceForm
                                imageUri={null}
                                date={formDate}
                                mileage={formMileage}
                                shopName={formShopName}
                                memo={formMemo}
                                items={formMaintenanceRows}
                                onDateChange={setFormDate}
                                onMileageChange={setFormMileage}
                                onShopNameChange={setFormShopName}
                                onMemoChange={setFormMemo}
                                onItemsChange={setFormMaintenanceRows}
                            />
                        ) : (
                            <FuelingForm
                                imageUri={null}
                                date={formDate}
                                mileage={formMileage}
                                shopName={formShopName}
                                memo={formMemo}
                                fuelType={formFuelType}
                                unitPrice={formUnitPrice}
                                fuelAmount={formFuelAmount}
                                totalCost={formTotalCost}
                                onDateChange={setFormDate}
                                onMileageChange={setFormMileage}
                                onShopNameChange={setFormShopName}
                                onMemoChange={setFormMemo}
                                onFuelTypeChange={setFormFuelType}
                                onUnitPriceChange={setFormUnitPrice}
                                onFuelAmountChange={setFormFuelAmount}
                                onTotalCostChange={setFormTotalCost}
                            />
                        )}
                        <TouchableOpacity
                            onPress={handleSaveManual}
                            disabled={loading}
                            className={`py-4 rounded-2xl items-center mt-6 ${selectedFormType === 'MAINTENANCE' ? 'bg-primary' : 'bg-orange-500'}`}
                        >
                            {loading ? (
                                <ActivityIndicator color="white" />
                            ) : (
                                <Text className="text-white font-bold text-lg">기록 저장하기</Text>
                            )}
                        </TouchableOpacity>
                    </ScrollView>
                </SafeAreaView>
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
