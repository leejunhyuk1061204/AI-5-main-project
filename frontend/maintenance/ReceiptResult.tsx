import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Image, TextInput, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useAlertStore } from '../store/useAlertStore';
import ocrApi, { OcrAnalysisResponse } from '../api/ocrApi';
import { formatInputWithCommas, parseFormattedNumber } from '../utils/formatNumber';

// 소모품 항목 목록
const CONSUMABLE_ITEMS = [
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
    { code: 'DRIVE_BELT', name: '구동 벨트 (겉벨트)' },
    { code: 'WHEEL_ALIGNMENT', name: '휠 얼라인먼트' },
    { code: 'BATTERY_12V', name: '12V 배터리' },
    { code: 'WIPER', name: '와이퍼' },
    { code: 'AIR_CON_REFRIGERANT', name: '에어컨 가스' },
    { code: 'OTHER', name: '기타 정비' },
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

    // 공통 상태
    const [shopName, setShopName] = useState(result.shopName || '');
    const [date, setDate] = useState(result.maintenanceDate || new Date().toISOString().split('T')[0]);
    const [cost, setCost] = useState(result.cost ? formatInputWithCommas(result.cost.toString()) : '');
    const [mileage, setMileage] = useState(result.mileageAtMaintenance ? formatInputWithCommas(result.mileageAtMaintenance.toString()) : '');
    const [memo, setMemo] = useState('');
    const [isSaving, setIsSaving] = useState(false);

    // 정비 전용 상태
    const [selectedItem, setSelectedItem] = useState(result.consumableItemCode || 'OTHER');
    const [showItemPicker, setShowItemPicker] = useState(false);

    // 주유 전용 상태
    const [fuelType, setFuelType] = useState(result.fuelType || 'GASOLINE');
    const [unitPrice, setUnitPrice] = useState(result.unitPrice ? formatInputWithCommas(result.unitPrice.toString()) : '');
    const [fuelAmount, setFuelAmount] = useState(result.fuelAmount ? result.fuelAmount.toString() : '');

    // 저장 핸들러
    const handleSave = async () => {
        if (!vehicleId) {
            useAlertStore.getState().showAlert('오류', '차량 정보가 없습니다.', 'ERROR');
            return;
        }

        setIsSaving(true);
        try {
            if (isFueling) {
                // 주유 내역 저장 (수동 API 사용)
                // TODO: 이미지 업로드 API가 있다면 추가 구현 필요
                const payload = {
                    fuelingDate: date,
                    mileageAtFueling: parseFormattedNumber(mileage),
                    fuelType,
                    amount: parseFloat(fuelAmount) || 0,
                    unitPrice: parseFormattedNumber(unitPrice),
                    totalCost: parseFormattedNumber(cost),
                    shopName,
                    memo,
                    receiptId: null // 이미지 연동 불가 시 null
                };
                await ocrApi.registerFuelingManual(vehicleId, payload);
            } else {
                // 정비 내역 저장 (OCR 분석 저장 API 사용)
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
