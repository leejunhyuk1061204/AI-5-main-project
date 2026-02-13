import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Image, TextInput, ActivityIndicator, KeyboardAvoidingView, Platform, Modal, Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useAlertStore } from '../store/useAlertStore';
import ocrApi, { OcrAnalysisResponse } from '../api/ocrApi';
import { formatInputWithCommas, parseFormattedNumber } from '../utils/formatNumber';

// 시드와 동일: 대표 소모품 + 위치 선택용 가상 항목
const CONSUMABLE_ITEMS = [
    { code: 'ENGINE_OIL', name: '엔진 오일' },
    { code: 'TIRE_POSITION', name: '타이어 (위치 선택)' },
    { code: 'TIRE_FL', name: '앞왼쪽 타이어' },
    { code: 'TIRE_FR', name: '앞오른쪽 타이어' },
    { code: 'TIRE_RL', name: '뒤왼쪽 타이어' },
    { code: 'TIRE_RR', name: '뒤오른쪽 타이어' },
    { code: 'BRAKE_POSITION', name: '브레이크 패드 (위치 선택)' },
    { code: 'BRAKE_PAD_FRONT', name: '앞 브레이크 패드' },
    { code: 'BRAKE_PAD_REAR', name: '뒤 브레이크 패드' },
    { code: 'BATTERY_12V', name: '12V 배터리' },
    { code: 'COOLANT', name: '냉각수' },
    { code: 'AIR_FILTER', name: '에어클리너' },
    { code: 'BRAKE_FLUID', name: '브레이크 오일' },
    { code: 'SPARK_PLUG', name: '점화 플러그' },
    { code: 'MISSION_OIL', name: '미션 오일' },
    { code: 'FUEL_FILTER', name: '연료 필터' },
    { code: 'OTHER', name: '기타 정비' },
];

const TIRE_POSITION_OPTIONS: { code: string; name: string }[] = [
    { code: 'TIRE_FL', name: '앞왼쪽' },
    { code: 'TIRE_FR', name: '앞오른쪽' },
    { code: 'TIRE_RL', name: '뒤왼쪽' },
    { code: 'TIRE_RR', name: '뒤오른쪽' },
];

const BRAKE_POSITION_OPTIONS: { code: string; name: string }[] = [
    { code: 'BRAKE_PAD_FRONT', name: '앞' },
    { code: 'BRAKE_PAD_REAR', name: '뒤' },
];

const FUEL_TYPE_NAMES: { [key: string]: string } = {
    'GASOLINE': '휘발유',
    'DIESEL': '경유',
    'LPG': 'LPG',
    'EV': '전기',
};

