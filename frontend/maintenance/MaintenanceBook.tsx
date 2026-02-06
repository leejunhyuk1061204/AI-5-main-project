import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl, Modal, Pressable, TextInput, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { useVehicleStore } from '../store/useVehicleStore';
import { useAlertStore } from '../store/useAlertStore';
import VehicleSelectModal from '../components/VehicleSelectModal';
import ocrApi, { MaintenanceHistoryResponse, FuelingHistoryResponse } from '../api/ocrApi';
import { formatInputWithCommas, parseFormattedNumber } from '../utils/formatNumber';

// 정비 항목 마스터 데이터
const MAINTENANCE_ITEMS_DATA = [
    { code: 'ENGINE_OIL', name: '엔진 오일' },
    { code: 'AIR_FILTER', name: '에어클리너' },
    { code: 'CABIN_FILTER', name: '에어컨 필터' },
    { code: 'BRAKE_FLUID', name: '브레이크 오일' },
    { code: 'MISSION_OIL', name: '미션 오일' },
    { code: 'FUEL_FILTER', name: '연료 필터' },
    { code: 'COOLANT', name: '냉각수' },
    { code: 'TIRES', name: '타이어 (전체)' },
    { code: 'TIRE_FRONT', name: '앞 타이어' },
    { code: 'TIRE_REAR', name: '뒤 타이어' },
    { code: 'BRAKE_PADS', name: '브레이크 패드 (전체)' },
    { code: 'BRAKE_PAD_FRONT', name: '앞 브레이크 패드' },
    { code: 'BRAKE_PAD_REAR', name: '뒤 브레이크 패드' },
    { code: 'SPARK_PLUG', name: '점화 플러그' },
    { code: 'DRIVE_BELT', name: '구동 벨트' },
    { code: 'WHEEL_ALIGNMENT', name: '휠 얼라인먼트' },
    { code: 'BATTERY_12V', name: '12V 배터리' },
    { code: 'WIPER', name: '와이퍼' },
    { code: 'AIR_CON_REFRIGERANT', name: '에어컨 가스' },
    { code: 'OTHER', name: '기타 정비' },
];

// 정비 항목 입력 인터페이스
interface MaintenanceFormItem {
    id: string;
    itemCode: string;
    itemName: string;
    cost: string; // 포맷된 문자열
}

export default function MaintenanceBook() {
    const navigation = useNavigation<any>();
    const { vehicles, primaryVehicle, setPrimaryVehicle } = useVehicleStore();

    const [selectedVehicle, setSelectedVehicle] = useState<any>(null);
    const [isVehicleModalVisible, setIsVehicleModalVisible] = useState(false);
    const [activeTab, setActiveTab] = useState<'MAINTENANCE' | 'FUELING'>('MAINTENANCE');
    const [maintenanceList, setMaintenanceList] = useState<MaintenanceHistoryResponse[]>([]);
    const [fuelingList, setFuelingList] = useState<FuelingHistoryResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [detailModalVisible, setDetailModalVisible] = useState(false);
    const [selectedGroup, setSelectedGroup] = useState<any | null>(null);
    const [isManualModalVisible, setIsManualModalVisible] = useState(false);

    // 부품별 필터
    const [selectedItemFilter, setSelectedItemFilter] = useState<string | null>(null);
    const [isFilterDropdownOpen, setIsFilterDropdownOpen] = useState(false);

    // 유종별 필터 (주유 탭)
    const [selectedFuelTypeFilter, setSelectedFuelTypeFilter] = useState<string | null>(null);
    const [isFuelFilterDropdownOpen, setIsFuelFilterDropdownOpen] = useState(false);

    // 정렬 순서
    const [sortOrder, setSortOrder] = useState<'date' | 'cost'>('date');

    // 공통 입력 필드
    const [formDate, setFormDate] = useState(new Date().toISOString().split('T')[0]);
    const [formMileage, setFormMileage] = useState('');
    const [formShopName, setFormShopName] = useState('');
    const [formMemo, setFormMemo] = useState('');

    // 정비 항목 리스트 (동적 추가/삭제)
    const [maintenanceItems, setMaintenanceItems] = useState<MaintenanceFormItem[]>([
        { id: '1', itemCode: '', itemName: '', cost: '' }
    ]);

    // 드롭다운 상태
    const [activeDropdownId, setActiveDropdownId] = useState<string | null>(null);

    // 주유 입력 필드
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

    const handleShowDetail = (group: any) => {
        setSelectedGroup(group);
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

    // 정비 이력 그룹화 (receiptId 기준)
    const groupedMaintenance = maintenanceList.reduce((acc: any[], item) => {
        const key = item.receiptId || item.id;
        const existing = acc.find(g => g.receiptId === key);
        if (existing) {
            existing.items.push(item);
            existing.totalCost += item.cost || 0;
        } else {
            acc.push({
                receiptId: key,
                maintenanceDate: item.maintenanceDate,
                mileageAtMaintenance: item.mileageAtMaintenance,
                shopName: item.shopName,
                totalCost: item.cost || 0,
                memo: item.memo,
                isFueling: false,
                items: [item]
            });
        }
        return acc;
    }, []);

    // 필터된 정비 이력 (부품별)
    const filteredMaintenance = selectedItemFilter
        ? groupedMaintenance.filter(group =>
            group.items.some((item: any) => item.itemDescription?.includes(selectedItemFilter))
        )
        : groupedMaintenance;

    // 정렬된 정비 이력
    const sortedMaintenance = [...filteredMaintenance].sort((a, b) => {
        if (sortOrder === 'date') {
            return new Date(b.maintenanceDate).getTime() - new Date(a.maintenanceDate).getTime();
        }
        return b.totalCost - a.totalCost;
    });

    // 유종 필터 적용
    const filteredFueling = selectedFuelTypeFilter
        ? fuelingList.filter(item => item.fuelType === selectedFuelTypeFilter)
        : fuelingList;

    // 정렬된 주유 이력
    const sortedFueling = [...filteredFueling].sort((a, b) => {
        if (sortOrder === 'date') {
            return new Date(b.fuelingDate).getTime() - new Date(a.fuelingDate).getTime();
        }
        return b.totalCost - a.totalCost;
    });

    // 유종 목록
    const FUEL_TYPE_NAMES: { [key: string]: string } = {
        'GASOLINE': '휘발유',
        'DIESEL': '경유',
        'LPG': 'LPG',
        'EV': '전기',
    };

    // 사용된 유종 추출
    const usedFuelTypes = [...new Set(fuelingList.map(item => item.fuelType))];

    // 사용된 부품 목록 추출
    const usedItemNames = [...new Set(
        maintenanceList.map(item => item.itemDescription).filter(Boolean)
    )] as string[];

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
                    const found = MAINTENANCE_ITEMS_DATA.find(m => m.code === value);
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

    // 주유 금액 자동 계산
    const handleFuelPriceChange = (field: 'unitPrice' | 'amount', value: string) => {
        const formattedValue = formatInputWithCommas(value);
        if (field === 'unitPrice') {
            setFormUnitPrice(formattedValue);
            if (formFuelAmount) {
                const total = parseFormattedNumber(formattedValue) * parseFloat(formFuelAmount);
                setFormTotalCost(formatInputWithCommas(Math.round(total).toString()));
            }
        } else {
            setFormFuelAmount(value);
            if (formUnitPrice) {
                const total = parseFormattedNumber(formUnitPrice) * parseFloat(value);
                setFormTotalCost(formatInputWithCommas(Math.round(total).toString()));
            }
        }
    };

    // 저장 핸들러
    const handleSaveManual = async () => {
        if (!selectedVehicle?.vehicleId) return;

        try {
            setLoading(true);
            if (activeTab === 'MAINTENANCE') {
                // 유효한 항목만 필터링
                const validItems = maintenanceItems.filter(item => item.itemCode && item.cost);
                if (validItems.length === 0) {
                    Alert.alert('알림', '정비 항목을 하나 이상 입력해주세요.');
                    setLoading(false);
                    return;
                }

                const payload = validItems.map(item => ({
                    maintenanceDate: formDate,
                    mileageAtMaintenance: parseFormattedNumber(formMileage),
                    shopName: formShopName,
                    cost: parseFormattedNumber(item.cost),
                    consumableItemCode: item.itemCode,
                    itemDescription: item.itemName,
                    memo: formMemo
                }));
                await ocrApi.registerMaintenanceManual(selectedVehicle.vehicleId, payload);
                await loadMaintenanceHistory();
            } else {
                const payload = {
                    fuelingDate: formDate,
                    mileageAtFueling: parseFormattedNumber(formMileage),
                    fuelType: formFuelType,
                    amount: parseFloat(formFuelAmount) || 0,
                    unitPrice: parseFormattedNumber(formUnitPrice),
                    totalCost: parseFormattedNumber(formTotalCost),
                    shopName: formShopName,
                    memo: formMemo,
                    receiptId: null
                };
                await ocrApi.registerFuelingManual(selectedVehicle.vehicleId, payload);
                await loadFuelingHistory();
            }
            setIsManualModalVisible(false);
            resetForm();
        } catch (error) {
            console.error('Failed to save manual record:', error);
            Alert.alert('오류', '기록 저장에 실패했습니다.');
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteHistory = async (group: any) => {
        Alert.alert('삭제 확인', '이 기록을 삭제하시겠습니까?', [
            { text: '취소', style: 'cancel' },
            {
                text: '삭제', style: 'destructive', onPress: async () => {
                    if (!group.items) return;
                    try {
                        setLoading(true);
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
                }
            }
        ]);
    };

    const handleDeleteFueling = async (fuelingId: string) => {
        Alert.alert('삭제 확인', '이 주유 기록을 삭제하시겠습니까?', [
            { text: '취소', style: 'cancel' },
            {
                text: '삭제', style: 'destructive', onPress: async () => {
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
                }
            }
        ]);
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
                    onPress={() => setActiveTab('MAINTENANCE')}
                    className={`flex-1 py-3 rounded-2xl items-center border ${activeTab === 'MAINTENANCE' ? 'bg-primary border-primary' : 'bg-white/5 border-white/10'}`}
                >
                    <Text className={`font-bold ${activeTab === 'MAINTENANCE' ? 'text-white' : 'text-text-dim'}`}>정비 이력</Text>
                </TouchableOpacity>
                <TouchableOpacity
                    onPress={() => setActiveTab('FUELING')}
                    className={`flex-1 py-3 rounded-2xl items-center border ${activeTab === 'FUELING' ? 'bg-orange-500 border-orange-500' : 'bg-white/5 border-white/10'}`}
                >
                    <Text className={`font-bold ${activeTab === 'FUELING' ? 'text-white' : 'text-text-dim'}`}>주유/충전</Text>
                </TouchableOpacity>
            </View>

            {/* Action Buttons */}
            <View className="px-5 pt-4 pb-2 flex-row gap-3">
                <TouchableOpacity
                    className="flex-1 flex-row items-center justify-center gap-2 bg-primary py-4 rounded-2xl active:opacity-80"
                    style={{ minWidth: 0 }}
                    onPress={() => navigation.navigate('ReceiptScan', { vehicleId: selectedVehicle?.vehicleId })}
                >
                    <MaterialIcons name="document-scanner" size={18} color="white" />
                    <Text className="text-white font-bold text-sm">영수증 스캔</Text>
                </TouchableOpacity>
                <TouchableOpacity
                    className="flex-1 flex-row items-center justify-center gap-2 bg-white/10 border border-white/5 py-4 rounded-2xl active:bg-white/20"
                    style={{ minWidth: 0 }}
                    onPress={() => {
                        resetForm();
                        setIsManualModalVisible(true);
                    }}
                >
                    <MaterialIcons name="edit-note" size={18} color="white" />
                    <Text className="text-white font-bold text-sm">직접 입력</Text>
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
                    {activeTab === 'MAINTENANCE' ? '최근 정비 내역' : '최근 주유 내역'}
                </Text>

                {/* 부품 필터 + 정렬 필터 (한 줄) */}
                <View className="flex-row items-center gap-2 mb-3">
                    {/* 부품별 드롭다운 필터 (정비 탭만) */}
                    {activeTab === 'MAINTENANCE' && usedItemNames.length > 0 && (
                        <View className="relative">
                            <TouchableOpacity
                                onPress={() => setIsFilterDropdownOpen(!isFilterDropdownOpen)}
                                className={`flex-row items-center gap-1 px-3 py-2 rounded-lg ${selectedItemFilter ? 'bg-primary' : 'bg-white/10'}`}
                            >
                                <MaterialIcons name="build" size={14} color={selectedItemFilter ? '#fff' : '#64748b'} />
                                <Text className={`text-xs font-bold ${selectedItemFilter ? 'text-white' : 'text-text-dim'}`}>
                                    {selectedItemFilter || '부품'}
                                </Text>
                                <MaterialIcons
                                    name={isFilterDropdownOpen ? 'keyboard-arrow-up' : 'keyboard-arrow-down'}
                                    size={16}
                                    color={selectedItemFilter ? '#fff' : '#64748b'}
                                />
                            </TouchableOpacity>
                        </View>
                    )}

                    {/* 유종별 드롭다운 필터 (주유 탭만) */}
                    {activeTab === 'FUELING' && usedFuelTypes.length > 0 && (
                        <View className="relative">
                            <TouchableOpacity
                                onPress={() => setIsFuelFilterDropdownOpen(!isFuelFilterDropdownOpen)}
                                className={`flex-row items-center gap-1 px-3 py-2 rounded-lg ${selectedFuelTypeFilter ? 'bg-orange-500' : 'bg-white/10'}`}
                            >
                                <MaterialIcons name="local-gas-station" size={14} color={selectedFuelTypeFilter ? '#fff' : '#64748b'} />
                                <Text className={`text-xs font-bold ${selectedFuelTypeFilter ? 'text-white' : 'text-text-dim'}`}>
                                    {selectedFuelTypeFilter ? FUEL_TYPE_NAMES[selectedFuelTypeFilter] : '유종'}
                                </Text>
                                <MaterialIcons
                                    name={isFuelFilterDropdownOpen ? 'keyboard-arrow-up' : 'keyboard-arrow-down'}
                                    size={16}
                                    color={selectedFuelTypeFilter ? '#fff' : '#64748b'}
                                />
                            </TouchableOpacity>
                        </View>
                    )}

                    {/* 정렬 버튼들 */}
                    <TouchableOpacity
                        onPress={() => setSortOrder('date')}
                        className={`flex-row items-center gap-1 px-3 py-2 rounded-lg ${sortOrder === 'date' ? 'bg-white/20' : 'bg-white/5'}`}
                    >
                        <MaterialIcons name="calendar-today" size={14} color={sortOrder === 'date' ? '#fff' : '#64748b'} />
                        <Text className={`text-xs font-bold ${sortOrder === 'date' ? 'text-white' : 'text-text-dim'}`}>날짜순</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        onPress={() => setSortOrder('cost')}
                        className={`flex-row items-center gap-1 px-3 py-2 rounded-lg ${sortOrder === 'cost' ? 'bg-white/20' : 'bg-white/5'}`}
                    >
                        <MaterialIcons name="attach-money" size={14} color={sortOrder === 'cost' ? '#fff' : '#64748b'} />
                        <Text className={`text-xs font-bold ${sortOrder === 'cost' ? 'text-white' : 'text-text-dim'}`}>금액순</Text>
                    </TouchableOpacity>
                </View>

                {/* 부품 드롭다운 펼쳐진 상태 */}
                {activeTab === 'MAINTENANCE' && isFilterDropdownOpen && (
                    <View className="bg-surface-dark border border-white/10 rounded-xl mb-3 overflow-hidden">
                        <TouchableOpacity
                            onPress={() => {
                                setSelectedItemFilter(null);
                                setIsFilterDropdownOpen(false);
                            }}
                            className={`p-3 border-b border-white/5 ${!selectedItemFilter ? 'bg-primary/10' : ''}`}
                        >
                            <Text className={`text-sm ${!selectedItemFilter ? 'text-primary font-bold' : 'text-white'}`}>전체</Text>
                        </TouchableOpacity>
                        {usedItemNames.map((itemName) => (
                            <TouchableOpacity
                                key={itemName}
                                onPress={() => {
                                    setSelectedItemFilter(itemName);
                                    setIsFilterDropdownOpen(false);
                                }}
                                className={`p-3 border-b border-white/5 ${selectedItemFilter === itemName ? 'bg-primary/10' : ''}`}
                            >
                                <Text className={`text-sm ${selectedItemFilter === itemName ? 'text-primary font-bold' : 'text-white'}`}>
                                    {itemName}
                                </Text>
                            </TouchableOpacity>
                        ))}
                    </View>
                )}

                {/* 유종 드롭다운 펼쳐진 상태 */}
                {activeTab === 'FUELING' && isFuelFilterDropdownOpen && (
                    <View className="bg-surface-dark border border-white/10 rounded-xl mb-3 overflow-hidden">
                        <TouchableOpacity
                            onPress={() => {
                                setSelectedFuelTypeFilter(null);
                                setIsFuelFilterDropdownOpen(false);
                            }}
                            className={`p-3 border-b border-white/5 ${!selectedFuelTypeFilter ? 'bg-orange-500/10' : ''}`}
                        >
                            <Text className={`text-sm ${!selectedFuelTypeFilter ? 'text-orange-500 font-bold' : 'text-white'}`}>전체</Text>
                        </TouchableOpacity>
                        {usedFuelTypes.map((fuelType) => (
                            <TouchableOpacity
                                key={fuelType}
                                onPress={() => {
                                    setSelectedFuelTypeFilter(fuelType);
                                    setIsFuelFilterDropdownOpen(false);
                                }}
                                className={`p-3 border-b border-white/5 ${selectedFuelTypeFilter === fuelType ? 'bg-orange-500/10' : ''}`}
                            >
                                <Text className={`text-sm ${selectedFuelTypeFilter === fuelType ? 'text-orange-500 font-bold' : 'text-white'}`}>
                                    {FUEL_TYPE_NAMES[fuelType] || fuelType}
                                </Text>
                            </TouchableOpacity>
                        ))}
                    </View>
                )}

                {loading ? (
                    <View className="py-20 items-center">
                        <ActivityIndicator size="large" color="#0d7ff2" />
                    </View>
                ) : activeTab === 'MAINTENANCE' ? (
                    maintenanceList.length === 0 ? (
                        <View className="items-center justify-center py-20">
                            <MaterialIcons name="build" size={48} color="#334155" />
                            <Text className="text-gray-500 text-sm mt-4">기록된 정비 내역이 없습니다.</Text>
                        </View>
                    ) : (
                        <View className="gap-3">
                            {sortedMaintenance.map((group, index) => (
                                <TouchableOpacity
                                    key={group.receiptId || index}
                                    className="bg-white/5 border border-white/10 rounded-2xl p-4 active:bg-white/10"
                                    onPress={() => handleShowDetail(group)}
                                >
                                    <View className="flex-row justify-between items-start mb-3">
                                        <View className="flex-row items-center gap-3">
                                            <View className="w-10 h-10 rounded-xl bg-primary/20 items-center justify-center">
                                                <MaterialIcons name="build" size={20} color="#0d7ff2" />
                                            </View>
                                            <View>
                                                <Text className="text-white font-bold text-base">
                                                    {group.items.length > 1
                                                        ? `${group.items[0].itemDescription} 외 ${group.items.length - 1}건`
                                                        : group.items[0].itemDescription}
                                                </Text>
                                                <Text className="text-text-dim text-xs">
                                                    {group.shopName || '정비소 미기록'}
                                                </Text>
                                            </View>
                                        </View>
                                        <View className="items-end">
                                            <Text className="text-primary font-bold">
                                                {formatCost(group.totalCost)}
                                            </Text>
                                            <Text className="text-text-dim text-[10px] mt-1">상세보기 &gt;</Text>
                                        </View>
                                    </View>
                                    <View className="flex-row gap-4 mt-2 pt-3 border-t border-white/5">
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-[10px] mb-1">정비일</Text>
                                            <Text className="text-white text-sm">
                                                {formatDate(group.maintenanceDate)}
                                            </Text>
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-[10px] mb-1">주행거리</Text>
                                            <Text className="text-white text-sm">
                                                {group.mileageAtMaintenance ? `${group.mileageAtMaintenance.toLocaleString()} km` : '-'}
                                            </Text>
                                        </View>
                                    </View>
                                </TouchableOpacity>
                            ))}
                        </View>
                    )
                ) : (
                    // Fueling Tab
                    fuelingList.length === 0 ? (
                        <View className="items-center justify-center py-20">
                            <MaterialIcons name="local-gas-station" size={48} color="#334155" />
                            <Text className="text-gray-500 text-sm mt-4">기록된 주유 내역이 없습니다.</Text>
                        </View>
                    ) : (
                        <View className="gap-3">
                            {sortedFueling.map((item, index) => (
                                <TouchableOpacity
                                    key={item.id || index}
                                    className="bg-white/5 border border-white/10 rounded-2xl p-4 active:bg-white/10"
                                    onPress={() => handleShowDetail({ ...item, isFueling: true })}
                                >
                                    <View className="flex-row justify-between items-start mb-3">
                                        <View className="flex-row items-center gap-3">
                                            <View className="w-10 h-10 rounded-xl bg-orange-500/20 items-center justify-center">
                                                <MaterialIcons name="local-gas-station" size={20} color="#f97316" />
                                            </View>
                                            <View>
                                                <Text className="text-white font-bold text-base">
                                                    {item.fuelType === 'EV' ? '전기 충전' : item.fuelType === 'DIESEL' ? '경유' : '휘발유'}
                                                </Text>
                                                <Text className="text-text-dim text-xs">
                                                    {item.shopName || item.stationName || '주유소 미기록'}
                                                </Text>
                                            </View>
                                        </View>
                                        <View className="items-end">
                                            <Text className="text-orange-500 font-bold">
                                                {formatCost(item.totalCost)}
                                            </Text>
                                            <Text className="text-text-dim text-[10px] mt-1">상세보기 &gt;</Text>
                                        </View>
                                    </View>
                                    <View className="flex-row gap-4 mt-2 pt-3 border-t border-white/5">
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-[10px] mb-1">주유일</Text>
                                            <Text className="text-white text-sm">
                                                {formatDate(item.fuelingDate)}
                                            </Text>
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-[10px] mb-1">수량</Text>
                                            <Text className="text-white text-sm">
                                                {item.amount ? `${item.amount} L` : '-'}
                                            </Text>
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-[10px] mb-1">주행거리</Text>
                                            <Text className="text-white text-sm">
                                                {item.mileageAtFueling ? `${item.mileageAtFueling.toLocaleString()} km` : '-'}
                                            </Text>
                                        </View>
                                    </View>
                                </TouchableOpacity>
                            ))}
                        </View>
                    )
                )}
            </ScrollView>

            {/* 상세보기 모달 */}
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
                                                    {selectedGroup.mileageAtMaintenance ? `${selectedGroup.mileageAtMaintenance.toLocaleString()} km` : '-'}
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

            {/* 직접 입력 모달 */}
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
                            {activeTab === 'MAINTENANCE' ? '정비 내역 입력' : '주유 내역 입력'}
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

                            {/* 주행거리 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">현재 주행거리</Text>
                                <View className="flex-row items-center bg-white/5 rounded-2xl border border-white/10">
                                    <TextInput
                                        className="flex-1 text-white p-4"
                                        value={formMileage}
                                        onChangeText={(v) => setFormMileage(formatInputWithCommas(v))}
                                        keyboardType="numeric"
                                        placeholder="0"
                                        placeholderTextColor="#64748b"
                                    />
                                    <Text className="text-text-dim pr-4">km</Text>
                                </View>
                            </View>

                            {activeTab === 'MAINTENANCE' ? (
                                <>
                                    {/* 정비소 */}
                                    <View>
                                        <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">정비소</Text>
                                        <TextInput
                                            className="bg-white/5 text-white p-4 rounded-2xl border border-white/10"
                                            value={formShopName}
                                            onChangeText={setFormShopName}
                                            placeholder="정비소 이름 (선택)"
                                            placeholderTextColor="#64748b"
                                        />
                                    </View>

                                    {/* 정비 항목 목록 */}
                                    <View>
                                        <View className="flex-row justify-between items-center mb-3">
                                            <Text className="text-text-dim text-xs uppercase tracking-wider">정비 항목</Text>
                                            <TouchableOpacity
                                                onPress={addMaintenanceItem}
                                                className="flex-row items-center gap-1 bg-primary/20 px-3 py-1.5 rounded-lg active:bg-primary/30"
                                            >
                                                <MaterialIcons name="add" size={16} color="#0d7ff2" />
                                                <Text className="text-primary text-xs font-bold">항목 추가</Text>
                                            </TouchableOpacity>
                                        </View>

                                        <View className="gap-3">
                                            {maintenanceItems.map((item, index) => (
                                                <View key={item.id} className="bg-white/5 rounded-2xl border border-white/10 overflow-hidden">
                                                    {/* 드롭다운 헤더 */}
                                                    <TouchableOpacity
                                                        onPress={() => setActiveDropdownId(activeDropdownId === item.id ? null : item.id)}
                                                        className="flex-row items-center justify-between p-4"
                                                    >
                                                        <View className="flex-row items-center gap-2 flex-1">
                                                            <MaterialIcons name="build" size={18} color="#64748b" />
                                                            <Text className={`${item.itemName ? 'text-white' : 'text-text-dim'}`}>
                                                                {item.itemName || '정비 항목 선택'}
                                                            </Text>
                                                        </View>
                                                        <View className="flex-row items-center gap-2">
                                                            {maintenanceItems.length > 1 && (
                                                                <TouchableOpacity
                                                                    onPress={() => removeMaintenanceItem(item.id)}
                                                                    className="p-1"
                                                                >
                                                                    <MaterialIcons name="close" size={18} color="#ef4444" />
                                                                </TouchableOpacity>
                                                            )}
                                                            <MaterialIcons
                                                                name={activeDropdownId === item.id ? 'keyboard-arrow-up' : 'keyboard-arrow-down'}
                                                                size={20}
                                                                color="#64748b"
                                                            />
                                                        </View>
                                                    </TouchableOpacity>

                                                    {/* 드롭다운 펼쳐진 상태 */}
                                                    {activeDropdownId === item.id && (
                                                        <View className="border-t border-white/5">
                                                            <ScrollView className="max-h-48" nestedScrollEnabled={true}>
                                                                {MAINTENANCE_ITEMS_DATA.map((mItem) => (
                                                                    <TouchableOpacity
                                                                        key={mItem.code}
                                                                        onPress={() => {
                                                                            updateMaintenanceItem(item.id, 'itemCode', mItem.code);
                                                                            setActiveDropdownId(null);
                                                                        }}
                                                                        className={`p-3 border-b border-white/5 ${item.itemCode === mItem.code ? 'bg-primary/10' : ''}`}
                                                                    >
                                                                        <Text className={`${item.itemCode === mItem.code ? 'text-primary font-bold' : 'text-white'}`}>
                                                                            {mItem.name}
                                                                        </Text>
                                                                    </TouchableOpacity>
                                                                ))}
                                                            </ScrollView>
                                                        </View>
                                                    )}

                                                    {/* 금액 입력 */}
                                                    {item.itemCode && (
                                                        <View className="border-t border-white/5 p-4">
                                                            <View className="flex-row items-center bg-white/5 rounded-xl">
                                                                <TextInput
                                                                    className="flex-1 text-white p-3 text-right"
                                                                    value={item.cost}
                                                                    onChangeText={(v) => updateMaintenanceItem(item.id, 'cost', v)}
                                                                    keyboardType="numeric"
                                                                    placeholder="금액 입력"
                                                                    placeholderTextColor="#64748b"
                                                                />
                                                                <Text className="text-text-dim pr-3">원</Text>
                                                            </View>
                                                        </View>
                                                    )}
                                                </View>
                                            ))}
                                        </View>

                                        {/* 합계 */}
                                        {getTotalMaintenanceCost() > 0 && (
                                            <View className="mt-3 p-4 bg-primary/10 rounded-2xl flex-row justify-between items-center">
                                                <Text className="text-text-dim">합계</Text>
                                                <Text className="text-primary font-bold text-lg">
                                                    {getTotalMaintenanceCost().toLocaleString()}원
                                                </Text>
                                            </View>
                                        )}
                                    </View>
                                </>
                            ) : (
                                <>
                                    {/* 유종 선택 */}
                                    <View>
                                        <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">유종</Text>
                                        <View className="flex-row gap-2">
                                            {[
                                                { code: 'GASOLINE', name: '휘발유' },
                                                { code: 'DIESEL', name: '경유' },
                                                { code: 'EV', name: '전기' }
                                            ].map((type) => (
                                                <TouchableOpacity
                                                    key={type.code}
                                                    onPress={() => setFormFuelType(type.code)}
                                                    className={`flex-1 py-3 rounded-xl border items-center ${formFuelType === type.code ? 'bg-orange-500 border-orange-500' : 'bg-white/5 border-white/10'}`}
                                                >
                                                    <Text className={`font-bold ${formFuelType === type.code ? 'text-white' : 'text-text-dim'}`}>
                                                        {type.name}
                                                    </Text>
                                                </TouchableOpacity>
                                            ))}
                                        </View>
                                    </View>

                                    {/* 주유소 */}
                                    <View>
                                        <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">주유소/충전소</Text>
                                        <TextInput
                                            className="bg-white/5 text-white p-4 rounded-2xl border border-white/10"
                                            value={formShopName}
                                            onChangeText={setFormShopName}
                                            placeholder="주유소 이름 (선택)"
                                            placeholderTextColor="#64748b"
                                        />
                                    </View>

                                    {/* 단가 & 수량 */}
                                    <View className="flex-row gap-3">
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">단가</Text>
                                            <View className="flex-row items-center bg-white/5 rounded-2xl border border-white/10">
                                                <TextInput
                                                    className="flex-1 text-white p-4 text-right"
                                                    value={formUnitPrice}
                                                    onChangeText={(v) => handleFuelPriceChange('unitPrice', v)}
                                                    keyboardType="numeric"
                                                    placeholder="0"
                                                    placeholderTextColor="#64748b"
                                                />
                                                <Text className="text-text-dim pr-4">원</Text>
                                            </View>
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">수량</Text>
                                            <View className="flex-row items-center bg-white/5 rounded-2xl border border-white/10">
                                                <TextInput
                                                    className="flex-1 text-white p-4 text-right"
                                                    value={formFuelAmount}
                                                    onChangeText={(v) => handleFuelPriceChange('amount', v)}
                                                    keyboardType="decimal-pad"
                                                    placeholder="0"
                                                    placeholderTextColor="#64748b"
                                                />
                                                <Text className="text-text-dim pr-4">{formFuelType === 'EV' ? 'kWh' : 'L'}</Text>
                                            </View>
                                        </View>
                                    </View>

                                    {/* 총액 */}
                                    <View>
                                        <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">총 결제 금액</Text>
                                        <View className="flex-row items-center bg-orange-500/10 rounded-2xl border border-orange-500/20">
                                            <TextInput
                                                className="flex-1 text-orange-500 font-bold p-4 text-right text-lg"
                                                value={formTotalCost}
                                                onChangeText={(v) => setFormTotalCost(formatInputWithCommas(v))}
                                                keyboardType="numeric"
                                                placeholder="0"
                                                placeholderTextColor="#64748b"
                                            />
                                            <Text className="text-orange-500 font-bold pr-4">원</Text>
                                        </View>
                                    </View>
                                </>
                            )}

                            {/* 메모 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2 uppercase tracking-wider">메모</Text>
                                <TextInput
                                    className="bg-white/5 text-white p-4 rounded-2xl border border-white/10 min-h-[100px]"
                                    value={formMemo}
                                    onChangeText={setFormMemo}
                                    multiline
                                    textAlignVertical="top"
                                    placeholder="특이사항 (선택)"
                                    placeholderTextColor="#64748b"
                                />
                            </View>
                        </View>
                    </ScrollView>

                    <View className="p-5 bg-surface-dark border-t border-white/5">
                        <TouchableOpacity
                            onPress={handleSaveManual}
                            disabled={loading}
                            className={`py-4 rounded-2xl items-center ${activeTab === 'MAINTENANCE' ? 'bg-primary' : 'bg-orange-500'}`}
                        >
                            {loading ? <ActivityIndicator color="white" /> : (
                                <Text className="text-white font-bold text-lg">저장하기</Text>
                            )}
                        </TouchableOpacity>
                    </View>
                </SafeAreaView>
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