export default function ReceiptResult({ navigation, route }: { navigation?: any; route?: any }) {
    const { vehicleId, imageUri, ocrResult, initialType } = route?.params || {};
    const result: OcrAnalysisResponse = ocrResult || {};

    // 초기 타입 결정 (파라미터 > OCR 결과 > 기본값)
    const isFueling = initialType === 'FUELING' || result.receiptType === 'FUELING';

    // OCR 코드 → 위치 선택 항목 매핑 (영수증에 "타이어"/"브레이크 패드"만 나올 때)
    const initialCode = result.consumableItemCode === 'TIRES' ? 'TIRE_POSITION' : result.consumableItemCode === 'BRAKE_PADS' ? 'BRAKE_POSITION' : result.consumableItemCode || 'OTHER';

    // 공통 상태
    const [shopName, setShopName] = useState(result.shopName || '');
    const [date, setDate] = useState(result.maintenanceDate || new Date().toISOString().split('T')[0]);
    const [cost, setCost] = useState(result.cost ? formatInputWithCommas(result.cost.toString()) : '');
    const [mileage, setMileage] = useState(result.mileageAtMaintenance ? formatInputWithCommas(result.mileageAtMaintenance.toString()) : '');
    const [memo, setMemo] = useState('');
    const [isSaving, setIsSaving] = useState(false);

    // 정비 전용 상태
    const [selectedItem, setSelectedItem] = useState(initialCode);
    const [showItemPicker, setShowItemPicker] = useState(false);
    // 위치 선택 (타이어/브레이크 패드): 저장 시 이 코드들로 각각 이력 생성
    const [selectedPositions, setSelectedPositions] = useState<string[]>([]);
    const [showPositionModal, setShowPositionModal] = useState(false);

    // 주유 전용 상태
    const [fuelType, setFuelType] = useState(result.fuelType || 'GASOLINE');
    const [unitPrice, setUnitPrice] = useState(result.unitPrice ? formatInputWithCommas(result.unitPrice.toString()) : '');
    const [fuelAmount, setFuelAmount] = useState(result.fuelAmount ? result.fuelAmount.toString() : '');

    const isPositionType = selectedItem === 'TIRE_POSITION' || selectedItem === 'BRAKE_POSITION';
    const positionOptions = selectedItem === 'TIRE_POSITION' ? TIRE_POSITION_OPTIONS : BRAKE_POSITION_OPTIONS;

    const togglePosition = (code: string) => {
        setSelectedPositions(prev => prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]);
    };

    const handleSave = async () => {
        if (!vehicleId) {
            useAlertStore.getState().showAlert('오류', '차량 정보가 없습니다.', 'ERROR');
            return;
        }

        if (!isFueling && isPositionType) {
            if (selectedPositions.length === 0) {
                setShowPositionModal(true);
                useAlertStore.getState().showAlert('위치 선택', '교체한 위치를 선택해 주세요.', 'INFO');
                return;
            }
        }

        setIsSaving(true);
        try {
            if (isFueling) {
                const payload = {
                    fuelingDate: date,
                    mileageAtFueling: parseFormattedNumber(mileage),
                    fuelType,
                    amount: parseFloat(fuelAmount) || 0,
                    unitPrice: parseFormattedNumber(unitPrice),
                    totalCost: parseFormattedNumber(cost),
                    shopName,
                    memo,
                    receiptId: null
                };
                await ocrApi.registerFuelingManual(vehicleId, payload);
            } else if (isPositionType && selectedPositions.length > 0) {
                const base = {
                    maintenanceDate: date,
                    mileageAtMaintenance: parseFormattedNumber(mileage) || null,
                    cost: cost != null && cost !== '' ? Math.round(parseFormattedNumber(cost)) : null,
                    shopName: shopName || null,
                    memo: memo || null,
                };
                const requests = selectedPositions.map(consumableItemCode => ({ ...base, consumableItemCode }));
                await ocrApi.registerMaintenanceManual(vehicleId, requests);
            } else {
                const formData = new FormData();
                formData.append('file', {
                    uri: imageUri,
                    type: 'image/jpeg',
                    name: 'receipt.jpg',
                } as any);
                const manualData = {
                    shopName,
                    maintenanceDate: date,
                    cost: parseFormattedNumber(cost),
                    mileageAtMaintenance: parseFormattedNumber(mileage),
                    consumableItemCode: selectedItem,
                    memo
                };
                formData.append('manualData', JSON.stringify(manualData));
                await ocrApi.analyzeAndSaveReceipt(vehicleId, formData);
            }

            useAlertStore.getState().showAlert(
                '저장 완료',
                isFueling ? '주유 기록이 저장되었습니다.' : '정비 이력이 저장되었습니다.',
                'SUCCESS',
                () => {
                    navigation.navigate('MaintenanceBook');
                }
            );
        } catch (error: any) {
            console.error('Save Error:', error);
            useAlertStore.getState().showAlert(
                '저장 실패',
                error.message || '저장 중 오류가 발생했습니다.',
                'ERROR'
            );
        } finally {
            setIsSaving(false);
        }
    };

    const getSelectedItemName = () => {
        const item = CONSUMABLE_ITEMS.find(i => i.code === selectedItem);
        return item?.name || '선택하세요';
    };

    // 주유 금액 자동 계산
    const handleFuelPriceChange = (field: 'unitPrice' | 'amount', value: string) => {
        if (field === 'unitPrice') {
            const formatted = formatInputWithCommas(value);
            setUnitPrice(formatted);
            if (fuelAmount) {
                const total = parseFormattedNumber(formatted) * parseFloat(fuelAmount);
                setCost(formatInputWithCommas(Math.round(total).toString()));
            }
        } else {
            setFuelAmount(value);
            if (unitPrice) {
                const total = parseFormattedNumber(unitPrice) * parseFloat(value);
                setCost(formatInputWithCommas(Math.round(total).toString()));
            }
        }
    };

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">
                    {isFueling ? '주유 분석 결과' : '정비 분석 결과'}
                </Text>
                <View className="w-10" />
            </View>

            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                className="flex-1"
            >
                <ScrollView className="flex-1" contentContainerStyle={{ paddingBottom: 120 }}>
                    {/* 원본 이미지 */}
                    <View className="px-5 pt-4">
                        <Text className="text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3">
                            원본 영수증
                        </Text>
                        <View className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden h-48 items-center justify-center">
                            <Image
                                source={{ uri: imageUri }}
                                className="w-full h-full"
                                resizeMode="contain"
                            />
                        </View>
                    </View>

                    {/* 추출된 정보 */}
                    <View className="px-5 pt-6 gap-4">
                        <Text className="text-[13px] font-semibold text-text-dim uppercase tracking-widest">
                            추출 및 수정
                        </Text>

                        {/* 공통 정보 */}
                        <View className="bg-white/5 border border-white/10 rounded-2xl p-4 gap-4">
                            <View>
                                <Text className="text-text-dim text-xs mb-2">{isFueling ? '주유소' : '정비소'}</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                    value={shopName}
                                    onChangeText={setShopName}
                                    placeholder={isFueling ? "주유소 이름" : "정비소 이름"}
                                    placeholderTextColor="#64748b"
                                />
                            </View>

                            <View>
                                <Text className="text-text-dim text-xs mb-2">{isFueling ? '주유일' : '정비일'}</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                    value={date}
                                    onChangeText={setDate}
                                    placeholder="YYYY-MM-DD"
                                    placeholderTextColor="#64748b"
                                />
                            </View>

                            <View>
                                <Text className="text-text-dim text-xs mb-2">주행거리 (km)</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                    value={mileage}
                                    onChangeText={(v) => setMileage(formatInputWithCommas(v))}
                                    placeholder="0"
                                    placeholderTextColor="#64748b"
                                    keyboardType="numeric"
                                />
                            </View>
                        </View>

                        {/* 타입별 정보 */}
                        <View className="bg-white/5 border border-white/10 rounded-2xl p-4 gap-4">
                            {isFueling ? (
                                // 주유 전용 UI
                                <>
                                    <View>
                                        <Text className="text-text-dim text-xs mb-2">유종</Text>
                                        <View className="flex-row flex-wrap gap-2">
                                            {Object.entries(FUEL_TYPE_NAMES).map(([code, name]) => (
                                                <TouchableOpacity
                                                    key={code}
                                                    onPress={() => setFuelType(code)}
                                                    className={`px-3 py-2 rounded-lg border ${fuelType === code ? 'bg-orange-500 border-orange-500' : 'bg-white/5 border-white/10'}`}
                                                >
                                                    <Text className={fuelType === code ? 'text-white font-bold' : 'text-text-dim'}>
                                                        {name}
                                                    </Text>
                                                </TouchableOpacity>
                                            ))}
                                        </View>
                                    </View>

                                    <View className="flex-row gap-3">
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-xs mb-2">단가 (원)</Text>
                                            <TextInput
                                                className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                                value={unitPrice}
                                                onChangeText={(v) => handleFuelPriceChange('unitPrice', v)}
                                                placeholder="0"
                                                placeholderTextColor="#64748b"
                                                keyboardType="numeric"
                                            />
                                        </View>
                                        <View className="flex-1">
                                            <Text className="text-text-dim text-xs mb-2">주유량 (L)</Text>
                                            <TextInput
                                                className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                                value={fuelAmount}
                                                onChangeText={(v) => handleFuelPriceChange('amount', v)}
                                                placeholder="0"
                                                placeholderTextColor="#64748b"
                                                keyboardType="numeric"
                                            />
                                        </View>
                                    </View>

                                    <View>
                                        <Text className="text-text-dim text-xs mb-2">총 결제금액 (원)</Text>
                                        <TextInput
                                            className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white font-bold text-lg"
                                            value={cost}
                                            onChangeText={(v) => setCost(formatInputWithCommas(v))}
                                            placeholder="0"
                                            placeholderTextColor="#64748b"
                                            keyboardType="numeric"
                                        />
                                    </View>
                                </>
                            ) : (
                                // 정비 전용 UI
                                <>
                                    <View>
                                        <Text className="text-text-dim text-xs mb-2">정비 항목</Text>
                                        <TouchableOpacity
                                            className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 flex-row justify-between items-center"
                                            onPress={() => setShowItemPicker(!showItemPicker)}
                                        >
                                            <Text className="text-white">{getSelectedItemName()}</Text>
                                            <MaterialIcons name="arrow-drop-down" size={24} color="#94a3b8" />
                                        </TouchableOpacity>

                                        {showItemPicker && (
                                            <View className="bg-surface-dark border border-white/10 rounded-xl mt-2 overflow-hidden max-h-48">
                                                <ScrollView nestedScrollEnabled>
                                                    {CONSUMABLE_ITEMS.map((item) => (
                                                        <TouchableOpacity
                                                            key={item.code}
                                                            className={`px-4 py-3 border-b border-white/5 ${selectedItem === item.code ? 'bg-primary/20' : ''}`}
                                                            onPress={() => {
                                                                setSelectedItem(item.code);
                                                                setShowItemPicker(false);
                                                                if (item.code === 'TIRE_POSITION' || item.code === 'BRAKE_POSITION') {
                                                                    setSelectedPositions([]);
                                                                    setShowPositionModal(true);
                                                                }
                                                            }}
                                                        >
                                                            <Text className={`${selectedItem === item.code ? 'text-primary font-bold' : 'text-white'}`}>
                                                                {item.name}
                                                            </Text>
                                                        </TouchableOpacity>
                                                    ))}
                                                </ScrollView>
                                            </View>
                                        )}

                                        {isPositionType && selectedPositions.length > 0 && (
                                            <TouchableOpacity
                                                className="mt-2 bg-white/5 border border-white/10 rounded-xl px-4 py-2 flex-row items-center gap-2"
                                                onPress={() => setShowPositionModal(true)}
                                            >
                                                <MaterialIcons name="edit" size={18} color="#94a3b8" />
                                                <Text className="text-text-dim text-sm">
                                                    선택됨: {selectedPositions.map(c => positionOptions.find(o => o.code === c)?.name).join(', ')}
                                                </Text>
                                            </TouchableOpacity>
                                        )}

                                        <Modal
                                            visible={showPositionModal}
                                            transparent
                                            animationType="fade"
                                            onRequestClose={() => setShowPositionModal(false)}
                                        >
                                            <Pressable className="flex-1 bg-black/60 justify-center px-6" onPress={() => setShowPositionModal(false)}>
                                                <Pressable className="bg-surface-dark border border-white/10 rounded-2xl p-5" onPress={e => e.stopPropagation()}>
                                                    <Text className="text-white font-bold text-lg mb-1">
                                                        {selectedItem === 'TIRE_POSITION' ? '어느 타이어를 교체했나요?' : '어느 브레이크 패드를 교체했나요?'}
                                                    </Text>
                                                    <Text className="text-text-dim text-sm mb-4">
                                                        {result?.quantity != null && result.quantity > 1
                                                            ? `영수증에 수량 ${result.quantity}개로 인식됨. 해당 개수만큼 선택해 주세요.`
                                                            : '복수 선택 가능'}
                                                    </Text>
                                                    <View className="gap-2 mb-5">
                                                        {positionOptions.map((opt) => (
                                                            <TouchableOpacity
                                                                key={opt.code}
                                                                className={`flex-row items-center gap-3 px-4 py-3 rounded-xl border ${selectedPositions.includes(opt.code) ? 'bg-primary/20 border-primary' : 'bg-white/5 border-white/10'}`}
                                                                onPress={() => togglePosition(opt.code)}
                                                            >
                                                                <MaterialIcons
                                                                    name={selectedPositions.includes(opt.code) ? 'check-box' : 'check-box-outline-blank'}
                                                                    size={24}
                                                                    color={selectedPositions.includes(opt.code) ? '#3b82f6' : '#64748b'}
                                                                />
                                                                <Text className={selectedPositions.includes(opt.code) ? 'text-white font-semibold' : 'text-text-dim'}>{opt.name}</Text>
                                                            </TouchableOpacity>
                                                        ))}
                                                    </View>
                                                    <View className="flex-row gap-3">
                                                        <TouchableOpacity
                                                            className="flex-1 py-3 rounded-xl bg-white/10 items-center"
                                                            onPress={() => setShowPositionModal(false)}
                                                        >
                                                            <Text className="text-white">취소</Text>
                                                        </TouchableOpacity>
                                                        <TouchableOpacity
                                                            className="flex-1 py-3 rounded-xl bg-primary items-center"
                                                            onPress={() => {
                                                                if (selectedPositions.length > 0) setShowPositionModal(false);
                                                                else useAlertStore.getState().showAlert('알림', '최소 1개 위치를 선택해 주세요.', 'INFO');
                                                            }}
                                                            disabled={selectedPositions.length === 0}
                                                        >
                                                            <Text className="text-white font-bold">선택 완료</Text>
                                                        </TouchableOpacity>
                                                    </View>
                                                </Pressable>
                                            </Pressable>
                                        </Modal>
                                    </View>

                                    <View>
                                        <Text className="text-text-dim text-xs mb-2">정비 비용 (원)</Text>
                                        <TextInput
                                            className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white font-bold text-lg"
                                            value={cost}
                                            onChangeText={(v) => setCost(formatInputWithCommas(v))}
                                            placeholder="0"
                                            placeholderTextColor="#64748b"
                                            keyboardType="numeric"
                                        />
                                    </View>
                                </>
                            )}

                            {/* 메모 (공통) */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2">메모</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white h-24"
                                    value={memo}
                                    onChangeText={setMemo}
                                    placeholder="메모 입력"
                                    placeholderTextColor="#64748b"
                                    multiline
                                    textAlignVertical="top"
                                />
                            </View>
                        </View>
                    </View>
                </ScrollView>
            </KeyboardAvoidingView>

            {/* 하단 버튼 */}
            <View className="absolute bottom-0 left-0 right-0 bg-background-dark border-t border-white/5 px-5 py-4 pb-8">
                <View className="flex-row gap-3">
                    <TouchableOpacity
                        className="flex-1 bg-[#1e2936] py-4 rounded-xl items-center"
                        onPress={() => navigation.goBack()}
                        disabled={isSaving}
                    >
                        <Text className="text-white font-bold">재촬영</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                        className={`flex-[2] py-4 rounded-xl items-center flex-row justify-center gap-2 ${isFueling ? 'bg-orange-500' : 'bg-primary'}`}
                        onPress={handleSave}
                        disabled={isSaving}
                    >
                        {isSaving ? (
                            <ActivityIndicator color="white" size="small" />
                        ) : (
                            <>
                                <MaterialIcons name="save" size={20} color="white" />
                                <Text className="text-white font-bold text-base">저장</Text>
                            </>
                        )}
                    </TouchableOpacity>
                </View>
            </View>
        </SafeAreaView>
    );
}
